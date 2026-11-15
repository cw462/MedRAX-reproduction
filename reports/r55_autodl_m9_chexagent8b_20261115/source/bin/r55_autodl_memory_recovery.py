"""Resume the unfinished AutoDL feedback ingests after the DeepSeek outage."""

import json
import os
import time
import uuid

import r55_memevolve_driver003 as bridge


def read(path):
    return json.loads(path.read_bytes())


def replace_json(path, value):
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def native_restore(arm, work, trajectory, failure, saved=None):
    """Return the native path and its state before the rejected ingest."""
    task = trajectory['metadata']['task_id']
    query = trajectory['query']
    correct = trajectory['metadata']['is_correct']
    if arm == 'M7':
        files = (work/'storage/mobilee').rglob('*.json')
        if any(path.stat().st_mtime_ns > failure.stat().st_mtime_ns for path in files):
            raise ValueError('MobileE store changed during the rejected ingest')
        return None, None
    if arm == 'M3' and not correct:
        path = work/'storage/memp/procedural_records.json'
        if path.stat().st_mtime_ns > failure.stat().st_mtime_ns:
            raise ValueError('MemP adjustment changed storage during the rejected ingest')
        return None, None
    if arm == 'M2':
        path = work/'storage/expel/success_trajectories.json'
        value = read(saved if saved is not None and saved.is_file() else path)
        candidate = value[-1]
        if (not correct or candidate['metadata'] != trajectory['metadata']
                or candidate['metadata']['task_id'] != task or candidate['query'] != query
                or candidate['result'] != trajectory['result'] or candidate['trajectory_text']):
            raise ValueError('ExpeL final trajectory is not the rejected partial write')
        return path, value[:-1]

    provider, name = {
        'M3': ('memp','procedural_records.json'),
        'M9': ('generative','generative_memory.json'),
    }[arm]
    path = work/'storage'/provider/name
    value = read(saved if saved is not None and saved.is_file() else path)
    rows, embeddings = value['memories'], value['embeddings']
    if not rows or len(rows) != len(embeddings):
        raise ValueError('Memory record and embedding counts differ')
    candidate = rows[-1]
    if arm == 'M3':
        if (candidate['meta'] != trajectory['metadata'] or candidate['question'] != query
                or not candidate['procedural_script'].startswith('(LLM call error: HTTP Error')):
            raise ValueError('MemP final sample is not from the rejected ingest')
    else:
        messages = trajectory['trajectory']
        summary = ['Task: '+query, '']
        summary.extend(f"Step {i} ({step.get('type', 'step')}): {step.get('content', '')}"
                       for i,step in enumerate(messages,1))
        if trajectory['result']:
            summary.extend(('', 'Final Result: '+trajectory['result']))
        if (candidate['task_name'] != query or candidate['metadata']['original_query'] != query
                or candidate['metadata']['task_description'] != '\n'.join(summary)):
            raise ValueError('Generative final sample does not match the saved fallback')
    restored = dict(value, memories=rows[:-1], embeddings=embeddings[:-1])
    return path, restored


def checkpoint(work, arm, inputs):
    out = work/'external_memory'
    episodes = out/'episodes'
    pending = [path for path in episodes.glob('*/ingest.started*.json')
               if not path.with_name('ingest.json').exists()]
    if not pending:
        return None
    if len({path.parent for path in pending}) != 1:
        raise ValueError('Expected one unfinished memory ingest')
    marker = next((path for path in pending if path.name == 'ingest.started.json'), pending[0])
    qid = marker.parent.name
    ids = [row['question_id'] for row in inputs]
    saved = {path.stem for path in (work/'predictions'/('R55-'+arm)).glob('*.json')}
    completed = {path.parent.name for path in episodes.glob('*/ingest.json')}
    if (not saved or saved != set(ids[:len(saved)])
            or qid != ids[len(saved)-1] or completed != saved-{qid}):
        raise ValueError('Unfinished memory ingest does not match the saved prediction prefix')
    pred = read(work/'predictions'/('R55-'+arm)/(qid+'.json'))
    feedback = read(work/'feedback'/(qid+'.json'))
    trajectory = read(marker)['trajectory']
    if any(read(path)['trajectory'] != trajectory for path in pending):
        raise ValueError('The saved ingest changed between attempts')
    retrieval = read(marker.with_name('retrieval.json'))
    query = bridge.question(inputs[len(saved)-1])
    if (feedback['saved_prediction'] != pred or feedback['timing'] != 'after_immutable_prediction'
            or trajectory['metadata']['task_id'] != qid or trajectory['query'] != query
            or retrieval['provider'] != bridge.PROVIDERS[arm]):
        raise ValueError('Saved prediction, feedback and memory episode do not agree')
    calls = out/'model_calls'
    prior = set(calls.glob('*/*/*/result.json'))
    started = {path.with_name('result.json') for path in calls.glob('*/*/*/started.json')}
    if started != prior:
        raise ValueError('The saved memory ledger has an unresolved send')
    phase = sorted((calls/qid/'ingest').glob('*/result.json'), key=lambda path: int(path.parent.name))
    if (not phase or phase[-1] != max(prior, key=lambda path: int(path.parent.name), default=None)
            or any(path.with_name('response.raw').is_file() for path in phase)):
        raise ValueError('Unsupported memory ingest retry sequence')
    failure = phase[-1]
    request = read(phase[0].with_name('request.json'))
    for path in phase:
        result = read(path)
        if (result['response_received'] is not False or result['error'] != 'HTTPError'
                or read(path.with_name('request.json')) != request):
            raise ValueError('The memory ingest lacks a consistent rejected request')
    retrieval_start = read(marker.with_name('retrieval.started.json'))
    if request['model'] != 'deepseek-flash' or retrieval_start['query'] != query:
        raise ValueError('Recovery would change the original request or retrieval')
    folder = out/'recovery'/qid
    saved = folder/'native_before_recovery.json'
    state, restored = native_restore(arm, work, trajectory, phase[0], saved)
    if state is not None and saved.is_file():
        current = read(state)
        if current not in (restored,read(saved)):
            _, current_prior = native_restore(arm, work, trajectory, failure)
            if current_prior != restored:
                raise ValueError('The native store changed after preparing the retry')
    return {'marker':marker,'qid':qid,'retrieval':retrieval,'trajectory':trajectory,
            'failure':failure,'state':state,'restored':restored,'request':request}


def restore_checkpoint(work, proof):
    folder = work/'external_memory'/'recovery'/proof['qid']
    folder.mkdir(parents=True, exist_ok=True)
    state = proof['state']
    original = folder/'native_before_recovery.json'
    if state is not None:
        if not original.exists():
            replace_json(original,read(state))
        current = read(state)
        if current != proof['restored']:
            retry_copy = folder/f"native_before_retry_{proof['failure'].parent.name}.json"
            if current != read(original) and not retry_copy.exists():
                replace_json(retry_copy,current)
            replace_json(state,proof['restored'])
    receipt = folder/'prepared.json'
    if not receipt.exists():
        bridge.record(receipt, {'question_id':proof['qid'],'attempt':int(proof['failure'].parent.name),
            'excluded_partial_native_write':state is not None,
            'native_state':str(state.relative_to(work)) if state else None,
            'original_prediction_reused':True, 'utc':bridge.utc()})


class RecoveryMemory(bridge.Memory):
    def __init__(self, arm, runtime, out, key, fixture=None, *, use_token_plan=False):
        work = out.parent
        self.pending = None
        if not fixture:
            self.pending = checkpoint(work,arm,read(work/'manifest.json')['inputs'])
            if self.pending is not None:
                restore_checkpoint(work,self.pending)
        super().__init__(arm, runtime, out, key, fixture, use_token_plan=use_token_plan)

    def ingest(self, row, trace, feedback):
        pending = self.pending
        if pending is None or row['question_id'] != pending['qid']:
            return super().ingest(row,trace,feedback)
        self.restore_retrieval(pending['trajectory']['query'],pending['retrieval'])
        marker = pending['marker']
        if marker.name == 'ingest.started.json':
            archive = marker.with_name(f'ingest.started.before-{time.time_ns()}.json')
            marker.rename(archive)
        real_model = self.model
        original_fixture = real_model.fixture
        first_request = True

        def retry_model(messages):
            nonlocal first_request
            if first_request:
                if messages != pending['request']['messages']:
                    real_model.failure = 'checkpoint_request_changed'
                    raise ValueError('Recovery changed the original memory request')
                first_request = False
            real_model.fixture = original_fixture
            try:
                return real_model(messages)
            finally:
                real_model.fixture = retry_model

        real_model.fixture = retry_model
        try:
            super().ingest(row,trace,feedback)
        finally:
            real_model.fixture = original_fixture
        self.pending = None
