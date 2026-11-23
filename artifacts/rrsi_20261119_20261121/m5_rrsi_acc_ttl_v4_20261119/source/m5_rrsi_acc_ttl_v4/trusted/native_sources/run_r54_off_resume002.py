"""Additive Off-only entry: replay immutable R54 commits and original API caches."""
import sys
from pathlib import Path
import run_online_skill_r54 as original
from r54_off_resume_evidence import ARM, QID, ORDINAL, approved_recovery, require_resume, read
from skill_services_r54_off_resume002 import Services

_run_stream = original.run_stream
_save_once = original.save_once


def save_manifest_compatibly(path, value):
    path = Path(path)
    if path.name == 'manifest.json' and path.is_file():
        prior = read(path)
        value = dict(value, implementation_files=prior['implementation_files'])
    return _save_once(path, value)


def run_stream(inputs, order, data, out, service, vault, tools, config=None, **kwargs):
    scope = require_resume(out)
    if original.ARM != ARM or kwargs.get('evolver') is not original.disabled_evolve:
        raise ValueError('R54_resume002_Off_only_stream_required')
    if scope['dataset'] == 'chexbench':
        approved_recovery(out)
    history = _run_stream(inputs, order, data, out, service, vault, tools, config, **kwargs)
    if scope['dataset'] == 'chexbench':
        recovered = approved_recovery(out)
        receipt = read(Path(out) / 'resume002_tool_deliveries' / QID / (str(ORDINAL) + '.json'))
        if receipt.get('adoption') != recovered['adoption']:
            raise ValueError('R54_recovery_delivery_required')
    return history


def main():
    if '--skill' not in sys.argv or sys.argv[sys.argv.index('--skill') + 1] != 'off':
        raise ValueError('R54_resume_entry_only_authorizes_Off')
    original.Services = Services
    original.run_stream = run_stream
    original.save_once = save_manifest_compatibly
    original.main()


if __name__ == '__main__':
    main()
