"""Resume the unfinished AutoDL feedback ingests after the DeepSeek outage."""

import json
import os
import time
import uuid

import r55_memevolve_driver_official as bridge


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



def archived_content(response_path):
    raw = read(response_path)
    choice = raw['choices'][0]
    content = choice['message']['content']
    if raw['model'] != 'DeepSeek-V4.1-Flash' or choice['finish_reason'] != 'stop' or not content:
        raise ValueError('Invalid archived Tongji response')
    return content


def extracted_tips(response_path):
    lines = (line.strip() for line in archived_content(response_path).strip().split('\n'))
    return [tip for line in lines if line and not line.startswith('#') and len(line)>10
            if (tip:=line.lstrip('•-*123456789. '))][:5]


def native_restore(arm, work, trajectory, failure, saved=None):
    query = trajectory['query']
    qid = trajectory['metadata']['task_id']
    storage = work/'storage'
    ledger = work/'external_memory/model_calls'
    episodes = work/'external_memory/episodes'

    if arm == 'M3':
        path = storage/'memp/procedural_records.json'
        value = read(saved) if saved and saved.is_file() else read(path)
        rows, embeddings = value['memories'], value['embeddings']
        if (read(failure).get('error')=='ProviderSwitchInterrupted' and len(rows)==len(embeddings)
                and all(row.get('meta', {}).get('task_id') != qid for row in rows)):
            return path, value
        tail = rows[-1]
        if (len(rows)!=len(embeddings) or tail['meta']!=trajectory['metadata'] or tail['question']!=query
                or (not tail['procedural_script'].startswith('(LLM call error:')
                    and not (read(failure).get('http_status')==429
                             and len(list(failure.parent.parent.glob('*/response.raw')))==1))):
            raise ValueError('MemP tail is not the interrupted fallback')
        return path, dict(value, memories=rows[:-1], embeddings=embeddings[:-1])

    if arm == 'M5':
        import re
        path = storage/'cerebra_fusion_memory/cf_database.json'
        value = read(saved) if saved and saved.is_file() else read(path)
        counts = [int(m[1]) for f in episodes.glob('*/ingest.json')
                  if (m:=re.match(r'Ingested (\d+) items',read(f)['native_description']))]
        tail = value['nodes'][-1]
        if (len(value['nodes'])!=8+sum(counts) or len(counts)>=50 or value['tools']
                or tail['node_type']!='success' or tail['metadata']['source_query']!=query
                or tail['content']!='Execution for: '+query[:100]
                or any(tail['id'] in (e['source'],e['target']) for e in value['edges'])):
            raise ValueError('Cerebra fallback node cannot be isolated')
        # The answered case already contributed its valid retrieval usage and success counts.
        # Keep those edge counts and remove the generated fallback node.
        nodes = value['nodes'][:-1]
        return path, dict(value,nodes=nodes,metadata=dict(value['metadata'],total_nodes=len(nodes)))

    if arm != 'M7':
        raise ValueError('Unsupported recovery arm')
    path = storage/'mobilee/tips/tips.json'
    value = read(saved) if saved and saved.is_file() else read(path)
    stored = storage/'mobilee/shortcuts/shortcuts.json'
    marker = episodes/qid/'ingest.started.json'
    if stored.stat().st_mtime > marker.stat().st_mtime:
        raise ValueError('MobileE shortcuts changed during the interrupted ingest')
    ids = [row['question_id'] for row in read(work/'manifest.json')['inputs']]
    before = ids[:ids.index(qid)]
    tips = []
    for prev in before:
        if not (episodes/prev/'ingest.json').is_file():
            raise ValueError('MobileE completed prefix is incomplete')
        replies = sorted((ledger/prev/'ingest').glob('*/response.raw'),key=lambda p:int(p.parent.name))
        if not replies:
            raise ValueError('MobileE lacks a saved tip response')
        tips.extend(extracted_tips(replies[0]))
    prefix = list(dict.fromkeys(tips))
    partial = sorted((ledger/qid/'ingest').glob('*/response.raw'),key=lambda p:int(p.parent.name))
    if len(partial)!=1 or list(dict.fromkeys(prefix+extracted_tips(partial[0])))!=value['tips']:
        raise ValueError('MobileE tip tail does not match the completed partial response')
    return path, dict(value,tips=prefix)


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
    if not phase or phase[-1] != max(prior,key=lambda path:int(path.parent.name),default=None):
        raise ValueError('The failed memory send is not the last ledger entry')
    failure=phase[-1]
    result=read(failure)
    if (result['response_received'] is not False or (result['error'] not in ('URLError','RemoteDisconnected','ProviderSwitchInterrupted')
            and not (result['error']=='HTTPError' and result.get('http_status')==429))
            or failure.with_name('response.raw').exists()):
        raise ValueError('Expected the recorded connection failure')
    request=read(failure.with_name('request.json'))
    prefix=[(read(path.with_name('request.json')),archived_content(path.with_name('response.raw')))
            for path in phase[:-1]]
    retrieval_start = read(marker.with_name('retrieval.started.json'))
    if request['model'] != 'deepseek-flash' or retrieval_start['query'] != query:
        raise ValueError('Recovery would change the original request or retrieval')
    folder = out/'recovery'/qid
    saved = folder/'native_before_recovery.json'
    state, restored = native_restore(arm, work, trajectory, failure, saved)
    if state is not None and saved.is_file():
        current = read(state)
        if current not in (restored,read(saved)):
            _, current_prior = native_restore(arm, work, trajectory, failure)
            if current_prior != restored:
                raise ValueError('The native store changed after preparing the retry')
    return {'marker':marker,'qid':qid,'retrieval':retrieval,'trajectory':trajectory,
            'failure':failure,'state':state,'restored':restored,'request':request,'prefix':prefix}


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
    def __init__(self, arm, runtime, out, key, fixture=None, *, use_official=False):
        work = out.parent
        self.pending = None
        if not fixture:
            self.pending = checkpoint(work,arm,read(work/'manifest.json')['inputs'])
            if self.pending is not None:
                restore_checkpoint(work,self.pending)
        super().__init__(arm, runtime, out, key, fixture, use_official=use_official)
        if arm=='M5' and self.pending is not None:
            count=sum(read(p)['native_description'].startswith('Ingested ') for p in (out/'episodes').glob('*/ingest.json'))
            self.provider.task_counter=count % self.provider.consolidation_interval


def ingest(self, row, trace, feedback):
    pending = self.pending
    if pending is None or row['question_id'] != pending['qid']:
        return bridge.Memory.ingest(self, row, trace, feedback)
    self.restore_retrieval(pending['trajectory']['query'],pending['retrieval'])
    marker = pending['marker']
    if marker.name == 'ingest.started.json':
        marker.rename(marker.with_name(f'ingest.started.before-{time.time_ns()}.json'))
    model = self.model
    original = model.fixture
    expected = list(pending['prefix'])+[(pending['request'],None)]

    def replay(messages):
        if expected:
            request,content = expected.pop(0)
            if request['messages'] != messages:
                model.failure='checkpoint_request_changed'
                raise ValueError('Recovery changed a previously sent memory request')
            if content is not None:
                return content
        model.fixture = original
        try:
            return model(messages)
        finally:
            model.fixture = replay

    model.fixture = replay
    try:
        result = bridge.Memory.ingest(self,row,trace,feedback)
        if expected:
            raise ValueError('The saved memory request was not reached')
    finally:
        model.fixture = original
    self.pending = None
    return result

RecoveryMemory.ingest = ingest
