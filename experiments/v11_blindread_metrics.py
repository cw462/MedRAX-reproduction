"""S3 adapter for the unchanged, label-isolated V11 S1/S2 scorer.

S3 uses the same frozen P0/candidate pair and final-answer accounting schema.
The original scorer restricts the stage name to S1/S2. This adapter changes only
that name in an in-memory copy for its pure scoring function, then returns S3
names throughout the report. Saved predictions and older scored runs are not
changed. The optional previous run must be S1, matching the inherited comparison.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from . import v11_metrics as original
except ImportError:
    import v11_metrics as original


def score(selection, p0_rows, source_rows, result_rows, labels, *, previous_rows=None):
    if not result_rows or any(row.get('stage') != 'S3' for row in result_rows):
        raise ValueError('S3 adapter requires S3 terminal records')
    if previous_rows and any(row.get('stage') != 'S1' for row in previous_rows):
        raise ValueError('Previous-run comparison must contain frozen S1 records')
    # Only a discriminator value changes; predictions, accounting, and evidence
    # are passed through without rewriting any saved inference file.
    adapted = [dict(row, stage='S2') for row in result_rows]
    payload = original.score(selection, p0_rows, source_rows, adapted, labels,
                             previous_rows=previous_rows)
    payload['stage'] = 'S3'
    payload['implementation'] = 'v11-blindread-cached-selection'
    payload['scoring_adapter'] = 'unchanged_v11_metrics_arithmetic_with_in_memory_stage_name_adapter'
    for group in payload['groups'].values():
        for collection in ('case_changes', 'representative_changes'):
            for case in group[collection]:
                if 'S2' in case:
                    case['S3'] = case.pop('S2')
    payload['limitations'] += [
        'S3 adds an answer-blind image-reader request before matching the frozen pair; it is not an equal-call-budget single-factor comparison with S1.',
        'S2 results, if discussed, must come from its separately completed report; this adapter does not rerun or rewrite S1/S2 scoring.']
    return payload


def generate_report(run_dir, source_run, labels_path, *, previous_run=None):
    run_dir, source_run = Path(run_dir), Path(source_run)
    base = original.base
    selection = json.loads((source_run/'selection.json').read_text(encoding='utf-8-sig'))
    planned = [base._qid(row) for row in selection.get('rows', [])]
    if len(planned) != 60 or len(set(planned)) != 60 or selection.get('planned_n') != 60:
        raise ValueError('S3 requires the fixed sixty; isolated labels have not been opened')
    result_rows = original._load_completed(run_dir, planned)
    if any(row.get('stage') != 'S3' for row in result_rows):
        raise ValueError('S3 records required; isolated labels have not been opened')
    previous_rows = original._load_completed(previous_run, planned) if previous_run else None
    if previous_rows and any(row.get('stage') != 'S1' for row in previous_rows):
        raise ValueError('Previous run must be S1; isolated labels have not been opened')
    p0_rows = base.read_jsonl(source_run/'p0_results.jsonl')
    source_rows = base.read_jsonl(source_run/'candidate_results.jsonl')
    p0 = original._index(p0_rows, planned)
    source = original._index(source_rows, planned, grouped=True)
    groups = {row['group'] for row in result_rows}
    if len(p0) != 60 or any((q, g) not in source for q in planned for g in groups):
        raise ValueError('Incomplete fixed V10 source; isolated labels have not been opened')
    payload = score(selection, p0_rows, source_rows, result_rows,
                    base._labels(labels_path, planned), previous_rows=previous_rows)
    base._atomic(run_dir/'paired_metrics.json', json.dumps(payload, ensure_ascii=False, indent=2)+'\n')
    base._atomic(run_dir/'paired_metrics.md', original._markdown(payload))
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--source-run', required=True, type=Path)
    parser.add_argument('--labels', required=True, type=Path)
    parser.add_argument('--previous-run', type=Path)
    args = parser.parse_args(argv)
    payload = generate_report(args.run, args.source_run, args.labels, previous_run=args.previous_run)
    print(json.dumps({'status': payload['run_status'], 'stage': payload['stage'],
        'planned_n': payload['planned_n'], 'p0_correct': payload['p0']['correct'],
        'final_correct': {g: value['final']['correct'] for g, value in payload['groups'].items()}}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
