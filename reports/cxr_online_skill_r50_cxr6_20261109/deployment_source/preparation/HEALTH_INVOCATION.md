# R50 new3 health invocation

Provider: existing MedRAX SSH host; existing warm interpreters/model assets.
Physical GPU1 only, RTX3090 UUID GPU-c6525ce9-f07f-ed3b-b2e8-fa8a8ac732f0. Index 1 is the actual scheduling contract. No other device/process may be modified.

Run after root has supplied the actual new code review readiness and staged the isolated code. Read `deploy_cxr6_r50.py` before invoking. Working directory: `C:/Users/cheng/MedRAX_v9_20261030`.

```powershell
python -X utf8 local_assets/deploy_cxr6_r50.py health
```

This exact single-use invocation starts and waits for a detached health controller on the server. It runs only medgemma, llava_rad, medvlm_r1 once each, serially, on the existing training_xmlab120.jpg; new CODE worker and all tool specs must mask GPU1. It makes zero main/META/embedding API calls and does not import outputs into Skill, same-image memory, production caches or scores. It preserves request, raw stdout/stderr, result, native worker exits, revisions, timing, actual backend events and errors in new RUN/health, then pulls only that newly created health evidence once to local preparation/health. Runtime arms remain declared health-pending; queue readiness uses this actual separate receipt.

Do not run stage, queue, modify code, fix failures, install packages/models, examine secrets, re-probe old tools, or repeat health. Report every doc-versus-reality mismatch and actual native result. If the command yields a running native session, wait on that session; do not invoke it again. Root owns production launch and all Git/publication work.
