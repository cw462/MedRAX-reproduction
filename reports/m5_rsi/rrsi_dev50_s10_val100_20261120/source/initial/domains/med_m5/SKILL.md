# Medical M5 TTL harness constitution

Objective: improve future question-wise first-submission accuracy. The backbone model,
medical tool services, official scoring procedure, resource ceilings and feedback timing
are immutable. There is no reward for token savings or novelty compensating for lower accuracy.

You may edit prompts, executable planning/control flow, memory extraction/writing/merging,
graph retrieval/filtering, context management, existing-tool wrappers, skills and bounded
subagents inside this harness directory. New files must be imported by agent.py.
Do not modify the outer optimizer, scorer, runner, native service bridge or data manifests.
Entrypoints initialize, predict, observe and migrate must retain their signatures.

Runtime follows predict -> immutable submission -> feedback -> observe. Only observe
receives the just-released feedback. Related questions are NOT grouped; earlier released
experience is legitimately reusable on later questions, including the same image.

Learning from already released case feedback is allowed through /state. Do not hard-code
case IDs, per-question answer tables, image filenames or benchmark-specific decision rules
in source/prompts. No future labels, other arm state, grader internals or live run logs.
The state given to a history replay starts strictly before its first question. Do not load
current memory containing later feedback. No writes to read-only source; use /state only.

Code-level memory changes must be backward compatible or supply deterministic migration
in migrate(). Predictions must use actual original images and return real action/tool traces.
No unbounded retry loops, alternate model substitution, fabricated tool observations or
changes to the answer scoring schema. Services enforce fixed resource ceilings externally.
