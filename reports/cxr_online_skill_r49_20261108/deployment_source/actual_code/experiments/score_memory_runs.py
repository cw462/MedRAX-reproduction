"""Independent scorer: turns a completed memory-agent run into a safe sidecar.

The scorer is the only component that opens reference labels. It never writes
question text, option text, report prose or predictions into the sidecar; the
sidecar contains one row per training question with a coarse outcome value, bound
to the exact manifest/results/split files it was computed from.

Outcome definitions (declared before the evaluation):
  correct    - status completed and the parsed letter equals the reference letter
  incorrect  - status completed with a parsed letter that differs
  invalid    - status completed without a parsable letter, or status invalid_answer
  error      - any other terminal status (tool/model/budget failure)
  unknown    - no reference label is available for the question

`--answer-key strict` uses the audited two-stage matcher result; `relaxed` uses
the runner's conservative fallback parser. The key is recorded in the report and
must not be switched after looking at the test outcomes.

This is not clinical verification: it is automatic multiple-choice agreement.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_jsonl(path):
    rows = []
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def wilson(successes, total, z=1.959963984540054):
    if total <= 0:
        return [None, None]
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--splits', type=Path, required=True, help='Frozen prepare_splits output directory')
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--outcomes', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--answer-key', choices=('strict', 'relaxed'), default='relaxed')
    parser.add_argument('--expected-split', default='memory_train',
                        help='Reject any question outside this frozen split')
    args = parser.parse_args(argv)

    manifest = read_json(args.run / 'manifest.json')
    terminals = {}
    for row in read_jsonl(args.run / 'results.jsonl'):
        if row.get('record_type') == 'terminal':
            terminals[(row['question_id'], row['arm'])] = row
    labels = {str(row['question_id']): str(row['answer']).strip().upper() for row in read_jsonl(args.labels)}
    audit_split = {str(row['question_id']): row['split'] for row in read_jsonl(args.splits / 'audit_index.jsonl')}

    key = 'answer_letter_relaxed' if args.answer_key == 'relaxed' else 'answer_letter'
    outcomes, detail = [], []
    counts = Counter()
    for (qid, arm), terminal in sorted(terminals.items()):
        if arm != 'agent':
            continue
        if audit_split.get(qid) != args.expected_split:
            raise ValueError(f'Run contains a question outside the {args.expected_split} split')
        label = labels.get(qid)
        status = terminal.get('status')
        letter = terminal.get(key)
        if label is None:
            outcome = 'unknown'
        elif status == 'completed' and letter:
            outcome = 'correct' if letter == label else 'incorrect'
        elif status in ('completed', 'invalid_answer'):
            outcome = 'invalid'
        else:
            outcome = 'error'
        outcomes.append({'question_id': qid, 'arm': 'agent', 'task_outcome': outcome})
        detail.append({'question_id': qid, 'status': status, 'letter': letter,
                       'reference': label, 'task_outcome': outcome,
                       'model_calls': terminal.get('actual_model_calls'),
                       'tool_calls': terminal.get('actual_tool_attempts')})
        counts[outcome] += 1

    payload = {
        'schema_version': 1,
        'source_run_manifest_sha256': file_hash(args.run / 'manifest.json'),
        'source_results_sha256': file_hash(args.run / 'results.jsonl'),
        'split_manifest_sha256': file_hash(args.splits / 'manifest.json'),
        'outcomes': outcomes,
    }
    args.outcomes.parent.mkdir(parents=True, exist_ok=True)
    temp = args.outcomes.with_name(args.outcomes.name + '.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    temp.replace(args.outcomes)

    graded = counts['correct'] + counts['incorrect']
    report = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'run': str(args.run),
        'answer_key': args.answer_key,
        'planned_terminals': len(terminals),
        'outcome_counts': dict(counts),
        'graded_denominator': graded,
        'accuracy_among_graded': round(counts['correct'] / graded, 4) if graded else None,
        'accuracy_among_all_planned': round(counts['correct'] / len(terminals), 4) if terminals else None,
        'wilson_95ci_among_graded': wilson(counts['correct'], graded),
        'detail': detail,
        'clinical_correctness_verified': False,
        'labels_read_only_here': True,
        'outcomes_sha256': file_hash(args.outcomes),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('outcome_counts', 'graded_denominator',
                                             'accuracy_among_graded', 'wilson_95ci_among_graded')},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
