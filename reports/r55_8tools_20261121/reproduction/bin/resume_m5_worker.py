"""Continue an interrupted M5 case using the native memory store and call journal."""

import json
from pathlib import Path
import runpy
import sys
import time

import r55_autodl_memory_recovery_official as recovery
from r55_deepseek_official import valid_response
from r55_memevolve_driver_official import Memory, question


ROOT = Path(__file__).resolve().parents[1]
CONSOLIDATION_INTERVAL = 50
TRANSPORT_ERRORS = {'TimeoutError', 'URLError', 'RemoteDisconnected', 'ConnectionResetError'}
read = recovery.read


def pending_calls(memory):
    ledger = memory / 'model_calls'
    closed = sorted((path.parent for path in ledger.glob('*/*/*/result.json')), key=lambda p: int(p.name))
    started = {path.parent for path in ledger.glob('*/*/*/started.json')}
    if not closed or set(closed) != started or [int(path.name) for path in closed] != list(range(1, len(closed) + 1)):
        raise ValueError('M5 model calls must have contiguous closed receipts')
    tail = closed[-1]
    failure = read(tail / 'result.json')
    if (failure['response_received'] is not False or failure.get('error') not in TRANSPORT_ERRORS
            or (tail / 'response.raw').exists()):
        raise ValueError('M5 must have a transport failure without a saved response')
    request = read(tail / 'request.json')
    if request['model'] != 'deepseek-flash':
        raise ValueError('Unexpected M5 memory writer')
    calls = []
    for path in closed:
        if path.parent != tail.parent or path == tail:
            continue
        prior = read(path / 'request.json')
        result = read(path / 'result.json')
        if result['response_received']:
            raw = read(path / 'response.raw')
            if not valid_response(raw):
                raise ValueError('Archived M5 memory response has the wrong model or reasoning mode')
            choice = raw['choices'][0]
            content = choice['message']['content']
            if choice['finish_reason'] != 'stop' or not isinstance(content, str) or not content.strip():
                raise ValueError('Archived M5 response has no complete text')
            calls.append((prior, content))
        elif prior != request or (path / 'response.raw').exists():
            raise ValueError('Unsuccessful M5 prefix requests do not match the pending call')
    calls.append((request, None))
    return tail, calls


def undo_fallback(graph, query, committed):
    if committed % CONSOLIDATION_INTERVAL == CONSOLIDATION_INTERVAL - 1:
        raise ValueError('The interrupted M5 ingest reached graph consolidation')
    value = read(graph)
    last = value['nodes'][-1]
    if (value['tools'] or last['node_type'] != 'success' or last['metadata']['source_query'] != query
            or last['content'] != 'Execution for: ' + query[:100]
            or any(last['id'] in (edge['source'], edge['target']) for edge in value['edges'])):
        raise ValueError('The interrupted ingest has no isolated fallback node')
    nodes = value['nodes'][:-1]
    return dict(value, nodes=nodes, metadata=dict(value['metadata'], total_nodes=len(nodes)))


def checkpoint(work):
    memory = work / 'external_memory'
    episodes = memory / 'episodes'
    rows = read(work / 'manifest.json')['inputs']
    predictions = {path.stem for path in (work / 'predictions/R55-M5').glob('*.json')}
    ingests = list(episodes.glob('*/ingest.json'))
    ids = [row['question_id'] for row in rows]
    if predictions != set(ids[:len(predictions)]) or {path.parent.name for path in ingests} != set(ids[:len(ingests)]):
        raise ValueError('Committed M5 records must be frozen question prefixes')
    tail, requests = pending_calls(memory)
    phase, qid = tail.parent.name, tail.parent.parent.name
    row = rows[len(ingests)]
    query = question(row)
    if row['question_id'] != qid:
        raise ValueError('The terminal memory failure must belong to the first uncommitted case')
    committed = sum(read(path)['native_description'].startswith('Ingested ') for path in ingests)
    graph = work / 'storage/cerebra_fusion_memory/cf_database.json'
    episode = episodes / qid
    retrieved = episode / 'retrieval.json'
    retrieval = episode / 'retrieval.started.json'
    if read(retrieval)['query'] != query:
        raise ValueError('Saved M5 retrieval does not match the frozen case')
    proof = {'qid': qid, 'phase': phase, 'requests': requests, 'committed': committed,
             'predictions': len(predictions), 'ingests': len(ingests), 'state': None,
             'failure': tail / 'result.json'}
    if phase == 'retrieve':
        if len(predictions) != len(ingests) or retrieved.exists() or graph.stat().st_mtime_ns > retrieval.stat().st_mtime_ns:
            raise ValueError('The interrupted M5 retrieval modified committed state')
        proof['marker'] = retrieval
    elif phase == 'ingest':
        marker = episode / 'ingest.started.json'
        trajectory = read(marker)['trajectory']
        prediction = read(work / 'predictions/R55-M5' / (qid + '.json'))
        feedback = read(work / 'feedback' / (qid + '.json'))
        if (len(predictions) != len(ingests) + 1 or read(retrieved)['provider'] != 'cerebra_fusion_memory'
                or trajectory['query'] != query or trajectory['metadata']['task_id'] != qid
                or feedback['timing'] != 'after_immutable_prediction' or feedback['saved_prediction'] != prediction):
            raise ValueError('The unfinished M5 ingest does not match its immutable prediction and feedback')
        proof.update(marker=marker, state=graph, restored=undo_fallback(graph, query, committed))
    else:
        raise ValueError('Unsupported M5 journal phase')
    return proof


def run(work):
    proof = checkpoint(work)
    qid, phase = proof['qid'], proof['phase']
    archive = work / 'external_memory/recovery' / qid
    archive.mkdir(parents=True, exist_ok=True)

    class ResumedMemory(Memory):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if self.out.parent != work or self.arm != 'M5' or self.provider.consolidation_interval != CONSOLIDATION_INTERVAL:
                raise ValueError('Unexpected native M5 checkpoint binding')
            self.provider.task_counter = proof['committed'] % CONSOLIDATION_INTERVAL

        def replay(self, invoke, *args):
            model = self.model
            original = model.fixture
            expected = iter(proof['requests'])
            remaining = len(proof['requests'])

            def same_request(messages):
                nonlocal remaining
                request, content = next(expected)
                remaining -= 1
                if request['messages'] != messages:
                    model.failure = 'checkpoint_request_changed'
                    raise ValueError('The regenerated M5 request differs from the saved request')
                if content is not None:
                    return content
                model.fixture = original
                return model(messages)

            model.fixture = same_request
            try:
                result = invoke(*args)
                if remaining:
                    raise ValueError('The interrupted memory call was not reached')
                return result
            finally:
                model.fixture = original

        def retrieve(self, row):
            native = super().retrieve
            if phase == 'retrieve' and row['question_id'] == qid:
                return self.replay(native, row)
            return native(row)

        def ingest(self, row, trace, feedback):
            native = super().ingest
            if phase == 'ingest' and row['question_id'] == qid:
                return self.replay(native, row, trace, feedback)
            return native(row, trace, feedback)

    if proof['state'] is not None:
        recovery.restore_checkpoint(work, proof)
    marker = proof['marker']
    marker.replace(archive / f'{marker.stem}.before-{time.time_ns()}.json')
    recovery.RecoveryMemory = ResumedMemory
    runpy.run_path(str(ROOT / 'bin/run_qwen8_memory.py'), run_name='__main__')


if __name__ == '__main__':
    if sys.argv[1] == '--check':
        model, dataset = sys.argv[2:] or ('deepseek', 'slake')
        proof = checkpoint(ROOT / model / 'generation/M5' / dataset)
        print(json.dumps({key: proof[key] for key in ('qid', 'phase', 'predictions', 'ingests', 'committed')}))
    else:
        model_root = Path(sys.argv[2])
        dataset = sys.argv[sys.argv.index('--dataset') + 1]
        run(model_root / 'generation/M5' / dataset)
