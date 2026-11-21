"""Run protocol-only fixtures and save their results; no external service clients."""
import argparse
import json
from pathlib import Path
import sys
import unittest


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    suite=unittest.defaultTestLoader.loadTestsFromNames(['test_audit_protocol','test_protocol_f','test_prepare_f'])
    with (out/'unittest.log').open('w',encoding='utf-8') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    summary={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
             'skipped':len(result.skipped),'successful':result.wasSuccessful(),
             'real_model_calls':0,'real_tool_calls':0,'memory_interface_calls':0,
             'groups':['attachment lexical audit','shared F contract and native executor fixtures','fixed 8/60 cohort selection'],
             'python':sys.version,'log':str(out/'unittest.log')}
    (out/'test_results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    raise SystemExit(run(parser.parse_args().out))
