"""Explicit user-requested prefix accuracy; separate from the final cohort score."""
import contextlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import random
import sys
from collections import Counter

from deploy_cxr6_r50 import connect, remote_python, script, LOCAL, RUN, ARM

DEST = LOCAL / 'local_assets/r50_cxr6_preparation/user_requested_interim_accuracy_20261110'


def once(name, value):
    with (DEST / name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def main():
    DEST.mkdir()
    once('started.json', {'utc': datetime.now(timezone.utc).isoformat(),
        'user_request': '做一下中途准确率评分', 'scope': 'One frozen committed prefix, current raw terminal answers before local labels.',
        'explicit_exception_to_waiting_for_whole_cohort_scoring': True,
        'final_dataset_pull_or_score_receipts_consumed': False, 'new_inference_calls': 0})
    source = script(r'''
from pathlib import Path
import json,time
g=Path(RUN)/'generation/chexbench'
manifest=json.loads((g/'manifest.json').read_text());inputs=manifest['inputs']
assert manifest['arm']==ARM and manifest['dataset']=='chexbench' and len(inputs)==618
limit=len(list((g/'predictions'/ARM).glob('*.json')))
cases=[]
for ordinal,row in enumerate(inputs[:limit],1):
 q=row['question_id'];p=g/'predictions'/ARM/(q+'.json');event=g/'prediction_events'/(q+'.json');feedback=g/'feedback'/(q+'.json')
 if not p.is_file() or not event.is_file() or not feedback.is_file():break
 try:
  prediction=json.loads(p.read_text());saved=json.loads(event.read_text())
 except json.JSONDecodeError:break
 assert prediction['question_id']==q and prediction['arm']==ARM and prediction['ordinal']==ordinal
 assert saved['saved_prediction']==prediction and saved['question_id']==q and saved['ordinal']==ordinal
 call=g/'services/calls/R50-AGENT'/q/str(prediction['main_calls'])
 assert all((call/name).is_file() for name in ('started.json','response.json','result.json'))
 started=json.loads((call/'started.json').read_text());receipt=json.loads((call/'result.json').read_text());response=json.loads((call/'response.json').read_text())
 assert not receipt.get('error') and receipt.get('response_received') is True and started['request_id']==receipt['request_id']
 cases.append({'row':row,'prediction':prediction,'prediction_event':saved,'terminal_response':response,
  'terminal_receipt':receipt,'terminal_call_relative':str(call.relative_to(g)),
  'feedback_file_exists_but_body_not_read':True})
assert cases and [v['row']['question_id'] for v in cases]==[v['question_id'] for v in inputs[:len(cases)]]
print(json.dumps({'snapshot_utc_epoch':time.time(),'dataset':'chexbench','arm':ARM,'full_cohort_n':618,
 'committed_prefix_n':len(cases),'initial_prediction_file_limit':limit,'inputs_config':manifest['config'],
 'feedback_vault_or_reference_bodies_read':0,'new_model_or_tool_calls':0,'cases':cases},ensure_ascii=False))
''', RUN=RUN, ARM=ARM)
    output = io.StringIO()
    try:
        with connect() as client, contextlib.redirect_stdout(output):
            remote_python(client, source, timeout=90)
        snapshot = json.loads(output.getvalue())
        once('raw_prefix_snapshot.json', snapshot)
        sys.path.insert(0, str(LOCAL / 'experiments'))
        from score_cxr_author_alignment import adapt, outcomes
        from score_online_skill_r50 import response_text
        # All raw answers adapted BEFORE opening any reference body.
        adapted = []
        for value in snapshot['cases']:
            message = value['terminal_response']['choices'][0]['message']
            raw = message.get('content')
            if isinstance(raw, list):
                raw = '\n'.join(block.get('text', '') for block in raw if isinstance(block, dict) and block.get('type') == 'text')
            if not isinstance(raw, str) or message.get('tool_calls') or message.get('function_call'):
                raw = None
            source_info = {'raw': raw, 'call_path': value['terminal_call_relative'],
                'ordinal': str(value['prediction']['main_calls']), 'reuse_chain': [], 'technical_stop': False,
                'evidence_status': 'received_terminal_text' if raw else 'nonfinal_or_unavailable'}
            adapted.append(adapt(value['row'], value['prediction'], source_info))
        once('reference_free_adaptation.json', {'all_prefix_answers_adapted': True,
             'references_read': False, 'n': len(adapted), 'answers': adapted})
        identity = json.loads((LOCAL / 'local_assets/r49_dataset_score_receipts/chexbench.json').read_text(encoding='utf-8'))['identity']
        reference_rows = [json.loads(line) for line in Path(identity['references']).read_text(encoding='utf-8').splitlines() if line.strip()]
        refs = {value['question_id']: value['answer'] for value in reference_rows}
        assert len(refs) == len(reference_rows) == 618
        rng = random.Random(0)
        details = []
        for value, answer in zip(snapshot['cases'], adapted):
            row = value['row'];qid = row['question_id']
            grade = outcomes(row, answer, refs[qid], rng)
            details.append({'question_id': qid, 'ordinal': value['prediction']['ordinal'],
                'subset': (row.get('source') or {}).get('subset', 'all'), 'reference': refs[qid],
                'skill_injected': bool(value['prediction'].get('selected_skill_ids')),
                'selected_skill_ids': value['prediction'].get('selected_skill_ids', []),
                'adapted': answer, 'score': grade})
        n = len(details);correct = sum(value['score']['aligned_correct'] for value in details)
        subsets = {}
        for label in sorted({value['subset'] for value in details}):
            rows = [value for value in details if value['subset'] == label]
            count = sum(value['score']['aligned_correct'] for value in rows)
            subsets[label] = {'n': len(rows), 'correct': count, 'accuracy_pct': 100 * count / len(rows)}
        groups = {}
        for flag in (False, True):
            values = [value for value in details if value['skill_injected'] is flag]
            count = sum(value['score']['aligned_correct'] for value in values)
            groups[str(flag)] = {'n': len(values), 'correct': count,
                'accuracy_pct': 100 * count / len(values) if values else None, 'descriptive_not_randomized': True}
        summary = {'utc': datetime.now(timezone.utc).isoformat(), 'dataset': 'chexbench', 'arm': ARM,
            'user_requested_interim_score': True, 'prefix_n': n, 'full_dataset_n': 618, 'full_run_n': 848,
            'correct': correct, 'incorrect_or_absent': n - correct, 'micro_accuracy_pct': 100 * correct / n,
            'macro_accuracy_of_present_subsets_pct': sum(value['accuracy_pct'] for value in subsets.values()) / len(subsets),
            'subsets': subsets, 'answer_absent': sum(value['adapted']['answer_absent'] for value in details),
            'domain_invalid': sum(value['adapted']['choice_domain_invalid'] for value in details),
            'raw_whole_json_valid': sum(value['adapted']['raw_whole_json_valid'] for value in details),
            'skill_injection_groups': groups, 'references_read_after_all_prefix_answers_adapted': True,
            'new_model_or_tool_calls': 0, 'old_private_score_invoked': False,
            'final_full_cohort_score_receipts_consumed': False,
            'interpretation': 'Ordered partial prefix only; later questions/datasets may differ. Injection groups are observational and confounded by time/source/order; not a causal Skill comparison.'}
        once('per_question.json', details)
        once('summary.json', summary)
        once('completed.json', {'status': 'completed', 'utc': datetime.now(timezone.utc).isoformat(),
            'native_scope': 'user-requested prefix snapshot and common-adapter accuracy',
            'n': n, 'correct': correct, 'final_scoring_consumed': False, 'new_inference_calls': 0})
    except Exception as error:
        once('failure.json', {'utc': datetime.now(timezone.utc).isoformat(), 'error': repr(error),
            'partial_originals_preserved': True, 'automatic_retry': False,
            'native_stderr': 'original exec transcript, not a separately captured raw-byte stderr file'})
        raise
    statepath = LOCAL / '.aris/IMPROVEMENT_STATE.json'
    state = json.loads(statepath.read_text(encoding='utf-8'))
    state['R50']['user_requested_interim_accuracy'] = dict(summary, output=str(DEST), native_exit=0)
    statepath.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
