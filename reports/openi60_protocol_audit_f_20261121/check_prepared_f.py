"""Inspect a prepared F runtime without instantiating inference or memory services."""
import argparse
import importlib
import inspect
import json
from pathlib import Path
import sys


def check(package):
    package=package.resolve()
    sys.path.insert(0,str(package))
    worker=importlib.import_module('native_worker')
    config=json.loads((package/'config.F.json').read_text(encoding='utf-8'))
    work=Path(config['work_dir'])
    frozen=worker.verify_frozen(work)
    runner,counts,services=worker.load_native(config)
    executor=services.Services.__mro__[1]
    expected=package/'native/code/M5/experiments/skill_services_r54.py'
    if Path(inspect.getfile(executor)).resolve()!=expected:
        raise ValueError('R55 inherited an executor outside the isolated F runtime')
    if 'action_protocol_f' not in executor.execute.__code__.co_names:
        raise ValueError('F contract is absent from the inherited native executor')
    guard=importlib.import_module('action_protocol_f')
    if guard.MAX_REPAIRS!=2:
        raise ValueError('Expected two repairs per decision')
    expected_ids=config['protocol_f']['question_ids']
    if frozen['cohort']['selected_ids']!=expected_ids:
        raise ValueError('Prepared cohort differs from the fixed historical cohort')
    for arm in ('B0','L1'):
        for name in ('services','storage','external_memory','predictions','feedback'):
            if (work/arm/name).exists():
                raise ValueError('Prepared work contains execution state: '+arm+'/'+name)
    return {'phase':'prepared_F_verified_no_generation','package':str(package),'work':str(work),
            'questions_per_arm':len(expected_ids),'question_ids':expected_ids,
            'executor':str(expected),'contract_module':guard.__file__,
            'model_calls':0,'tool_calls':0,'memory_writes':0,
            'independent_arms_with_no_execution_state':['B0','L1']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,required=True)
    print(json.dumps(check(parser.parse_args().package),ensure_ascii=False,indent=2))
