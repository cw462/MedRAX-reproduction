"""Score one completed R55 full-cohort dataset from its saved responses."""

import argparse
from collections import Counter
import csv
from pathlib import Path
import random
import sys

from run_r55_full848_dataset import ARMS, COUNTS


def score_dataset(code, run):
    sys.path.insert(0, str(code/'experiments'))
    from compare_r55live import step_searches
    from cxr_online_primitives_r49 import assert_closed_sends, tool_failure_reason
    from online_memory_r49 import read, save_once
    from r54_author_metrics import outcomes
    from r54_reporting_io import receipt_resources, utc
    from report_skill_r54 import adapt_run
    from r55_full848_e_slake_main_recovery import original_results

    manifest = read(run/'manifest.json')
    done = read(run/'complete.json')
    inputs = manifest['inputs']
    ids = [row['question_id'] for row in inputs]
    arm = manifest['arm']
    assert arm in ARMS.values() and done['arm'] == arm
    assert (run/'generation.exitcode').read_text().strip() == '0'
    assert done['status'] == 'generation_complete'
    assert len(ids) == len(set(ids)) == done['questions'] == COUNTS[manifest['dataset']]
    prediction_dir = run/'predictions'/arm
    for folder in (prediction_dir, run/'steps', run/'contexts', run/'prediction_events', run/'feedback'):
        assert {path.stem for path in folder.glob('*.json')} == set(ids), folder
    assert_closed_sends(run, require_receipts=True)
    adapted = adapt_run(run)

    rng = random.Random(0)
    cases = []
    seen = set()
    tools = Counter()
    is_evolver = arm == ARMS['E']
    for ordinal, row in enumerate(inputs, 1):
        qid = row['question_id']
        filename = qid+'.json'
        prediction = read(prediction_dir/filename)
        feedback = read(run/'feedback'/filename)
        context = read(run/'contexts'/filename)
        assert prediction['ordinal'] == feedback['ordinal'] == context['ordinal'] == ordinal
        assert feedback['saved_prediction'] == prediction and feedback['timing'] == 'after_immutable_prediction'
        assert utc(feedback['released_at']) >= utc(prediction['prediction_saved_at'])
        reference = feedback['reference_annotation']['answer']
        observations = prediction['observations']
        tools.update(obs['tool'] for obs in observations)
        case = {
            'ordinal': ordinal, 'question_id': qid, 'question': row['question'], 'options': row.get('options', {}),
            'reference': reference, 'answer': adapted[qid]['explicit_answer'], 'choice': adapted[qid]['choice'],
            'correct': outcomes(row, adapted[qid], reference, rng)['aligned_correct'],
            'same_image_ids': prediction['same_image_ids'], 'main_calls': prediction['main_calls'],
            'tool_calls': prediction['tool_calls'],
            'failed_tool_calls': sum(bool(tool_failure_reason(obs)) for obs in observations),
        }
        if is_evolver:
            steps = read(run/'steps'/filename)
            search = read(run/'services/experience_searches'/qid/'pre_answer.json')
            assert steps[0]['pre_answer_experience_search'] == search
            assert search['trigger'] == 'required_pre_answer'
            assert search['status'] in ('empty_bank', 'retrieved')
            assert bool(search['active_card_count']) == bool(search['results']) == (search['status'] == 'retrieved')
            for card in search['results']:
                assert card['source_question_ids'] and set(card['source_question_ids']) <= seen
            followups = [item for step in steps for item in step_searches(step)
                         if item.get('trigger') == 'model_followup']
            case.update(pre_answer_search=search, followup_searches=followups)
        seen.add(qid)
        cases.append(case)

    resources = {}
    for slot in sorted((run/'services/calls').iterdir()):
        if slot.is_dir():
            records = [read(path) for path in slot.glob('*/*/result.json')]
            assert len(records) == len(list(slot.glob('*/*/started.json')))
            records.extend(original_results(run, slot.name))
            resources[slot.name] = receipt_resources([(None, None, item) for item in records])
            resources[slot.name]['received'] = sum(item.get('response_received') is True for item in records)
            resources[slot.name]['failed'] = sum(bool(item.get('error')) for item in records)
    correct = sum(case['correct'] for case in cases)
    summary = {
        'dataset': manifest['dataset'], 'arm': arm, 'questions': len(cases),
        'correct': correct, 'accuracy_pct': 100*correct/len(cases),
        'main_calls': sum(case['main_calls'] for case in cases),
        'tool_calls': sum(case['tool_calls'] for case in cases), 'tools_by_name': dict(tools),
        'failed_tool_calls': sum(case['failed_tool_calls'] for case in cases), 'model_usage_by_role': resources,
        'saved_prefix_questions': manifest.get('continuation', {}).get('historical_predictions', 0),
    }
    if is_evolver:
        summary.update(required_pre_answer_checks=len(cases), experience_delivered_questions=sum(
            bool(case['pre_answer_search']['results']) for case in cases))
    out = run/'analysis'
    save_once(out/'summary.json', summary)
    save_once(out/'per_question.json', cases)
    columns = ('ordinal', 'question_id', 'question', 'answer', 'choice', 'reference', 'correct',
               'main_calls', 'tool_calls', 'failed_tool_calls')
    with (out/'per_question.csv').open('x', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(cases)
    return summary


if __name__ == '__main__':
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(score_dataset(args.code, args.run), ensure_ascii=False))
