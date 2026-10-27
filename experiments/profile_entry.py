"""Run a sibling experiment with process-local CUDA peak-memory evidence.

This wrapper does not change model parameters or infer medical correctness.
It measures PyTorch allocations of this process, not all device/process memory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entry', choices=('multi_tool_eval',), required=True)
    parser.add_argument('--profile-output', type=Path, required=True)
    parser.add_argument('entry_args', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.profile_output.exists():
        parser.error('Profile output already exists; use a new file')
    import torch
    if not torch.cuda.is_available():
        parser.error('CUDA unavailable; no silent fallback')
    entry = Path(__file__).with_name(args.entry + '.py')
    devices = list(range(torch.cuda.device_count()))
    for index in devices:
        torch.cuda.synchronize(index)
        torch.cuda.reset_peak_memory_stats(index)
    record = {'schema_version': 1, 'torch_version': torch.__version__,
              'entry_sha256': hashlib.sha256(entry.read_bytes()).hexdigest(),
              'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'started_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'PyTorch allocations in this process, including initialization and inference'}
    forwarded = args.entry_args[1:] if args.entry_args[:1] == ['--'] else args.entry_args
    previous = sys.argv
    try:
        sys.argv = [str(entry), *forwarded]
        runpy.run_path(str(entry), run_name='__main__')
        record['exit_code'] = 0
    except SystemExit as exc:
        record['exit_code'] = exc.code
        raise
    except BaseException as exc:
        record['exit_code'] = 1
        record['error_type'] = type(exc).__name__
        raise
    finally:
        sys.argv = previous
        record['finished_utc'] = datetime.now(timezone.utc).isoformat()
        record['devices'] = []
        for index in devices:
            torch.cuda.synchronize(index)
            record['devices'].append({'visible_index': index, 'name': torch.cuda.get_device_name(index),
                'max_allocated_bytes': torch.cuda.max_memory_allocated(index),
                'max_reserved_bytes': torch.cuda.max_memory_reserved(index)})
        args.profile_output.parent.mkdir(parents=True, exist_ok=True)
        with args.profile_output.open('x', encoding='utf-8') as stream:
            json.dump(record, stream, indent=2)


if __name__ == '__main__':
    main()
