"""One paired replay on frozen OpenI 0028 messages, with retrieval as the difference."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import time


QID = 'chexbench_openi_0028'
QUERY = ('(lateral chest radiograph OR lateral chest X-ray) AND '
         '((radiographic side marker OR radiographic laterality marker) OR '
         '((central venous catheter OR PICC) AND (insertion site OR catheter course OR catheter position)))')
FINAL_INSTRUCTION = ('Give your final answer now using JSON with keys "answer" and "reason". '
                     'The answer must include the option letter and its matching full text. '
                     'State the specific evidence for keeping or changing the proposed answer. '
                     'Do not request another tool.')


def main(pilot, paused_run, code, out, *, preflight=False):
    sys.path.insert(0, str(code/'experiments'))
    from online_memory_r49 import read, save_once
    from r55_skemex.medrag_search import MedRAGSearchTool
    from r55_skemex.reasoning_tools import VerifierTool
    from r55_verifier import DeepSeekVerifier
    from run_cxr_action_r41 import parse
    from skill_services_r55 import _query, _traceable_snippets
    from toolsets_r54 import PaidCalls, append_observations

    e = pilot/'generation/E'
    manifest = read(e/'manifest.json')
    row = manifest['inputs'][28]
    assert row['question_id'] == QID and row['options'] == {
        'A': 'left indwelling catheter', 'B': 'right indwelling catheter'}
    candidate = 'B. ' + row['options']['B']
    pause = read(paused_run/'jobs/user_pause_before_full293_continue.json')
    state = (Path('/proc')/str(pause['runner_pid'])/'stat').read_text().rsplit(') ', 1)[1].split()
    assert state[0] == 'T' and int(state[19]) == pause['runner_start_ticks']
    steps = read(e/'steps'/(QID+'.json'))
    assert [x['action']['tool'] for x in steps[0]['executed_calls']] == ['chest_xray_expert', 'llava_med_qa']
    assert steps[1]['executed_calls'][0]['action']['tool'] == 'verify'
    cards = read(e/'services/experience_searches'/QID/'pre_answer.json')['results']
    assert len(cards) == 3 and steps[0]['pre_answer_experience_search']['results'] == cards

    calls = e/'services/calls'
    original_verify = read(calls/'R55-VERIFY'/('verify_'+QID+'_3')/'1/request.json')
    original_final = read(calls/'R49-AGENT'/QID/'3/request.json')
    verify_messages = deepcopy(original_verify['messages'])
    final_messages = deepcopy(original_final['messages'][:8])
    assert len(original_final['messages']) == 10 and final_messages[7]['role'] == 'assistant'
    assert json.loads(final_messages[2]['content'].split('\n', 1)[1]) == cards
    pre_observations = json.loads(final_messages[5]['content'][0]['text'].split('\n', 1)[1])
    assert [x['tool'] for x in pre_observations] == ['chest_xray_expert', 'llava_med_qa']
    assert verify_messages[1]['content'][3] == final_messages[1]['content'][2]
    context = json.loads(verify_messages[1]['content'][-1]['text'])
    assert context['options'] == row['options'] and context['retrieval_evidence'] == []
    old_candidate = parse(final_messages[7]['content'])['calls'][0]['args']['proposed_answer']
    assert old_candidate == 'B. left indwelling catheter'
    assert 'Proposed Answer: '+old_candidate in verify_messages[1]['content'][0]['text']
    risk = context['risk'].replace('supports left side', 'supports either side')
    plan = parse(final_messages[7]['content'])
    plan['calls'][0]['args'].update(proposed_answer=candidate, risk=risk)
    final_messages[7]['content'] = json.dumps(plan, ensure_ascii=False)
    verify_messages[1]['content'][0]['text'] = verify_messages[1]['content'][0]['text'].replace(old_candidate, candidate)
    shared = {'options': row['options'], 'risk': risk, 'retrieval_evidence': [],
              'prior_image_tool_observations': pre_observations, 'experience_cards': cards}

    query = _query(row, {'query': QUERY, 'top_k': 3})
    if preflight:
        assert not out.exists()
        return {'status': 'verified_frozen_inputs', 'question': QID, 'candidate': candidate,
                'cards': [x['id'] for x in cards], 'image_tools_reused': len(pre_observations),
                'new_model_calls': 0, 'medret_calls': 0}
    key = sys.stdin.readline().strip()
    assert key and not out.exists()
    out.mkdir(parents=True)
    save_once(out/'shared.json', {'question': row, 'candidate': candidate, 'historical_candidate': old_candidate,
                                'risk': risk, 'cards': cards, 'prior_image_tool_observations': pre_observations,
                                'source_ordinal': 29, 'reference_passed_to_models': False})
    save_once(out/'medret/request.json', query)
    save_once(out/'medret/started.json', {'utc_epoch': time.time()})
    tick = time.monotonic()
    # Same R55 retrieval and snippet selection, with synthesis disabled to
    # preserve the requested four-model-call budget.
    retrieval = MedRAGSearchTool(default_corpus='PubMed', top_k=3,
                                  select_snippets=_traceable_snippets,
                                  synthesis_call=lambda **_: '').run(query).payload
    retrieval['elapsed_s'] = time.monotonic() - tick
    save_once(out/'medret/result.json', retrieval)
    if not retrieval['snippets']:
        return {'status': 'no_traceable_retrieval', 'medret_calls': 1, 'verify_calls': 0, 'final_calls': 0}

    evidence = [{'tool_ordinal': 1, 'query': retrieval['query'], 'snippets': retrieval['snippets']}]
    results = {}
    for arm, snippets in (('control', []), ('medret', evidence)):
        branch = out/arm
        vm = deepcopy(verify_messages)
        vm[1]['content'][-1]['text'] = json.dumps(dict(shared, retrieval_evidence=snippets), ensure_ascii=False)
        verifier = DeepSeekVerifier(branch, key)

        def audit(**_):
            return verifier('verify_'+QID, vm)

        report = VerifierTool(evaluation_call=audit).run({'question': row['question'], 'proposed_answer': candidate}).payload
        save_once(branch/'verify_observation.json', report)
        protocol = dict(manifest['protocol'], experiment_id='r55_openi0028_replay_'+arm)
        paid = PaidCalls(manifest['config'], protocol, branch, key, parallel=True)
        fm = deepcopy(final_messages)
        append_observations(fm, [{'status': 'completed', 'backend': 'verifier', 'tool': 'verify', 'observation': report}], branch, 'M')
        fm.append({'role': 'user', 'content': FINAL_INSTRUCTION})
        raw = paid.call(row, 'R49-AGENT', 1, fm)
        try:
            final = parse(raw)
        except (ValueError, IndexError):
            final = {'unparsed_response': raw}
        verify_dir = branch/'calls/R55-VERIFY'/('verify_'+QID)/'1'
        final_dir = branch/'calls/R49-AGENT'/QID/'1'
        for path, template in ((verify_dir, original_verify), (final_dir, original_final)):
            actual = read(path/'request.json')
            assert {k:v for k,v in actual.items() if k!='messages'} == {k:v for k,v in template.items() if k!='messages'}
        results[arm] = {'verify': report, 'final': final, 'verify_receipt': read(verify_dir/'result.json'),
                        'final_receipt': read(final_dir/'result.json')}

    # The reference is opened only after both final answers have been saved.
    reference = read(e/'feedback'/(QID+'.json'))['reference_annotation']['answer']
    return {'status': 'completed', 'reference': reference, 'candidate': candidate, 'retrieval': retrieval,
            'results': results, 'medret_calls': 1, 'verify_calls': 2, 'final_calls': 2,
            'image_tool_calls': 0, 'embedding_calls': 0, 'synthesis_calls': 0}


if __name__ == '__main__':
    preflight = sys.argv[-1] == '--preflight'
    paths = [Path(s) for s in (sys.argv[1:-1] if preflight else sys.argv[1:])]
    result = main(*paths, preflight=preflight)
    from online_memory_r49 import save_once
    if not preflight:
        save_once(paths[-1]/'completed.json', result)
    print(json.dumps(result, ensure_ascii=False))
