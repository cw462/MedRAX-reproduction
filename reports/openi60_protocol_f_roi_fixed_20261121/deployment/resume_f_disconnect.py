"""Resume one closed local connection error without replaying the saved memory prefix."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory

MEMORY_TRANSPORT_ERRORS = {'RemoteDisconnected', 'TimeoutError'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(work, arm, qid, ordinal, pending_memory=False):
    cfg = read(work / 'frozen.json')
    arm_root = work / arm
    ids = cfg['cohort']['selected_ids']
    order = ids.index(qid)
    prefix = set(ids[:order])
    saved = {p.stem for p in (arm_root / 'predictions').glob('*/*.json')}
    require(saved == prefix, 'Locked predictions must equal the prefix before the pending question')
    require({p.stem for p in (arm_root / 'feedback').glob('*.json')} == prefix,
            'Feedback must end with the locked prefix')
    episodes = arm_root / 'external_memory/episodes'
    expected_retrievals = prefix if pending_memory else prefix | {qid}
    require({p.parent.name for p in episodes.glob('*/retrieval.json')} == expected_retrievals,
            'Retrieval membership does not match the requested recovery')
    require({p.parent.name for p in episodes.glob('*/ingest.json')} == prefix,
            'Memory ingest must end with the locked prefix')
    require(not (episodes / qid / 'ingest.started.json').exists(), 'Pending question already began ingest')
    if pending_memory:
        require(not (arm_root / 'services/calls/R49-AGENT' / qid).exists(), 'Solver has already started')
        folders = sorted((arm_root / 'external_memory/model_calls' / qid / 'retrieve').iterdir(),
                         key=lambda path: int(path.name))
        original = folders[-1]
        receipt = read(original / 'result.json')
        require(receipt['response_received'] is False and receipt['error'] in MEMORY_TRANSPORT_ERRORS and
                not (original / 'response.raw').exists() and (original / 'started.json').is_file(),
                'Expected a disconnected memory request with no reply')
        return cfg, original, receipt
    original = arm_root / 'services/calls/R49-AGENT' / qid / str(ordinal)
    receipt = read(original / 'result.json')
    require(receipt['response_received'] is False and receipt['error'] == 'Connection error.' and
            not (original / 'response.json').exists() and (original / 'started.json').is_file(),
            'Request must be a saved connection error without a usable response')
    require(read(original / 'started.json')['request_id'] == receipt['request_id'], 'Request identity mismatch')
    require(not (arm_root / 'services/protocol_events' / qid / f'{ordinal}.json').exists(),
            'Cannot repeat a decision with a saved response')
    return cfg, original, receipt


def memory_recovery(runner, qid, pending_memory=False, graph_checkpoint=None):
    from r55_memory_token_plan import enabled
    original = runner.CheckpointMemory

    class PendingRetrievalMemory(original):
        def __init__(self, runtime, out, key, inputs, fixture=None):
            ids = [row['question_id'] for row in inputs]
            self.prefix = set(ids[:ids.index(qid)])
            self.retry_question = None
            pending_ingest = graph_checkpoint is not None
            ledger = out / 'model_calls'
            receipts = {p.parent for p in ledger.glob('*/*/*/result.json')}
            require(receipts == {p.parent for p in ledger.glob('*/*/*/started.json')} and
                    sorted(int(p.name) for p in receipts) == list(range(1, len(receipts) + 1)),
                    'Memory call ledger must be closed and contiguous')
            pending = out / 'episodes' / qid
            row = inputs[len(self.prefix)]
            require(read(pending / 'retrieval.started.json')['query'] == runner.bridge.question(row),
                    'Saved retrieval query differs from the pending question')
            live_graph = out.parent / 'storage/cerebra_fusion_memory/cf_database.json'
            graph = read(graph_checkpoint if pending_ingest else live_graph)
            ingests = [read(out / 'episodes' / q / 'ingest.json') for q in ids[:len(self.prefix)]]
            if pending_ingest:
                with TemporaryDirectory() as tmp:
                    sandbox = Path(tmp)
                    local_graph = sandbox / 'storage/cerebra_fusion_memory/cf_database.json'
                    local_graph.parent.mkdir(parents=True)
                    shutil.copy2(graph_checkpoint, local_graph)
                    (sandbox / 'storage/models').symlink_to(runtime / 'models', target_is_directory=True)
                    cwd = Path.cwd()
                    try:
                        os.chdir(sandbox)
                        runner.bridge.Memory.__init__(self, 'M5', runtime, out, key, fixture)
                    finally:
                        os.chdir(cwd)
                self.provider.db_path = str(live_graph)
            else:
                require(bool(ingests) and ingests[-1]['native_description'].startswith('Ingested '),
                        'Graph must cover the completed prefix')
                runner.bridge.Memory.__init__(self, 'M5', runtime, out, key, fixture)
            provider = self.provider
            require(not provider.enable_tool_memory and not provider.active_usage_tracking and
                    [vars(node) for node in provider.nodes.values()] == graph['nodes'] and
                    [edge.to_dict() for edge in provider.edges] == graph['edges'],
                    'Native M5 graph and provider settings must restore exactly')
            ingested = sum(item['native_description'].startswith('Ingested ') for item in ingests)
            provider.task_counter = ingested % provider.consolidation_interval
            self.model.calls = len(receipts)
            self.model.use_token_plan = enabled(Path(runner.__file__).resolve().parent)
            self.pending_ledger = ledger / qid / 'retrieve'
            if pending_ingest:
                last_persisted = max(i for i, x in enumerate(ingests) if x['native_description'].startswith('Ingested '))
                for previous_row in inputs[last_persisted+1:len(self.prefix)]:
                    case = previous_row['question_id']
                    require(read(out / 'episodes' / case / 'ingest.json')['native_description'] ==
                            'Skipped: only successful tasks are ingested', 'Unexpected non-persisted prefix write')
                    self.restore_retrieval(previous_row, read(out / 'episodes' / case / 'retrieval.json'),
                                           ledger / case / 'retrieve')
                    provider._update_memory_success_counts(runner.bridge.question(previous_row), False)
                    require(not provider.active_usage_tracking, 'Archived skipped write did not close usage tracking')
            if not pending_memory:
                archived_retrieval = read(pending / 'retrieval.json')
                self.pending_context = archived_retrieval['injected']
                require(isinstance(self.pending_context, str), 'Pending retrieval must have saved injected text')
                self.restore_retrieval(row, archived_retrieval, self.pending_ledger)

        def restore_retrieval(self, row, saved, ledger):
            from dataclasses import asdict
            from EvolveLab.memory_types import MemoryRequest, MemoryStatus
            calls = sorted((p for p in ledger.iterdir() if p.is_dir()), key=lambda p: int(p.name))
            archived = iter(calls)
            errors = []
            replayed = []

            def fixture(messages):
                try:
                    path = next(archived)
                    require(read(path / 'request.json')['messages'] == messages, 'Retrieval request differs from archive')
                    receipt = read(path / 'result.json')
                    response = read(path / 'response.raw')['choices'][0]
                    require(receipt['response_received'] is True and not receipt.get('error') and
                            response['finish_reason'] == 'stop', 'Retrieval archive has no usable response')
                    replayed.append(int(path.name))
                    return response['message']['content']
                except Exception as error:
                    errors.append(str(error) or type(error).__name__)
                    raise

            previous = self.model.fixture
            self.model.fixture = fixture
            try:
                replay = self.provider.provide_memory(MemoryRequest(query=runner.bridge.question(row),
                                                                    context='', status=MemoryStatus.BEGIN))
            finally:
                self.model.fixture = previous
            require(not errors and len(replayed) == len(calls), 'Retrieval API replay mismatch: ' + ', '.join(errors))

            def comparable(native):
                payload = json.loads(json.dumps(native, default=runner.bridge.plain))
                payload.pop('request_id', None)
                for item in payload['memories']:
                    item.pop('id', None)
                return payload

            require(comparable(asdict(replay)) == comparable(saved['native']) and
                    len(self.provider.active_usage_tracking) == 1,
                    'Saved memory response or usage tracking did not restore exactly')

        def retry_memory_request(self, row, dry=False):
            from EvolveLab.memory_types import MemoryRequest, MemoryStatus
            import time

            calls = sorted(self.pending_ledger.iterdir(), key=lambda path: int(path.name))
            previous = self.model.fixture
            visited, errors = [], []

            def fixture(messages):
                if len(visited) == len(calls):
                    if dry:
                        raise RuntimeError('Offline checkpoint verified')
                    self.model.fixture = previous
                    return self.model(messages)
                path = calls[len(visited)]
                if read(path / 'request.json')['messages'] != messages:
                    errors.append(str(path))
                    raise ValueError('Pending retrieval request differs from archive')
                receipt = read(path / 'result.json')
                visited.append(path.name)
                if receipt['response_received']:
                    return read(path / 'response.raw')['choices'][0]['message']['content']
                if dry:
                    raise RuntimeError('Offline checkpoint verified')
                require(path == calls[-1] and receipt['error'] in MEMORY_TRANSPORT_ERRORS,
                        'Only the last disconnected request can be retried')
                self.model.fixture = previous
                return self.model(messages)

            self.model.fixture = fixture
            try:
                if dry:
                    result = self.provider.provide_memory(MemoryRequest(query=runner.bridge.question(row),
                                                                         context='', status=MemoryStatus.BEGIN))
                else:
                    marker = self.out / 'episodes' / qid / 'retrieval.started.json'
                    marker.rename(marker.with_name(f'retrieval.started.before-{time.time_ns()}.json'))
                    result = super().retrieve(row)
            finally:
                self.model.fixture = previous
            require(not errors and len(visited) == len(calls), 'Archived memory request sequence did not restore')
            return result

        def retrieve(self, row):
            if row['question_id'] == qid:
                if pending_memory:
                    return self.retry_memory_request(row)
                return self.pending_context
            return super().retrieve(row)

        def retry_ingest(self, row, trace=None, feedback=None, dry=False):
            from EvolveLab.memory_types import TrajectoryData
            import time

            marker = self.out / 'episodes' / qid / 'ingest.started.json'
            trajectory = read(marker)['trajectory']
            folders = sorted((self.out / 'model_calls' / qid / 'ingest').iterdir(), key=lambda path: int(path.name))
            require(len(folders) == 1, 'Expected one unresponded summary request')
            failed = folders[0]
            require(read(failed / 'result.json')['error'] in MEMORY_TRANSPORT_ERRORS and
                    not (failed / 'response.raw').exists(), 'Unexpected pending memory write response')
            expected = read(failed / 'request.json')['messages']
            prior = self.model.fixture
            matched = False
            dry_graph = None

            def fixture(messages):
                nonlocal matched
                require(not matched and messages == expected, 'Pending write request differs from archive')
                matched = True
                if dry:
                    raise RuntimeError('Offline checkpoint verified')
                self.model.fixture = prior
                return self.model(messages)

            self.model.fixture = fixture
            try:
                if dry:
                    with TemporaryDirectory() as tmp:
                        self.provider.db_path = str(Path(tmp) / 'check.json')
                        self.provider.take_in_memory(TrajectoryData(**trajectory))
                        dry_graph = read(Path(self.provider.db_path))
                else:
                    marker.rename(marker.with_name(f'ingest.started.before-{time.time_ns()}.json'))
                    super().ingest(row, trace, feedback)
            finally:
                self.model.fixture = prior
            require(matched, 'The originally disconnected memory write was not reached')
            return dry_graph

        def ingest(self, row, trace, feedback):
            if graph_checkpoint is not None and row['question_id'] == qid:
                return self.retry_ingest(row, trace, feedback)
            return super().ingest(row, trace, feedback)

    return PendingRetrievalMemory


def generate(work, arm, qid, pending_memory=False, graph_checkpoint=None):
    config = read(work / 'frozen.json')['config']
    sys.path.insert(0, str(Path(config['native_root']).parent))
    import native_worker
    original = native_worker.install_memory_audit

    def install(runner, root, name):
        runner.CheckpointMemory = memory_recovery(runner, qid, pending_memory, graph_checkpoint)
        original(runner, root, name)

    native_worker.install_memory_audit = install
    sys.argv = [str(Path(config['native_root']).parent / 'native_worker.py'), 'generate',
                '--work', str(work), '--arm', arm]
    native_worker.main()


def validate_write(work, arm, qid, graph_checkpoint):
    frozen = read(work / 'frozen.json')
    ids = frozen['cohort']['selected_ids']
    name = ids.index(qid)
    prefix, locked = set(ids[:name]), set(ids[:name+1])
    out = work / arm
    require({p.stem for p in (out/'predictions').glob('*/*.json')} == locked and
            {p.stem for p in (out/'feedback').glob('*.json')} == locked, 'Prediction and feedback prefix must already be locked')
    episodes = out / 'external_memory/episodes'
    require({p.parent.name for p in episodes.glob('*/ingest.json')} == prefix and
            {p.parent.name for p in episodes.glob('*/retrieval.json')} == locked, 'Unexpected completed memory prefix')
    original = read(graph_checkpoint)
    live = read(out / 'storage/cerebra_fusion_memory/cf_database.json')
    require(len(live['nodes']) == len(original['nodes']) + 1 and len(live['edges']) == len(original['edges']),
            'Unexpected graph writes after the independently saved checkpoint')
    require(all(a == b for a,b in zip(original['nodes'],live['nodes'])), 'Backup nodes do not match the persisted prefix')
    for before,after in zip(original['edges'],live['edges']):
        fields = {'usage_count','success_count'}
        require({k:v for k,v in before.items() if k not in fields} ==
                {k:v for k,v in after.items() if k not in fields}, 'Backup topology differs from live graph')
    folder = sorted((out/'external_memory/model_calls'/qid/'ingest').iterdir(), key=lambda path:int(path.name))[-1]
    receipt = read(folder/'result.json')
    require(receipt['response_received'] is False and receipt['error'] in MEMORY_TRANSPORT_ERRORS and
            not (folder/'response.raw').exists(), 'Expected an unanswered failed memory write')
    return frozen, folder, receipt


def check_restore(work, arm, qid, ordinal, pending_memory=False, graph_checkpoint=None):
    cfg, _, _ = (validate_write(work, arm, qid, graph_checkpoint) if graph_checkpoint else
                 validate(work, arm, qid, ordinal, pending_memory))
    cfg = cfg['config']
    os.environ.update(CUDA_VISIBLE_DEVICES=cfg['gpu'], R55_MEMEVOLVE_GPU=cfg['gpu'])
    sys.path.insert(0, str(Path(cfg['native_root']).parent))
    import native_worker
    native_worker.verify_frozen(work)
    runner, _, _ = native_worker.load_native(cfg)
    out = work / arm
    runtime = Path(cfg['memory_runtime'])
    runner.bridge.load_runtime(runtime, out)
    def no_external(_):
        raise RuntimeError('Unexpected memory model request during offline restore')
    inputs = read(out / 'manifest.json')['inputs']
    memory = memory_recovery(runner, qid, pending_memory, graph_checkpoint)(runtime, out / 'external_memory', '', inputs, no_external)
    if pending_memory:
        memory.retry_memory_request(next(row for row in inputs if row['question_id'] == qid), dry=True)
    if graph_checkpoint:
        memory.retry_ingest(next(row for row in inputs if row['question_id'] == qid), dry=True)
    print(json.dumps({'arm': arm, 'pending_question': qid, 'archived_memory_response_matches': True,
                      'pending_graph_usage_restored': not pending_memory, 'provider_calls': 0}))


def derive_checkpoint(work, arm, qid, output):
    """Reverse a proved single-node fallback and verify by replaying it offline."""
    from copy import deepcopy
    config = read(work / 'frozen.json')['config']
    os.environ.update(CUDA_VISIBLE_DEVICES=config['gpu'], R55_MEMEVOLVE_GPU=config['gpu'])
    sys.path.insert(0, str(Path(config['native_root']).parent))
    import native_worker
    native_worker.verify_frozen(work)
    runner, _, _ = native_worker.load_native(config)
    out = work / arm
    runtime = Path(config['memory_runtime'])
    runner.bridge.load_runtime(runtime, out)
    rows = read(out / 'manifest.json')['inputs']
    ids = [row['question_id'] for row in rows]
    position = ids.index(qid)
    records = [read(out/'external_memory/episodes'/name/'ingest.json') for name in ids[:position]]
    require(records[-1]['native_description'].startswith('Ingested ') and
            sum(r['native_description'].startswith('Ingested ') for r in records) < 49,
            'The last prefix must have persisted and the pending write must not consolidate')
    row = rows[position]
    live = read(out / 'storage/cerebra_fusion_memory/cf_database.json')
    provisional = deepcopy(live)
    fallback = provisional['nodes'].pop()
    require(fallback['content'] == 'Execution for: '+runner.bridge.question(row)[:100]
            and all(fallback['id'] not in (edge['source'],edge['target']) for edge in live['edges']),
            'Expected one isolated fallback node for the pending write')

    def no_external(_):
        raise RuntimeError('External calls are disabled in checkpoint reconstruction')

    with TemporaryDirectory() as folder:
        candidate = Path(folder) / 'provisional.json'
        candidate.write_text(json.dumps(provisional, ensure_ascii=False), encoding='utf-8')
        memory = memory_recovery(runner, qid, graph_checkpoint=candidate)(runtime, out/'external_memory', '', rows, no_external)
        memory.provider._update_memory_success_counts(runner.bridge.question(row), True)
        fields = ('usage_count', 'success_count')
        for before, advanced in zip(provisional['edges'], memory.provider.edges, strict=True):
            value = advanced.to_dict()
            require((before['source'], before['target']) == (value['source'], value['target']), 'Edge order differs')
            for field in fields:
                delta = value[field] - before[field]
                require(0 <= delta <= before[field], 'Cannot reverse the pending edge counters')
                before[field] -= delta
        candidate.write_text(json.dumps(provisional, ensure_ascii=False), encoding='utf-8')
        validate_write(work, arm, qid, candidate)
        memory = memory_recovery(runner, qid, graph_checkpoint=candidate)(runtime, out/'external_memory', '', rows, no_external)
        replay = memory.retry_ingest(row, dry=True)
        def comparable_nodes(graph):
            fields = {'id','created_at'}
            return graph['nodes'][:-1]+[{k:v for k,v in graph['nodes'][-1].items() if k not in fields}]
        require(replay['edges'] == live['edges'] and comparable_nodes(replay) == comparable_nodes(live),
                'Forward replay failed to reproduce the persisted fallback graph')
    with output.open('x', encoding='utf-8') as stream:
        json.dump(provisional, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'checkpoint':str(output),'forward_replay_matches':True,
                      'provider_calls':0,'pending_question':qid}))


def resume(work, arm, qid, ordinal, pending_memory=False, graph_checkpoint=None):
    from datetime import datetime, timezone
    cfg, source, receipt = (validate_write(work, arm, qid, graph_checkpoint) if graph_checkpoint else
                            validate(work, arm, qid, ordinal, pending_memory))
    cfg = cfg['config']
    profile = Path('/root/.config/medrax-autodl-r55/memory_resume.keys')
    key = next(line.strip() for line in profile.read_text().splitlines() if line.strip().startswith('sk-sp-'))
    jobs = work / 'jobs' / arm
    attempt = jobs / f'attempt-{len(list(jobs.glob("attempt-*"))) + 1:03d}'
    attempt.mkdir()
    if graph_checkpoint:
        shutil.copy2(work / arm / 'storage/cerebra_fusion_memory/cf_database.json', attempt / 'graph_after_unanswered_write.json')
    elif not pending_memory:
        old = attempt / 'unknown_provider_outcome' / qid / str(ordinal)
        old.parent.mkdir(parents=True)
        source.rename(old)
        source.mkdir()
        # The native sender compares the exact archived payload, including image assets.
        shutil.copy2(old / 'request.json', source / 'request.json')
    identity = {'utc': datetime.now(timezone.utc).isoformat(), 'arm': arm, 'question_id': qid,
                'ordinal': int(source.name), 'previous_request_id': receipt.get('request_id'),
                'original_request': str(source.relative_to(work)), 'role': 'memory' if pending_memory or graph_checkpoint else 'solver',
                'previous_response_received': False, 'prior_provider_billing': 'unknown',
                'retry_uses_identical_archived_request': True, 'pending_retrieval_reused': True}
    (attempt / 'resume.json').write_text(json.dumps(identity, indent=2)+'\n', encoding='utf-8')
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=cfg['gpu'], R55_MEMEVOLVE_GPU=cfg['gpu'],
               LANGCHAIN_TRACING_V2='false', LANGSMITH_TRACING='false', PYTHONDONTWRITEBYTECODE='1')
    command = [sys.executable, '-B', '-u', __file__, '--child', '--work', str(work), '--arm', arm, '--qid', qid]
    if pending_memory:
        command.append('--pending-memory')
    if graph_checkpoint:
        command.extend(['--graph-checkpoint',str(graph_checkpoint)])
    (attempt / 'generate.started.json').write_text(json.dumps({**identity, 'command': command}, indent=2)+'\n')
    print(json.dumps({'resuming': arm, 'question_id': qid, 'attempt': str(attempt)}), flush=True)
    with (attempt / 'generate.stdout.log').open('xb') as out, (attempt / 'generate.stderr.log').open('xb') as err:
        result = subprocess.run(command, cwd=cfg['native_root'], env=env,
                                input=(key+'\n'+key+'\n').encode(), stdout=out, stderr=err)
    (attempt / 'generate.exit.json').write_text(json.dumps({'utc': datetime.now(timezone.utc).isoformat(),
                                                           'returncode': result.returncode})+'\n')
    (work / arm / 'generation.exitcode').write_text(str(result.returncode)+'\n')
    return result.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--arm', choices=('B0','L1'), required=True)
    parser.add_argument('--qid', required=True)
    parser.add_argument('--ordinal', type=int, default=1)
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--pending-memory', action='store_true')
    parser.add_argument('--graph-checkpoint', type=Path)
    parser.add_argument('--derive-checkpoint', type=Path)
    args = parser.parse_args()
    if args.derive_checkpoint:
        derive_checkpoint(args.work, args.arm, args.qid, args.derive_checkpoint)
    elif args.child:
        generate(args.work, args.arm, args.qid, args.pending_memory, args.graph_checkpoint)
    elif args.check:
        check_restore(args.work, args.arm, args.qid, args.ordinal, args.pending_memory, args.graph_checkpoint)
    else:
        sys.exit(resume(args.work, args.arm, args.qid, args.ordinal, args.pending_memory, args.graph_checkpoint))
