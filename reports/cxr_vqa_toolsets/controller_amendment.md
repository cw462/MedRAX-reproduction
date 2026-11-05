# Controller repair before C/X generation

The initial implementation used the direct-answer system instruction for all
arms. That instruction required final answer/reason JSON without distinguishing
intermediate planning. It conflicted with the M/C/X planning JSON schemas.
The first M run completed 114 predictions with no tool selections. No reference
answers or correctness scores were read to discover this: only stage counters,
tool-selection counts and the frozen prompt source were inspected.

This is an implementation error, not evidence that an adequately instructed
MedRAX controller would choose no tools or that its tools have no value.
The original M predictions, raw requests, responses, shared accounting and fault
records are retained. They will not be overwritten or silently relabelled as
the requested repaired M experiment.

The repaired agent system instruction explicitly permits stage-specific planning,
validation and expert schemas and limits answer/reason JSON to final answering.
No tool call is forced. Questions, image bytes, settings, tool budget, output
contract, scorer, references and money cap do not change. D's one-call system
instruction is unchanged, so all 114 D predictions can be reused without new
paid calls. C/X have not started generation and will use the repaired controller.

Rerunning the already-completed M group would create new paid requests. This
requires the user's specific exception to the first-request/no-repeat rule.
If approved, use a fresh repaired-run namespace and retain/refer to the original
D evidence; do not change original M terminal files or use its scores to tune
the repair. The same shared ledger and cumulative budget remain mandatory.

Validation: the offline C scenario requests actual planning, EDV, expert and final
schemas within four calls and explicitly checks that the agent system permits
intermediate stages. No paid probe is needed; the first new M call, if approved,
is a real result retained in its new namespace.
