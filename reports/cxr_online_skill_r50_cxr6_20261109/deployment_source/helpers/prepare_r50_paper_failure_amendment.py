"""Single-use preparation only; extend execution in new files, no model calls."""
import ast
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / 'local_assets/r50_cxr6_preparation/amendment003'


def replace_once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('amendment_source_boundary_not_unique:' + before[:90])
    return source.replace(before, after)


def build_services(source):
    source = replace_once(source, 'from skill_lifecycle_r50 import category',
        'from skill_lifecycle_r50 import category\nfrom r50_failure_observation import delivered_failure')
    return replace_once(source,
        "                if failure:raise RuntimeError('tool_failure_stop_no_automatic_retry:'+failure)",
        "                if failure:obs=delivered_failure(self.out,row,used,actual,obs)")


def build_runner(source):
    source = replace_once(source, 'from skill_services_r50 import Services,conditioning',
        'from r50_services_amended import Services,conditioning\nfrom r50_failure_observation import amendment,validate_prediction_failures,validate_selection_failures,POLICY_ID')
    source = replace_once(source,
        "            if any(tool_failure_reason(value) for value in result.get('observations',[])):\n                raise RuntimeError('saved_prediction_contains_failed_tool')",
        "            failed_tools=validate_prediction_failures(out,q,result)")
    source = replace_once(source, "                   'technical_failure':False,'max_step_failure':False,",
        "                   'technical_failure':bool(failed_tools),'max_step_failure':False,\n                   'failed_tool_observations':failed_tools,'execution_protocol_amendment':POLICY_ID,")
    # Preserve byte-semantic historical trajectories for the already committed prefix.
    source = replace_once(source,
        "            save_once(window/'trajectories'/(q+'.json'),trace);batch.append(trace)",
        "            if ordinal<=amendment(out)['saved_prefix']:\n                trace.pop('failed_tool_observations');trace.pop('execution_protocol_amendment')\n            save_once(window/'trajectories'/(q+'.json'),trace);batch.append(trace)")
    source = replace_once(source,
        "    for p in (out/'services'/'tool_selections'/'R50-AGENT').glob('*/*.json'):\n        if tool_failure_reason(read(p)):raise RuntimeError('unhealthy_tool_selection')",
        "    failed_selection_count=validate_selection_failures(out)")
    source = replace_once(source,
        "              'fixed_main_call_limit':None,'fixed_tool_call_limit':None,'final_repo':copy.deepcopy(repo)})",
        "              'fixed_main_call_limit':None,'fixed_tool_call_limit':None,'final_repo':copy.deepcopy(repo),\n              'execution_protocol_amendment':POLICY_ID,'failed_tool_selections_delivered':failed_selection_count})")
    source = replace_once(source, "        save_once(a.out/'manifest.json',manifest)",
        "        amendment(a.out)\n        save_once(a.out/'manifest.json',manifest)")
    return source


def main():
    approval = json.loads((PREP/'USER_APPROVAL.json').read_text(encoding='utf-8'))
    assert approval['approved'] is True and approval['user_reply']=='那按照论文中的同样来吧'
    marker=PREP/'source_preparation.started.json'
    with marker.open('x',encoding='utf-8') as f:
        json.dump({'utc':datetime.now(timezone.utc).isoformat(),'paid_or_remote_calls':0},f,indent=2)
    builds={'r50_services_amended.py':build_services((ROOT/'experiments/skill_services_r50.py').read_text(encoding='utf-8')),
            'r50_run_amended.py':build_runner((ROOT/'experiments/run_online_skill_r50.py').read_text(encoding='utf-8'))}
    for name,source in builds.items():
        ast.parse(source)
        with (ROOT/'experiments'/name).open('x',encoding='utf-8') as f:f.write(source)
    ast.parse((ROOT/'experiments/r50_failure_observation.py').read_text(encoding='utf-8'))
    receipt={'utc':datetime.now(timezone.utc).isoformat(),'original_11_producers_modified':False,
             'new_execution_modules':['r50_failure_observation.py',*builds],
             'boundary':'CheX ordinal317 onward; SLAKE/VQA from ordinal1',
             'original_manifest_retained':True,'separate_protocol_amendment_required':True,
             'saved_prefix_trajectories_retained':True,'failed_tool_trajectories_follow_existing_technical_failure_exclusion':True,
             'old_tests_or_model_reviews_repeated':False,'paid_or_remote_calls':0}
    with (PREP/'source_preparation.completed.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2)
    print(json.dumps(receipt))


if __name__=='__main__':main()
