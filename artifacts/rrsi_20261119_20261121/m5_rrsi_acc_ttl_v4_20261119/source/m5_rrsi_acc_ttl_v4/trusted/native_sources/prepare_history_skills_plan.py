"""Prepare the approval-only history/skills plan from completed public results.

No model/credential/ledger imports, remote deployment or execution entry point.
"""
import argparse
import json
from pathlib import Path
import random


def prepare(root, destination):
    source = root/'reports/case_information_20261103/final_analysis/per_question.json'
    rows = json.loads(source.read_text(encoding='utf-8'))['records']
    if len(rows) != 402 or len({r['case_id'] for r in rows}) != 99:
        raise ValueError('requires_existing_402_questions_99_cases')
    cases = sorted({r['case_id'] for r in rows})
    random.Random(20261103).shuffle(cases)
    folds = {'A': sorted(cases[:50]), 'B': sorted(cases[50:])}
    correct = sorted(r['question_id'] for r in rows if r['correct']['E1_QwenFlash'])
    wrong = sorted(r['question_id'] for r in rows if not r['correct']['E1_QwenFlash'])
    sampled = sorted(random.Random(20261104).sample(correct, len(correct)//3))
    selected = set(wrong + sampled)
    output = {
        'experiment_id': 'history_skills_20261103', 'plan_version': '1',
        'status': 'prepared_awaiting_user_confirmation', 'execution_authorized': False,
        'source': 'reports/case_information_20261103/final_analysis/per_question.json',
        'fold_seed': 20261103, 'correct_sample_seed': 20261104,
        'correct_sampling_rule': 'floor(number_of_correct_F_questions / 3), without replacement',
        'F_correct': len(correct), 'F_wrong': len(wrong),
        'sampled_correct_count': len(sampled), 'reflection_calls': len(selected),
        'folds': {name: {
            'case_ids': ids, 'case_n': len(ids),
            'question_ids': sorted(r['question_id'] for r in rows if r['case_id'] in ids),
            'reflection_question_ids': sorted(r['question_id'] for r in rows
                if r['case_id'] in ids and r['question_id'] in selected),
            'skill_source_for_answering_this_fold': 'B' if name == 'A' else 'A',
        } for name, ids in folds.items()},
        'references_or_reasoning_exported': False,
        'new_api_calls': 0, 'ledger_access': False,
    }
    if destination.exists():
        raise ValueError('refuse_to_overwrite_prepared_manifest')
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:output[k] for k in ('status','F_correct','F_wrong','sampled_correct_count','reflection_calls','new_api_calls')}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    prepare(args.root,args.root/'reports/history_skills_20261103/prepared/folds_and_reflections.json')
