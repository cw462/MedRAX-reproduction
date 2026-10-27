"""Compile a new immutable execution pool, without reading reference labels."""
import argparse
import json
from pathlib import Path
from .core import Boundary, compile_run, freeze_pool, file_hash


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('splits', 'exclusions', 'run', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--exclusions-sha256', required=True)
    parser.add_argument('--family', choices=('multitool_original', 'historical_classifier'), default='multitool_original')
    parser.add_argument('--pool-version', type=int, required=True)
    parser.add_argument('--previous-pool-sha256')
    parser.add_argument('--outcomes', type=Path)
    args = parser.parse_args(argv)
    boundary = Boundary.from_split_directory(args.splits, args.exclusions,
                                              expected_exclusions_sha256=args.exclusions_sha256)
    records, report = compile_run(args.run, boundary, family=args.family, outcomes=args.outcomes)
    pool = freeze_pool(boundary, records, family=args.family, version=args.pool_version,
                       previous_sha256=args.previous_pool_sha256)
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / '.gitignore').write_text('*\n', encoding='utf-8')
    snapshot = args.output / 'pool.json'
    report.update(pool_sha256=pool.save(snapshot), pool_file_sha256=file_hash(snapshot), boundary_sha256=boundary.sha256,
                  success_retrieval_ready=any(x['task_outcome'] == 'correct' for x in records))
    (args.output / 'compile_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
