# R54 Skill 实际提示词原文

以下由已归档的 R54 源码导出。MUTATE、REVIEW 和 MERGE 已展开继承的 R49 提示词。

## ANALYZE

```text
Analyze a completed episode using ONLY released feedback and actual image/tool evidence.
Two INDEPENDENT tasks: (A) attribute previously ACTIVATED skills; [] if none.
(B) discover new procedural operations. Empty skill memory NEVER prevents discovery.
Short successful trajectories can contain useful operations. Correct final labels do NOT validate
all intermediate claims. Wrong final labels do NOT prove a proposed repair would work.
Identify one observed decision event: tool_disagreement, scope_gap, output_boundary,
targeted_verification, tool_parameter_repair, evidence_sufficient_stop, other, or none.
Separate OBSERVED operation from an UNEXECUTED HYPOTHESIS. A hypothesis is stored but not activated.
Do not infer lesions from yes/no labels, interpret classifier scores as severity, or use image mean
intensity as a clinical laterality rule. Do not invent a causal success story from final correctness.
Give CREATE for a supported reusable operation, PATCH for a supported refinement of an existing
snapshot skill, or NONE with a specific missing-evidence/triviality reason. No CREATE quota.
General: domain-agnostic process; task_level: task/tool routing; action_level: one tool interface.
Return JSON:
{"skill_adoption":[{"skill_id":"...","status":"ADOPTED_POSITIVE|ADOPTED_NEGATIVE|IGNORED",
"step_index":0,"evidence":"observable executed action"}],
"event_type":"...","evidence_steps":[0],"support_level":"observed|hypothesis|none",
"observed_operation":"...","proposed_operation":"...","trigger":"...",
"stop_condition":"...","extracted_pattern":"...","output_intent":"CREATE|PATCH|NONE",
"none_reason":null,"patch_target_id":null,"branch":"general|task_level|action_level"}.
Use ONLY activated_skill_ids for attribution; candidate retrieval alone is not activation or adoption.
Each attributed ID once. No hypothetical counterfactual claims. All step indices are zero based.
```

## MUTATE

```text
Convert the approved source analysis into ONE reusable procedural skill or a local patch.
Only source observations support the content. No fixed source answer, option letter, figure number or patient identity.
Trigger must specify applicability. core_action must specify observable checks, appropriate tool actions, failure/unknown
handling and when to stop; never require access to the current task's unknown reference answer.
Return JSON {"operation":"CREATE|PATCH|NONE","patch_target_id":null,"patch_section":null,"patch_content":null,
"content":{"name":"...","description":"...","applicable_conditions":"...","branch":"general|task_level|action_level",
"tool_name":null,"task_category":"provided category","required_tools":[],"risk_level":"low|medium|high","core_action":"..."}}.
For PATCH only return patch_target_id, patch_section (one content field), patch_content and operation;
do not replace unrelated sections. Scope fields branch, task_category and tool_name cannot change.
NONE may omit all other fields. Registered tools only. No invented measurements or blanket disease exclusion.

R54: Include explicit question-type/object requirements, triggering evidence,
exclusions, required tool capabilities and stopping/unknown conditions in applicable_conditions/core_action.
Preserve the original nine-field content schema. Do not add fields or thresholds without source support.
If supplied reviewer feedback, perform ONE targeted repair: remove unsupported details or narrow scope.
Do not add evidence, change CREATE to PATCH or change an existing PATCH target during repair.
```

## REVIEW

```text
Review a candidate against the actual source trajectory, source image, existing nearest skills and tool menu.
Reject unsupported clinical specifics, rules requiring unknown current labels, copied source answers, vague reminders,
unsafe generalization or incompatible tool capabilities. A binary label does not verify all findings in a model explanation.
Return JSON {"quality":true/false,"reason":"specific source evidence or failure","duplicate_of":null or exact existing ID}.
Duplicate means same reusable operation within the same branch/scope; different conditions may require a local PATCH.
Do not approve merely because JSON is valid. You are a same-model reviewer, not an independent clinician.

R54: Check each trigger and procedural operation against the cited source steps.
Assess separately whether execution occurred and whether final correctness actually supports the operation.
An unexecuted repair is a hypothesis, not an approved skill. Reject invented thresholds, inferred findings,
and treating tool agreement as truth. Allow a narrow supported operation without requiring a broad maxim.
```

## MERGE

```text
Consider two same-scope procedural skills. Merge ONLY if preconditions and actions are compatible.
Preserve conditional exceptions, unknown handling and provenance; do not combine incompatible advice.
Return JSON {"merge":false,"reason":"..."} or {"merge":true,"content":{...complete content schema unchanged...},"reason":"..."}.
No new medical claim beyond the two skills. This is repository maintenance, not access to new patient labels.
```

## PRESCREEN

```text
Select candidate procedural skills compatible with the CURRENT question/options.
Check question type, target object, exclusions and registered capabilities using applicable_conditions.
A future runtime condition (e.g. two tools disagree) may remain pending; do not assert it already happened.
Reject object-specific skills on unrelated questions. Similarity alone is insufficient. Returning no IDs is valid.
Return JSON {"ids":[...],"decisions":[{"id":"...","keep":true,"reason":"..."}]}.
IDs must come from supplied candidates. This is candidate selection, NOT activation.
```

## ACTIVATE

```text
Decide which candidate skill, if any, is applicable NOW using current question and REAL
observations. You have no current label. A precondition requiring tool disagreement is false until
contradictory observations on the SAME finding actually exist. No observations means no tool-conflict proof.
Check object, question type, trigger, exclusions and tool capabilities. Allow zero active skills.
Select at most ONE skill. Do not activate merely to raise hit rate. Do not infer patient findings from skills.
Return JSON {"ids":[...],"decisions":[{"id":"...","applicable":true,
"evidence_observation_indices":[0],"reason":"explicit current evidence or question-only precondition"}]}.
Selected IDs must be candidates. Evidence indices are zero-based indices in supplied observations;
question-only preconditions may use []. All selected IDs need an applicable decision with a reason.
```
