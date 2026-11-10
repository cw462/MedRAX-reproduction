# R50 CXR6 — running experiment

The actual user requested inspecting and running the supplied R50 CXR6 plan.
The single arm `M43-IM-GT-S50-CXR6` has now started: CheXbench618 → SLAKE114
→ VQA-RAD116, serially, each with empty Skill and same-image state.
This is a running record; complete-denominator scores are not available yet.

The six-model dynamic tool menu and nonempty-pool applicability prescreen are
a combined intervention. Existing late-R49 ordinary schema/EOS controls apply
uniformly from start. Main/META sampling, post-prediction online annotation
feedback, window30/buffer20/topk6 and no fixed total Agent/tool call ceiling
are retained. Health probes are separate and never reused as scored answers.

Actual new3 health checks each completed once with native0 on GPU1. The full
execution code review and one bounded tool-I/O archive-delta continuation are
complete; the exact tool request, raw stdout/stderr and available timeout logs
are now archived. Previous sources, synthetic fixture failure, reviewer
limitations and actual model/time/cost metadata are preserved.

R49 is archived and published at commit
`3ab0a927526e0910328b8db2503ac0fdc0e10036`. Its predictions, private scores,
transfers and result review are reused. The user waived post-push remote
verification. No R50 result is claimed from its targets or from enabling tools.

Fixed details: [protocol](PROTOCOL.json), [actual initial launch](INITIAL_ACTUAL_LAUNCH.json).
Results will retain full denominators, negative outcomes, all failures and
unknown costs, with onlineGT/budget/prompt/EOS/dataset-overlap confounds.
