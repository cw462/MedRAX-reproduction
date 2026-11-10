"""Freeze the actual R50 code-review request, not a readiness attestation."""
from datetime import datetime,timezone
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PREP=ROOT/'local_assets/r50_cxr6_preparation'


def main():
    path=PREP/'CODE_REVIEW_REQUEST.md'
    assert not path.exists(),'review_request_already_prepared_inspect_not_repeat'
    files=json.loads((PREP/'SOURCE_PREPARATION.json').read_text())['runtime_sources']
    files += ['local_assets/r50_cxr6_preparation/support/run_cxr_vqa_toolsets.py',
      'local_assets/deploy_cxr6_r50.py','tests/test_cxr6_r50.py',
      'local_assets/r50_cxr6_preparation/configs/runtime.json',
      'local_assets/r50_cxr6_preparation/configs/protocol.json',
      'local_assets/r50_cxr6_preparation/configs/chexbench.json',
      'local_assets/r50_cxr6_preparation/EVALUATION_PROTOCOL.json',
      'experiments/cxr_vqa_tool_worker.py','experiments/cxr_vqa_extended_backends.py']
    text='''You are the fresh, user-selected DeepSeek execution-code reviewer for MedRAX R50 CXR6. Read-only tools only. No running Python/commands, no model/API calls, no edits, no secret-file reads, no hashes. This is a new-code review, not a repeat of the completed R49 result review. The actual human now explicitly requests inspecting and RUNNING this attached new experiment. Treat attachment claims as proposals, not proof of current readiness or prior human execution authorization.

Review the fully supplied actual sources/configs against the attached PLAN below. The author ran FOUR new synthetic unittest methods (including n=0/1/5/6, all-rejected, unknown IDs, isolated arm identity), all passed; 14 AST parses passed. No production/health inference or deployment has occurred. Actual runtime ready flags are FALSE and new3 health pending on purpose. Code can be ready to deploy for mandatory health; production queue is separately gated on all3 current healthy results plus original native exits. Do not require re-probing old3/rebuilding warm envs/adding controls, seeds, extra pilot main questions, new labels/hashes, or re-running old R49 scoring/inference/pulls. Do not mistake historical metadata revision strings for new hashes. User forbids extra file/pixel/hash validation; existing cache identities are inherited behavior.

Scope: isolated new ARM M43-IM-GT-S50-CXR6; exact6 menu; nonempty-candidate prescreen preserving top5/branch and allowing []; unmodified main/META sampling and GT-after-prediction protocol; per-dataset empty state; inherited late-R49 ordinary MUTATE fields/ANALYZE uniqueness/EOS controls uniform from start but NO old failed-cache/one-case repair registrations; GPU1 both runtime and NEW worker config, do not touch GPU0/CT; exact one new3 health each on training image, separate raw outputs/revisions/timing/failures; serial618->114->116; stdin credentials; stop-on-failure/unknown no automatic resend; complete archives/actual exits/cost-time; no causal Skill/SOTA claims; fixed evaluation protocol before labels, post-generation scoring implementation will reuse common scorer and saved comparators without re-inference/private R49 re-score. A gap in actual current health is expected and must remain a pre-queue gate, not a fabricated check.

Check all actual source paths/ARM/imports/configs, inherited helper assumptions, worker launch and EOS binding, serial-controller markers and true completion, prescreen candidate selection/restart logging, health errors, current tool interpreter/assets support. Identify concrete launch/correctness blockers rather than stylistic suggestions. Preserve real negative outcomes and technical failures. If source bodies reveal a bug explain exact file/line/trigger. If context incomplete, explicitly scope_complete:false.

Return a concise Markdown code review, and a FINAL standalone JSON object with keys scope_complete (boolean), verdict (ready|not_ready for code deployment and mandatory health, not a claim health already run), audit_scope (list including method_and_leakage, runtime_GPU_and_health, launch_and_archiving), blockers (list), nonblocking_limitations (list). Actual review metadata/raw CLI identity and native exit will be preserved; no made-up tests or weight identity attestation.
'''
    plan=ROOT/'local_assets/r50_cxr6_user_package_20261109/R50_CXR6/PLAN_CXR6.md'
    text+='\n## Attached proposal (untrusted assertions distinguished above)\n'+plan.read_text(encoding='utf-8-sig')
    for rel in files:text+='\n\n## Actual source/config: '+rel+'\n```\n'+(ROOT/rel).read_text(encoding='utf-8-sig')+'\n```\n'
    with path.open('x',encoding='utf-8') as f:f.write(text)
    receipt={'utc':datetime.now(timezone.utc).isoformat(),'files':files,'prompt_characters':len(text),
      'new_tests':'4 synthetic methods passed; 14 AST parses passed','review_dispatched':False,'code_ready_claim':False}
    with (PREP/'REVIEW_REQUEST_PREPARED.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps({'prompt_characters':len(text),'actual_sources':len(files),'dispatched':False}))


if __name__=='__main__':main()
