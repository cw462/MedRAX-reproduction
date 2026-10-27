"""Extract an inference-only subset from metadata, without copying answers or explanations."""
import argparse
import json
from pathlib import Path


def flatten(value):
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [p for item in value for p in flatten(item)]
    return []


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--metadata', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path, help='New file; never overwrite')
    p.add_argument('--max-cases', required=True, type=int)
    args = p.parse_args()
    if args.max_cases < 1:
        p.error('max-cases must be positive')
    count, seen = 0, set()
    with args.metadata.open(encoding='utf-8') as source, args.output.open('x', encoding='utf-8') as output:
        for line in source:
            if not line.strip():
                continue
            obj = json.loads(line)
            qid = obj.get('question_id')
            if not isinstance(qid, (str, int)) or not isinstance(obj.get('question'), str):
                raise ValueError('Expected question_id and question; inspect actual metadata before continuing')
            if str(qid) in seen:
                raise ValueError('Duplicate question_id')
            seen.add(str(qid))
            paths = [s.replace('figures/', '', 1) if s.startswith('figures/') else s for s in flatten(obj.get('images'))]
            row = {'question_id': qid, 'question': obj['question'], 'images': paths}
            output.write(json.dumps(row, ensure_ascii=False) + '\n')
            count += 1
            if count >= args.max_cases:
                break
    print(f'Wrote {count} inference-only records. No answer or explanation fields copied.')


if __name__ == '__main__':
    main()
