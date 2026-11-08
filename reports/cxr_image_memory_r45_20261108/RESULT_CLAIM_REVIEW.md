# R45 M43-IM result-to-claim evaluation

- experiment: `m43_image_memory_r45_20261108`
- review_date: `2026-11-08`
- intended_claim: Adding sequential exact-image memory improves complete-denominator answer accuracy over the fixed historical M43 baseline on CheXbench618.
- claim_supported: **no**
- confidence: **high** for the fixed-run numerical verdict; causal efficacy, generalization, and equivalence are not established.
- review_completed: true
- required_numeric_and_scope_review_completed: true
- review_independence: **same-family**
- acceptance_status: **provisional**
- requested_reviewer_route: Codex native; `gpt-6-astra`, `ultra`, as recorded in `reviewer_route.json`
- actual_reviewer_model: **null / unknown**; the requested route is not independent evidence of the model that actually performed this review.
- integrity_status: **unavailable**
- integrity_note: **provisional — no integrity audit run**; root `EXPERIMENT_AUDIT.json` is absent. This absence does not itself block publication.
- evidence_precheck: 7 values found; presence-only evidence, not semantic approval.
- routing_action: Record and publish the negative descriptive result within the completed authorized scope. No pivot, new experiment, resampling, full re-score, or re-export is requested or authorized by this review.

The intended accuracy-improvement claim is not supported. M43-IM achieved **465/618**, compared with **466/618** for fixed historical M43: six corrections, seven harms, net minus one. The primary equal-subset macro accuracy also decreased. Positive changes in two subsets do not reverse the full-cohort result. This is evidence of no observed gain in this particular completed comparison, not proof that memory inherently reduces accuracy or cannot help under a different controlled design.

## Evidence actually examined

I read repository `AGENTS.md`; the full current PLAN; the PROTOCOL fields and frozen order; `CODE_SOURCE_REVIEW.md`; recovery-design review 002 and implementation review 003; `results/summary.json`; all 618 existing records in `results/per_question.json`; the deterministic precheck and reviewer route. I inspected primary private evidence under `D:/MedRAX_Experiment_Artifacts/image_memory_r45_20261108`, including the frozen baseline/input/order object, generation prediction/context membership, all actual main-request/response/receipt sets, tool-selection payloads, the failed question's actual responses and selections, recovery receipts, and raw job exits. I also inspected the corresponding public evidence, health assessment, actual conflict responses, selected other changed responses and memory context, and the scorer's existing bootstrap/cluster definitions.

The numerical cross-check aggregated the already recorded per-question correctness flags and compared preserved prediction fields. It did **not** rerun the scorer, change an answer, reinterpret a medical image, use reasoning text to guess a final option, run inference, retry a tool, or perform an integrity audit. I did not run bootstrap resampling again; the interval values below are the completed scorer's reported values, with their implementation read for interpretation. The final README, TABLES, ERROR_ANALYSIS, and REPRODUCTION files were not yet present when this review was completed, so this review does not certify those later-authored documents or remote publication.

## What the results support

### 1. A complete-denominator negative result for this fixed comparison

| Cohort | Questions | Historical M43 correct | M43-IM correct | Corrections | Harms | Net |
|---|---:|---:|---:|---:|---:|---:|
| Full CheXbench | 618 | 466 | 465 | 6 | 7 | -1 |
| Rad-Restruct | 115 | 73 | 74 | 1 | 0 | +1 |
| SLAKE | 123 | 117 | 113 | 1 | 5 | -4 |
| OpenI | 380 | 276 | 278 | 4 | 2 | +2 |
| First/single, reused | 488 | 363 | 363 | 0 | 0 | 0 |
| Repeated-image, regenerated | 130 | 103 | 102 | 6 | 7 | -1 |

The 618 per-question records have unique IDs, with exactly 466 before-correct and 465 after-correct flags. All 488 reused prediction answer/reason/status triples match their frozen M43 records; their adapted records are identical between arms. Thus the unchanged 488/618 portion is an explicit reuse policy, not an independent demonstration of memory robustness. All 130 regenerated positions have nonempty included-memory lists.

Micro accuracy changes from **75.4045307% to 75.2427184%**, a **-0.1618123 percentage-point** difference. Equal-weight macro across the three subsets changes from **77.0772637% to 76.4585465%**, a **-0.6187172 percentage-point** difference. The existing paired cluster-bootstrap 95% intervals are **[-1.288245, +0.980392] pp** for micro and **[-2.067865, +0.784061] pp** for macro. The source uses 10,000 draws, seed 20261105, and clusters connected through image identities and available official patient/study identities. Both intervals include zero. They do not establish either a positive effect or a systematic degradation, and they do not establish equivalence. They also do not remove historical-baseline or selection/exposure confounds.

The frozen order directly contains **488 exact-image groups**, including **five cross-subset groups comprising ten questions**. Cross-subset context is therefore real and must be disclosed. These groups represent image identity under the stated grouping rule, not demonstrated independent patients.

### 2. The technical missing answer remains part of the result

`chexbench_slake_0046` is one of the seven harms. Its historical answer was correct; its new answer and reason are explicitly null with `missing_tool_unhealthy_stop` and `technical_failure: true`. The archived prefix contains exactly **two main calls and two logical tool attempts**. The expert returns healthy evidence; the classifier selection fails with `backend_exit_-11`. The second and final main response requests the classifier; it is not a final answer. There is no subsequent main call for that question.

The observed native-worker SIGSEGV symptom is established; its root cause is unknown. The resize warning is not causal proof. The healthy expert response must not be promoted to the main answer, and the historical answer must not fill the technical null. The existing zero credit on the full 618 denominator is appropriate to the declared result.

Later same-image contexts for `_0049`, `_0072`, and `_0074` contain the technical status and prior processed record while excluding the failed classifier payload. This means the realized run includes potential downstream consequences of the interruption and preserved healthy evidence. Their counterfactual outcomes without the failure are unknown.

Removing the technical harm from the change tally leaves **six corrections and six other harms, arithmetic net zero**. This is only a post hoc decomposition. It is not an alternate favorable main result, a repaired 466/618 result, or proof that the technical failure caused the entire difference. The true counterfactual without the crash was never observed.

### 3. Two explicit option-label/text conflicts are real answer failures

The actual final reply for `chexbench_rad_restruct_0218` is **`B. no`**, while the current options are A=no, B=yes. The actual final reply for `_0231` is **`B. yes`**, while the current options are A=yes, B=no. The existing reference-free adapter rejects both with `choice: null` and `choice_domain_invalid: true`. Both historical answers were already wrong, so these are two new domain-conflict outputs, not two additional correct-to-wrong harms.

Neither the option letter nor the reason can be chosen after seeing the reference to rescue an answer. Both responses are syntactically valid JSON, illustrating why JSON validity is not answer correctness. The sampled rationale for SLAKE0054 explicitly refers to prior assessments, but that alone does not identify the causal contribution of memory. Individual error narratives must remain observations or hypotheses, not clinical adjudications or causal proof.

### 4. Complete accounting is supported; universally healthy execution is not

The primary private generation archive contains **203 each** of `request.json`, `started.json`, `response.json`, and `result.json`, across 203 actual call directories. All 203 receipts state response received without an error; their request IDs are unique. All returned service model fields are `qwen3.7-plus`. All inspected actual request parameter sets preserve temperature 0.2, top_p 0.95, max_tokens 2048, thinking disabled, and non-streamed calls. This service alias does not independently attest an immutable underlying model build.

There are 618 prediction records and 618 context records with frozen-cohort membership. There are **72 logical tool attempts**, **71 healthy** under the existing nested-error predicate and **one failed**, with **zero tool-cache hits**. The public export has matching counts of these principal records. The sum of existing local request settlements is **2.197356 CNY**; this is a usage-based local proxy, not a provider invoice or a complete infrastructure bill. The resource report retains **one unknown episode duration**. Request duration measurements are present; the known episode subtotal cannot be described as a fully measured episode total. The reported interruption-inclusive wall time is 2286.981658 seconds.

The eight separate pre-run health probes involve zero main-model calls. Their authoritative assessment records **seven healthy tools and one expected DICOM-on-PNG refusal**. Eight outer-completed envelopes are not eight healthy probes. These probes are separate from the 72 main-run tool selections and should not be silently conflated with them.

Original generation exit is **1**; the resumed frozen child also exits **1** at `ValueError: unhealthy_tool_selection`. The recovery wrapper exits **0**, and the separate effective generation marker is **0**. The completion mode is explicitly `independent_known_failure_finalization`, with `generation_complete_with_known_technical_missing`. Thus this is complete accounting with a known technical missing answer, not successful all-healthy completion of the original runner or a repaired classifier. Public job-log and exit artifacts are sanitized JSON string wrappers, so they should not be described as byte-identical raw text files; private original text remains the raw source.

### 5. A further archived request-image defect must be disclosed

The outgoing-content inspection identified an invalid archived request-image blob. I independently confirmed that the **209,945-byte** file `evidence/invalid_request_image_bytes/400cb33af212e5d66ab9270d435ce3c5f535c93bb074c8e0008627be5229d98e.bin` cannot be decoded by Pillow. Public request records for `chexbench_openi_0045` calls **2 and 3** reference this blob in the original-image content slot; call 1 references the original image. Call 3 also references a separate derived overlay. The API returns recorded responses, including a final answer in call 3.

This question is correct in both arms, so its observed correctness difference is zero. That does not establish that the malformed archived input had no effect on the episode. The corruption source and provider-side handling are unknown, and this review did not inspect the provider's actual image decoding. The defect does not justify retroactive answer repair, record deletion, or a paid repeat. Preserve and disclose it. The publication must not claim that every archived actual request image is valid or that every request is independently verified to have transmitted the intended original pixels. Valid source images and valid derived overlays do not establish that stronger statement.

## What the results do not support

- Improved complete-denominator answer accuracy over M43: both primary macro and micro point estimates decrease.
- A causal memory benefit or harm, including attributing any particular correction, harm, or label conflict solely to memory. There is no contemporaneous regenerated no-memory arm, and time, sampling, service behavior, and GPU binding differ from the historical comparison.
- Official independent-question benchmark performance, an unseen test evaluation, independent-patient generalization, clinical reliability, or SOTA. The benchmark has been exposed during development, and earlier same-image model answers and tools are supplied to later questions, including across subsets.
- Independent new SLAKE114 or VQA116 results. The completed new generation belongs to the 130 repeated-image positions of this CheXbench618 extension.
- Equivalence, proof of no useful effect, or proof of a systematic degradation. This single realized comparison and its reported intervals do not support those stronger statistical claims.
- A successful answer recovery, all-healthy execution, a known SIGSEGV root cause, all-valid request-image bytes, or assurance that every archived image was decoded by the provider as intended.

## Missing evidence and suggested claim revision

The missing evidence concerns stronger future claims, not whether this negative result can be published: a matched contemporaneous no-memory control; independent stochastic replications; an untouched evaluation cohort with appropriate image/patient separation; interventions that distinguish prior answers from tool evidence and option-letter transfer; and established causes or provider-side consequences of the observed technical/input faults. No retrospective cleaning of this completed run can supply those counterfactuals.

Suggested revised claim:

> In one sequential exact-image-memory extension on the exposed CheXbench618 development cohort, reusing 488 first/single-question historical M43 outputs and regenerating 130 repeated-image questions produced 465/618 correct versus fixed historical M43's 466/618. There were six corrections and seven harms, including one explicit technical-null answer; equal-subset macro accuracy decreased from 77.0773% to 76.4585%. This completed comparison showed no observed accuracy gain. Historical-baseline and sampling/runtime confounds, cross-subset image reuse, and the disclosed technical and request-image defects prevent causal memory or independent-test claims.

## Future hypotheses only — not executed or authorized here

1. **Memory versus regeneration:** A preregistered contemporaneous memory/no-memory comparison on an untouched, fixed-order cohort, with matched infrastructure and stochastic replications, could test whether memory improves accuracy beyond rerun variability. Preserve full denominators and technical failures in both arms.
2. **Context composition and answer binding:** A fixed comparison of tool-only memory, text-normalized prior answers, and the current full record could test whether fallible prior answers or transferred option labels contribute to domain conflicts and contradictory assessments. The two observed conflicts motivate this hypothesis but do not prove it.
3. **Input and backend reliability:** An isolated reproduction using the preserved malformed bytes and the failed classifier prefix could investigate image preservation and backend-failure mechanisms before any future benchmark run. Any reliability repair would define a new future condition, not repair this run's score.

These are at most three proposed research directions. None is required to publish the completed negative result; none should launch from this review.

## Publication disposition

**No unresolved scientific-claim blocker to honest publication of this completed negative result was found in the reviewed evidence.** The publication must retain the full denominator, original/effective exit distinction, explicit technical null, proxy-cost qualification, unknown duration, cross-subset/historical/exposure limits, and malformed archived request-image limitation. The current PROTOCOL's generic `score_gate` phrase about generation exit 0 should be read and explained together with its later `operational_recovery` amendment; it must not be used to claim native runner success.

The lack of a root integrity audit and same-family reviewer status keep the review provisional; neither requires manufacturing an audit or repeating tests solely to publish. Privacy/credentials, source attribution, outgoing allowlist, final narrative consistency, and confirmed GitHub push are the publisher's separate delivery responsibilities. This response is a numerical and scientific-scope review, not a legal/image-privacy review, clinical image adjudication, or certification that publication has already succeeded.
