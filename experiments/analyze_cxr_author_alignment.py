"""Inventory complete published answer archives, without server or API access."""
from collections import Counter
from functools import lru_cache
import json
from pathlib import Path

from cxr_author_alignment import extract

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/cxr_author_alignment_20261108'
EXPECTED = {'chexbench':618, 'slake':114, 'vqarad':116}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def registry():
    specs = []

    def add(dataset, key, folder, arm, fallback=None, partial=False):
        specs.append({'dataset':dataset, 'key':key, 'folder':folder, 'arm':arm,
                      'fallback':fallback, 'partial':partial})

    for ds in EXPECTED:
        original = ('reports/cxr_vqa_extension/results/' if ds == 'chexbench'
                    else 'reports/cxr_vqa_toolsets/results/') + ds
        for arm in ['D','M','C','X']:
            add(ds, 'original_'+arm, original, arm)
        for arm in ['O','M-R']:
            add(ds, arm, 'reports/cxr_vqa_extension/results/'+ds, arm)
        for arm in ['M-S','M-E']:
            add(ds, arm, 'reports/cxr_vqa_extension/results/stage2/'+ds, arm)
        for arm in ['M-A','M-AS']:
            add(ds, 'v32_'+arm, 'reports/cxr_gain_v32_20261107/results/'+ds, arm)
        for arm in ['M-S41','M-C41']:
            add(ds, arm, 'reports/cxr_action_r41_20261108/results/'+ds, arm, 'original_M')
        for arm in ['D-Q','M-Q']:
            add(ds, arm, 'reports/cxr_vqa_extension/results/stage3/'+ds, arm,
                partial=ds != 'slake')
        if ds == 'vqarad':
            add(ds, 'M42', 'reports/cxr_answer_domain_r42_20261108/results/'+ds,
                'M42', 'original_M')
        else:
            add(ds, 'M43', 'reports/cxr_task_completion_r43_20261108/results/'+ds,
                'M43', 'M-C41' if ds == 'chexbench' else 'M-S41')
    return specs


SPECS = {(spec['dataset'],spec['key']):spec for spec in registry()}


@lru_cache(maxsize=None)
def predictions(dataset, key):
    spec = SPECS[dataset,key]
    values = rows(ROOT/spec['folder']/('predictions_'+spec['arm']+'.jsonl'))
    out = {value['question_id']:value for value in values}
    assert len(out) == len(values)
    return out


@lru_cache(maxsize=128)
def call_entries(path):
    return read(ROOT/path)


def terminal(dataset, key, qid, chain=()):
    """Only the last actual request in the fixed archive supplies an answer.

    Empty request files are expected for documented historical reuse.  Follow
    that fixed whole-arm fallback, never a correctness-dependent alternative.
    """
    assert key not in chain
    spec = SPECS[dataset,key]
    prediction = predictions(dataset,key)[qid]
    status = prediction['status']
    technical = status in ['missing_transport_unknown_sent','missing_tool_unhealthy_stop']
    stopped = prediction.get('official_stop') == 'official_graph_recursion_limit'
    group = prediction.get('group_id',qid)
    path = Path(spec['folder'])/'calls'/spec['arm']/(group+'.json')
    entries = call_entries(path.as_posix()) if (ROOT/path).exists() else []
    if not entries and spec['fallback']:
        result = terminal(dataset,spec['fallback'],qid,chain+(key,))
        result = dict(result)
        if technical or stopped:
            result.update(technical_stop=True, raw=None)
        return result
    if not entries:
        return {'raw':None,'evidence_status':'no_archived_request','technical_stop':technical or stopped,
                'call_path':path.as_posix(),'ordinal':None,'reuse_chain':list(chain+(key,))}
    last = max(entries,key=lambda value:int(value['ordinal']))
    response = last.get('response')
    choices = response.get('choices',[]) if isinstance(response,dict) else []
    message = choices[0].get('message',{}) if choices else {}
    content = message.get('content')
    if isinstance(content,list):
        content = '\n'.join(item.get('text','') for item in content if isinstance(item,dict) and item.get('type')=='text')
    tool_plan = bool(message.get('tool_calls'))
    unavailable = not isinstance(content,str) or not content.strip()
    stop = technical or stopped or tool_plan or unavailable
    return {'raw':None if stop else content,'technical_stop':technical or stopped,
            'evidence_status':('technical_or_graph_stop' if technical or stopped else
                               'native_tool_plan_not_final' if tool_plan else
                               'last_request_without_text_response' if unavailable else 'received_terminal_text'),
            'call_path':path.as_posix(),'ordinal':str(last['ordinal']),
            'reuse_chain':list(chain+(key,))}


def prepare():
    assert (REPORT/'PROTOCOL.json').exists()
    summaries = []
    for spec in registry():
        ds,key = spec['dataset'],spec['key']
        values = predictions(ds,key)
        inputs = {row['question_id']:row for row in rows(ROOT/'reports/cxr_action_r41_20261108/results'/ds/'inputs.jsonl')}
        assert set(values) <= set(inputs)
        if not spec['partial']:
            assert len(values) == EXPECTED[ds] and set(values) == set(inputs)
        assert (ROOT/spec['folder']/('complete_'+spec['arm']+'.json')).exists()
        status, mechanisms, missing = Counter(),Counter(),[]
        for qid in values:
            source = terminal(ds,key,qid)
            status[source['evidence_status']] += 1
            answer = extract(source['raw'],qid,inputs[qid].get('options'))
            mechanisms[answer.mechanism] += 1
            if source['evidence_status']=='no_archived_request':
                missing.append(qid)
        summaries.append(dict(spec,questions=len(values),full_comparison=not spec['partial'],
                              evidence_status=dict(status),adapter_mechanisms=dict(mechanisms),
                              unresolved_archive_qids=missing))
    out = {'phase':'reference_free_archive_preparation','new_paid_requests':0,
           'references_read_by_this_program':False,'comparison_arms':len(summaries),
           'arms':summaries}
    path = REPORT/'ARCHIVE_INVENTORY.json'
    if path.exists():
        assert read(path) == out, 'Inventory changed; do not silently replace an old preparation.'
    else:
        path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'prepared_arms':len(summaries),'full_arms':sum(x['full_comparison'] for x in summaries),
                      'unresolved_archives':sum(len(x['unresolved_archive_qids']) for x in summaries),
                      'new_paid_requests':0}))


if __name__ == '__main__':
    prepare()
