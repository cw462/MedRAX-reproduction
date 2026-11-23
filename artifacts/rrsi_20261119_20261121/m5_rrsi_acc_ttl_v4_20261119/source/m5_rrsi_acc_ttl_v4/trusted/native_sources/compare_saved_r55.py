"""Build R55 paired results from the six complete saved R54-format score outputs."""

import argparse
import csv
import json
from pathlib import Path

from online_memory_r49 import read, save_once
from r55_de.compare_de import DATASETS, compare


def saved_rows(run, arm, dataset, count):
    cohort = run / 'generation' / arm / dataset
    jobs = run / 'jobs' / f'{arm}.{dataset}'
    for path in (jobs / 'runner.exitcode', cohort / 'generation.exitcode', jobs / 'score.exitcode'):
        if path.read_text().strip() != '0':
            raise ValueError(f'nonzero native exit: {path}')
    manifest = read(cohort / 'manifest.json')
    expected_arm = 'M43-IM-GT-T55-' + arm
    if (manifest['arm'], manifest['dataset'], manifest['skill_enabled']) != (expected_arm, dataset, arm == 'E'):
        raise ValueError('R55 manifest scope mismatch')
    summary = read(cohort / 'analysis/summary.json')
    details = read(cohort / 'analysis/per_question.json')
    scores = {item['question_id']: item for item in details}
    ids = [row['question_id'] for row in manifest['inputs']]
    order_ids = [item['question_id'] for item in manifest['order']]
    if (len(ids) != count or len(set(ids)) != count or order_ids != ids or len(details) != count
            or set(scores) != set(ids) or summary['questions'] != count
            or (summary['arm'], summary['dataset']) != (expected_arm, dataset)
            or any(type(item['correct']) is not bool for item in details)
            or summary['correct'] != sum(item['correct'] for item in details)):
        raise ValueError('R55 saved score denominator or count mismatch')
    return manifest, [
        {'arm': arm, 'dataset': dataset, 'question_id': qid, 'ordinal': index + 1,
         'image_id': manifest['order'][index]['image_key'], 'correct': scores[qid]['correct'],
         'answer': scores[qid]['explicit_answer'], 'tool_calls': scores[qid]['tool_calls'],
         'activated': scores[qid]['activated']}
        for index, qid in enumerate(ids)
    ]


def export_pair(run):
    all_rows = {'D': [], 'E': []}
    pairs = []
    for dataset, count in DATASETS.items():
        d, d_rows = saved_rows(run, 'D', dataset, count)
        e, e_rows = saved_rows(run, 'E', dataset, count)
        for key in ('inputs', 'order', 'runtime', 'config', 'protocol', 'new_tool_model_policy'):
            if d[key] != e[key]:
                raise ValueError(f'R55 unmatched {key} for {dataset}')
        all_rows['D'].extend(d_rows)
        all_rows['E'].extend(e_rows)
        for left, right in zip(d_rows, e_rows, strict=True):
            pair = {key: left[key] for key in ('dataset', 'question_id', 'ordinal', 'image_id')}
            pair.update({f'{arm}_{key}': row[key] for arm, row in (('D', left), ('E', right))
                         for key in ('answer', 'correct', 'tool_calls', 'activated')})
            pairs.append(pair)
    out = run / 'paired'
    out.mkdir()
    grade_files = {arm: out / f'{arm}_grades.jsonl' for arm in all_rows}
    for arm, rows in all_rows.items():
        grade_files[arm].write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows),
                                    encoding='utf-8')
    summary = compare(grade_files['D'], grade_files['E'])
    save_once(out / 'summary.json', summary)
    save_once(out / 'per_question.json', pairs)
    with (out / 'per_question.csv').open('x', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_pair(args.run), ensure_ascii=False))
