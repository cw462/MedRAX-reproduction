"""Secondary offline format sensitivity from released predictions and replies."""

import argparse
import json
from pathlib import Path
import re

from run_cxr_vqa_toolsets import parse_final
from score_cxr_vqa_extension import grade, rows


def score(published, reused):
    inputs = rows(published / 'inputs.jsonl')
    refs = {r['question_id']: r['answer'] for r in rows(published / 'references.jsonl')}
    summary = {'rule': 'Secondary sensitivity only. Remove one enclosing Markdown JSON fence and parse the unchanged final response with the original parser. All six arms use the same rule. Original predictions retained.', 'arms': {}}
    detail = []
    for arm in ['D', 'M', 'C', 'X', 'O', 'M-R']:
        source = published if arm in ['O', 'M-R'] else reused
        predictions = {r['question_id']: r for r in rows(source / f'predictions_{arm}.jsonl')}
        correct = missing = recovered_count = 0
        for row in inputs:
            qid = row['question_id']
            pred = predictions[qid]
            recovered = False
            if pred['status'] != 'completed':
                calls = json.loads((source / 'calls' / arm / (qid + '.json')).read_text(encoding='utf-8'))
                replies = [c for c in calls if c.get('response')]
                if replies:
                    message = max(replies, key=lambda c: int(c['ordinal']))['response']['choices'][0]['message']
                    match = re.fullmatch(r'\s*```(?:json)?\s*\n?([\s\S]*?)\n?```\s*', message.get('content') or '', re.I)
                    if match and not message.get('tool_calls'):
                        parsed = parse_final(match[1])
                        if parsed['status'] == 'completed':
                            pred = {**pred, **parsed}
                            recovered = True
            good, absent = grade(row, pred, refs[qid])
            correct += good
            missing += absent
            recovered_count += recovered
            detail.append(dict(arm=arm, question_id=qid, answer=pred.get('answer'), reference=refs[qid], correct=good, missing=absent, format_recovered=recovered))
        summary['arms'][arm] = dict(correct=correct, missing=missing, format_recovered=recovered_count, n=len(inputs), accuracy_pct=100*correct/len(inputs))
    return summary, detail


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--published', type=Path, required=True)
    parser.add_argument('--reused', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    summary, detail = score(args.published, args.reused)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'format_sensitivity_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.out / 'format_sensitivity_per_question.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in detail), encoding='utf-8')
