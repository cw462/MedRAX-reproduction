"""Resume the frozen V12 generation after the user's ledger-policy amendment.

Only the raw file-byte equality sentinel is removed. The original generation
entrypoint, prompts, completed predictions, fee cap and accounting remain intact.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--out',type=Path,required=True)
    known,_=parser.parse_known_args(argv)
    out=known.out.resolve()
    if not (out/'effective_config.json').exists():
        raise ValueError('original_frozen_run_required_for_this_recovery')
    from v12_ledger import V12ProviderLedger
    import provider_ledger
    provider_ledger.ProviderLedger=V12ProviderLedger
    import run_v12_ab
    amendment=out/'runtime_amendments/01_ledger_byte_check_removed.json'
    if not amendment.exists():
        amendment.parent.mkdir(parents=True,exist_ok=True)
        amendment.write_text(json.dumps({
            'version':'v12-ledger-byte-check-removed-1',
            'recorded_utc':datetime.now(timezone.utc).isoformat(),
            'authorization':'User explicitly requested removal of the raw byte consistency stopping requirement on 2026-10-31.',
            'change':'V12ProviderLedger._check_disk checks object lifecycle only; no raw disk-byte equality requirement.',
            'retained':['original ledger path and identity','exclusive ledger lock','original cap and call budgets',
                        'original monetary validation and reserve/settle operations','original conservative pending recovery'],
            'unchanged':['fixed 60 questions','prompts and model','B then A order','saved initial and branch terminals'],
            'resume_policy':'Reuse six existing initial and B terminals, including the recorded fallback; no prediction retry.',
            'source_sha256':{name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                             for name in ['run_v12_resume.py','v12_ledger.py']}
        },ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return run_v12_ab.main(argv)


if __name__=='__main__':raise SystemExit(main())
