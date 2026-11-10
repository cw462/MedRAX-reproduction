# R50 approved protocol amendment003 — paper tool-failure observations

The user asked how the original MedRAX paper defines tool failures, received the paper/author-code explanation, and explicitly replied **“那按照论文中的同样来吧”**. USER_APPROVAL.json records this instruction. The earlier pending proposal and ACTUAL_THIRD_STOP.json remain unchanged historical records.

MedRAX appendix A.4, page16, returns explicit tool-error result messages to the reasoning model, which chooses how to proceed. The pinned author grounding wrapper defaults to300 new tokens and catches execution/parser exceptions as failed results. R50 adopts that failure-delivery mechanism in its existing JSON observation interface. It does not become an exact reproduction of the original paper's model, graph or §5.1 evaluation retries.

Sources: [paper](https://proceedings.mlr.press/v267/fallahpour25a.html), [grounding](https://github.com/bowang-lab/MedRAX/blob/dae30e2f136ef0b2a40885a4c335386e9ffad052/medrax/tools/grounding.py), [agent](https://github.com/bowang-lab/MedRAX/blob/dae30e2f136ef0b2a40885a4c335386e9ffad052/medrax/agent/agent.py).

## Boundary and behavior

- Original316 CheX predictions, their feedback/events/trajectories, original manifests and all three failed native phase histories remain in place.
- Applies uniformly from CheX ordinal317 and from SLAKE/VQA ordinal1 through the remaining cohorts.
- The held MAIRA300-token non-EOS result remains failed. No regeneration, output repair/truncation, synthetic successful cache, EOS relaxation, model/runtime install or parameter change occurs.
- Terminal failed cache/selection records remain unchanged. The new execution code writes a separate failure_observations receipt binding the raw terminal result to the explicit failed observation sent to the main model.
- Unknown sends and started_unknown tool outcomes still stop without resending. Ordinary three-no-progress stopping is unchanged. No automatic paid evaluation or tool retries are introduced.
- The main model may answer or choose other tools after receiving the error. Existing same-image evidence filtering continues to exclude failed tool outputs. Existing Skill eligibility excludes trajectories with technical tool failures; ordinary prediction/event-before-own-reference ordering remains.
- Original11 remote producer modules are retained. Three additional execution modules are deployed: r50_failure_observation.py, r50_services_amended.py and r50_run_amended.py. Original manifests are retained with a separate protocol_amendment.json sidecar per dataset. Do not call the executed producer code unchanged merely because original files were retained.

## Actual launch and verification

prepare_r50_paper_failure_amendment.py executed once native0. Three new synthetic tests passed once in0.692s: failed-selection reuse without backend execution; raw failed300-token output and delayed own feedback retained; unknown attempts, changed actions and repaired records refused. No old tests/model reviews repeated.

launch_r50_paper_failure_amendment_once.py executed once native0. Controller3517457 and CheXrunner3517463 started in distinct amended jobs. One actual status native0 showed317predictions/318contexts/317feedback,832main sends/responses,155META/10complete windows; SLAKE/VQA had not started. This verifies the held question completed under error delivery, without calling the failed tool again. It does not assert completed cohort scores or final exit0.

Active mapping: jobs/protocol_amendment003.json; controller_amendment003, queue_status.amendment003.json; every dataset job is ds_amendment003 and every final generation file is generation.amendment003.exitcode. All actual final exits remain pending. Original controller/CheX, recovery001 and recovery002 exit1 files are never overwritten.

Report this as amendedR50, retaining failure/time/resource uncertainty, online annotation exposure, same-image reuse, prompt/EOS/budget and time/order confounds. All new execution, recovery and postprocessing code requires the planned single fresh complete-results review before final publication.
