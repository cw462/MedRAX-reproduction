ANALYZE = """Analyze a completed PAST trajectory (feedback already released) using its released released label/reward and actual images/observations.
Identify a transferable turning point, not a diagnosis lookup or current answer. Attribute each injected skill:
ADOPTED_POSITIVE, ADOPTED_NEGATIVE, or IGNORED. For adoption cite a zero-based step_index and concise evidence
of changed action/interpretation; mere presence in context is not adoption. Attribution is provisional, not causal proof.
Return JSON: {"skill_adoption":[{"skill_id":"...","status":"...","step_index":0,"evidence":"..."}],
"extracted_pattern":"...","output_intent":"CREATE|PATCH|NONE","patch_target_id":null,
"branch":"general|task_level|action_level"}.
General = concrete domain-agnostic process; task_level = clinical task/tool choice or sequence;
action_level = one tool's input/output operation. NONE for unsupported, case-specific or trivial lessons.
Do not infer a specific lesion solely from a binary source answer. State uncertainty. Never assume unexecuted tools ran.
"""
MUTATE = """Convert the approved source analysis into ONE reusable procedural skill or a local patch.
Only source observations support the content. No fixed source answer, option letter, figure number or patient identity.
Trigger must specify applicability. core_action must specify observable checks, appropriate tool actions, failure/unknown
handling and when to stop; never require access to the current task's unknown reference answer.
Return JSON {"operation":"CREATE|PATCH|NONE","patch_target_id":null,"patch_section":null,"patch_content":null,
"content":{"name":"...","description":"...","applicable_conditions":"...","branch":"general|task_level|action_level",
"tool_name":null,"task_category":"provided category","required_tools":[],"risk_level":"low|medium|high","core_action":"..."}}.
For PATCH only return patch_target_id, patch_section (one content field), patch_content and operation;
do not replace unrelated sections. Scope fields branch, task_category and tool_name cannot change.
NONE may omit all other fields. Registered tools only. No invented measurements or blanket disease exclusion.
"""
REVIEW = """Review a candidate against the actual source trajectory, source image, existing nearest skills and tool menu.
Reject unsupported clinical specifics, rules requiring unknown current labels, copied source answers, vague reminders,
unsafe generalization or incompatible tool capabilities. A binary label does not verify all findings in a model explanation.
Return JSON {"quality":true/false,"reason":"specific source evidence or failure","duplicate_of":null or exact existing ID}.
Duplicate means same reusable operation within the same branch/scope; different conditions may require a local PATCH.
Do not approve merely because JSON is valid. You are a same-model reviewer, not an independent clinician.
"""
PRESCREEN = """Select relevant candidate skill IDs for the current question and its supplied options.
Use applicable_conditions, not answer guesses. Return JSON {"ids":[...]}. At most five per branch.
Never invent IDs. Keep applicable candidates; exclude clearly unmet contextual preconditions.
"""
MERGE = """Consider two same-scope procedural skills. Merge ONLY if preconditions and actions are compatible.
Preserve conditional exceptions, unknown handling and provenance; do not combine incompatible advice.
Return JSON {"merge":false,"reason":"..."} or {"merge":true,"content":{...complete content schema unchanged...},"reason":"..."}.
No new medical claim beyond the two skills. This is repository maintenance, not access to new patient labels.
"""

# Source here means an already completed episode, never a future/current unsubmitted question.
