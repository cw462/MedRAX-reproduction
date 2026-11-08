# 共同适配器的实际独立审查

同家族provisional，requestedgpt-6-astra xhigh，实际身份unknown。第1轮6/notready，第2轮8/ready；仅允许当前适配器/归档准备进入零付费分析。评分代码与完整结果另由[结果判定](CLAIMS_FROM_RESULTS.md)检查。以下保留原文，工作区绝对前缀如有则转为仓库相对。


---

Score: 6/10
Verdict: not ready

Run: run_20261108_6f8dd07d, round 1. Scope: readiness of the author-metric/common-adapter protocol for zero-paid offline comparison, not publication quality, paid inference, clinical benefit, or SOTA. Requested reviewer route: native Codex, gpt-6-astra, xhigh, host-default; actual underlying model identity is unknown. Review independence: same-family. Acceptance status: provisional. Review completed within this scope.

The source attribution and intended comparison are sound. One concrete unfinished-control-flow error still blocks aligned score generation. The first completed inventory establishes archive availability, but its extraction counts also need refreshing after the already applied joint-question correction.

1. Remaining blocker: an earlier explicit answer in a reply is credited even when that same reply ends with an outstanding JSON tool plan.

   Actual counterexample: `reports/cxr_vqa_extension/results/chexbench/calls/X/chexbench_openi_0081.json`, ordinal 1. The reply starts with `{"answer":"A. left indwelling catheter",...}`, then revisits that answer and ends with `Actually, let me use region_parse to confirm anatomy and check for any linear densities.` followed by a complete outer `{"calls":[{"tool":"region_parse","args":{"regions":["left lung","right lung"]}}],"reason":...}` object. This is the repository's real action interface: the archived request offers final answer/reason JSON or a calls plan, and `experiments/run_cxr_vqa_toolsets.py` in `episode` parses that branch before executing tools. The published prediction is `missing_invalid_tool_plan`; no subsequent request executes the requested action and returns a final answer.

   Nevertheless, the currently inspected `terminal` in `experiments/analyze_cxr_author_alignment.py` only excludes native `message.tool_calls`, and the embedded-object branch of `extract` in `experiments/cxr_author_alignment.py` accumulates answer fields while ignoring outer calls objects. I reproduced `received_terminal_text`, followed by `Extracted(answer='A. left indwelling catheter', mechanism='embedded_json_answer', ...)` for this archive. Thus an unfinished plan becomes a completed model answer. Its correctness is immaterial, and I did not inspect its reference.

   Minimum correction: recognize the existing outer JSON calls-plan interface as control flow, as well as native tool calls. A mixed reply with an answer and an outstanding explicit tool plan must remain nonfinal/ambiguous; do not infer completion from prose or select the earlier answer. Inspect outer parsed structures only, preserving the current protection against reason/examples. Add one focused fixture derived from this actual reply and disclose the resulting nonfinal category. Do not reject all `missing_invalid_tool_plan` rows: `slake_12416` in the original M archive is a counterexample where the raw reply contains explanatory prose and an explicit answer but no tool request, so format recovery is appropriate there. No new model/tool requests are needed.

2. Found and resolved during this review: direct question-ID maps were incorrectly discarded.

   Initial `object_answers` handled `answers[qid].answer` but not `root[qid].answer`. Actual D-Q archive `reports/cxr_vqa_extension/results/stage3/slake/calls/D-Q/q-54dce64c51c4c84c1bb70d80.json` contains a fenced root map with `slake_11982.answer = Yes` and `slake_11986.answer = No`. Initial extraction returned no_explicit_string_answer. Comparable direct maps occur in the inspected CheXbench and VQA-RAD D-Q archives. The first inventory's D-Q missing-string counts were 70/114 on SLAKE, 101/204 on CheXbench and 26/94 on VQA-RAD; these counts alone do not establish that every one has the identical cause.

   The executor corrected this while review was active. I re-read the updated code and fixtures and reran extraction on the actual SLAKE group: the two question IDs now yield their own explicit Yes/No strings. Retaining Object.pairs preserves duplicate qid and answers keys for conflict detection; the code does not recursively search arbitrary reason fields. This correction satisfies the intended common adapter. Preserve the initial inventory as preparation history and regenerate extraction counts after the remaining control-flow fix. No accuracy/reference table should use the stale preparation counts.

What is correct and supported:

- The pinned CheXagent BaseLM extracts the first parenthesized uppercase letter and otherwise randomly selects an option. The proposed separately labeled sensitivity on extracted answer text is accurately described as an adaptation, not exact paper reproduction. I inspected the updated missing-answer guard: absent/empty explicit answers now return None even with an RNG, preventing random credit for genuine missing/technical outcomes.
- Pinned M4CXR compute_vqa_metrics removes the four specified special tokens, strips, removes periods and lowercases the full answer before exact match. Its recall is reference-token-set overlap using wordpunct tokenization; the local regular expression implements that tokenization. No invented true-to-yes mapping is present. Full plain-text replies are retained for this metric. BLEU-1 exists in the author code, but omission here is disclosed by selecting the MedRAX-described EM/recall metrics, rather than claiming full reproduction of every M4CXR metric.
- The pinned MedRAX CheXbench GPT checker uses A/B prefixes, whereas ChestAgentBench has a separate final-letter call. The paper describes choice extraction/retries and SLAKE114 EM/recall. These are accurately distinguished. CXRAgent describes accuracy for the other tasks, and the exact benchmark parser remains explicitly unknown.
- Additional fields, missing reason, fences and the old 300-character limit are not correctness gates in the proposed adapter. Ordinary explicit answer conflicts remain unchosen; nested reason examples are not mined for an answer. Choice mapping uses supplied options rather than a medical inference or reference.
- The registry has 45 dataset-arm combinations: 41 full cohorts and four separately labeled partial cohorts. The first ARCHIVE_INVENTORY.json reports zero unresolved archive paths. Code enforces identical canonical question-ID sets for full arms. The inspected source paths use frozen published archives; sampled M43 rows resolve through the declared fixed M-C41/M-S41 chains, not the changed live SLAKE directory. Numeric maximum ordinal chooses the last actual request, including archives stored in lexicographic order.
- Native tool plans, absent terminal response text, declared transport/tool stops and graph limits are excluded by the terminal reader. The remaining blocker concerns the separate JSON calls-plan interface demonstrated above.

Supported limits and gate:

This is an already exposed development benchmark, and common-adapter rescoring cannot establish unseen generalization, an isolated Skill/memory effect, clinical benefit, or official SOTA. SLAKE's count of 114 does not prove paper-identical IDs. VQA-RAD116 M4CXR-style scoring is a declared extension, not a MedRAX VQA-RAD paper result. Partial joint cohorts must remain separate or use explicitly matched subset comparisons. Previous R42/R43 frozen-contract records remain completed records and must not be overwritten.

I read the protocol, plan, adapter, archive reader, seven test methods, current inventory, R43 contract and claims report, the specified pinned author code, relevant actual paper passages, and selected real raw request/reply archives. I made no API/server requests, opened no benchmark reference files, generated no target accuracy, and did not launch another preparation process. The executor's reported seven passing tests are not an independent reviewer test run; I used focused read-only reproductions of the actual extraction counterexamples instead.

After the single control-flow correction and a refreshed reference-free inventory, the next review can approve only the zero-paid offline comparison. The score-generation/reporting implementation is not present in the reviewed files and is not pre-certified by this review.

Memory update

- Confirmed and fixed: direct root question-ID answer maps were systematically missed, especially in D-Q; current code and actual SLAKE sample now handle them without reading other questions or reason examples.
- Unresolved: original_X chexbench_openi_0081 is unfinished JSON tool control flow but currently receives its earlier answer. Recognize outer calls plans while retaining legitimate prose-plus-answer recoveries such as original_M slake_12416.
- Resolved small guard: missing explicit answers cannot receive seeded legacy random-fallback credit.
- Pending after fixes: refresh the reference-free inventory; preserve the old preparation and all historical predictions/scores. No new paid experiment is requested.


---

Score: 8/10
Verdict: ready

Run: run_20261108_6f8dd07d, round 2 continuation. Scope: the current author-metric/common-adapter protocol and reference-free archive preparation for a zero-paid offline comparison. This does not certify future score-generation/reporting code, new inference, paper readiness, clinical benefit, or SOTA. Requested reviewer route: native Codex, gpt-6-astra, xhigh, host-default; actual underlying model identity is unknown. Review independence: same-family. Acceptance status: provisional. Review completed within this scope.

The remaining round-1 blocker is resolved. I re-read the current adapter, tests, revision-2 protocol and refreshed inventory, and independently reran only the requested read-only extraction checks against real archived replies. No remaining concrete blocker was found in this narrow scope.

Verified corrections:

1. Outstanding JSON tool plans no longer supply a final answer. In `experiments/cxr_author_alignment.py`, `is_tool_plan` recognizes nonempty outer calls/actions/tool_calls. Both the whole-JSON branch and embedded-outer-object branch reject these as `structured_tool_plan_not_final`. The latter checks this before returning collected answer candidates. It does not inspect nested reason text to determine control flow.

   Actual regression case: `reports/cxr_vqa_extension/results/chexbench/calls/X/chexbench_openi_0081.json`, ordinal 1, still contains the tentative answer followed by the explicit region_parse calls plan. Current extraction returns answer=None and mechanism=structured_tool_plan_not_final. The earlier A answer is no longer credited. This resolves the specific round-1 defect.

2. Legitimate format recovery remains available. `reports/cxr_vqa_toolsets/results/slake/calls/M/slake_12416.json` has explanatory prose plus the explicit No answer and no outer tool request. Current extraction still returns No with mechanism=embedded_json_answer. The fix therefore does not blanket-reject historical missing_invalid_tool_plan statuses or restore the old exact-JSON correctness gate.

3. Direct question-ID maps remain supported. The actual D-Q archive `reports/cxr_vqa_extension/results/stage3/slake/calls/D-Q/q-54dce64c51c4c84c1bb70d80.json` produces Yes for slake_11982 and No for slake_11986. Current code retains Object.pairs and collects only explicit answer values at the documented root/current-qid or answers/current-qid locations; duplicate qid/answer conflicts remain visible, and arbitrary nested reasons are not traversed.

4. The refreshed inventory is present and covers 45 dataset-arm combinations: 41 full and four separately labeled partial cohorts, with zero unresolved archive paths and zero paid requests. It declares references_read_by_this_program=false. Its mechanism counts reflect the fixes: SLAKE D-Q now has 114 whole_json_answer outcomes, VQA-RAD D-Q has 94, and CheXbench D-Q has 200 whole_json_answer, three embedded_json_answer and one conflicting_explicit_answers outcome. These are extraction counts, not correctness claims. The affected full arms now expose structured_tool_plan_not_final outcomes separately. I confirmed the first protocol and inventory remain present as PROTOCOL.prepare1.json and ARCHIVE_INVENTORY.prepare1.json; current PROTOCOL.json records clarification_revision=2 and the corrections before any aligned score table.

The eight current test methods include the focused mixed-answer/tool-plan regression. I read them and performed the actual-archive checks above; I did not rerun the full suite or preparation. The executor reports eight passing methods. No benchmark reference files, accuracy tables, servers, or paid endpoints were accessed during this continuation.

The source-attribution findings from round 1 still hold: the text metric follows the pinned M4CXR cleaning/EM/word-set recall semantics, the MCQ path is explicitly a common answer adapter, and CheXagent parenthesized-parser/random-fallback sensitivity is separate. Missing explicit answers remain ineligible for seeded random credit. JSON compliance stays separate from answer correctness. These distinctions support an honest uniform offline comparison under the stated adapter, not a claim of untouched universal official-parser reproduction.

The positive verdict applies only to the current adapter/protocol and archive preparation. The eventual scorer must preserve the already specified full denominators, null/ambiguous/nonfinal outcomes, fixed cohort/reuse rules, separate legacy-random contribution, and unchanged historical results. A received_terminal_text archive status establishes receipt; it does not override an extraction result of structured_tool_plan_not_final. Future scoring/reporting code has not been inspected or certified here.

The exposed-development-set limitation, uncertain paper-identical SLAKE IDs, unknown CXRAgent exact parser, and declared VQA-RAD116 extension remain appropriately disclosed. They limit the interpretation of subsequent results; they do not block the zero-paid offline comparison. No further paid experiments, additional test framework, or expanded audit is requested by this review.

Memory update

- Resolved: original_X chexbench_openi_0081 now remains nonfinal because of its outstanding outer JSON tool plan; the earlier answer is not credited.
- Verified preserved: original_M slake_12416 still recovers its explicit No without using its reason, and actual direct-qid D-Q replies resolve to their own question IDs.
- Resolved: refreshed reference-free inventory incorporates the corrections; first preparation artifacts remain available, with 45 arms, 41 full, four partial and zero unresolved archives.
- Remaining blockers in reviewed scope: none.
- Boundary: ready/provisional permits the zero-paid offline comparison using the reviewed adapter; it does not pre-approve unseen scorer/report code or any medical, generalization, or SOTA claim. Round-1 score 6/not ready remains a valid historical review record and is not overwritten.
