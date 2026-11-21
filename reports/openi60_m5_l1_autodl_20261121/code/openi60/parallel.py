"""Run the two independent memory streams concurrently on shared resident tools."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys

from openi60.common import ExperimentError, require
from openi60.setup import verify_frozen
from openi60_cli import child, lock_work, preflight, run


def run_parallel(work: Path, execute: bool):
    require(execute, "Add --execute to start the configured B0/L1 experiment")
    frozen = verify_frozen(work)
    cfg = frozen['config']
    preflight(work)
    main_key = os.environ.get(cfg['main_key_env'], '').strip()
    memory_key = os.environ.get(cfg['memory_key_env'], '').strip()
    require(main_key and memory_key, "The configured model credentials are required")
    require('\n' not in main_key and '\n' not in memory_key, "Credentials must be single lines")
    credentials = (main_key + '\n' + memory_key + '\n').encode()

    with lock_work(work):
        attempts = {}
        for arm in ('B0', 'L1'):
            out = work / arm
            require(not any((out / name).exists() for name in
                            ('storage', 'external_memory', 'services', 'predictions', 'generation.exitcode')),
                    f"{arm} already has execution state; inspect it and use the native resume workflow")
            attempt = work / 'jobs' / arm / 'attempt-001'
            attempt.mkdir(parents=True)
            attempts[arm] = attempt

        def generate(arm):
            print(f"Running {arm}: {cfg['n']} ordered episodes; logs: {attempts[arm]}", flush=True)
            code = child('generate', work, arm, cfg, attempts[arm], credentials)
            (work / arm / 'generation.exitcode').write_text(str(code) + '\n')
            return code

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {arm: pool.submit(generate, arm) for arm in ('B0', 'L1')}
            codes = {arm: future.result() for arm, future in futures.items()}
        require(all(code == 0 for code in codes.values()),
                f"Generation stopped: {codes}. Inspect the arm logs before any explicit resume")

    return run(work, True, False, 'all')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    try:
        value = run_parallel(args.work.resolve(), args.execute)
    except (ExperimentError, FileNotFoundError, KeyError, ValueError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
