# EvolveR 的 426 张经验卡

按保存的写入顺序排列。每张卡链接到来源题的 D/EvolveR 记录，其中包含该题的写卡请求和回复。最终库中 422 张活跃、4 张已剪枝。
保存的最终库含每张卡的向量。此页展示卡片 ID、来源、最终状态和出站副本中的全文。

[返回报告](../../README.md) · [最终库 JSON](final_repo.json) · [窗口状态](windows/) · [嵌入调用回执](embedding_receipts.json)

## exp_36588f01f6be5c22bf234646

来源题 [chexbench_rad_restruct_0127](../../cases/rad_restruct/chexbench_rad_restruct_0127.json) · 活跃

```text
Trigger: You are answering a binary thorax-disease question and are about to finalize “yes” because a grounded report lists findings, even though a direct chest X-ray QA tool answered “No” and the listed findings are incidental or chronic descriptors such as hiatal hernia, calcified granuloma, or aortic elongation.

Verification action: Before finalizing, check each grounded finding against the exact question’s criterion: is it an active disease in the thorax as the question intends, not merely an incidental or chronic finding? If no finding clearly satisfies that criterion, keep the direct “No” answer rather than overturning it with the grounded report. Do not treat a verifier’s “CORRECT” as resolving the conflict when it merely restates the proposed “yes” and the same unverified findings. If choosing “yes,” state which listed finding is the qualifying disease and why. Then map the supported answer text to the displayed option and confirm the letter and text agree.

Lesson from the case: the terminal answer was B. yes, but the direct chest_xray_expert observation had said “No,” and the released reference was A. no. The grounded report’s hiatal hernia, calcified granuloma, and aortic elongation were not sufficient to convert the direct disease-presence answer to “yes,” and the verifier’s approval did not repair that semantic conflict.
```

## exp_d32d5b09b1115a75b0f6199c

来源题 [chexbench_rad_restruct_0123](../../cases/rad_restruct/chexbench_rad_restruct_0123.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about lung abnormality after tool observations report “No” or “No significant findings.”

Action: Before emitting, state the supported answer text (“no”), look up the displayed option whose text exactly matches it, and verify the letter–text pair is correct—here “B. no,” not “A. yes.” Also confirm each cited observation addressed the same lung-abnormality question and that no tool result conflicts; keep the reason limited to what the tools actually reported.
```

## exp_8fbf5da7ecb44a7d3db6d1bd

来源题 [chexbench_rad_restruct_0124](../../cases/rad_restruct/chexbench_rad_restruct_0124.json) · 活跃

```text
Trigger: When finalizing a yes/no imaging answer about disease in a named anatomical structure after receiving tool outputs, especially when one output is structure-specific and another is only a generic report.

Observable verification action: Before selecting the option, confirm that at least one observation addresses the same object and attribute as the question. In this case, chest_xray_expert was asked directly about tracheal disease and returned “No”; maira2_grounded_report returned “No significant findings,” which is supportive but not trachea-specific because it does not name the trachea. Check for any conflicting positive finding. Then map the supported answer text back to the displayed options and verify that the letter and text agree: “B. no” matches option B = “no” and the reference B/no. If only a generic “No significant findings” report were available, do not treat that alone as definitive proof about the trachea; require a structure-specific answer or state uncertainty.
```

## exp_098093e4cb71206ae3d880d7

来源题 [chexbench_rad_restruct_0125](../../cases/rad_restruct/chexbench_rad_restruct_0125.json) · 活跃

```text
Trigger: When a no/yes multiple-choice question asks whether a named anatomic system is abnormal, and a radiology report lists abnormalities only outside that system, do not convert the report’s silence about the target system into a negative answer.

Verification action: Find an observed tool result that explicitly addresses the same system and attribute—here, chest_xray_expert explicitly answered “No” to skeletal abnormality. Use that direct statement as the decisive support; treat the MAIRA-2 findings (right paratracheal soft tissue density, apical pleural thickening) as non-skeletal and only corroborative. Then map the supported text back to the displayed option and check letter and text agree: “no” must map to “A. no,” not “B. yes.” If no tool result directly evaluates the target system, do not infer “no” from omission; run a targeted query or flag insufficient evidence. A verifier’s “CORRECT/SAFE” and a correct final grade are corroboration only, not proof that the evidence-to-option mapping was sound.
```

## exp_abc576c64755f47819f89d80

来源题 [chexbench_rad_restruct_0126](../../cases/rad_restruct/chexbench_rad_restruct_0126.json) · 活跃

```text
Trigger: Before finalizing a multiple-choice “no abnormality” answer about a named anatomical structure when the evidence includes a structure-specific QA result and a general radiology report.

Verification action: Identify the observation that explicitly names the same structure and attribute as the question; use that answer text as the support, map it back to the displayed option, and check that the option letter and text agree. When writing the rationale, cite the general report only if its text explicitly mentions that structure. If the report omits the structure, treat it as non-confirming rather than as a second confirmation.

In this case, `chest_xray_expert` answered “No” to the trachea question, so option B “no” is supported and the letter/text mapping is correct. But `maira2_grounded_report` listed lungs, heart, mediastinum, pleura, and skeleton without mentioning the trachea, so the final rationale’s claim that “both” tools indicate no tracheal abnormality overstated the evidence. Omission is not negative evidence.
```

## exp_5466e9b5f79085bfc435e942

来源题 [chexbench_rad_restruct_0128](../../cases/rad_restruct/chexbench_rad_restruct_0128.json) · 活跃

```text
Trigger: When finalizing a multiple-choice answer from imaging-tool observations, especially a binary “yes/no” option question.

Verification action: Extract the supported conclusion from the tool observation, map its exact text to the currently displayed option map, and emit the option letter and text together; then check that the emitted letter and text agree. Also confirm the tool result addressed the same image/object and same attribute as the question, and that no other observed tool result conflicts. In the supplied case, chest_xray_expert answered “No” to a cardiovascular-abnormality question, maira2_grounded_report reported “No significant findings” for the same image, and the displayed option A was “no,” so verifying “A. no” against the option map was the reusable step. The lesson is to verify final option mapping and evidence alignment explicitly; a correct reference match alone does not prove that this check occurred.
```

## exp_c6cde9b7cf031eb43e2b03a3

来源题 [chexbench_rad_restruct_0129](../../cases/rad_restruct/chexbench_rad_restruct_0129.json) · 活跃

```text
**Trigger:** You are about to finalize a yes/no multiple-choice answer about an anatomical finding, and your supporting tool query paraphrased the original question into a narrower list of findings (here, “any signs in the pleura?” became “pleural effusion, pneumothorax, or pleural thickening?”).

**Verification action:** Do two observable checks before emitting the choice:

1. **Option-map check:** Re-read the displayed option map and confirm the supported answer *word* matches the option *text*, not just the remembered letter. In this case “no” must map to the option whose text is “no” (B), not to “yes” (A). State the letter and text together and confirm they agree.

2. **Source-scope check:** Reconcile the final rationale against the exact observation text. The expert model explicitly said “no signs of pleural effusion, pneumothorax, or pleural thickening,” but the grounded report only explicitly said “No effusions are noted” and “lung fields are clear.” Saying “both confirm … pneumothorax or thickening” overstates the grounded report; the expert’s explicit negative is the load-bearing evidence. If a narrowed query does not cover the full attribute named in the question, either broaden the query or limit the conclusion to the findings actually observed.

A correct final grade here does not show that either check was performed; the reusable lesson is to perform both at finalization: letter/text agreement plus attribution of each claim to the tool that actually made it.
```

## exp_3dda5104f26950408a173f4b

来源题 [chexbench_rad_restruct_0130](../../cases/rad_restruct/chexbench_rad_restruct_0130.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether disease is present in a specified anatomical region, especially when tool results include normal findings or incidental findings outside that region.

Observable verification action: Before emitting the answer, restate the supported proposition, locate its exact text in the displayed option map, and confirm the emitted letter and text match. Then check each tool finding by object and location: only a disease/abnormality in the queried region can support “yes”; outside-region hardware or normal findings cannot. In this case, “No” from chest_xray_expert plus “Lungs are clear,” “Heart is not enlarged,” and “No acute osseous abnormality” support “no,” while “lower cervical fusion hardware” is outside the thorax and does not support “yes.” Confirm the final choice is B. no only after this letter/text and region/attribute check.
```

## exp_7c669392e2ecb951d4dd4134

来源题 [chexbench_rad_restruct_0131](../../cases/rad_restruct/chexbench_rad_restruct_0131.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether a named finding is present (for example, “anything abnormal in the pleura?”), especially after tool evidence reports absence of that finding.

Observable verification action: Before emitting the answer, re-read the displayed option map and check that the supported answer text maps to the chosen letter and that the letter and text agree. Also verify that the tool observations addressed the same anatomic object and attribute as the question and that no result conflicted. In this case, chest_xray_expert explicitly said there was no pleural effusion, pneumothorax, or thickening, and maira2_grounded_report said “No pleural abnormalities are seen”; both addressed the pleura, agreed on absence, and the supported text “no” maps to option B. The terminal answer “B. no” therefore has matching letter and text. This is an option-mapping check, not a substantive reconsideration: if the evidence had instead supported “yes,” the correct repair would be to change the conclusion, not merely relabel the option.
```

## exp_6a54566aec58dcabc05d3169

来源题 [chexbench_rad_restruct_0132](../../cases/rad_restruct/chexbench_rad_restruct_0132.json) · 活跃

```text
Trigger: When finalizing a multiple-choice answer about abnormality in a named anatomical region after consulting imaging/report tools, especially when the final reason cites more than one tool.

Verification action: Before choosing, check each cited tool observation for the same region and attribute as the question. In this case, CheXagent explicitly said the abdomen appears normal, while MAIRA-2 only gave a generic “No significant findings,” so MAIRA-2 should not be cited as direct abdominal evidence. Treat the supported answer text as “no,” then map it back to the displayed options: Option A = “no.” Confirm the selected letter and text agree, and emit “A. no.”
```

## exp_cf1f5a8743e38d46605bf8f8

来源题 [chexbench_rad_restruct_0134](../../cases/rad_restruct/chexbench_rad_restruct_0134.json) · 活跃

```text
Trigger: When finalizing a yes/no lung-abnormality answer supported by a generative expert saying “Yes” plus a grounded report that names a focal finding but itself says the finding is unverified/model output, and `verify` returns CORRECT after being given the same proposed answer and evidence.

Verification action: Before emitting “yes,” read each positive tool result’s limitations and check whether any independent observation explicitly confirms the same lung abnormality. Do not count a grounded report marked “Unverified findings; boxes are model outputs, not independent confirmation,” or a verifier that merely echoes the same evidence, as independent confirmation. If only unverified generative outputs support the abnormality, treat “yes” as a hypothesis rather than confirmed evidence and do not write that “both” tools confirm it. In this case, the option map was correct—A=no, B=yes, and “B. yes” matches option B—so the failure was not letter/text mapping; it was a wrong substantive conclusion from unverified positive tool outputs, while the released reference was A=no.
```

## exp_3e0a764c0c943de27b686aa4

来源题 [chexbench_rad_restruct_0133](../../cases/rad_restruct/chexbench_rad_restruct_0133.json) · 活跃

```text
Trigger: You are about to finalize a yes/no multiple-choice answer about whether a named anatomical region is abnormal—for example, “Is there anything abnormal in the pleura?”—after a direct image-QA tool has returned a negative result.

Verification action: Extract the answer word explicitly supported by the tool observation (“no”), then find the displayed option whose text exactly matches that word and state the letter and text together as “B. no.” Check that the letter–text pair is correct, not merely remembered. Confirm the tool observation addressed the same object and attribute as the question—here the chest_xray_expert was asked about pleural abnormality and answered, “No, there is no pleural abnormality visible in the image”—and check that no other tool result conflicts. Keep the final rationale limited to what was actually observed: attribute “no pleural abnormality” to the chest_xray_expert, and do not add “visual inspection shows clear costophrenic angles” or other specific visual findings unless the returned observation supplied them. In this case the supported conclusion was not lost and the option mapping was correct: B. no matches the reference B/no. The reusable lesson is still to verify letter/text agreement and evidence attribution at finalization, because a correct grade alone does not prove either check was performed.
```

## exp_49ed87418a8ce811ee4bf080

来源题 [chexbench_rad_restruct_0140](../../cases/rad_restruct/chexbench_rad_restruct_0140.json) · 活跃

```text
Trigger: When a yes/no "is there disease/abnormality in [named anatomic system]?" item is answered by a single VQA tool with a blanket negative ("No, the [system] structures do not show any abnormalities"), and the pre-answer memory search surfaces historical cases that also answered "no" on other images.

Observable verification action: Before finalizing, look for at least one independent observation that addresses the same object and attribute as the question (e.g., a grounded radiology report or a second VQA model asked the same system-specific question). If any of those report a finding in that system, or if the observations conflict, do not emit the blanket negative — issue a targeted follow-up query or flag the evidence as insufficient. Treat retrieved memory cards as style/priors only: a "no" supporting a different image is not corroboration for the current image. Finally, restate the supported proposition and map it to the displayed option map, checking letter and text agree (A = no, B = yes).

Why this case illustrates the lesson: the terminal answer "A. no" was internally consistent — `chest_xray_expert` was asked "Are there any abnormalities in the skeletal system?" and explicitly answered "No, the skeletal structures do not show any abnormalities," and "no" correctly maps to option A. So this was not an option-mapping error; the letter/text pairing was sound. The error was evidentiary: the single negative VQA response was treated as decisive, and the pre-answer retrieval of similarly "no" historical cases (from `chexbench_rad_restruct_0125` on a different image) reinforced rather than tested it. The released reference labels the case "yes," so the observation itself did not support the final answer. The caution to carry forward is that a lone blanket negative from one tool, especially on a system that is peripheral to that tool's imaging focus, should be corroborated or re-queried before it is finalized; historical memory from other images cannot substitute for that corroboration.
```

## exp_a98c8f90a3dd6b9da42f2f6f

来源题 [chexbench_rad_restruct_0135](../../cases/rad_restruct/chexbench_rad_restruct_0135.json) · 活跃

```text
Trigger: You are about to finalize a yes/no multiple-choice answer about whether an anatomical region (e.g., the pleura) is abnormal, after tool observations return “No” or “No [region] abnormalities,” and the displayed option letters may differ from a prior similar case.

Verification action: Before emitting the choice, state the supported answer text from the observations (e.g., “no”), re-read the entire displayed option map, and write the matching option as a letter–text pair; confirm the letter and text agree—here “A. no,” not an assumed letter from memory. Then reconcile the rationale with the exact observation wording: if one tool said only “No pleural abnormalities are seen,” do not claim it explicitly enumerated effusion, pneumothorax, and thickening; that specific list belongs only to a tool that answered at that scope. If the letter–text match or the source-attribution check fails, correct it before finalizing. A correct final grade alone does not show these checks were performed.
```

## exp_6bd5aa3af16cb6885bc20864

来源题 [chexbench_rad_restruct_0136](../../cases/rad_restruct/chexbench_rad_restruct_0136.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice imaging answer about whether disease is present in a named anatomical structure, especially lymph nodes, after a structure-specific tool query has returned a negative result.

Observable verification action: Before emitting the answer, restate the supported proposition (“no disease in the lymph nodes”). Confirm the tool observation addresses the same object and attribute as the question—here, chest_xray_expert was asked directly about lymph-node disease and returned “No.” Check that no positive finding in the lymph nodes conflicts with that result. Then map the supported answer text “no” back to the displayed option map: A = “no,” B = “yes”; emit A only if its letter and text agree. In this case, the direct “No” supports “A. no,” matching the reference. Do not add an unsupported visual-inspection claim when the direct tool result alone supports the answer.
```

## exp_0f4bddad1acb0db0a09b007f

来源题 [chexbench_rad_restruct_0137](../../cases/rad_restruct/chexbench_rad_restruct_0137.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer about whether a named anatomical system shows abnormal signs, when one tool directly answers a narrowed finding list and another tool returns a general radiology report.

Verification action: Re-read the displayed option map and match the supported answer word to its letter and text (here, “no” must map to “B. no”). Then reconcile the final rationale line by line with the exact tool observations: use the direct structure-specific answer as the load-bearing evidence, and cite the general report only for attributes it explicitly states. Do not say “both” tools confirmed a finding unless both actually did. If the tool query paraphrased the original question into a narrower list, check that the list still covers the requested attribute; if not, broaden the query or limit the conclusion. In this case, chest_xray_expert’s “No” supports B. no; maira2_grounded_report supports normal cardiomediastinal silhouette and pulmonary vasculature, but it does not mention calcification, so claiming both tools confirmed “no calcification” overstates the evidence. The median sternotomy finding is a postsurgical change outside the cardiovascular system and does not support “yes.” A correct reference grade alone does not prove these checks were performed.
```

## exp_d44c5bb4c0d308297b17fe47

来源题 [chexbench_rad_restruct_0138](../../cases/rad_restruct/chexbench_rad_restruct_0138.json) · 活跃

```text
Trigger: When finalizing a binary yes/no multiple-choice answer about disease in a named anatomical region, after a direct regional imaging QA tool has returned an answer and a second report tool has returned only a generic “No significant findings.”

Observable verification action: Before emitting the choice, restate the supported proposition in text (for this case, “no abdominal disease”), find that exact text in the displayed option map, and confirm the selected letter and text agree — here, Option A = “no,” so the candidate is “A. no.” Then audit each cited tool by object and attribute: chest_xray_expert was asked directly about abdominal disease and answered “No”; maira2_grounded_report gave only “No significant findings” without naming the abdomen, so it should not be cited as direct abdominal evidence. If no tool reports a region-specific abnormality, keep “no.” If a generic report names an abnormality or conflicts with the regional tool, do not silently transfer it to the queried region; resolve the object/attribute mismatch explicitly. The correct grade does not validate the final reason’s overstatement — the generic report can be consistent background, not direct proof.
```

## exp_b4c0f2a15399666380aca909

来源题 [chexbench_rad_restruct_0139](../../cases/rad_restruct/chexbench_rad_restruct_0139.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about a named anatomical structure from a focused structure-specific QA result plus a general grounded radiology report, especially when the results are negative.

Verification action: Before emitting the choice, locate the observation that explicitly names the same structure and attribute as the question, and use its answer text as the supported conclusion. Map that supported word to the displayed option map, state the option letter and text together to confirm they agree, and compare both with the released reference if available. Then check the rationale against the exact tool texts: cite the general report as confirmation only if it explicitly names the same structure or attribute; if it only says “No significant findings,” treat it as non-confirming rather than as a second explicit finding for that structure. If an earlier explicit same-attribute answer was dropped or a letter/text mismatch is found, restore the supported conclusion before finalizing. In this case, chest_xray_expert answered “No” to the mediastinum abnormality question, option B was “no,” and the reference was B/no, so the conclusion and letter/text mapping were correct; the final rationale’s “both” slightly overstated the grounded report because that report did not explicitly mention the mediastinum. A correct grade alone does not prove the rationale’s evidence attribution was sound.
```

## exp_06a728b158cceb340fef4a33

来源题 [chexbench_rad_restruct_0141](../../cases/rad_restruct/chexbench_rad_restruct_0141.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer about lung abnormality when tool observations say the lungs are clear or show no abnormality.

Verification action: State the supported answer text (“no”), re-read the displayed option map, and match that text to the option whose text is exactly “no.” Confirm the letter–text pair is correct—here “A. no,” not “B. yes.” Also verify that each cited tool observation explicitly addresses the lungs and does not conflict: in this case, chest_xray_expert said the lungs appear clear, and maira2_grounded_report said “The lungs are clear.” Keep the rationale limited to those explicit reports. Emit the answer only after confirming the option letter and text agree with the supported evidence.
```

## exp_18f90a4cb22b76310eec526c

来源题 [chexbench_rad_restruct_0142](../../cases/rad_restruct/chexbench_rad_restruct_0142.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer about whether a named anatomic system or attribute is abnormal, especially when the tentative answer is “no.”

Verification action: Find a tool observation that explicitly addresses the same system and attribute named in the question, and use that direct statement as the load-bearing evidence. Do not treat a report’s silence or omission about that system as a negative answer; if no tool directly evaluates it, run a targeted query or flag insufficient evidence. Then map the supported answer word back to the displayed option and verify that the option letter and text agree.

In this case, `chest_xray_expert` explicitly answered “No” to skeletal abnormality, and `llava_med_qa` explicitly answered “No, the chest X-ray does not show any signs of skeletal abnormality…”. Both addressed the same target system and attribute. The supported answer word “no” maps to option “A. no,” not “B. yes,” so the terminal choice is supported. A correct final grade alone is not the lesson; the reusable check is: explicit same-target evidence first, then observable letter/text option mapping.
```

## exp_4b160a3122c40c23cadc2932

来源题 [chexbench_rad_restruct_0145](../../cases/rad_restruct/chexbench_rad_restruct_0145.json) · 活跃

```text
**Reusable decision procedure (plain text)**

**Trigger:** You are about to finalize a yes/no multiple-choice answer to a question of the form "Are there any signs in the lung?" (or any "any signs in <region>" question), and your only support is a single free-text grounded report whose statement about that region is a global normal line such as "The lung fields are clear" or "no abnormality."

**Verification action — do these two observable checks before emitting:**

1. **Option-map check.** Say the supported answer word out loud ("no"), look up the displayed option whose text is exactly that word, and emit letter and text together. In this case "no" maps to B, so "B. no" is the correct letter–text pair — the option mapping is not the failure.

2. **Scope check.** Confirm that the tool sentence addresses the same object *and the same attribute* as the question. "The lung fields are clear" is a summary clearance statement; the question asks about "any signs" in the lung. A global normal line enumerates only the negative findings the report chose to state, so it is narrower than "any signs." Before concluding, reconcile that line against any other findings the same report lists, and if the report gives no finding-level coverage of the asked attribute, seek a second observation or another tool, or state the scope limitation explicitly. Also check whether any other tool result conflicts with the "clear" line.

**Diagnosis of this case:** the released reference is A ("yes"), while the terminal answer was B ("no"). The letter–text pair was internally consistent, so this is a **wrong conclusion / evidence-scope error, not an option-mapping error**. The tool result did address the lung attribute ("The lung fields are clear"), but a single global clearance sentence was treated as dispositive for the broad "any signs" question, and the terminal choice used that evidence without reconciling its scope or checking for a conflicting finding.

**Caution (unverified repair):** the observation that a "lungs clear" summary can under-cover an "any signs" question comes from this failed trajectory; the suggested remedy — broader query or a second confirming tool — was not executed here, so it is a caution about the observed failure, not a demonstrated fix.
```

## exp_f8aeef8413b7d5795a027740

来源题 [chexbench_rad_restruct_0143](../../cases/rad_restruct/chexbench_rad_restruct_0143.json) · 活跃

```text
Trigger: You are about to finalize a yes/no multiple-choice answer about whether the pleura has abnormal signs, after a direct chest-xray tool answered a pleural-scope query with “No” and a grounded report returned only a broad “No significant findings.”

Verification action: Before emitting the choice, state the supported answer word from the direct observation (“no”), re-read the displayed option map, and match that word to the option text, writing the letter and text together as “A. no.” Confirm that A is “no” and not “yes.” Also reconcile the rationale with the exact wording of each tool result: the specific pleural negative comes from chest_xray_expert (“No”); maira2_grounded_report supports only the broader “No significant findings,” so do not claim it explicitly enumerated effusion, pneumothorax, or thickening. If the letter-text pair or the attribution does not match the observations, correct it before finalizing. A correct grade alone does not prove this check was performed.
```

## exp_bb69cac9532633030a48ac1f

来源题 [chexbench_rad_restruct_0146](../../cases/rad_restruct/chexbench_rad_restruct_0146.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer about lung abnormality when tool observations report the lungs are clear or show “No significant findings.”

Verification action: State the supported answer text from the observations (“no”), then re-read the entire current option map and select the option whose text exactly matches it. Verify the letter–text pair is correct—here “B. no,” not “A. yes,” and do not carry over a letter such as “A. no” from another option map. Confirm each cited tool addressed the same lung-abnormality question and that no result conflicts: chest_xray_expert said the lungs appear clear, and maira2_grounded_report said “No significant findings.” Keep the rationale limited to those explicit reports. If the letter–text match or source attribution fails, correct it before emitting; a correct final grade alone does not prove the mapping check was performed.
```

## exp_ca3388e4539e653daf524f25

来源题 [chexbench_rad_restruct_0147](../../cases/rad_restruct/chexbench_rad_restruct_0147.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer about whether a named anatomical region is abnormal—e.g., “Is there anything abnormal in the pleura?”—after the direct image-QA tool returns a negative finding for that region.

Verification action: Extract the answer word supported by the observation (“no”), re-read the entire displayed option map, and state the chosen option as a letter–text pair (“B. no”). Confirm that the letter and text agree, and confirm the tool observation addressed the same object and attribute as the question—here, pleural abnormality—with no conflicting result. Keep the final rationale limited to the exact observation, e.g., “chest_xray_expert reported no signs of pleural effusion, pneumothorax, or thickening,” rather than adding unsupported visual details. If the letter–text match or source attribution fails, correct it before finalizing. A correct grade alone does not prove these checks were performed.
```

## exp_76a1d8b93e1bf4078433f9fe

来源题 [chexbench_rad_restruct_0148](../../cases/rad_restruct/chexbench_rad_restruct_0148.json) · 活跃

```text
Trigger: When finalizing a binary yes/no multiple-choice answer about pleural disease after the direct chest X-ray QA tool returns “No” and a grounded report returns only “No significant findings.”

Verification action: Before emitting the choice, state the supported answer word from the direct observation (“no”), re-read the displayed option map, and write the matching option as a letter–text pair; confirm the letter and text agree (here, “B. no,” not an assumed letter). Then reconcile the rationale with the exact tool wording: the direct tool supports the pleural-specific “No,” while the grounded report only supports “No significant findings.” Do not claim the grounded report enumerated pleural abnormalities. If the letter–text match or source attribution fails, correct it before finalizing.
```

## exp_b0d9cefd21f7c5d3012ba77f

来源题 [chexbench_rad_restruct_0149](../../cases/rad_restruct/chexbench_rad_restruct_0149.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer to “Is there anything abnormal in [a named anatomical structure]?” when a structure-specific QA tool returns “No” and a general grounded report either omits that structure or says only “No significant findings.”

Verification action: Identify the observation that explicitly names the same structure and attribute as the question. Use its answer text as the primary support, map it back to the displayed option map, and confirm the letter and text agree—here “No” maps to “B. no.” Treat the general report as non-confirming if it does not explicitly mention the trachea; do not present its silence as a second negative finding. If the rationale says “both tools show no tracheal abnormality,” revise it to say the direct trachea QA said “No” and the general report omitted tracheal findings. A correct final grade alone does not prove the evidence scope and option mapping were checked.
```

## exp_282e5951da2561ab49b619f2

来源题 [chexbench_rad_restruct_0150](../../cases/rad_restruct/chexbench_rad_restruct_0150.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about disease in a named anatomical region—here, “Are there any diseases in the breast?”—after a region-specific VQA tool returns “No” and a general radiology report lists only other structures as normal.

Observable verification action: Before emitting the answer, restate the supported proposition (“no breast disease”) and check that each cited observation actually addresses the same object and attribute. Confirm the direct tool query explicitly asked about breast tissue and returned “No.” Then inspect the general report for an explicit breast finding; if it only says “lungs are clear,” “cardiomediastinal silhouette is unremarkable,” “no pleural effusions,” “no pneumothorax,” and “no abnormal calcifications,” do not cite it as independent breast corroboration and do not say “both found no abnormalities in the breast tissue.” If no in-region positive finding conflicts with the direct negative, map the supported text “no” back to the displayed option map—here B = “no”—and confirm the emitted letter and text agree.

The final “B. no” was correct, and the letter/text mapping was sound. The evidence lesson is that the second report did not address the breast, so the reason overstated corroboration; only the direct breast-specific negative supported the answer.
```

## exp_a5cfb16665c86a5453351305

来源题 [chexbench_rad_restruct_0151](../../cases/rad_restruct/chexbench_rad_restruct_0151.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether a named anatomical region is abnormal, after consulting imaging/report tools, especially if the reason cites more than one tool or a retrieved prior experience suggests an option letter.

Verification action: Before emitting, state the supported answer text using only tool observations that explicitly address the same region and attribute as the question. Do not count a generic report or findings about other regions as direct evidence. Then re-read the entire current option map and map the supported text to the exact displayed choice, checking that the letter and text agree. Also check that the final reason cites only tools that actually support that region-specific conclusion. In this case, CheXagent answered the exact abdominal question with “No,” while MAIRA-2 listed only right-sided chest findings and did not address the abdomen; the supported text is “no,” and the current option map makes that “B. no.” Do not rely on a prior memory that mapped “no” to A, and do not cite MAIRA-2 as abdominal evidence.
```

## exp_cd4d2a572dfc28180a9f3d51

来源题 [chexbench_rad_restruct_0152](../../cases/rad_restruct/chexbench_rad_restruct_0152.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether a named anatomical region is abnormal, after one tool directly answers for that region and another report/QA tool mentions only other findings or omits the region.

Verification action: Before emitting, state the supported answer text from the observation that actually addresses the same region and attribute. Do not treat another tool’s silence or unrelated report as direct region evidence, and do not copy a letter from a similar prior case. Re-read the current displayed option map from scratch and match the supported text to it: here the direct observation says the abdomen appears normal with no free air, so the supported text is “no”; with current options A=yes, B=no, the correct final form is “B. no.” Check that the letter and text agree and that the final reason’s attribution matches each observation—CheXagent directly addressed the abdomen, while MAIRA-2 only reported cardiac enlargement and clear lungs and did not directly assess the abdomen. If the letter–text match or source attribution fails, correct it before finalizing.
```

## exp_4dad7fe4f1a20491925319bc

来源题 [chexbench_rad_restruct_0160](../../cases/rad_restruct/chexbench_rad_restruct_0160.json) · 活跃

```text
Trigger: Before finalizing a yes/no imaging answer when a positive finding comes from a multi-category tool prompt or from phrase grounding that was queried using the very phrase in question—e.g., “foreign objects” answered with “surgical clips” under a prompt that also allowed “medical devices” or “hardware.”

Verification action: Compare the exact category in the question with the exact finding in each observation. Do not treat “surgical clips,” “medical devices,” or “hardware” as automatically equivalent to “foreign objects” unless the observation explicitly supports that same label. Also treat prompted phrase grounding as non-independent confirmation: it was asked to ground “surgical clips,” so it does not by itself prove clips were present; check whether its box/location agrees with the other observation rather than merely repeating the prompted phrase. If the positive evidence requires broadening the question’s category or merging inconsistent locations, do not choose “yes” on that basis. With no direct foreign-object evidence, select the supported negative text “no,” map it to the displayed option—“B. no”—and confirm the letter and text agree. In this case “A. yes” correctly mapped to “yes,” so the error was not option mapping; it was accepting category-broadened/conflicting positive evidence for a narrower question. The reference is “B. no.” This failed trajectory supports a caution about same-category and location checks; it does not verify an unexecuted repair.
```

## exp_8003c09f18fd110b715e743f

来源题 [chexbench_rad_restruct_0153](../../cases/rad_restruct/chexbench_rad_restruct_0153.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether a named anatomical region is abnormal after a tool returns a short “No”/“Yes,” especially when retrieved prior-case memories suggest a different option letter.

Verification action: Before emitting, identify the tool observation that directly answers the same region and attribute as the question. Here, CheXagent answered “No” to the exact abdomen question, so the supported answer text is “no.” Re-read the entire current option map and emit the matching letter–text pair, checking that they agree: current map A = yes, B = no, so the answer is “B. no.” Do not reuse a remembered mapping from another case. Keep the final reason limited to what the tool actually supports; do not claim that it explicitly enumerated specific findings unless the observation did so. If the letter–text pair or evidence attribution fails, correct it before finalizing. A correct grade alone does not prove that this check was performed.
```

## exp_3ef56a521309094d7afc347c

来源题 [chexbench_rad_restruct_0161](../../cases/rad_restruct/chexbench_rad_restruct_0161.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there any signs in the lung?” and one tool has explicitly answered “Yes” to that exact question, but the terminal choice is “No” based on other tools plus a verifier—especially when one of the cited “No” observations only lists absence of specific or unilateral findings such as “no right pneumothorax” or “no right effusion.”

Verification action: Before emitting the answer, compare each observation to the exact question and attribute. Do not count a narrow report like “No right pneumothorax/effusion; heart size normal” as a global “no signs in the lungs,” and do not describe it as a second model confirming “no lung abnormality.” If an explicit “Yes” to “any signs in the lungs” remains in the record and is not contradicted by an equally broad negative, retain that supported positive answer rather than overruling it by majority vote or by the verifier’s “CORRECT” label. Then map the supported text to the displayed option—here “yes” is A, not B—and confirm the letter and text agree.
```

## exp_e1502074624cf4a971d73602

来源题 [chexbench_rad_restruct_0164](../../cases/rad_restruct/chexbench_rad_restruct_0164.json) · 已剪枝

```text
Trigger: You are finalizing a binary “Are there any diseases in the thorax?” answer and are about to choose “yes” because maira2_grounded_report lists a thoracic finding (e.g., “Linear atelectasis left lung base”), while chest_xray_expert, asked the exact same question, answered “No” and/or the grounded finding is a minor, incidental, or chronic descriptor rather than a clearly qualifying active thoracic disease.

Verification action: Before emitting the answer, re-read the displayed option map and confirm the letter/text (here A = no, B = yes). Treat chest_xray_expert’s direct answer to the exact question as load-bearing. Check each grounded finding against the question’s intended criterion: does it clearly denote an active disease in the thorax, not merely a minor/incidental/chronic finding or a finding that the direct disease-presence QA already considered? If no clearly qualifying disease is identified, keep “No”/A. Do not let a verifier’s “CORRECT” resolve the conflict when it merely restates the proposed “yes” and the same unverified grounded finding. If choosing “yes,” name the qualifying thoracic disease and why it meets the criterion; then map that supported answer text to the displayed option and confirm letter and text agree.

Lesson from this case: chest_xray_expert answered “No” to the exact question, but the model finalized “B. yes” after maira2_grounded_report listed linear atelectasis, and the verifier approved the proposed answer without independent evidence. The released reference was A. no. This was not an option-letter/text mapping error—B matched “yes”—the error was accepting a non-qualifying or conflicting grounded finding as sufficient to overturn the direct exact-question negative.
```

## exp_b0de0a2479551e7fc210b33d

来源题 [chexbench_rad_restruct_0169](../../cases/rad_restruct/chexbench_rad_restruct_0169.json) · 活跃

```text
Trigger: When a yes/no multiple-choice question asks whether a named anatomic system has “signs” or abnormalities, and a direct system-specific tool answers negatively (e.g., “No, the skeletal structures do not show any abnormalities”), but a later grounded report contains a related status phrase or hardware mention (e.g., “Patient status post sternotomy”) that phrase grounding localizes, do not treat that later mention as automatic affirmative evidence.

Observable verification action: Before changing the answer to “yes,” check whether the later observation explicitly addresses the same object and attribute as the question—i.e., whether it actually asserts an abnormality/sign in the skeletal system, not merely a history or device phrase. Phrase grounding that returns “sternotomy wires are midline and intact” only confirms that the phrase is localizable; it is not independent proof of an abnormal skeletal sign and should not override the direct negative unless the conflict is explicitly reconciled. If no direct independent result conflicts, keep the supported “no,” map it to the displayed option whose text is “no” (here A), and verify that letter and text agree.

Why this case illustrates the lesson: The terminal “B. yes” was not an option-mapping error—B correctly maps to “yes.” The error was evidentiary: the final rationale treated “status post sternotomy” plus localization of sternotomy wires as confirmation of a skeletal finding, while losing the earlier direct observation that the skeletal structures showed no abnormalities. The released reference is “A. no,” so the lesson is to preserve the direct same-attribute negative and require explicit same-attribute affirmative evidence before flipping to “yes.”
```

## exp_aa8f9c0540d3e3d147bbdf8d

来源题 [chexbench_rad_restruct_0154](../../cases/rad_restruct/chexbench_rad_restruct_0154.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about disease/abnormality in a named anatomical region after consulting multiple imaging/report tools, especially when the draft reason cites a report that lists findings only in other regions.

Verification action: Before emitting, identify the observation that directly answers the exact region-and-attribute question. Do not count a thoracic-only or generic report as direct evidence about the abdomen. Here, CheXagent answered the exact abdominal question with “No,” while MAIRA-2 listed only heart, vascular, lung, consolidation, effusion, and bony-thorax findings and did not address the abdomen; therefore the supported text is “no,” and MAIRA-2 should not be cited as showing “no abdominal disease.” Then re-read the entire current option map and confirm the selected letter and text agree: A = “no.” The terminal choice “A. no” matches the supported text and the reference, but the correct grade does not cure the overclaim in the reason. If no tool directly addresses the target region, or if direct observations conflict, issue a targeted follow-up rather than finalizing.
```

## exp_fab07360539a163723ee250e

来源题 [chexbench_rad_restruct_0155](../../cases/rad_restruct/chexbench_rad_restruct_0155.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer to “Are there any signs [of abnormality] in [a named anatomical structure]?” when a structure-specific QA tool gives a direct answer and a general grounded report either omits that structure or says only “no other significant findings.”

Verification action: Re-read the displayed option map and match the supported answer word to the option text, stating the letter and text together—here “No” maps to “A. no,” and the released reference is also A/no, so there is no option-mapping error. Then attribute the evidence: use the observation that explicitly names the same structure and attribute as the question; here `chest_xray_expert` answered “No” to the trachea question, so that is the load-bearing support. If the general grounded report does not mention the trachea, treat its silence as non-confirming rather than as a second negative finding; revise any rationale that implies both tools showed no tracheal abnormality. Confirm that the terminal choice uses the direct evidence and that each rationale claim matches the exact tool text. A correct final grade alone does not prove this check was performed; the observable checks are letter/text agreement and exact attribution of every evidence claim.
```

## exp_2edece80a85cd9df2385226d

来源题 [chexbench_rad_restruct_0156](../../cases/rad_restruct/chexbench_rad_restruct_0156.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about a named anatomical region after a region-specific imaging QA tool returns a negative observation.

Verification action: State the supported answer text using only the tool observation that explicitly names the same region and attribute. In this case, the abdomen query returned “does not show any free air, bowel obstruction, or calcifications in the abdomen,” so the supported text is “no.” Then re-read the entire current option map and pair the exact letter with the exact text before emitting: here A = “no” and B = “yes,” so the correct terminal form is “A. no.” Do not carry over a remembered letter from prior cases where “no” mapped differently. Also ensure the final rationale cites only that direct abdominal observation and does not treat unrelated silence or generic findings as additional evidence.
```

## exp_d75147e5c10b5039cbba9037

来源题 [chexbench_rad_restruct_0157](../../cases/rad_restruct/chexbench_rad_restruct_0157.json) · 已剪枝

```text
Trigger: You are finalizing a yes/no multiple-choice item that asks whether a named anatomic system shows "any signs/abnormalities," and the only supporting observation is one VQA tool's blanket "No" returned to a paraphrased, system-specific prompt (here, chest_xray_expert asked about "abnormalities in the skeletal system, such as fractures, lytic lesions, or deformities" → "No").

Verification action: Before emitting the option, run these observable checks on the actual tool text.

1. Same object and same attribute. Confirm the observation explicitly names the target system and the attribute asked about, rather than a narrower list or an inference from the report's silence. In this trajectory the expert did answer "No" to the skeletal-abnormality question directly, so the observation is on-target; had the question asked about "signs in the skeletal system" and the tool only returned "no fractures," the negative would not cover the asked attribute and should be broadened or flagged.

2. Independence and conflict. If that single negative is the sole evidence, mark it provisional rather than decisive — especially when the system is peripheral to the tool's imaging focus. Look for a second independent observation on the same image and attribute (e.g., a grounded radiology report, or another VQA model asked the same system-specific question). If one exists and conflicts, resolve it before finalizing; if none exists and no follow-up was actually run, say so and do not describe the negative as corroborated. Do not treat retrieved historical "no" cards from other images as corroboration — they are priors about style, not evidence about this image.

3. Option mapping at finalization. Restate the supported answer word and map it to the displayed option map, writing letter and text together and checking they agree (A = no, B = yes). Here the terminal "No" maps to A "no," matching the released reference — so this was a correct mapping, not an option-mapping error. The residual lesson is evidentiary: the same pattern (one blanket negative treated as decisive) is what the retrieved card exp_49ed87418a8ce811ee4bf080 documents failing on a different image whose reference was "yes," and a correct grade here does not demonstrate that the single-tool evidence was adequate.
```

## exp_c11102cb8677f3879f099399

来源题 [chexbench_rad_restruct_0158](../../cases/rad_restruct/chexbench_rad_restruct_0158.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is there anything abnormal in [named anatomic system]?” and the evidence includes a system-specific QA response or a grounded-report line mentioning that system.

Observable verification action: Before emitting the answer, identify at least one completed observation that explicitly names the same system and attribute as the question. In this case, `chest_xray_expert` was asked about skeletal abnormalities and answered “No,” and the MAIRA-2 report explicitly said “No significant skeletal abnormalities are identified.” Check that no other completed observation reports an abnormality in that same system. Do not treat omission or a general “no significant findings” statement as a system-specific negative unless the target system is explicitly mentioned; if no direct observation exists, run a targeted query or flag insufficient evidence. Then map the supported text back to the displayed option map and check that letter and text agree—here “no” must map to “A. no,” not “B. yes.” Treat retrieved historical cases, corroborating verifier labels, and a correct final grade as non-decisive; they do not replace the direct same-system evidence or the letter/text mapping check.
```

## exp_cc65ffa47cf5f4ae4c6176eb

来源题 [chexbench_rad_restruct_0159](../../cases/rad_restruct/chexbench_rad_restruct_0159.json) · 活跃

```text
**Trigger:** You are about to finalize a yes/no multiple-choice answer about a finding (e.g., "Are there any signs in the lung?") after one or more tool observations report "no," "clear," or "no significant findings"—especially when retrieved experience cards or memory reference a different letter for the same word (e.g., a card saying "B. no," not "A. no").

**Verification action:** Before emitting, do two observable checks:

1. **Letter–text map check against the *current* option map.** State the supported answer word ("no"), then re-read the displayed options for this exact question and locate the option whose text is exactly "no." Emit the letter and text together and confirm they agree. In this case the map was {A: "no", B: "yes"}, so the correct pair is "A. no." Do not carry over a letter from a prior case where the ordering differed (the retrieved cards cited "B. no" against an "A: yes" map); the letter is only valid relative to the option list actually shown.

2. **Evidence attribution check.** Confirm each cited observation addresses the same object and attribute named in the question (the lungs) and that no tool conflicts. Here maira2_grounded_report said "No significant findings" and chest_xray_expert said "The lungs appear clear"—both concern the lungs and agree, so the rationale may cite both. If a tool's text had addressed a narrower or different attribute, limit the conclusion to what that tool actually observed rather than overstating agreement.

A correct final grade does not by itself prove these checks were performed; the reusable discipline is to perform the letter/text reconciliation against the live option map and to attribute each claim to the tool that actually made it.
```

## exp_97a586226a2cb5256d9241ea

来源题 [chexbench_rad_restruct_0162](../../cases/rad_restruct/chexbench_rad_restruct_0162.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer about a named anatomical structure when a structure-specific QA tool returns “No” and the draft rationale adds a separate visual-inspection claim.

Verification action: Re-read the displayed option map and map the observed answer word to the option whose text matches exactly, stating letter and text together—here the tool answered “No” to the trachea abnormality question, so confirm “A. no,” not a remembered letter. Then check each rationale clause against an actual observation: use the direct structure-specific QA answer as the load-bearing support, and remove or flag as unverified any extra claim such as “visual inspection confirms a midline tracheal air column” unless an observed result recorded that same structure and attribute. The correct reference “A/no” does not by itself prove the letter/text mapping and evidence scope were checked.
```

## exp_80b8cf99a394c737d83d8a70

来源题 [chexbench_rad_restruct_0163](../../cases/rad_restruct/chexbench_rad_restruct_0163.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer about pleural signs, especially when a direct chest-xray expert answered a narrowed pleural query with “No,” a grounded report says only “Lungs are clear”/cardiomegaly, and an earlier draft may have had a letter–text pair.

Verification action: Before emitting the answer, restate the supported answer word from the direct pleural observation (“no”), re-read the entire displayed option map, and write the choice as a letter–text pair. Confirm the letter and text agree—here “B. no,” not “A. yes”—and check that any earlier supported letter–text pair was not lost when the final answer was reduced to a bare letter. Then reconcile the rationale with the exact tool wording: attribute the specific pleural negative (“no pleural effusion, pneumothorax, or thickening”) to the chest-xray expert; do not claim the grounded report explicitly enumerated those pleural negatives when it only said “Lungs are clear” and listed cardiomegaly. If the tool query covered only a narrowed list but the question asks about “any signs in the pleura,” either broaden the query or limit the conclusion to what was actually observed. A correct grade alone does not prove these checks were performed.
```

## exp_0926cdd3a6f409e1d3a11d27

来源题 [chexbench_rad_restruct_0165](../../cases/rad_restruct/chexbench_rad_restruct_0165.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer about whether a named anatomical structure is abnormal, after a structure-specific imaging tool has returned “No.”

Observable verification action: Restate the supported proposition using only the tool result that explicitly addresses the same structure and attribute—here, “no lymph-node abnormality.” Check that no positive finding about lymph nodes conflicts with it. Then re-read the entire current option map instead of relying on a prior memory: A = “yes,” B = “no.” Map the supported text “no” to the displayed choice and confirm that the letter and text agree. Emit “B. no” only after that check. If the supported text is “no” but the current map assigns “no” to another letter, correct the option mapping; do not change the evidence. Do not cite a general report’s silence as an additional negative finding unless it explicitly addresses lymph nodes.
```

## exp_0858ca33636cb98b6c987711

来源题 [chexbench_rad_restruct_0166](../../cases/rad_restruct/chexbench_rad_restruct_0166.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about disease or abnormality in a named anatomical region after a region-specific imaging/VQA tool has returned a negative, especially when a retrieved precedent suggests a different option letter.

Observable verification action: Restate the supported proposition (“no breast disease/abnormality”). Check that the tool query and observation both name the same region and attribute—here the query asked about breast tissue disease/abnormality and chest_xray_expert answered “No, the breast tissue does not show any signs of disease or abnormalities.” Confirm there is no conflicting in-region positive finding. Then map the supported text “no” to the current displayed option map rather than copying a letter from a retrieved precedent: here A = no and B = yes, so emit A. no only if its letter and text agree. Finally, audit the final reason’s citations: the direct tool negative supports the answer; do not add “visual inspection confirms...” unless an observation explicitly reports that inspection. In this case A. no is correct and matches the reference, but the visual-inspection clause is unsupported corroboration and should be omitted.
```

## exp_bed447dd76c928901a7a543d

来源题 [chexbench_rad_restruct_0167](../../cases/rad_restruct/chexbench_rad_restruct_0167.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether a named anatomical region or attribute is abnormal, after querying both a region-specific VQA tool and a generic grounded-report tool, especially when the draft reason cites both tools as agreeing.

Verification action: Before emitting, go through each cited tool observation and ask whether it explicitly addresses the same anatomical object and attribute as the question. Count only observations that directly answer that region/attribute as supporting evidence; treat a generic report whose findings are confined to a different region (e.g., heart, sternotomy, interstitial markings in the thorax) as silent on the target region, not as a negative finding and not as corroboration. State the supported answer text using only those direct observations, then re-read the displayed option map and confirm the chosen letter's text matches that supported text (here B = "no"). If a cited tool does not address the region, either remove it from the reason or label it non-contributory.

Why this case illustrates the lesson: The final answer "B. no" was correct and the letter/text pairing was sound, but the terminal reason claimed "Both chest_xray_expert and MAIRA-2 report no abdominal abnormalities." Only chest_xray_expert was actually asked the abdominal question and answered "No"; the maira2_grounded_report listed only thoracic findings ("The heart size is normal. Patient status post sternotomy. Increased interstitial markings are identified bilaterally.") and never mentioned the abdomen. Thus the reason overstated the second tool's support — a correct grade does not prove the cited evidence was sound. The safe procedure is to credit only the region-specific "No" from the exact-question tool, explicitly note that the generic report did not address the abdomen, and then map "no" to the displayed option B.
```

## exp_6c2dd73e651aa562b16f5542

来源题 [chexbench_rad_restruct_0168](../../cases/rad_restruct/chexbench_rad_restruct_0168.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is there anything abnormal in [named anatomic system]?” after several imaging tools have been called, especially when the rationale claims multiple tools concur but one of them is a general radiology report that may merely omit the target system.

Verification action: Before selecting an option, list each cited observation and check whether it explicitly names the same anatomic system and attribute as the question. Count a direct system-specific statement as support—e.g., `chest_xray_expert` answering “No” to skeletal abnormality and `llava_med_qa` answering “no abnormalities in the skeletal system.” Do not count a MAIRA-2 report that lists only cardiac, lung, and pleural findings as a skeletal negative; omission is not corroboration. If the direct evidence is consistently negative and no direct result reports the target abnormality, finalize “no” and map it back to the displayed option map, checking letter and text agree (A = no, B = yes). If the only support is a general report’s silence, or if direct observations conflict, issue a targeted follow-up or flag insufficient evidence instead of finalizing. A verifier’s “CORRECT” and a correct final grade are corroboration only; they do not prove that the evidence scope and option mapping were checked.
```

## exp_84f10bacba1e7e5cbe22a8ad

来源题 [chexbench_rad_restruct_0170](../../cases/rad_restruct/chexbench_rad_restruct_0170.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice imaging answer about whether disease is present in a specifically named anatomical structure—especially lymph nodes—after a structure-specific tool query has returned a negative result.

Observable verification action: Before emitting the answer, restate the supported proposition as “no disease in the lymph nodes.” Confirm that the tool observation addressed the same object and attribute as the question and that no positive lymph-node finding conflicts with it. Then read the current displayed option map rather than trusting any remembered map: in this case A = “yes” and B = “no.” Map the supported answer text “no” back to that exact option and emit it only when the letter and text agree, yielding “B. no.” Also do not add unsupported details such as “visual inspection shows no hilar or mediastinal lymphadenopathy” unless an observed tool result or image finding actually supports that specific claim.
```

## exp_bf22889f1730dd124ced8a24

来源题 [chexbench_rad_restruct_0171](../../cases/rad_restruct/chexbench_rad_restruct_0171.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer that asks whether a named anatomical system (e.g., skeletal system) shows any signs or abnormalities, especially after one tool gives a blanket negative.

Observable verification action: Check the completed tool observations for at least one explicit statement about the same system and attribute—not just silence in a general report. If available, require a second independent observation and compare for conflict. Reconcile the final rationale against the exact tool text, then map the supported answer word back to the displayed option map and state the letter and text together to confirm they agree. If the only support is a single blanket negative, omission, or conflicting evidence, issue a targeted follow-up instead of finalizing. In this case, chest_xray_expert explicitly said “No” to skeletal abnormalities and MAIRA-2’s report included “No significant skeletal abnormalities are identified,” so the supported answer “no” correctly mapped to “A. no.”
```

## exp_bd94206d7d85eb11bbcd8822

来源题 [chexbench_rad_restruct_0172](../../cases/rad_restruct/chexbench_rad_restruct_0172.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer to “Is there anything abnormal in [a named anatomical system]?” when a system-specific VQA tool gives a yes/no response and a grounded report lists radiology findings.

Observable verification action: Check that the grounded report contains at least one finding explicitly belonging to the named system, and that the direct VQA response agrees with the yes/no proposition. For a cardiovascular question, cardiomegaly and aortic elongation are same-system support; pleural effusion or pleural thickening are not and must not be cited as cardiovascular evidence. Then restate the supported proposition and map it to the displayed option map, checking that the letter and text agree—here “yes” must map to “B. yes,” and “no” to “A. no.” If the tools conflict, or only out-of-system findings support the answer, issue a targeted follow-up or mark the evidence insufficient. Do not say “both tools confirmed” unless both actually address the same system and attribute. In this case, chest_xray_expert said “Yes,” and the grounded report listed cardiomegaly and aortic elongation, so B. yes was both supported and correctly mapped; the pleural findings were irrelevant to the cardiovascular question.
```

## exp_14f672e0e70afe51af34cb31

来源题 [chexbench_rad_restruct_0186](../../cases/rad_restruct/chexbench_rad_restruct_0186.json) · 活跃

```text
Trigger: You are finalizing a yes/no option for a disease-presence question such as “Are there any diseases in the pleura?” when the only positive support is a nonspecific descriptor like “blunting of the left costophrenic angle,” and the draft rationale is about to convert that sign into a named disease such as effusion or thickening.

Verification action: Re-read the entire option map, write the answer as a letter-text pair, and compare the draft rationale word-for-word with the tool observations. Strike any disease term that no observation explicitly stated; phrase grounding confirms only the phrase’s location, not the diagnosis. If no observation explicitly names a qualifying pleural disease, do not select “yes” merely because a nonspecific sign is present. In this case B matched “yes,” so this was not an option-mapping error; the error was over-interpreting “blunting of the left costophrenic angle” as confirming pleural disease, when the report did not explicitly name effusion or thickening. If a direct QA tool answered “yes” but the grounded report supplies only a nonspecific sign, treat the direct answer as unconfirmed at the disease level rather than sufficient. The final rationale should cite only explicit observation wording, and the letter and text must agree.
```

## exp_0e64d3f536285c8207aab29d

来源题 [chexbench_rad_restruct_0183](../../cases/rad_restruct/chexbench_rad_restruct_0183.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice imaging answer about whether a named anatomical structure—especially lymph nodes—is abnormal, after a structure-specific tool was asked directly about that structure and returned a negative result.

Observable verification action: Restate the supported proposition using only the observed tool result: the chest_xray_expert was asked “Are there any abnormal lymph nodes, such as hilar or mediastinal lymphadenopathy?” and returned “No,” so the supported text is “no abnormal lymph nodes.” Confirm the tool result addresses the same object and attribute as the question and that no positive lymph-node finding conflicts with it. Re-read the current displayed option map instead of relying on a remembered map: here A = “yes” and B = “no.” Map the supported text “no” back to that exact option and emit “B. no” only when the letter and text agree. Do not add unsupported visual-inspection claims such as “visual inspection shows no hilar or mediastinal enlargement” unless that specific finding was actually observed; a correct final letter does not validate unsupported reason details. If the current map assigns “no” to a different letter, correct the option mapping, not the evidence.
```

## exp_6ce8bf7bbbee463ff5e32614

来源题 [chexbench_rad_restruct_0194](../../cases/rad_restruct/chexbench_rad_restruct_0194.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is there anything abnormal in [named anatomic system]?” and the rationale relies on a grounded radiology report’s findings.

Observable verification action: Before finalizing, confirm that at least one cited finding explicitly belongs to the queried system—e.g., cardiomegaly and aortic tortuosity support “yes” for the cardiovascular system, while findings from other systems do not. Confirm that the cited report observation is actually present in the current evidence for this image, not merely asserted from an earlier answer or retrieved memory. Then re-read the displayed option map and match the supported answer word to its exact letter and text. In this case, “yes” correctly maps to “A. yes,” matching the reference; a historical card where “yes” mapped to another letter must not be copied. If the same-system evidence is missing, conflicting, or not shown in the current observations, verify or follow up rather than finalizing.
```

## exp_b15ccafcadb1f40d1cff3e87

来源题 [chexbench_rad_restruct_0192](../../cases/rad_restruct/chexbench_rad_restruct_0192.json) · 活跃

```text
Reusable decision procedure (plain text):

Trigger: You are about to finalize a yes/no multiple-choice answer to an open-ended anatomical question such as "Are there any signs in the pleura?", when the tool query you actually ran narrowed that question to a short list of specific entities (for example, "pleural effusion, pneumothorax, or pleural thickening") and the tool returned "No."

Observable verification action: Before emitting the choice, compare the scope of the tool query against the scope of the question. If the question asks broadly about "any signs" but the query only enumerated a subset, a "No" on that subset does not establish a broad "no signs in the pleura" — there can be pleural findings outside the queried list. In this case both tools answered only the narrowed list ("No" from chest_xray_expert; "No left pneumothorax / No left effusion / Right lung clear" from maira2_grounded_report), yet the released reference is "yes." So either broaden the query to cover the full breadth of pleural signs before concluding, or explicitly limit the conclusion to the enumerated entities and flag the unexamined scope; do not present the narrowed negative as a global negative, and do not write a rationale claiming both tools confirmed the broad absence.

Also separate the two checks: the letter–text mapping here was correct ("no" → "B. no"), so this is a wrong conclusion from an over-narrow negative, not an option-mapping error. Confirm the letter/text pair agrees, but do not let a correct mapping stand in for evidence that actually covers the question's full scope; a correct grade on a mapping check alone does not prove the conclusion is right.
```

## exp_c30ecce9ae0f30677693ac54

来源题 [chexbench_rad_restruct_0193](../../cases/rad_restruct/chexbench_rad_restruct_0193.json) · 活跃

```text
**Trigger (narrow):** You are about to finalize a yes/no multiple-choice item of the form "Is there anything abnormal in [named anatomic system]?" on the strength of a single VQA tool's blanket negative, plus a general grounded report that you are citing as corroboration.

**Observable verification action:** Before emitting the option, open the actual tool text for every source you intend to cite and check two things on the literal wording:

1. **Scope of the negative matches the asked attribute.** The negative must cover the attribute the question asks about, not a narrower slice of it. Here `chest_xray_expert` returned "No, there are **no acute** skeletal abnormalities detected" to a prompt that itself listed only "fractures, lytic lesions, or deformities." That is a negative for *acute* skeletal findings; the question asks about *anything* abnormal in the skeletal system, which includes non-acute changes (degenerative disease, old deformity, osteopenia, post-surgical change). A negative on a subset cannot be promoted to the blanket answer.

2. **The corroborating report actually names the target system.** `maira2_grounded_report` returned five findings — clear lungs, normal heart size, CTR 0.45, no active pleural pathology, no chest wall pathology — plus mild aortic-arch atherosclerosis. **None of these is a statement about the skeletal system.** "No chest wall pathology" is soft tissue, and a report's silence about the skeleton is not an observation of a normal skeleton. So the terminal reason's claim that "both ... found no skeletal abnormalities" misdescribes the evidence: one tool gave a scoped negative, the other never addressed the object.

If either check fails, do not finalize the negative on that evidence: issue a targeted follow-up that drops the "acute" qualifier and asks directly about the skeletal system, or record the evidence as insufficient. Then restate the supported word and map it to the displayed option map, checking letter and text agree (A = no, B = yes) — the mapping here was sound; the failure was evidentiary, and it produced a wrong answer (reference B, yes) from evidence that was narrower than and silent about what was asked.

**Carry-forward caution:** a correct letter/text pairing does not rescue an over-claimed evidence base. When you write a justification that says "both tools found X," be able to point to the exact sentence in each tool output that says X about the asked object.
```

## exp_687a3441be2267d097969388

来源题 [chexbench_rad_restruct_0195](../../cases/rad_restruct/chexbench_rad_restruct_0195.json) · 活跃

```text
Trigger: You are finalizing a binary "Are there any diseases in the lung?" answer as "No"/B because chest_xray_expert answered "No", while a grounded report (maira2_grounded_report) explicitly lists a lung finding such as atelectasis. This is the narrow pattern: a direct QA "No" conflicts with an explicit grounded lung abnormality.

Verification action: Before emitting, re-read the displayed option map and confirm the letter–text pair (here A = yes, B = no). Then check the grounded report against the question's exact object and attribute: does it name a disease/abnormality of the lung? Atelectasis is a lung finding, so it supports "yes" for "any diseases in the lung". Do not discard an explicit grounded lung finding as "minor/incidental" merely because the direct QA tool returned "No" — the QA tool can be a false negative. If the grounded report names a lung abnormality, choose "yes" and map that text to the option whose text is exactly "yes" (A here), confirming letter and text agree. Choose "No" only when no report names a lung abnormality.

Lesson from this case: The model finalized "B. no", citing chest_xray_expert's "No" and dismissing the grounded report's atelectasis as a minor/incidental finding. The released reference was "A yes". This was not an option-mapping error — B correctly matched "no" — it was a wrong conclusion caused by letting a direct-tool negative override an explicit grounded lung finding. The prior experience cards ("direct tool is load-bearing; atelectasis is incidental") misfired here, because for a question asking whether there are any lung diseases, a documented lung finding like atelectasis counts as evidence for "yes". So the check is: compare each tool result to the question's object/attribute, note the conflict, and verify the terminal choice actually used the explicit lung finding rather than silently overriding it.
```

## exp_7db5c2963f84731328330cd3

来源题 [chexbench_rad_restruct_0199](../../cases/rad_restruct/chexbench_rad_restruct_0199.json) · 活跃

```text
Trigger: You are about to finalize a "no" answer (or the "no" option) to a broad presence question of the form "Are there any diseases in the pleura/thorax?", where the sole supporting evidence is one direct visual-QA tool response of "No" — no grounded report, phrase grounding, or region-specific finding was obtained, and the tool returned only a bare "No" with no enumerated findings.

Verification action: Before emitting the choice, (1) re-read the exact tool output and check that the rationale cites only what the tool actually returned; a bare "No" does not license claims such as "no effusion, pneumothorax, or thickening is present" — delete or downgrade any such enumerated-exclusion language. (2) Recognize that a lone negative from one VQA model on a broad "any diseases" query is weak corroboration, not a settled normal; in this case the released reference was "A. yes," so the single "No" was contradicted. Before treating the negative as settled, obtain at least one independent observation of the same region/attribute (e.g., maira2_grounded_report or xray_phrase_grounding). (3) Then map the supported answer word back to the displayed option and confirm letter and text agree (here A = yes, B = no). Note that the repair in step 2 was not executed in this case, so it stands as a caution about the observed failure, not a verified success.

What this case does and does not show: the terminal choice's letter/text pairing was correct (B = no), so this is not an option-mapping error; the tool observation addressed the same object and attribute as the question and the terminal choice did use it. The failure was a wrong conclusion resting on an uncorroborated single negative, plus an over-attributed rationale. Also note the retrieved experience cards were scoped to the opposite configuration (direct "No" versus contrary grounded findings) and did not match this evidence setup (no grounded report was produced); they must not be treated as evidence for "No" or as authority to skip corroboration. A correct grade alone would not prove this procedure works — the check must be performed.
```

## exp_4ec7cb03ef03f7582daf3506

来源题 [chexbench_rad_restruct_0200](../../cases/rad_restruct/chexbench_rad_restruct_0200.json) · 活跃

```text
Trigger: When a yes/no multiple-choice question asks whether a named anatomic system has “any diseases” or “any abnormalities,” and the available tool evidence is a blanket negative limited to “acute abnormalities” or a general report such as “No significant findings” that does not explicitly address that system.

Observable verification action: Before finalizing, inspect the exact tool text and confirm it names the target system and covers the same attribute asked—here, “any disease/abnormality,” not merely “acute” skeletal abnormalities or a general normal report. Require an independent same-image observation addressing that same system and attribute. If the supporting text is narrower or only general, do not treat it as proof of “no”; issue a targeted system-specific query or flag the evidence as insufficient. Then restate the supported answer word and map it back to the displayed option, checking that letter and text agree (A = no, B = yes). In this case, the A/no mapping was internally consistent, but “No acute skeletal abnormalities” plus “No significant findings” did not establish “no skeletal disease”—the error was evidentiary, not an option-mapping error.
```

## exp_7c633780faa14002046af61f

来源题 [chexbench_rad_restruct_0203](../../cases/rad_restruct/chexbench_rad_restruct_0203.json) · 活跃

```text
Trigger: You are finalizing a yes/no multiple-choice item that asks whether a named anatomic system shows “any signs” or a similarly broad finding, and the only support for “no” is a blanket negative/normal output from VQA or a general report tool—e.g., “No, the skeletal structures do not show any abnormalities” or “Bones are normal.”

Verification action: Check each tool text for whether it explicitly answers the exact broad attribute for the named system, not merely a narrower list or a general normal line. If the support is only a blanket negative, before selecting “no,” run a targeted follow-up with an independent tool using the exact question or a positive-finding enumeration for that system, such as “List any visible skeletal signs/findings; if none, say none.” Compare all observations for conflict; if any direct query reports a positive sign, select the positive option. Only select “no” after a direct broad query remains negative. Then map the supported word back to the displayed option map and state the letter and text together—here A = no, B = yes.

In this trajectory, “A. no” agreed with the option map and was based on the observed tool outputs, so it was not an option-letter error. No earlier step contained a positive skeletal finding that was lost during finalization. The released reference was B/yes, so the failure was evidentiary/conclusion-level: two normal or negative outputs—“no skeletal abnormalities” and “Bones are normal”—were treated as decisive for a broad “any signs” question, even though the general report did not explicitly enumerate skeletal signs. This failed case supports a caution about requiring a direct broad-attribute query before finalizing “no”; it does not verify a repaired procedure because no such follow-up was actually run and shown to change the result.
```

## exp_9ada18e9a91883511f746e7d

来源题 [chexbench_rad_restruct_0205](../../cases/rad_restruct/chexbench_rad_restruct_0205.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is there anything abnormal in the lung?” after one tool says “No” or “lung fields are clear” but another tool’s report contains a positive abnormal finding such as “Cardiomegaly.”

Verification action: Before emitting the choice, list every finding from every tool, separate negative lung-specific statements from positive abnormal findings, and do not summarize the whole report as “no abnormalities” based only on “lung fields are clear.” If any positive abnormal finding is present and the question asks whether there is “anything abnormal,” select “yes” and state the finding. Then re-read the displayed option map and confirm the letter–text pair is correct—here “A. yes,” not “B. no.” If the question is strictly limited to lung parenchyma and the only positive finding is cardiomegaly, record that scope conflict instead of silently answering “no.” In this case, “B. no” was an option-mapping-correct choice but a wrong conclusion: the final rationale omitted the positive cardiomegaly finding from maira2_grounded_report and over-relied on the negative “lung fields are clear” statement.
```

## exp_4164e9dcec6e61c3fadcacbd

来源题 [chexbench_rad_restruct_0206](../../cases/rad_restruct/chexbench_rad_restruct_0206.json) · 活跃

```text
Trigger: When finalizing a yes/no answer to “Are there any signs/abnormalities in [named anatomic system]?”, and the support for “no” is a blanket negative from one VQA tool or a general report phrase such as “the bony thorax is intact,” especially when a second tool also gives only a partial or normal statement.

Verification action: Before mapping to an option, inspect the actual tool text and confirm it explicitly addresses the same object and the same broad attribute as the question—the whole named system and “any signs,” not merely a narrower list such as fractures, lytic lesions, or deformities, and not merely one substructure such as the bony thorax. If the only support is a narrow blanket negative, a general normal phrase, or a second observation covering only a partial attribute, treat the negative as insufficient: issue a targeted follow-up using the exact broad question wording, or use another independent check, and look for any explicit positive finding in that system. Do not describe a negative as corroborated unless a second independent observation covers the same broad attribute and agrees. Then restate the supported answer word and map it to the displayed option map, checking that letter and text agree. In the supplied case, “no” correctly mapped to A “no,” but the evidence consisted of a blanket negative and a partial normal report phrase for a broad “any signs” question; the released reference was B “yes.” The error was therefore evidentiary, not an option-mapping error.
```

## exp_66ce6e81cd9ed356fa365fcc

来源题 [chexbench_rad_restruct_0207](../../cases/rad_restruct/chexbench_rad_restruct_0207.json) · 活跃

```text
Trigger: You are finalizing a yes/no multiple-choice answer to “Are there any diseases/abnormalities in [named anatomic system]?” when the “no” support is a single VQA blanket negative or a report that only excludes a narrower list of findings (e.g., “no fractures, lytic lesions, or deformities” or “no displaced rib fracture; no expansile or destructive process”).

Verification action: Check the exact observation text for the same object and attribute. It must explicitly support the broad claim “no disease/abnormality in that system,” not merely exclude selected findings. If the tool only rules out a sublist, or the report’s skeletal statements are narrower than the question while other findings are non-skeletal, do not convert that into a general “no”; obtain a targeted follow-up observation for the broad system/attribute or flag the evidence as insufficient. If any observation reports disease in that system, answer “yes.” Then restate the supported answer word and map it to the displayed options, checking letter and text agree. In this case, “A. no” matched option text “no,” so it was not an option-mapping error; it was an evidentiary overreach: a limited skeletal negative was treated as proof of no skeletal disease, while the released reference was “B. yes.”
```

## exp_d3129c71032a46588df6931f

来源题 [chexbench_rad_restruct_0208](../../cases/rad_restruct/chexbench_rad_restruct_0208.json) · 活跃

```text
Decision procedure: when a yes/no disease-presence answer would rest on a single negative direct-QA tool response, obtain one independent corroborating observation before finalizing the negative.

Trigger: You are about to finalize “no” / “B” for a binary question such as “Are there any diseases in the lung?” solely because the direct chest X-ray QA tool answered “No,” and no second tool or grounded report has been consulted.

Verification action: Before emitting the answer, run at least one independent evidence source on the same image/question — e.g., a grounded radiology report or a second visual QA model — and check whether it names any qualifying disease in the queried organ. Treat a lone exact-question “No” as supporting evidence, not as sufficient proof of absence. If an independent source identifies a qualifying active disease, choose “yes” and name it; if no independent source does, keep “no.” Then map the supported answer text back to the displayed option map and confirm the letter and text agree (here A = yes, B = no).

Lesson from this case: the terminal answer was “B. no,” and its letter/text mapping was correct — B did match “no.” The failure was not an option-mapping error but an evidence error: chest_xray_expert answered “No” to the exact question and the model finalized on that single negative without corroboration, while the released reference was “A — yes.” The tool did address the same object and attribute as the question and the terminal choice did use its result, so the defect is accepting an uncorroborated negative as decisive. A correct-looking mapping and a clean rationale do not validate the underlying evidence; a single negative direct-QA response should be cross-checked against an independent observation before a negative disease-presence answer is finalized.
```

## exp_2141fac5213c3ac79918f947

来源题 [chexbench_rad_restruct_0209](../../cases/rad_restruct/chexbench_rad_restruct_0209.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is there anything abnormal in the lung?” and tool observations say “clear” or only “no infiltrates or pulmonary condensations,” especially if the draft rationale generalizes them to “no lung abnormalities.”

Verification action: Before emitting, state the supported answer text, map it to the displayed option, and confirm the letter–text pair agrees. Then check each cited observation against the exact object and attribute scope of the question: a report that only excludes infiltrates/condensations does not establish that there is no abnormality at all, so do not cite it as global clearance. In this case B. no correctly matched the option text and both tools were negative, so this was not an option-mapping error; the released reference was A yes, and the terminal rationale overread the narrower maira2 finding as “lungs are clear.” If a cited negative is narrower than the question or conflicts with another result, reconcile it or treat the evidence as insufficient rather than finalizing “no” solely on that basis. This is a caution supported by the failed trajectory, not a verified repair.
```

## exp_f12b9052d38ba1bfa1ba8d34

来源题 [chexbench_rad_restruct_0210](../../cases/rad_restruct/chexbench_rad_restruct_0210.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there any diseases in the lung?” and chest_xray_expert gives a direct negative (“no acute cardiopulmonary disease”) while maira2_grounded_report lists any positive abnormality, especially a non-parenchymal one such as “Cardiomegaly.”

Verification action: Before emitting the answer, enumerate all grounded-report findings instead of summarizing only “pulmonary parenchyma without significant alterations.” Check whether any listed finding qualifies as a disease/abnormality under the question’s intended scope. If Cardiomegaly or another positive finding qualifies, choose “yes,” name that finding in the rationale, and map the supported text to the displayed option (“B. yes”); do not select “no” solely because the lung parenchyma is clear. If a positive finding is excluded as out of scope, state the exclusion explicitly. Finally, re-read the option map and confirm the selected letter and text agree. This case was not an A/B mapping error—the error was finalizing “no” while omitting the positive Cardiomegaly finding from the evidence synthesis.
```

## exp_27fe980fa4f371f7910b7387

来源题 [chexbench_rad_restruct_0211](../../cases/rad_restruct/chexbench_rad_restruct_0211.json) · 活跃

```text
Trigger: When finalizing a binary “Are there any diseases in the lung?” answer and chest_xray_expert answers “No” while maira2_grounded_report lists a specific lung-localized finding (e.g., “A calcified granuloma in the right lower lung”), especially when the model is tempted to call that finding incidental or chronic and answer “no.”

Verification action: Re-read the exact question for an explicit “active” or “acute” qualifier. If none is present, treat the grounded lung-localized finding as a candidate positive for “any disease/abnormality,” not as automatically non-qualifying because it is calcified or incidental. State the finding and its lung location, and note the conflict with the direct-QA “No.” If the only reason for “no” is dismissing that in-lung finding, choose the option whose text is “yes” and confirm the letter–text mapping (here A = yes, B = no). In this case, B = “no” was mapped correctly, so this was not an option-mapping error; it was an evidence-interpretation error. The released reference was A = “yes” because the calcified granuloma was itself an in-lung finding under the literal question. Do not apply a historical retrieval rule that “incidental means non-disease” unless the current question explicitly requires active disease.
```

## exp_3bdc49c16a419bbeeb0e157c

来源题 [chexbench_rad_restruct_0212](../../cases/rad_restruct/chexbench_rad_restruct_0212.json) · 活跃

```text
Trigger: Before finalizing a yes/no answer to a broad anatomical question such as “Are there any signs in the mediastinum?”, when the structure-specific tool was asked a narrower question (“abnormal signs such as widening, mass, or calcification”) and answered “No,” and the general grounded report does not mention that structure at all.

Verification action: Compare the original question’s exact object and attribute with the tool prompt. If the tool ruled out only a listed subset, treat its “No” as evidence only for that subset, not for the broad “any signs” question. Broaden or re-run the query to cover the full requested scope, or state that the broad negative is unsupported; do not cite a grounded report that discusses only other structures (here, left ribs and left lung) as confirming a normal mediastinum. Then map the supported answer word to the displayed option and check that letter and text agree. In this case, the letter-text mapping “A. no” was internally correct, but the conclusion was unsupported because the negative covered only widening/mass/calcification and the grounded report did not evaluate the mediastinum; the released reference was “B. yes.” A correct grade alone would not prove this scope and attribution check was performed.
```

## exp_ea63da28e961fbd1e79e9ba9

来源题 [chexbench_rad_restruct_0184](../../cases/rad_restruct/chexbench_rad_restruct_0184.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about lung abnormality after tool observations report “No,” “No other relevant findings,” or only a normal variant.

Verification action: Before emitting, state the supported answer word (“no”), re-read the displayed option map, and select the option whose text exactly matches that word—confirming the letter and text together (here “B. no,” not “A. yes”). Then check that each cited observation actually addresses the same question and does not conflict: the grounded report says “Azygos lobe as a variant of normality. No other relevant findings,” and the expert QA says “No.” Keep the rationale limited to those observations. If the observations conflict or address only a narrower attribute, reconcile or broaden the evidence before finalizing. A correct grade alone does not prove this check was done; the reusable step is the final letter–text match plus evidence attribution.
```

## exp_9095fc73969ab320d6ef9ebe

来源题 [chexbench_rad_restruct_0185](../../cases/rad_restruct/chexbench_rad_restruct_0185.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer when the visual-QA tool was asked a broader multi-category question than the exact category in the question—e.g., asking “Are there any foreign objects, medical devices, or hardware visible?” for the question “Are there any foreign objects?”

Verification action: Check the observation’s exact answer and scope against the asked category. A negative answer to a superset that includes the question’s category (“No” to foreign objects/medical devices/hardware) supports “no” for the narrower category; do not treat a positive finding in a different category—such as a medical device or hardware—as equivalent to a foreign object. Then map the supported word “no” to the current option map (here B. no) and emit the letter and text together, confirming they agree. In this case the terminal “B. no” matches the displayed option B: “no” and the reference B/no, so there is no option-mapping error.
```

## exp_12d1ade744bda656503d3d69

来源题 [chexbench_rad_restruct_0187](../../cases/rad_restruct/chexbench_rad_restruct_0187.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether a named anatomical region is abnormal, after querying a region-specific QA tool and a generic report tool.

Verification action: Before emitting, write the supported answer text using only tool observations that explicitly name the same region and attribute as the question. Do not count a generic report that lists only other regions (or its silence about the target region) as direct evidence. Then re-read the entire current option map, pair the supported text with the exact displayed letter, and check that the letter and text agree in the terminal answer. Finally, confirm the rationale cites only the region-specific observation — not the generic report as if it addressed the region — and do not import a letter mapping remembered from a prior case.

In this case, CheXagent answered the exact abdominal question with “No,” which supports “no.” The MAIRA-2 report listed only lungs, mediastinum, hilar areas, osseous structures, and soft tissues; it did not address the abdomen, so it should not be cited as abdominal evidence. The current option map was A = “no,” B = “yes,” so “A. no” was the correct letter-text pairing. The answer was right, but the rationale improperly leaned on MAIRA-2’s thoracic-only report; the durable lesson is to keep the evidence source matched to the region named in the question and to re-derive the letter from the current option map rather than from memory.
```

## exp_57755ce4b28b7aafc000ac9c

来源题 [chexbench_rad_restruct_0213](../../cases/rad_restruct/chexbench_rad_restruct_0213.json) · 活跃

```text
**Trigger:** When finalizing a yes/no multiple-choice item of the form “Is there anything abnormal/diseased in the [named anatomic system]?” and the “no” case rests on blanket-negative VQA answers while a grounded report or other observation explicitly notes a concrete finding (e.g., calcification, density, lesion) in or near that system.

**Observable verification action:** Before locking in “no,” enumerate every specific finding reported anywhere in the evidence and check (a) whether it falls inside the named system and (b) whether it is genuinely a normal variant/artifact supported by direct observation rather than by assertion. Do not count multiple VQA tools that each answered the same question with a blanket negative as “independent confirmation” — they can share the same failure mode, so three unanimous “normal” responses are really one weak piece of evidence. Likewise, a verifier’s reassurance (e.g., “the calcification is consistent with ECG electrodes”) is an opinion that must be grounded in the image, not a fact that erases an observed finding; verifier approval is not ground truth. If a concrete finding in the named system remains unexplained, or is dismissed only by assertion, answer “yes.” Then restate the supported answer word and map it back to the displayed options, confirming letter and text agree (A = no, B = yes).

**Why this case illustrates the lesson:** The terminal answer was “A. no,” and its letter/text pairing was internally consistent (A = no), so this was not an option-mapping error — it was a conclusion/evidentiary error. The model cited “three independent tools confirm normal skeletal structures,” but those three were VQA-style blanket negatives that may share a failure mode; the grounded report had, in fact, flagged a calcification inferior to the right glenohumeral joint. The verifier then reasoned that finding away as ECG electrodes and endorsed “no,” and the model accepted that rationalization without independent evidence. The released reference was “B. yes.” The durable caution: agreement among similarly scope-limited tools plus a verifier is not corroboration of a specific-finding dismissal — when a concrete finding inside the named system is present and not genuinely explained as a normal variant, “yes” is the supportable answer.
```

## exp_4c99b9994d3d618630a1a8ab

来源题 [chexbench_slake_0001](../../cases/slake/chexbench_slake_0001.json) · 活跃

```text
Trigger: When finalizing a broad yes/no answer such as “Is there any abnormality in [named region]?” after tools return a direct “No” and/or a report that only negates selected findings (“no focal consolidation,” “no pleural effusion,” “no pneumothorax”) while also listing other positive findings or findings not localized to that region.

Verification action: Before emitting “no,” enumerate every positive finding in the grounded report and the exact scope of each negative. Confirm that the evidence explicitly covers “any abnormality” in the queried region, not merely absence of a few named findings. Do not convert “no focal consolidation/effusion/pneumothorax” into “no abnormalities.” If a positive finding is in, overlaps with, or cannot be confidently excluded from the queried region, do not finalize “no”; seek localization or answer “yes.” Separately, map the supported answer word back to the displayed option and check letter–text agreement.

In this case, “A. no” had correct letter–text mapping, but the conclusion “no” was unsupported: the grounded report listed cardiac silhouette enlargement and a port-a-cath while only negating three specific findings, and the final rationale incorrectly treated those selected negatives as a broad right-lung negative. This is a wrong-conclusion/evidence-scope error, not an option-mapping error.
```

## exp_9206f5ce8046767da4f74156

来源题 [chexbench_rad_restruct_0214](../../cases/rad_restruct/chexbench_rad_restruct_0214.json) · 活跃

```text
Trigger: When finalizing a binary “Are there any diseases in the lung?” answer after a grounded report names an explicit lung finding, such as a calcified granuloma in the right upper lobe.

Verification action: Before emitting the choice, re-read the displayed option map and confirm that the selected letter’s text is exactly “yes” and that the rationale cites the exact grounded finding. Check that the finding is in the lung, addressing the same object and attribute as the question, and treat it as positive evidence for “yes” unless the report or question scope explicitly excludes it. Do not downgrade an explicit grounded lung abnormality as incidental without a stated reason. If no lung abnormality is named, choose “no”; if one is named, choose the option whose text is “yes” and verify letter–text agreement. In this case, “Calcified granuloma in the right upper lobe” supported “yes,” and the terminal “B. yes” correctly matched the displayed option map and the reference.
```

## exp_150b9106180c40a6558ba140

来源题 [chexbench_slake_0002](../../cases/slake/chexbench_slake_0002.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer asking whether an image was taken by a named modality, such as “Is this image taken via X-Ray?”, especially when no direct tool observation is recorded and the rationale relies on visual features.

Observable verification action: Restate the supported modality proposition, map its exact answer word to the displayed option map, and emit the choice as a letter–text pair, e.g. “A. yes.” Confirm that the letter and text agree and that the rationale cites only modality-relevant evidence actually observed—for example, bony thorax, lung fields, and radiographic contrast for an X-ray—rather than unrelated clinical findings or unverified details such as “medical devices.” In this case “A. yes” matches option A and the reference A/yes, so there was no option-mapping error; but because no tool observation was recorded, the correct grade alone does not prove that the evidence attribution and rationale limits were checked.
```

## exp_5b49f307822684cec4efb28f

来源题 [chexbench_rad_restruct_0216](../../cases/rad_restruct/chexbench_rad_restruct_0216.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is there anything abnormal/diseased in [named anatomic system]?” and the support for “no” consists of VQA/report outputs that are blanket negatives, general “no significant findings” reports, or negatives limited to a sublist such as fractures, lytic lesions, deformities, or degenerative changes.

Observable verification action: Before choosing the option, inspect the exact observation text for the same image, system, and broad attribute. Require at least one observation that explicitly supports “no abnormality/disease in that system,” not merely absence of selected subfindings or a general normal report. Do not count several models as independent corroboration if they were given the same narrowed prompt; that is one evidentiary line. If no observation covers the broad attribute, run a fresh targeted query for broad abnormality/disease in that system or use a system-specific grounding/ROI check. If any same-image evidence reports a finding in that system, answer “yes.” Then restate the supported answer word and map it back to the displayed options, checking that letter and text agree (A = no, B = yes).

Case lesson: The original “A. no” was not an option-mapping error—A correctly maps to “no.” It was an evidentiary error: chest_xray_expert answered “No” to a question containing example findings, maira2_grounded_report returned only “No significant findings,” and llava_med_qa denied the same limited list. Those correlated narrowed/general negatives did not establish the broad claim “no skeletal abnormality,” while the released reference was B/yes.
```

## exp_5fceac8e0e31463d40d0dbe6

来源题 [chexbench_rad_restruct_0217](../../cases/rad_restruct/chexbench_rad_restruct_0217.json) · 活跃

```text
Trigger: You are finalizing a binary “Are there any signs/disease/abnormality in the lung?” answer, especially when chest_xray_expert returns “No” to a narrowed disease list but your rationale also mentions a grounded report or other lung finding. This is the narrow pattern where a direct QA negative may be overriding an explicit grounded lung finding, or where the rationale cites a source that was not actually executed.

Verification action: Before emitting, re-read the displayed option map and state the supported answer text with its letter (here “yes” = A, “no” = B). Then inspect the actual executed observations. If the rationale cites maira2_grounded_report or another source, confirm that source appears in the observation list; if it does not, remove the citation and do not use it as evidence. Compare each observed finding to the question’s exact object and attribute: does it explicitly name a lung abnormality or sign such as atelectasis, opacity, consolidation, edema, nodule, or mass? If any observed grounded report names such a lung finding, treat that as “yes” for “any signs in the lung”; do not dismiss it as minor/incidental and do not let a direct QA “No” to a narrower list override it. Choose “yes” and map it to the option whose text is exactly “yes” (A here). Choose “no” only when all observed evidence for the lung attribute is negative and no lung finding is named. Finally confirm the terminal letter and text agree with the supported text.
```

## exp_c40aa74aebb2605ac5bfc01f

来源题 [chexbench_rad_restruct_0218](../../cases/rad_restruct/chexbench_rad_restruct_0218.json) · 活跃

```text
Trigger: When finalizing a binary answer to “Is there anything abnormal in the lung?” if chest_xray_expert directly answers “Yes,” but another QA/report/verifier says “normal” or “no” by listing only absent non-lung or right-sided findings (e.g., no right rib fracture, no right pneumothorax, no right effusion, normal heart size, no right soft-tissue abnormality), and the option map is A = no, B = yes.

Verification action: Before emitting, state the supported answer word and map it to the displayed option; for this map, “yes” must become “B. yes” — not “A. no,” and not “B. no.” Then check each cited negative result against the exact question’s object and attribute: a report that omits lung parenchyma or lists only absent pleural/rib/heart/soft-tissue findings does not establish “no lung abnormality.” If the direct expert’s “Yes” is the only same-question positive and no tool explicitly documents a same-scope normal lung, preserve “yes” and select B. If a verifier proposal pairs a letter with the wrong text (e.g., “B. no” when B = “yes”), flag the mapping error before relying on its conclusion. Cite only evidence that addresses the same object/attribute.

Lesson from this case: the terminal “A. no” matched A = no, so the final letter-text mapping was internally correct; the error was the conclusion. The direct expert said “Yes,” while the negative report described other structures and the verifier returned a conflicting negative opinion. The released reference was “B yes.” A negative report or verifier should override a direct positive only when it explicitly resolves the same lung-abnormality question, not when it merely lacks a finding.
```

## exp_2a5d3003373efcdaf1e8b78c

来源题 [chexbench_rad_restruct_0221](../../cases/rad_restruct/chexbench_rad_restruct_0221.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer to “Are there any signs in [named anatomical structure]?” when the only structure-specific QA result says “No” but its prompt asked a narrower question, such as “any abnormal signs such as deviation, narrowing, or mass.”

Verification action: Re-read the exact question and the exact tool prompt and require the same object and attribute. If the tool only ruled out “abnormal signs/deviation/narrowing/mass,” do not treat that “No” as ruling out “any signs”; use it only for the narrower abnormality set. Obtain or cite an observation that answers the exact wording—same structure and same attribute—or flag the answer as not directly supported. Check every rationale clause against an observed result, and drop unsupported claims such as “visual inspection shows a midline tracheal air column” unless an observation recorded that finding. Then map the supported answer word to the displayed option and state letter and text together. In this case, the tool’s “No” maps correctly to “A. no,” so the error is not letter/text mapping; the released reference “B. yes” indicates a wrong conclusion/evidence-scope failure because a narrowed “No” was used to answer the broader question.
```

## exp_3782d5a6ada6e3d01318c729

来源题 [chexbench_rad_restruct_0225](../../cases/rad_restruct/chexbench_rad_restruct_0225.json) · 活跃

```text
Trigger: Before finalizing a yes/no answer to a presence question such as "Are there any foreign objects?" when one observation is a bare negative from a VQA model (here chest_xray_expert answered "No") while another observation is an unprompted grounded report that explicitly names an implanted structure (here maira2_grounded_report: "Median sternotomy cerclage"), and phrase grounding on the question phrase ("foreign objects") returns nothing.

Verification action: Enumerate every concrete entity named across the observations before choosing. If any named entity is retained/implanted material within the question's category — median sternotomy cerclage (sternal wires) is a foreign body — treat the answer as positive unless some observation explicitly evaluated that same entity and ruled it out. A bare "No" from a different VQA model and a null phrase-grounding result do not rule it out: they address a coarser granularity, and the phrase grounding was prompted with the question term itself, so its emptiness is not independent evidence of absence. Do not resolve the conflict by reasoning "strict definition of foreign objects vs. post-surgical changes" to dismiss a listed cerclage; that is precisely the move that produced the wrong terminal answer here. The caution in retrieved cards about not equating "surgical clips/medical devices/hardware" with "foreign objects" applies to prompted, ambiguous, or location-conflicting positives; it does not license ignoring an unprompted, grounded, named structure that matches the question's category. After settling on the word "yes," map it back to the current option list (here B = "yes"), emit the letter and text together, and confirm they agree. In this case "A" correctly mapped to "no" in the displayed options, so the failure was a wrong conclusion from discarding positive evidence, not an option-mapping error. This is a caution about the observed failure; the reconciliation rule is not claimed as an independently verified repair.
```

## exp_77ddafe21408203619618ac8

来源题 [chexbench_rad_restruct_0226](../../cases/rad_restruct/chexbench_rad_restruct_0226.json) · 活跃

```text
Trigger: You are about to finalize a "no"/B answer to a broad "Are there any diseases in the lung?" when every tool result is a bare or hedged negative — chest_xray_expert returns only "No", and maira2_grounded_report returns only "No significant findings." with zero grounded boxes/findings — and the draft rationale collapses both into "no diseases in the lung."

Verification action (observable, before emitting):
1. Re-read each tool output literally. "No significant findings" answers "any significant/acute findings?" — not the broader "any diseases?". Do not upgrade a screening/hedged negative into a categorical "no disease."
2. Check the terminal rationale against what was actually returned. Here "Both ... indicate no significant findings or diseases in the lung" overstates the report: neither tool enumerated any positive finding, so claims of "no diseases" go beyond the evidence.
3. Treat two agreeing bare negatives (zero enumerated findings) as weak, not settled, corroboration for a broad presence query. Unless you can obtain a positive finding or an independent region-specific observation (e.g., xray_phrase_grounding / roi_crop), mark "no" as low-confidence rather than asserting it.
4. Re-read the displayed option map and confirm the letter–text pairing (here A = yes, B = no). In this case "B. no" correctly matched the text "no" — so this was not an option-mapping error; the failure was a wrong conclusion reached by over-reading the negative evidence (the released reference was "A. yes").

Caution about the prior lessons: the retrieved cards ("explicit grounded positive findings override a negative direct QA") require an actual positive finding. Here the grounded report was also negative, so that override did not apply — do not manufacture a conflict that is not in the observations. The card's suggested repair — obtain an independent observation before settling on "no" — was not executed in this trajectory, so it stands only as a caution about the observed failure, not a verified success.
```

## exp_7d7f5f763af905abfdedd50d

来源题 [chexbench_rad_restruct_0229](../../cases/rad_restruct/chexbench_rad_restruct_0229.json) · 活跃

```text
Trigger: When finalizing a yes/no answer to a broad chest-X-ray question such as “Are there any diseases in the lung?” and the grounded report says “lung fields are clear” but also lists a positive abnormality such as “Cardiomegaly,” do not dismiss the positive finding as irrelevant merely because it is cardiac rather than parenchymal lung disease.

Verification action: Before emitting, enumerate all positive findings from the grounded report, not just the negative pulmonary/pleural statements. If any positive finding is within the benchmark’s intended “any diseases” scope — including a non-parenchymal finding like cardiomegaly when prior cases/reference treat it as qualifying — choose “yes,” name that finding in the rationale, and map “yes” to the displayed option text (here B). Do not choose “no” solely because the lung fields are clear. If you deliberately exclude a positive finding as out of scope, state the exclusion explicitly. Finally, re-read the option map and confirm the selected letter and text agree. In this case, “A. no” correctly matched “no,” so the error was a wrong conclusion caused by discarding the positive cardiomegaly finding, not an option-mapping error. This is a caution from the observed failure, not an executed verified repair.
```

## exp_32730b7e554ab2ffbfc6a53b

来源题 [chexbench_rad_restruct_0233](../../cases/rad_restruct/chexbench_rad_restruct_0233.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is there anything abnormal in the cardiovascular system?” and the direct system-specific VQA tool answers “No,” while the grounded report gives only a generic negative such as “No pathological findings for the patient’s age” with no explicit cardiovascular finding.

Verification action: Check whether the grounded report actually names a same-system cardiovascular attribute, such as cardiomegaly, aortic elongation, cardiomediastinal silhouette, pulmonary vasculature, or coronary calcification. If it does not, do not cite the report as confirming “no cardiovascular abnormalities” and do not say “both tools indicate” no abnormality; only the direct VQA addressed that exact attribute. Because a lone blanket negative can be a false negative for a subtle cardiovascular finding, either issue a targeted same-attribute follow-up query or mark the evidence insufficient before finalizing. Then restate the supported proposition and map it to the displayed option map, checking that letter and text agree: “no” maps to A. no, “yes” maps to B. yes. In this case the A/no mapping was correct, but the conclusion conflicted with the released reference (B/yes), and the rationale overstated the generic report as cardiovascular corroboration.
```

## exp_3691d20df44c59680c5c6ce4

来源题 [chexbench_rad_restruct_0234](../../cases/rad_restruct/chexbench_rad_restruct_0234.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice chest-imaging answer about disease in the lymph nodes, when the structure-specific VQA tool has returned “No” and the displayed options are A = yes, B = no.

Observable verification action: Treat the single “No” as provisional, not decisive. Check an actually observed independent result for the same image and same structure/attribute—such as a grounded report or phrase-grounding output—for an explicit lymph-node finding. If an independent result explicitly reports a positive lymph-node abnormality, answer “yes” and map that text to the displayed option. If it explicitly reports a negative, answer “no.” If no independent result is available, do not invent a corroborating statement such as “the grounded report shows no hilar or mediastinal lymphadenopathy”; either obtain/check that evidence or acknowledge that the negative rests only on the VQA tool. Finally, re-read the current option map and confirm the emitted letter matches the chosen text.

In this case, B = “no” was the correct mapping of the tool’s “No,” so the failure was not option mapping. The failure was treating one negative VQA response as conclusive and adding an unsupported negative-report claim, while the released reference was A = “yes.” Correct letter-text agreement alone does not validate the underlying evidence.
```

## exp_caf842d70f726c0665235116

来源题 [chexbench_rad_restruct_0235](../../cases/rad_restruct/chexbench_rad_restruct_0235.json) · 活跃

```text
Trigger: When finalizing a “no” answer to a broad yes/no lung-abnormality question after a grounded report that says only “Right lung is clear,” or otherwise clears only one lung, and does not explicitly state “both lungs are clear” or “no pulmonary abnormality.”

Verification action: Before emitting, quote the exact lung statement and check its scope against the question. “Right lung is clear” does not support a global “no”; it does not establish that the left lung is normal, and it should not be paraphrased as “no pulmonary abnormalities.” Answer “no” only when the evidence explicitly clears both lungs/all relevant lung fields or explicitly reports no lung abnormality. If coverage is unilateral or missing, treat “no” as unsupported and obtain a lung-specific observation or visual check; if an abnormality is identified, answer “yes.” Then map the supported word back to the displayed option and verify the letter–text pair. In this case the terminal letter–text mapping was correct (A = no), so this was not an option-mapping error; it was an evidence-scope error. The model overread “Right lung is clear” as a global normal report, while the released reference was B/yes. The verified lesson is the scope check; the additional-evidence repair was not executed here.
```

## exp_e2f7a2fbcb961b47d4520988

来源题 [chexbench_rad_restruct_0236](../../cases/rad_restruct/chexbench_rad_restruct_0236.json) · 活跃

```text
Trigger: When finalizing a “no” answer to a broad yes/no question such as “Are there any signs in the lung?” after the tools return only generic negatives—e.g., maira2_grounded_report says “Lungs appear clear” with zero grounded boxes and an unverified-findings limitation, while chest_xray_expert returns only a bare “No”—and there is no explicit enumerated rule-out or positive finding.

Verification action: Before emitting, re-read the displayed option map and confirm the letter–text pair (here A = no, B = yes). Then check whether the negative evidence actually covers the question’s broad attribute: a generic “clear” impression or bare “No” is a low-specificity negative, not proof that no sign exists. If no region-specific corroboration or enumerated absence is available, do not present the negative as a settled “no abnormalities”; obtain an independent targeted observation (e.g., xray_phrase_grounding/ROI) or treat the “no” as low-confidence. In this case the letter–text mapping was correct and the terminal choice did use the tool results, but the conclusion was still wrong against reference B yes: two generic negatives were false negatives. The reason also over-attributed “no abnormalities” to a report that only said “Lungs appear clear” and a QA tool that only said “No.” The targeted check was not run here, so this remains a caution about the observed failure, not a verified repair.
```

## exp_72f70d713efa3dbfbb1acc89

来源题 [chexbench_rad_restruct_0237](../../cases/rad_restruct/chexbench_rad_restruct_0237.json) · 活跃

```text
Trigger: When a yes/no multiple-choice question asks whether a named anatomic system has “anything abnormal,” and the proposed “no” rests on tool wording that is narrower (“no signs of acute abnormalities”) or on a single model-generated broad impression (“osseous structures are unremarkable”), especially when the final reasoning counts such statements as independent broad negatives.

Verification action: Before finalizing “no,” quote the exact observation and check that it addresses the same system and the same breadth of attribute—broad “any abnormality/disease,” not merely “acute” findings or a selected sublist. Do not describe a narrower statement as if it were a broad negative. If the only broad negative is an unconfirmed model report, issue a targeted system-specific broad query or mark the evidence as insufficient rather than presenting it as settled. If any observation reports a relevant abnormality in that system, answer “yes.” Then restate the supported answer word and map it back to the displayed option map, checking that letter and text agree. In this case, “B. no” matched option B = no and A = yes, so the error was not option mapping; the released reference was A = yes, and the terminal reason overstated “no signs of acute abnormalities” plus “osseous structures are unremarkable” as two independent broad negatives.
```

## exp_7170d684248a6c29f717e5ea

来源题 [chexbench_rad_restruct_0219](../../cases/rad_restruct/chexbench_rad_restruct_0219.json) · 活跃

```text
Trigger: Before finalizing a yes/no answer to “Are there any foreign objects?” when the visual-QA tool was asked that exact question and answered “Yes,” and a grounded report names a specific implanted device on the same image—e.g., a right chest wall port-a-cath.

Verification action: Re-read the exact question and the tool prompt to confirm the “Yes” was for “foreign objects,” not merely a broader category such as “medical devices” or “hardware.” Then check that the grounded report identifies a concrete indwelling/implanted object with location support, not just a prompted label, and that no other observation conflicts. If the exact-question positive and the specific implanted-device finding agree, accept “yes” as supported; map the word “yes” back to the current option map (here A: “yes”) and confirm the letter and text match before emitting “A. yes.” This case was correct and its final letter/text matched the reference, but the reusable safeguard is the exact-question/specific-object agreement plus live option-map check, not the correct grade alone.
```

## exp_e0f9012d4d9e9d402a2fb572

来源题 [chexbench_rad_restruct_0220](../../cases/rad_restruct/chexbench_rad_restruct_0220.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there any diseases/abnormalities in [named anatomic system]?” and a system-specific VQA tool returns a bare negative, or when available observations conflict.

Verification action: Before choosing “no,” check an independent grounded report or targeted same-system observation for findings that explicitly belong to the named system and attribute. If any same-system abnormality is listed, answer “yes.” For a cardiovascular question, “aorta is tortuous and calcified” is same-system support for “yes”; “heart size is normal” or a negative limited to a sublist does not establish broad “no.” If the VQA tool says “No” but the grounded report lists a same-system cardiovascular abnormality, do not let the single blanket negative override the report; use the supported positive finding and do not claim both tools confirmed. Then restate the supported answer word and map it to the displayed options, checking letter and text agree.

In this case, `chest_xray_expert` returned “No,” but `maira2_grounded_report` listed “The aorta is tortuous and calcified,” which is a cardiovascular abnormality. The final “A. yes” was therefore evidence-supported and correctly mapped to option A = “yes”; the initial negative was properly not treated as decisive.
```

## exp_a5559edc52ce47d23b2716d1

来源题 [chexbench_rad_restruct_0222](../../cases/rad_restruct/chexbench_rad_restruct_0222.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to a broad question such as “Are there any signs in the lung?” and the grounded report contains at least one positive finding localized to the lung (for example, “Right upper lobe azygos fissure”), even when mixed with negative or non-lung findings.

Verification action: Before emitting, separate positive lung-localized findings from negatives and non-lung findings. If any positive finding names a sign within the lung, set the supported answer text to “yes” even if it is benign or an anatomical variant; do not let “no pneumothorax/effusion” or “tortuous aorta” override it. Then re-read the displayed option map and confirm the letter–text pair for “yes” (here B = yes; A = no). Cite only the qualifying lung finding as support. If no positive lung-localized finding exists, “no” is supported. In this source case, the azygos fissure was the qualifying lung sign, the terminal choice B/yes matched the released reference, and no option-mapping or evidence-loss error occurred.
```

## exp_6c7e497ce24f0880e041b1f8

来源题 [chexbench_rad_restruct_0223](../../cases/rad_restruct/chexbench_rad_restruct_0223.json) · 活跃

```text
Experience: When finalizing a yes/no multiple-choice answer to “Are there any diseases/abnormalities in [named anatomic system]?”, first check the exact system-specific tool observation against the same object and attribute asked.

Trigger: You are about to answer a yes/no option question asking whether a named anatomic system has any disease or abnormality, and a tool was queried about that system.

Observable verification action: Read the tool result text and confirm it explicitly names the same system and the broad attribute “disease/abnormality,” not merely a narrow exclusion such as “no acute abnormality” or “no fracture.” If the tool explicitly reports an abnormality/disease in that system, use “yes” and map it to the displayed option letter, checking that letter and text agree. If the only negative support is narrow, blanket, general, or from a different image/context, do not finalize “no” without a targeted same-image follow-up or an insufficiency flag. If tool results conflict, do not silently pick one; re-query or flag the conflict.

In this case, the targeted chest_xray_expert query asked about the skeletal system including ribs, clavicles, scapulae, spine, and shoulders, and the observation was “Yes.” The terminal answer “B. yes” matched option B text “yes” and the released reference B. This was a supported conclusion, not an option-mapping error and not an evidentiary overreach. A correct final grade alone does not prove the procedure, but here the terminal choice did use the explicit same-system positive evidence.
```

## exp_55e225a999aa0b7e85f1171c

来源题 [chexbench_slake_0010](../../cases/slake/chexbench_slake_0010.json) · 活跃

```text
Trigger: When finalizing a yes/no image-plane question such as “Is this a coronal section?” and the draft answer is “no” because the image is a frontal chest X-ray/projection rather than a CT/MRI cross-sectional slice.

Verification action: Before emitting, check for an observed tool result, metadata, or explicit image-plane classification that uses the question’s terminology. Do not replace that check with a general modality argument about projection versus cross-sectional slice. If the intended labeling treats a frontal/coronal-plane image as a coronal section, the supported answer text is “yes”; then re-read the current option map and state the exact letter and text together—here A = “no” and B = “yes,” so the correct terminal form is “B. yes.” In this case, “A. no” correctly matched option A’s text, so the error was not letter/text mapping; the error was using an unsupported semantic distinction to overrule the released reference “yes.” If no direct plane evidence is available, mark the plane label as unverified rather than treating the CT/MRI “section” definition as decisive.
```

## exp_a300eb28afa5cab97f90dd66

来源题 [chexbench_slake_0005](../../cases/slake/chexbench_slake_0005.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there abnormalities in this image?” after a direct chest X-ray QA tool answers “Yes” and a same-image grounded report lists a specific abnormal finding.

Verification action: Before emitting, state the supported answer word from evidence that addresses the exact question. Treat the answer as “yes” if the direct tool answered the abnormality question affirmatively or the report contains at least one explicit abnormal finding; normal statements about other attributes do not cancel that finding. Then re-read the displayed option map and choose the exact letter/text pair — here B. yes, not A. no. Check that the final reason cites an actually observed abnormal finding from the same image and does not cite normal findings as proof. If the direct answer and report conflict, flag or query for confirmation rather than silently choosing. In this case, chest_xray_expert returned “Yes” and MAIRA-2 reported a calcified granuloma in the left midlung field, so B/yes is supported; the correct grade alone does not prove that the evidence and option-mapping checks were actually performed.
```

## exp_2bf55ef3de6fd79c284e14e1

来源题 [chexbench_slake_0006](../../cases/slake/chexbench_slake_0006.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to an imaging-modality question such as “Is this image taken via X-Ray?”, especially after reasoning from image features like bone/air contrast or radiographic markers.

Observable verification action: Before emitting the final answer, restate the supported proposition in words (“yes, this is an X-ray”), locate that exact text in the displayed option map, and confirm the emitted letter and text agree as “A. yes.” Check that the cited evidence—white bony structures, dark air-filled lungs, and markers such as “PORTABLE” and “L”—actually supports the X-ray modality claim and does not conflict with any tool result. In this case the supported conclusion and option mapping were correct and the reference confirms A/yes, but the final response should still be checked for a letter–text match because a correct grade alone does not prove the mapping was verified.
```

## exp_7288c734fbe0c55484420ab6

来源题 [chexbench_slake_0007](../../cases/slake/chexbench_slake_0007.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Can [condition] be observed in the [left/right] lung?” after a grounded report names a lateralized focal finding and phrase grounding returns a box for that same phrase.

Verification action: Before emitting, state the exact supported answer word and the evidence separately. Check that the grounded finding names the correct side and region—here “Right upper lobe infiltrate” supports the right lung—and that the phrase-grounding result is for the same phrase and same side/box, with no conflicting tool result. Treat “infiltrate” as consistent with pneumonia rather than as an explicit pneumonia diagnosis, and keep the rationale limited to what the tools actually returned; unrelated findings such as left chest tube or “no definite pneumothorax” neither support nor contradict the right-lung pneumonia question. Then re-read the entire displayed option map, map the supported text “yes” to its exact option, and confirm the letter–text pair agrees—here “B. yes,” which matches the reference “B / yes.” If an earlier supported conclusion is about to be dropped, trace back to the exact observation before changing it. A correct final grade alone does not show that these evidence and option-mapping checks were performed.
```

## exp_06fc89fc79dd42a2dc25226f

来源题 [chexbench_slake_0009](../../cases/slake/chexbench_slake_0009.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer asking whether an image is a named anatomical plane or projection (e.g., “Is this a coronal plane?”), especially when the rationale relies on general modality/projection knowledge rather than a recorded imaging-tool observation.

Verification action: Before emitting, reduce the supported answer to the exact word (“yes” or “no”), re-read the entire current option map, and pair that word with the exact displayed letter and text. Compare the resulting letter/text with the released reference only after that mapping. Also audit the rationale for evidence provenance: if no tool observation directly addressed the same plane/projection question, state the conclusion as an image/projection inference and do not imply that a tool confirmed it. In this case, “B. yes” matches option B = “yes” and the reference B/yes, but no imaging-tool observation was recorded, so the correct grade supports an option-mapping check, not a claim that a tool-based coronal-plane verification occurred.
```

## exp_6f944e382182c9703256ecaa

来源题 [chexbench_slake_0022](../../cases/slake/chexbench_slake_0022.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice question asking whether an image has “any abnormalities,” and an earlier tool directly answered that exact question “yes,” but you are about to choose “no” because a later report says “normal” or a verifier labels “no” as correct.

Verification action: Before emitting the answer, retrieve the earliest direct answer to the exact abnormality question and compare it with the current option map. If that direct answer is “yes,” do not override it with “no” based only on a general normal report, clear lungs, normal heart size, or a verifier’s “correct” label. Require a same-image observation that explicitly addresses the exact “any abnormality” attribute and specifically explains away or resolves the positive finding. If that explicit reconciliation is missing or still conflicting, treat “yes” as the supported answer text, map it to the displayed option, and check that the letter and text agree. If overriding to “no,” the final reason must name the direct positive evidence and cite same-object evidence that actually invalidates it, not merely restate a normal report. In this case, CheXagent directly answered “Yes” to the exact chest X-ray abnormality question; MAIRA-2 gave a normal report, and the verifier endorsed “B. no” while also noting prominent lower-zone opacities and the unresolved CheXagent/MAIRA-2 conflict. The terminal “B. no” was not an option-mapping error (A = yes, B = no); it lost an earlier direct positive answer that matched the reference.
```

## exp_636ccb066e593d9094d221fa

来源题 [chexbench_slake_0008](../../cases/slake/chexbench_slake_0008.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is this a study of the [named anatomical region]?”, where the question is about study type/anatomical coverage rather than disease presence.

Verification action: Restate the supported option text exactly (“yes” or “no”), re-read the displayed option map, and emit the letter–text pair whose text matches—here “A. yes.” Then verify that the rationale addresses the same object and attribute: it must describe the study as involving the chest/thoracic region, not merely mention chest findings or abnormality. If tool observations exist, confirm they explicitly address the study/region; if none exist, keep the rationale limited to visible image evidence and do not imply tool confirmation. In this case “A. yes” matches the reference A/yes, and the rationale identifies a frontal chest radiograph; the reusable lesson is to perform the text-to-letter and region/attribute checks at finalization, because a correct grade alone does not prove those checks were made.
```

## exp_b3a14aae6fff8b9340249279

来源题 [chexbench_slake_0011](../../cases/slake/chexbench_slake_0011.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer about whether an image is a named section or plane (e.g., coronal), especially when the draft rationale uses a plane term and prior retrieved experiences warn about option-letter drift.

Verification action: Re-read the current option map and explicitly pair the supported answer word with its displayed letter and text. In this case, the rationale says the image shows the coronal plane, so the supported word is “yes”; the current map makes that “B. yes,” not a remembered letter from another case. Also check that the rationale’s plane/section term matches the question’s attribute, and do not add an unverified visual claim beyond what was actually observed. If no observation or tool result addresses the same plane/section attribute, flag the conclusion as unverified rather than inferring it from a generic image description. The correct reference match “B/yes” does not by itself prove the mapping and evidence-scope checks were done; the reusable procedure is to use the displayed map and same-attribute support at finalization.
```

## exp_2ca7cf8266ab063a615ac22a

来源题 [chexbench_slake_0012](../../cases/slake/chexbench_slake_0012.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Does this image look abnormal?” after consulting imaging tools, especially when one tool gives a direct yes/no and another gives a grounded report.

Observable verification action: Before emitting, find at least one same-image tool observation that explicitly supports “abnormal”—for example, an expert answer of “Yes” to an abnormality question or a report finding such as a port-a-cath or prominent heart size. Do not let a normal component such as “Lungs are clear” cancel another abnormal finding. Then restate the supported answer word, re-read the entire current option map, and confirm the selected letter and text agree (A = yes, B = no). Also check that the final reason cites only findings actually present in the tool outputs. In this case, chest_xray_expert answered “Yes” and maira2 reported a port-a-cath and slightly prominent heart, so “A. yes” was both supported and correctly mapped; the reusable lesson is to verify same-image abnormality evidence and the final letter–text mapping.
```

## exp_df01381dd6d67567f6aa165b

来源题 [chexbench_slake_0013](../../cases/slake/chexbench_slake_0013.json) · 活跃

```text
Trigger: When finalizing a binary lung-health multiple-choice answer and the executed observations conflict—one report says “The lungs are clear” while another executed tool names a lung abnormality such as “Lung Opacity, Pleural Effusion,” or a related finding such as blunting of the right costophrenic angle.

Verification action: Before emitting, determine the supported answer text from the observed evidence, not from the final rationale alone. If any executed observation explicitly names a lung abnormality or a finding that entails one, the supported text for “Is the lung healthy?” is “no”; do not let a separate “lungs are clear” sentence override that positive finding without explicitly reconciling the conflict. Then re-read the displayed option map and map “no” to the option whose text is exactly “no” (here A = no), confirming the terminal letter and text agree. Cite only tools that actually ran and whose results explicitly address lung health, and confirm the cited finding appears in the observation. In this case, A. no matched the reference; the safer rationale would cite chest_xray_expert’s “Lung Opacity, Pleural Effusion” and the grounded blunting finding while acknowledging, not silently omitting, the grounded report’s “The lungs are clear.” If no executed observation names a lung abnormality, map “yes” to B and check letter–text agreement.
```

## exp_6f649417b0ec67121b8b9f03

来源题 [chexbench_slake_0015](../../cases/slake/chexbench_slake_0015.json) · 活跃

```text
Trigger: When finalizing a binary question asking whether pneumonia/consolidation is visible in a specific lung region, and a direct chest X-ray QA tool answered “Yes” to that exact region/attribute, but the grounded report only enumerated other findings (e.g., right pleural effusion, left lower-lobe nodule, left basal atelectasis) and did not explicitly name pneumonia/consolidation in that region.

Verification action: Before emitting the choice, compare each observation to the exact object and attribute in the question. Here, the direct QA response to “Is there pneumonia or consolidation in the lower right lung?” supports “yes”; the grounded report’s right pleural effusion is a separate finding and is not itself confirmation of pneumonia. Map the supported answer text “yes” to the displayed option whose text is exactly “yes” (A), and confirm that letter and text agree. Then audit the rationale: cite only what was actually returned, e.g., “chest_xray_expert answered yes to pneumonia/consolidation in the lower right lung,” and delete unsupported additions such as “dense opacity observed” or “grounded report confirms pneumonia” unless an observation explicitly says that. If no observation addressed the exact region and attribute, obtain one or avoid asserting “yes.” In this case the terminal “A. yes” was correct and the option mapping was sound; the caution is to preserve the exact-attribute direct evidence without over-attributing it to the grounded report.
```

## exp_884468710bb9b1346455acb4

来源题 [chexbench_slake_0016](../../cases/slake/chexbench_slake_0016.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about lung abnormality after a generic expert returns only “Yes” and a grounded report enumerates specific pulmonary findings—especially when retrieved memory cards concern the opposite answer.

Verification action: Before emitting, state the answer word supported by the current image evidence (“yes”), re-read the entire displayed option map, and select the exact letter–text pair (“A. yes,” not “B. no”). Then audit the rationale against the current grounded report: it must cite findings that directly answer the lung-abnormality question—here pneumothorax, heterogeneous opacities, pleural effusions, and atelectasis—and must not rely on unrelated incidental items such as chest tube, surgical clips, or unchanged cardiomediastinal contours. Confirm the generic expert’s “Yes” does not conflict with the grounded report, and do not copy an opposite-polarity letter from historical memory. If those checks hold, finalize A. yes, which matches the reference. The reusable step is this explicit letter–text and evidence audit, not the correct grade alone.
```

## exp_147bf86e4df7edd48afe270c

来源题 [chexbench_slake_0017](../../cases/slake/chexbench_slake_0017.json) · 活跃

```text
Trigger: When finalizing a binary multiple-choice answer to a positive health-status question such as “Is the lung healthy?” after tools return evidence phrased as presence or absence of abnormality—e.g., chest_xray_expert answers “Yes” to “any signs of lung disease or abnormality?” and the grounded report lists an elevated right diaphragm—check answer polarity before emitting.

Verification action: Convert the observed evidence into the exact answer text required by the health-status question: evidence of abnormality/disease → “no” (the lung is not healthy); evidence of clear/normal lung → “yes.” Re-read the displayed option map (here A = yes, B = no), select the option whose text exactly matches the converted text, and confirm the terminal letter–text pair (here B. no). Do not copy the expert’s “Yes” to the abnormality question into the health-status answer; “Yes, there are signs of abnormality” supports “No, the lung is healthy” only if the question were “Is the lung abnormal?” Also confirm that the cited observations were actually executed and address the same object/attribute—lung health or lung abnormality. If a grounded finding and an expert answer conflict, note the conflict and use the explicit observed abnormality rather than silently overriding it. The rationale should say “lungs are not healthy” only when the selected option text is “no,” and the letter and text must agree.

Lesson: In this case B. no matched option B’s text and the released reference B/no. The key risk was polarity inversion—expert “Yes, abnormality” supports “No, healthy”—not an option-mapping error. A correct grade alone is not the check; the observable check is converting the supported health-status claim back to the displayed option text and confirming the letter–text pair.
```

## exp_f037a714421484f69506ac5e

来源题 [chexbench_slake_0019](../../cases/slake/chexbench_slake_0019.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether the image is a study of a named anatomical region—for example, “Is this a study of the chest?”—especially when retrieved pre-answer experience cards concern a different region, a different abnormality, or the opposite answer.

Verification action: Determine the answer word supported by the current image/question (“yes” for a chest study), then re-read the entire displayed option map and select the option whose text exactly matches that word. Confirm the emitted letter and text agree—here “B. yes,” not “A. no”—and compare them with the released reference. Check that the rationale’s findings address the same object and attribute as the question: lungs, ribs, clavicles, and mediastinum support a chest study. Because there were no tool observations in this case, do not attribute the conclusion to a tool and do not treat retrieved historical cards favoring “no” as evidence about the current image. Emit only after this letter–text and region/attribute check.
```

## exp_bc12cfebac6f1b1126d25892

来源题 [chexbench_slake_0020](../../cases/slake/chexbench_slake_0020.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is the lung healthy?” and the observed evidence includes any lung abnormality—for example, maira2_grounded_report names infiltrates or effusion, or chest_xray_expert answers “Yes” to a question about lung abnormalities.

Verification action: Convert the polarity explicitly before choosing: any observed lung abnormality means the lung is not healthy → answer text “no”; no observed lung abnormality means “yes.” Re-read the displayed option map and select the option whose text is exactly the supported answer—here A = “no,” not B = “yes”—and confirm the letter and text agree. Check that the cited observations actually address the lung and that a “Yes” to “any lung abnormalities?” is not mistakenly mapped to “yes, the lung is healthy.” In this case, bilateral lower lobe infiltrates, small left-sided effusion, and the expert’s “Yes” to abnormalities all supported “no,” and the terminal “A. no” matched the reference “A”/“no.”
```

## exp_8bc9508a7d6146561e3de3d5

来源题 [chexbench_slake_0021](../../cases/slake/chexbench_slake_0021.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice CXR answer about a specific localized finding—for example, “mass or multiple nodules in the lower right lung”—and a specialized CXR QA tool returns a bare “Yes” to that exact question while the grounded report mentions only different or resolved findings and does not name the queried mass.

Verification action: Before emitting, confirm the specialized tool’s question matched the same object, attribute, and region; a bare “Yes” to that exact question supports “yes,” but it does not support added details such as “visible rounded opacities” unless an observation states them. Re-read the grounded report and classify it as corresponding, non-corresponding, or conflicting: here it mentions residual fluid and resolved airspace opacity, not a mass, so do not cite it as confirming a mass and do not treat its silence as an explicit denial. Limit the rationale to what was actually observed, such as “chest_xray_expert answered yes to the exact question.” Then map the supported word “yes” back to the displayed option and verify letter and text agree: A. yes, not B. no. If no observed result addressed the exact finding, or if results conflicted, seek corroboration or choose the supported option rather than citing non-corresponding evidence.

Lesson: The original A. yes matched the reference, but the correct grade does not prove the rationale was clean; this case is a caution about over-attributing evidence. The reusable safeguard is exact-question evidence matching, labeling non-corresponding evidence correctly, and confirming the final letter–text pair.
```

## exp_58ec027b91a94d9e4c2fb249

来源题 [chexbench_slake_0025](../../cases/slake/chexbench_slake_0025.json) · 活跃

```text
Trigger: When a binary question asks for a health status such as “Is the lung healthy?” and the options are “A yes / B no,” while the grounded report lists lung abnormalities and a direct QA tool reports “no” or “no focal consolidation.” This specifically guards against flipping a finding into the wrong polarity because another prior lesson says “a lung finding supports yes” for a different question such as “Are there any diseases in the lung?”

Verification action: Before finalizing, restate the answer in full against the exact question: “The grounded report lists pneumothorax and atelectasis, so the lung is not healthy.” Then map that supported text to the displayed option whose text is exactly “no” (here B) and confirm the letter–text pair is B = no. Check that the rationale has the correct polarity: abnormalities support “no” for “Is the lung healthy?”, not “yes.” Do not let a direct QA “no focal consolidation” override explicit grounded lung abnormalities, but also do not use the mere presence of a lung abnormality to select “yes” without checking the question polarity.

Lesson from this case: The terminal answer “B. no” was correct, but the key decision was polarity mapping: a lung abnormality means the lung is not healthy. The same finding would support “yes” for “Are there any lung abnormalities?”, so the procedure must compare the finding to the question’s exact object and attribute and to the exact option text.
```

## exp_36011fd2b0f43b1de521455b

来源题 [chexbench_slake_0026](../../cases/slake/chexbench_slake_0026.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is the lung normal appearing?” after a grounded report lists any pulmonary abnormality such as infiltrate, atelectasis, or effusion, even if the other lung is described as clear.

Action: Before emitting, derive the supported answer word from the report: any reported lung abnormality supports “no”; only normal/clear lung findings support “yes.” Then re-read the displayed option map and select the option whose text exactly matches that word, checking both letter and text—here A = “no” and B = “yes,” so the supported choice is “A. no.” Limit the rationale to the findings that actually support that answer, such as the left lower lobe infiltrate, atelectasis, and effusion, and do not let “right lung is clear” override the abnormal left lung. In this case the terminal choice matched the evidence and the reference; the reusable check is the final answer-word-to-option mapping plus evidence attribution, not the correct grade alone.
```

## exp_81fb8807e66c1bcd13ae64ed

来源题 [chexbench_slake_0027](../../cases/slake/chexbench_slake_0027.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is this image taken via X-Ray?” after visual inspection shows modality cues such as projectional bony thorax, lung fields, and an L orientation marker.

Observable verification action: Before emitting the answer, restate the supported proposition as “the image is an X-ray,” find the displayed option whose text exactly matches “yes,” and confirm the final answer is the letter–text pair “A. yes.” Check that the rationale cites only modality evidence—projectional ribs/clavicles/spine, lung fields, and the L marker—and does not drift into disease findings. If no tool observation is present, do not attribute the conclusion to a tool. If “yes” were mapped to B/no or the letter and text disagreed, that would be an option-mapping error, not a visual conclusion error; correct it before finalizing. In this case the answer A. yes matched the reference A/yes, and the same supported conclusion was carried from the earlier step, but the letter/text and evidence-scope check should still be done because a correct grade alone does not prove the procedure was followed.
```

## exp_d49a8f939d41e22e495293a1

来源题 [chexbench_slake_0028](../../cases/slake/chexbench_slake_0028.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is this a study of [named anatomical region]?” and the rationale relies on only partial or incidental visibility of that region.

Verification action: Confirm the image’s primary field of view and diagnostic focus, not just whether the named region appears incidentally at the edge. If the primary study is the chest/thorax and the neck is only partially included, the supported answer text is “no.” Then map that text to the displayed options and state the letter and text together: here “no” corresponds to “A. no,” not “B. yes.” Check that the rationale says “chest-focused study, not a dedicated neck study” rather than claiming the neck is absent. The retrieved prior experiences about tracheal abnormalities are not evidence for this case because they address a different structure/attribute; require support for the same object—neck as the study focus—and the same attribute—whether the study is dedicated to it. A correct final grade alone does not prove this mapping and focus check were performed.
```

## exp_3579c91222bc04974c588249

来源题 [chexbench_slake_0035](../../cases/slake/chexbench_slake_0035.json) · 活跃

```text
**Trigger**
You are about to finalize a yes/no (presence) answer about a *named region* (e.g., "upper right lung") and the only positive support for "yes" is a phrase-grounding tool (e.g., `xray_phrase_grounding`) that was queried with that very phrase and returned a bounding box.

**Verification action**
Before emitting the choice, separate localization from detection: a phrase-grounding box is produced for whatever phrase you submit, so it confirms *where that phrase would be*, not that the finding is present — using it as proof of existence is circular. Check the independent grounded report's finding list: does any finding explicitly name that region and the abnormality (e.g., "right upper lobe opacity/consolidation")? A generic "bilateral airspace disease" with one large box spanning both lungs does not license a region-specific claim about the right upper zone. If neither the report's wording nor a region-confined box supports the finding, answer the negative option, then map the supported answer text back to the displayed option and confirm letter and text agree.

**What this case shows**
The letter–text pairing (B = yes) was consistent with the option map, so this was not an option-mapping error; the failure was evidentiary. The rationale said "grounded phrase localization confirms a right upper lung opacity," but the grounding step only returned a box for the phrase the model itself supplied, and the report's single bilateral box could not be narrowed to the right upper region. The released reference was "A. no." The correction — requiring independent region-specific evidence before answering "yes" — was not executed here, so it stands as a caution about the observed failure, not a verified repair.
```

## exp_c5e036d358181d4da61521fc

来源题 [chexbench_slake_0037](../../cases/slake/chexbench_slake_0037.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to a regional presence question after a grounded report returns a finding with a bounding box, especially when the finding text and option map must be reconciled.

Verification action: Before emitting, match the observation to the exact object and attribute in the question: confirm the report names the same abnormality and the same laterality/region, and if a bounding box is supplied, check that the box lies in or overlaps the asked region. Derive the supported answer word from that matched evidence (“yes” if the named finding is present there; “no” only if a same-scope observation says absent). Then re-read the displayed option map and write the final choice as a matching letter–text pair—for this case, “B. yes”—confirming that letter and text agree. Keep the rationale limited to the matched finding and box. If the evidence supports the answer text but the selected letter differs, correct the option mapping; if the evidence does not support the answer text, correct the conclusion. A correct final grade alone does not prove this check was performed.
```

## exp_a2f7cbe6791366d6039b5b24

来源题 [chexbench_slake_0038](../../cases/slake/chexbench_slake_0038.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to a general question such as “Does the patient have any abnormalities?” after consulting a direct VQA tool and a grounded report, especially when prior retrieved cases involved region-specific “abnormal?” questions and different option maps.

Verification action: Before emitting, state the supported answer text using the tool observation that directly answers the same question — here the chest X-ray VQA tool returned “Yes” and the grounded report independently listed explicit abnormal findings (“Extensive right-sided infiltrate,” “Less extensive left perihilar infiltrate”), so the supported text is “yes.” Then re-read the entire current option map and pair the exact letter with the exact text: here A = “no” and B = “yes,” so the correct terminal form is “B. yes.” Do not carry over an option letter from prior cases where “no” or “yes” mapped differently; do not treat the report’s negative statements (“No definite pleural effusion,” “No pneumothorax”) as evidence against abnormalities when positive infiltrates are also reported. If the direct QA and grounded report conflicted, prefer the observation that explicitly addresses the question’s object and attribute, and check that the final rationale cites only that supporting evidence.
```

## exp_cf299251a00dcdb0ac90dc0d

来源题 [chexbench_slake_0041](../../cases/slake/chexbench_slake_0041.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there abnormalities in this image?” and the proposed answer is “yes.”

Verification action: Before emitting, require at least one actual observation for this image that explicitly names an abnormality. Do not cite specific findings—such as bilateral interstitial infiltrates, blunting of the right costophrenic angle, or tracheostomy/NG tube—unless those findings are present in the observed image or tool/report output for this case. If no such observation exists, treat the stated reason as unverified even if the final letter is correct. Then map the supported answer word back to the displayed options and check letter/text agreement. Here, “yes” maps to A. yes and matches the reference A/yes, so there is no option-mapping error; the lesson is that the correct grade alone does not establish that the cited evidence was observed.
```

## exp_b7cdf21a03edfb303f59a0c4

来源题 [chexbench_slake_0047](../../cases/slake/chexbench_slake_0047.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer about whether an image is a named anatomical plane or projection (e.g., “Is this sagittal plane?”), especially when the rationale relies on image/projection inference and no tool observation directly addresses that plane.

Verification action: Reduce the supported answer to the exact word (“no” or “yes”), re-read the entire displayed option map, and pair that word with the exact shown letter and text. In this case, the supported word is “no,” the current map is A = “no,” B = “yes,” and the terminal answer “A” must be checked as “A. no,” not remembered from another case. Also check that the rationale uses the same plane/projection attribute as the question—here it says frontal rather than sagittal, which supports “no.” If no recorded tool result directly addressed the plane/projection, state the conclusion as an image/projection inference rather than implying tool confirmation. A correct reference match alone does not prove these mapping and evidence-scope checks were performed.
```

## exp_e7aa7e7e13a4a44c56386ae3

来源题 [chexbench_slake_0036](../../cases/slake/chexbench_slake_0036.json) · 活跃

```text
Trigger: You are finalizing a multiple-choice or binary answer after an earlier tool result or intermediate response already states the supported answer text — especially when the rationale says “present,” “infiltrates,” or “consolidation,” and the terminal output is about to emit only a letter. In this case, the expert tool answered “Yes” to pneumonia/consolidation in the lower left lung, and the intermediate response concluded “Yes,” but the final answer was emitted as “A.”

Verification action: Before emitting the final letter, re-read the displayed option map and map the supported answer text exactly to its letter. If the supported text is “yes” and the map is A = no, B = yes, the final letter must be B. Then verify that the terminal letter and the terminal reason agree: a reason asserting pneumonia/consolidation must not be paired with the letter for “no.” If the letter contradicts the supported text and rationale, correct the letter to the option whose text matches the supported text. This was an option-mapping/finalization error, not an evidence error: the tool observation addressed the same object and attribute as the question, and the earlier conclusion used it; the supported “Yes” was lost when the final letter was chosen.
```

## exp_57b823141ac321af1e12ea54

来源题 [chexbench_slake_0042](../../cases/slake/chexbench_slake_0042.json) · 活跃

```text
Trigger: You are about to finalize a “no” answer to a region-specific presence question such as “Can pneumothorax be observed on the lower left lung?” when the grounded report names the finding elsewhere in the same lung field (e.g., “small left apical pneumothorax”) and/or mentions only a different finding in the queried region (e.g., “left base atelectasis”), with no explicit statement that the finding is absent from the lower left lung.

Verification action: Before choosing, separate “not mentioned in that exact subregion” from “explicitly absent there.” Check the reported finding’s box/region or run a region-specific check such as phrase grounding or ROI review for pneumothorax in the lower left lung. If the finding is already confirmed in the same left lung/hemithorax and no observation explicitly denies lower-left involvement, do not convert that into “no” merely because the report labeled it apical; for a “can be observed” presence question, use the supported yes answer unless a direct regional observation says no. Then map the supported word back to the displayed option map and confirm letter and text agree (here B = yes, A = no). This case was not an option-mapping error—A/no matched—but a wrong conclusion from treating an unmentioned subregion as absent despite a reported left pneumothorax and a released reference of yes.
```

## exp_b7c73c1581d2cb25af2a4f24

来源题 [chexbench_slake_0060](../../cases/slake/chexbench_slake_0060.json) · 活跃

```text
Narrow trigger: When finalizing a negative answer (“no”/A) to a region-specific pneumonia/consolidation question based on a single chest_xray_expert response of “No,” and the draft rationale claims corroboration such as “both the focused assessment and the prior grounded report” — especially when no grounded-report call appears in the executed steps.

Observable verification action: Before emitting, inspect the executed observation list and match every evidence source named in the rationale to an actual tool call. If a cited “prior grounded report” or other corroborating source is absent, remove that claim; a bare “No” from one VQA model must not be described as agreement with an unobserved report. Confirm the observed result addresses the same object and attribute as the question (lower right lung; pneumonia/focal consolidation). If no independent observation exists, either obtain one or state that the negative is uncorroborated, rather than treating it as settled. Finally, map the supported answer word to the displayed option and confirm letter and text agree (A = no, B = yes). In this case the A/no mapping was correct, so the failure was not option mapping but an unsupported/wrong negative conclusion; the referenced prior grounded report was never executed. Because the released reference was “yes,” this is a caution about the observed single-negative failure, not a verified repair.
```

## exp_c478e08e4d385107fd802aaa

来源题 [chexbench_slake_0039](../../cases/slake/chexbench_slake_0039.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to "Is the lung healthy?" (or any binary lung-health question) and an executed observation—such as a grounded report—names lung findings, especially when the option order might place "yes" or "no" at either letter.

Verification action: First derive the answer text from the evidence, not from the rationale. Any explicit lung abnormality—nodular opacities, pleural effusions, consolidation, atelectasis—means the lung is not healthy, so the supported text is "no"; if no observation names a lung abnormality, the supported text is "yes." Then re-read the displayed option map and pick the option whose text exactly matches that word, and confirm the terminal letter and text agree. In this case the grounded report named diffuse bilateral nodular opacities, bilateral pleural effusions, and focal consolidation—all findings that address the lung itself—so "no" was correct, and since the displayed map was A = yes, B = no, mapping "no" to B was correct.

Caution: do not carry over the option order from a prior case. Earlier lung-health cards had A = no / B = yes, so a letter that was right there would be wrong here. Re-reading the current map and checking letter–text agreement is the load-bearing step, because the same conclusion ("no") can map to different letters across questions. Also confirm the cited findings actually appear in the executed observation and concern the lung, rather than citing an unrelated structure or a finding that was never returned.
```

## exp_98eede21d4422a04a1f3798a

来源题 [chexbench_slake_0040](../../cases/slake/chexbench_slake_0040.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether a finding (for example, pleural effusion) is present in a named subregion (for example, the upper right chest), and the grounded report returns an effusion-related or localizing finding in a different region—such as blunting of the right costophrenic angle in the lower chest—plus broad statements like “the lungs are clear.”

Verification action: Before emitting the choice, compare the reported finding’s stated location, and any provided box location, with the queried region. Confirm that the only positive finding is outside the target region. If no same-region finding is reported, use “no” for the target question but phrase the rationale precisely: the only reported change is blunting at the right costophrenic angle in the lower chest, and no upper-right-chest effusion is described. Do not use “lungs are clear” as though it directly excludes pleural effusion, and do not claim the report explicitly negated upper-right pleural effusion unless it did. Then re-read the displayed option map and write the answer as a letter–text pair, confirming that A = no and B = yes here. If the finding overlaps the target region or the report is contradictory, do not answer no from outside-region evidence; obtain or compare another same-region observation. In this source case the letter/text mapping was correct (“A. no,” reference “A/no”), so the reusable lesson is the region-and-attribution check, not an option-mapping repair.
```

## exp_2df64d8e7905e8d7ae41724f

来源题 [chexbench_slake_0043](../../cases/slake/chexbench_slake_0043.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Does this image look abnormal?” after a direct imaging-expert answer and a grounded report that names a medical device such as a PICC line but says the lungs/heart are otherwise normal.

Verification action: Before emitting, inspect the exact tool text. Require either a tool explicitly answering the same image and question with “Yes,” or a report naming a concrete abnormal finding/device such as “Right PICC line.” Do not let “otherwise normal” lung/cardiac statements cancel an explicitly reported device when the direct abnormality question was answered “Yes.” Restate the supported answer text as “yes.” Then re-read the entire current option map and choose the displayed option whose text is exactly “yes”—here B—and check that the selected letter and text agree. If only an incidental device is listed and no tool directly answers the abnormality question, query verification or an abnormality-specific tool instead of inferring alone. Do not reuse an option letter from a prior experience; the current displayed options control the mapping.
```

## exp_32cbc683f4bed3092fb904eb

来源题 [chexbench_slake_0044](../../cases/slake/chexbench_slake_0044.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether the lung is normal-appearing by reusing a conclusion from an earlier verified question on the same image, especially when the current option letters may differ from the earlier question’s option map.

Verification action: Before emitting, state the supported answer word from the evidence (“no” for not normal/abnormal), then re-read the current displayed option map and select the option whose text exactly matches that word, confirming the letter and text together. In this case current A = “no” and B = “yes”; the earlier verified “B. no” belonged to the earlier option map, so copying that letter into the current question would have produced the wrong answer. Also check that the earlier conclusion addressed the same image and attribute, and that conflicting tool reports (e.g., clear lungs vs. expert/prior abnormality) are not misattributed; keep the rationale tied to the verified prior abnormality or conflict rather than an unsupported “normal” finding. Final check: “A. no” matches the supported word “no” and the reference, but the reusable step is the explicit letter–text match against the current option map, not reliance on the prior letter or a correct grade alone.
```

## exp_e1a80b486bb690ce1a1c8fa5

来源题 [chexbench_slake_0045](../../cases/slake/chexbench_slake_0045.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to a global image-abnormality question such as “Are there abnormalities in this image?” with options like A = no and B = yes, especially when the draft reason lists specific imaging findings.

Verification action: Before emitting, restate the supported answer word (“yes” or “no”), re-read the entire displayed option map, and map that word to the exact choice, checking that the letter and text agree. Then check the rationale against the actual observations: every cited abnormality must come from an observed result for this same image and must support the broad conclusion “abnormalities present”; if the observations are empty or do not address the same object/attribute, do not add specific findings to the reason—obtain a direct observation or keep the rationale limited. In the supplied case, B. yes matches the option map and the reference, but the step record shows no observations, so the reusable lesson is option-agreement plus evidence-attribution checking; the correct grade alone does not prove those checks were performed.
```

## exp_c97b88a711a10a1f45a9f8af

来源题 [chexbench_slake_0046](../../cases/slake/chexbench_slake_0046.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether pneumonia/opacity is present in a named lung region, after `maira2_grounded_report` returns a boxed finding in that region and an `roi_crop` of that box has been reviewed.

Verification action: Before emitting the choice, state the supported answer text (“yes”), re-read the full option map, and write the exact letter–text pair (“A. yes,” not an assumed letter). Then check the rationale against the actual observations: the grounded report must name the same region and attribute as the question (here, “focal area of increased markings in the right upper lobe”), and the crop box must match that finding. Any statement that the crop “confirms patchy opacity consistent with pneumonia” is a visual inference from the image, not quoted tool text; label it as such and do not attribute it to the report. If the region/laterality, letter–text pairing, or evidence attribution disagrees, correct it before finalizing. In this case the final A/yes choice and right-upper-lobe evidence were aligned, but a correct grade alone would not prove the verification was performed.
```

## exp_c42d36a9ba56870cb712356a

来源题 [chexbench_slake_0048](../../cases/slake/chexbench_slake_0048.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is the lung healthy?” and the terminal rationale cites abnormal lung findings while the displayed options are a letter–text map such as A = no, B = yes.

Verification action: Before emitting, derive the supported answer text from executed observations, not from the rationale alone. If any executed observation explicitly names a lung abnormality or a finding that entails one—pleural effusion, atelectasis, lung opacity, infiltrate, etc.—the supported text is “no”; only if no executed observation names a lung abnormality is it “yes.” Then re-read the displayed option map and choose the option whose text exactly matches the supported text, confirming the terminal letter and text agree. Also check that every abnormality cited in the final rationale appears in an actually executed tool result for this image; do not present unobserved findings as verified evidence. In the supplied case, the terminal “A. no” text-match with the reference “A”/“no” supports option mapping, but with no tool observations shown it does not independently verify the cited imaging findings.
```

## exp_bff0109bd7a8ca7aa452b04b

来源题 [chexbench_slake_0050](../../cases/slake/chexbench_slake_0050.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about a finding at a named lung location, and the executed evidence includes a direct QA answer plus a grounded report or phrase-grounding result whose stated location may differ from the question.

Action: Before emitting, re-read the displayed option map and map the supported answer word to the exact option text, checking letter and text together—here “yes” must be “A. yes,” not merely “A.” Compare the terminal letter–text pair with the released reference when available. Then list the exact finding, attribute, and location from each actually executed observation. Do not call the evidence “consistent” if the grounded report says “left mid-lung” while the question asks “lower left lung”; treat that as a location mismatch, not corroboration. Use the direct QA answer and/or a phrase-grounding box only for the exact requested location, and keep the final rationale limited to what those observations actually show. In this case the terminal answer “A. yes” matches the reference, but the rationale overclaims that all tools identified a lower-left mass; the grounded report names a left mid-lung nodular density. If exact-location evidence is negative or absent, choose “no”; if evidence conflicts, resolve the object/attribute/location before mapping to the option.
```

## exp_daab75a40ac74c931911ccd9

来源题 [chexbench_slake_0051](../../cases/slake/chexbench_slake_0051.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there abnormalities in this image?” after consulting an imaging report or image-QA tool, especially when the rationale cites specific report findings.

Verification action: Before emitting, extract the exact answer word supported by the tool observation, using only text that explicitly addresses abnormalities in the same image. For example, “bilateral lower lobe infiltrates” and “small left-sided effusion” support “yes,” while a generic normal statement or a finding in another region does not. Then re-read the entire displayed option map and map the supported word to the exact option, checking that letter and text agree. In this case the supported text was “yes” and the option map was A = no, B = yes, so “B. yes” was correct. Also confirm the rationale cites only tool findings actually returned as evidence; a correct grade alone does not prove this evidence-to-option check was performed.
```

## exp_2ea80b6ab974d3f8eea3930e

来源题 [chexbench_slake_0054](../../cases/slake/chexbench_slake_0054.json) · 活跃

```text
Trigger: When finalizing a yes/no lung-health multiple-choice answer to “Does the lung look unhealthy?” with an option map such as A = “yes,” B = “no,” and the rationale cites a lung abnormality—e.g., a calcified granuloma—as support.

Verification action: First convert the finding to the question’s polarity: any documented lung abnormality supports “unhealthy” → answer text “yes,” not “no.” Then re-read the entire displayed option map, select the option whose text is exactly “yes” (here A), and confirm the terminal letter and text agree. Do not double-reverse “unhealthy” into “no,” and do not choose a letter without checking its displayed text. If no executed observation actually names a lung abnormality or unhealthiness, do not treat an unobserved “prior report” as verified evidence; note the evidence limitation instead. In this case, “A. yes” matched the reference “A”/“yes,” but the correct grade alone does not prove the evidence procedure was verified because no tool observation was executed.
```

## exp_c37bd0a18c85f0182eac16c0

来源题 [chexbench_slake_0056](../../cases/slake/chexbench_slake_0056.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether an image is abnormal, and the final reason claims that multiple tools "identify" specific abnormalities or findings.

Observable verification action: Before emitting, take each specific finding named in the reason and locate the exact tool output that states it. Do not credit a tool with identifying specific findings if it only returned a generic "Yes"/"No" or a blanket report; attribute each listed finding only to the tool whose text actually contains it. Then state the supported answer word, re-read the displayed option map, and confirm the chosen letter and text agree.

Applied to this case: the step-0 CheXagent output was the single word "Yes" in answer to a question that mentioned pleural effusion, consolidation, and cardiomegaly. That directly establishes "abnormal = yes," but it does not individually confirm cardiomegaly, pulmonary vascular congestion, bilateral effusions, or atelectasis. Those specifics came from the step-1 MAIRA-2 grounded report ("The heart size is enlarged," "pulmonary vascular congestion," "bilateral effusions," "compressive atelectasis at both lung bases"). The final reason's phrasing "Both CheXagent and MAIRA-2 identify multiple abnormalities including..." therefore over-attributes the finding list to CheXagent. The answer itself remains correct because the direct "Yes" plus the corroborating report both support "yes," and the option map (B = yes) matches. Also note the MAIRA-2 report's tube/line entries (endotracheal tube, PICC lines, NG tube) are device placements, not the abnormalities being cited, so they should not be counted as evidence of abnormality.

Caution supported by this trajectory: a correct letter does not validate the reason. Check finding-by-finding attribution against the exact tool text, exclude incidental device findings from "abnormalities" evidence, then verify the supported word ("yes") maps to the displayed choice (B) with matching text.
```

## exp_7c97c827113aab0dfa2d2e61

来源题 [chexbench_slake_0057](../../cases/slake/chexbench_slake_0057.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether an image is an X-ray, especially when a retrieved experience card or similar case used a different option order or assigned “yes” to a different letter.

Observable verification action: Restate the supported answer as the exact text “yes,” re-read the current displayed option map, and match that text to its current letter; emit the current letter–text pair (here “B. yes”). Do not copy a letter from a similar historical case, such as an old “A. yes,” unless the current map actually assigns “yes” to A. Confirm the rationale cites only modality evidence and does not claim tool support when no tool observation exists; also confirm the earlier supported conclusion was carried through unchanged. In this case “B. yes” matched both the current map and the reference B/yes, so no repair was needed, but the letter–text and current-option-map check is still required because a correct grade alone does not prove the procedure was followed.
```

## exp_9d044e61a4fd2bd60ae31977

来源题 [chexbench_slake_0065](../../cases/slake/chexbench_slake_0065.json) · 活跃

```text
Trigger: When answering a yes/no question such as “Can pneumonia be observed on the left lung?” from a grounded report, and the only relevant left-lung finding is “left perihilar infiltrate” (or another nonspecific infiltrate/atelectasis) rather than an explicit report of pneumonia or consolidation, and you are about to equate “infiltrate” with “pneumonia” and answer yes.

Verification action: Before finalizing, re-read the grounded report for the exact queried entity and region: does it explicitly state pneumonia or consolidation in that lung? Do not treat “infiltrate” alone as proof of pneumonia. If the report does not explicitly confirm pneumonia/consolidation there, do not emit yes solely from the infiltrate finding; obtain a region-specific confirmation such as phrase grounding, ROI review, or expert VQA, or answer no if the options require a direct presence judgment. Then map the supported answer word back to the displayed option map and check that letter and text agree. In this case, A/yes matched the option map, so this was not an option-mapping error; it was a wrong conclusion from over-interpreting “left perihilar infiltrate” as pneumonia, while the released reference was B/no. The grounded report addressed the left lung but did not explicitly address pneumonia, and the terminal rationale used it as if it did. The repair was not executed here, so this stands as a caution about the observed failure, not a verified success.
```

## exp_4bcae5430c83e320ffdd5862

来源题 [chexbench_slake_0066](../../cases/slake/chexbench_slake_0066.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is this a study of the [named anatomical region]?”, especially when the question concerns study type or anatomical coverage rather than disease presence.

Verification action: Restate the answer text supported by the visible evidence (“yes” if the image is a frontal chest radiograph; otherwise “no”), then re-read the displayed option map and select the option whose text exactly matches it. Confirm that the letter and text agree—in this case the current map is A = no and B = yes, so supported “yes” must be emitted as “B. yes,” not recalled from a different option map. Check that the rationale addresses the same object and attribute as the question: it should state that the study covers the chest/thoracic region, not merely mention chest-related findings or abnormality. If no tool observations exist, keep the rationale limited to visible image evidence and do not imply tool confirmation; if tool observations exist, confirm they explicitly address the study/region and do not conflict. Emit the answer only after the letter–text and region/attribute checks agree.
```

## exp_08231c3cbdb619667f7f6823

来源题 [chexbench_slake_0067](../../cases/slake/chexbench_slake_0067.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is the lung healthy?” and an executed observation contains an explicit lung abnormality—e.g., maira2_grounded_report says “mild left basilar atelectasis”—or chest_xray_expert answers “Yes” to a question explicitly about lung abnormalities, pause before emitting.

Verification action: Convert the evidence to the question’s polarity first: any observed lung abnormality means the lung is not healthy, so the supported answer text is “no”; no observed lung abnormality means “yes.” Re-read the displayed option map and select the option whose text exactly matches the supported answer. In this case the map was A = no, B = yes, so “no” maps to A, and “A. no” is correct. Confirm the cited finding actually appears in the tool observation and addresses lung health, and do not mistake “Yes” to “any lung abnormalities?” for “yes, the lung is healthy.” Check that the terminal letter and text agree, and use this evidence/polarity check rather than relying on the final grade alone.
```

## exp_f3df064a5591194534e4a470

来源题 [chexbench_slake_0070](../../cases/slake/chexbench_slake_0070.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about an anatomical region after a direct visual QA tool returns a one-word answer such as “Yes” or “No,” and the draft rationale also cites prior reports or specific imaging findings.

Verification action: Before emitting, restate the supported answer word from the observed tool result; re-read the entire displayed option map and select the option whose text exactly matches that word, checking letter and text together. Then audit the rationale against the actual observation list: cite only observations that address the same object and attribute as the question, and do not claim a second tool result or specific findings such as pneumothorax or increased opacity unless those results are present and nonconflicting. In this case, the observed chest_xray_expert result was “Yes,” which correctly maps to “B. yes” and matches the reference; the extra citations in the final rationale go beyond the shown observation and should be removed or verified before finalizing.
```

## exp_0da02bc66ee93be1cca259f4

来源题 [chexbench_slake_0071](../../cases/slake/chexbench_slake_0071.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer asking whether an image is a named anatomical plane or projection (e.g., “Is this a coronal plane?”), especially when the draft rationale relies on image-type/projection inference and the recorded observations or tool results are empty or do not directly address that same plane.

Verification action: Reduce the supported conclusion to the exact option word (“yes” or “no”), re-read the entire current option map, and pair that word with the displayed letter and exact text. In this case, the supported word “yes” maps to B = “yes,” and the terminal “B. yes” agrees with the released reference B/yes. Also check that the rationale’s plane attribute matches the question’s attribute (coronal plane vs. coronal-plane inference) and that the letter is not remembered from another case. Because no tool observation addressed whether this image is a coronal plane, label the conclusion as an image/projection inference rather than tool-confirmed evidence; the correct reference match alone does not prove that the option-mapping and evidence-scope checks were performed.
```

## exp_5cf7ab8ec301efc4afae3b59

来源题 [chexbench_slake_0081](../../cases/slake/chexbench_slake_0081.json) · 活跃

```text
**Trigger:** You are about to finalize a "no"/"absent" answer to a region-specific presence question (e.g., "Can pneumonia be observed on the lower right lung?") when the only evidence is a grounded report that names a *different* finding in that same region (e.g., "right lower lobe lung mass") and never mentions the queried condition. This is the "not mentioned = absent" trap.

**Verification action:** Before choosing, do three checks. (1) Confirm the tool output actually addressed the same object *and attribute* as the question: a report about "mass" is silent on "pneumonia/consolidation/infiltrate," so it is not a negative on the queried attribute and cannot by itself license "no." (2) Check whether the named finding sits in the queried region and could be an alternative label for the queried condition — a mass-like opacity in the lower right lung may be exactly the pneumonia the question asks about. (3) Obtain an independent observation that explicitly addresses pneumonia/consolidation in that region (e.g., chest_xray_expert, llava_rad, or roi_crop review) rather than inferring absence from omission; choose "no" only if a direct regional observation explicitly denies it. Finally, map the supported answer word back to the displayed option map (here A = no, B = yes) and confirm the terminal letter and text agree.

**What this case shows:** The terminal A/no pairing was internally correct, so this was not an option-mapping error — it was a wrong conclusion: absence of mention was treated as evidence of absence, and the released reference was B/yes. The retrieved cards did not supply a verified repair; the lesson stands as a caution about converting an unaddressed subregion into "no" without a direct region-specific check.
```

## exp_45ad40137f723cf5b595de19

来源题 [chexbench_slake_0068](../../cases/slake/chexbench_slake_0068.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to a global normality question such as “Does this image look normal?” after a direct image-QA tool has returned a bare “No”/“Yes” and a grounded report lists both normal statements and concrete findings or devices.

Verification action: Before emitting, restate the exact supported answer word for the same image and attribute. If the grounded report contains a concrete abnormality or device relevant to “not normal”—as here, “Right diaphragm is elevated” and “right-sided PICC catheter”—treat the supported text as “no”; do not let “lungs are clear” or “heart size is normal” cancel those findings. If the direct QA prompt was ambiguous because it asked both whether the image looks normal and whether abnormalities are present, do not rely on its bare “No” alone; use the explicit grounded finding or query verification. Then re-read the entire displayed option map and select the option whose text exactly matches the supported word—here B = no—checking that the selected letter and text agree. In this case the final “B. no” matched the reference B/no; the caution is that a correct grade alone does not prove the ambiguous direct-tool evidence and option mapping were both properly checked.
```

## exp_bd82a55df7fa40f270c27cb7

来源题 [chexbench_slake_0072](../../cases/slake/chexbench_slake_0072.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there abnormalities in this image?” after citing an imaging report, grounded report, visual QA, or image-QA tool as support.

Verification action: Before emitting, find the actual current-trajectory tool observation that explicitly addresses abnormalities in the same image. Derive the supported answer word only from that observation; if the recorded observations are empty or do not mention same-image abnormalities, do not say “grounded report and visual QA confirm” the finding—treat that evidence as unsupported or obtain the specific observation. Then re-read the displayed option map and map the supported word to the exact option, checking that letter and text agree. In this case, “yes” maps correctly to B. yes, so there is no option-mapping error, but the rationale cites evidence that was not actually present in the observed steps; a correct grade does not prove the evidence-to-answer check was performed.
```

## exp_a51d0fcd115f0c70a15eefb2

来源题 [chexbench_slake_0073](../../cases/slake/chexbench_slake_0073.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to an image-normality question such as “Is this image normal?” with options like A = yes, B = no, especially after a rationale cites imaging findings or retrieved prior experiences.

Verification action: Before emitting, extract the supported answer word from evidence that explicitly addresses the same image and the same attribute—normal versus abnormal. Any abnormal current-image finding, such as extensive bilateral infiltrates or a port-a-cath, supports “no/not normal”; only an explicit normal or negative current-image observation supports “yes/normal.” Do not use retrieved historical experiences or findings from another image as proof. If no same-image observation is available, flag the evidence as insufficient or obtain verification rather than presenting it as confirmed. Then re-read the entire displayed option map and map the supported word back to the exact option, checking that letter and text agree. In this case “no” maps to “B. no,” matching the reference, but the reusable check is the evidence polarity plus the displayed letter/text agreement, not merely the final letter.
```

## exp_e3e9025e1f1f58d8f3139a83

来源题 [chexbench_slake_0076](../../cases/slake/chexbench_slake_0076.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Does the patient have any abnormalities?” after citing an imaging report or finding.

Observable verification action: Before emitting, inspect the exact cited report text and confirm it explicitly supports at least one abnormality for the patient—e.g., a small pleural effusion or basilar atelectasis/scarring—rather than only a generic normal statement or a negative limited to “acute” abnormalities. Do not treat “no acute abnormalities” as proof of “no abnormalities” for the broader question; if the evidence is only that narrow, flag it as insufficient or query the same attribute explicitly. Then map the supported answer word back to the full current option map and check that letter and text agree; in this case the supported word is “yes,” corresponding to A. yes, B. no. Keep the final rationale limited to the finding that directly supports the chosen answer.
```

## exp_3211057f5c3f1ec6c8089a25

来源题 [chexbench_slake_0077](../../cases/slake/chexbench_slake_0077.json) · 活跃

```text
Trigger: You are about to finalize a “no” answer to a region-specific binary chest-imaging question because a direct VQA tool answered “No,” and you are considering citing a whole-image grounded report as corroboration even though that report lists only other abnormalities (e.g., patchy basilar airspace disease, no effusion/pneumothorax) and never explicitly names the queried region/attribute.

Verification action: Before emitting the choice, inspect the grounded report finding by finding. If no finding explicitly addresses the same region and attribute as the question, do not say the report “indicates no” that finding; say only that the report is silent on the target or describes other abnormalities. Keep the negative conclusion tied to the direct VQA observation that actually answered the exact question, unless another explicit observation contradicts it. Then map the supported text “no” back to the displayed options and confirm the terminal letter and text agree. In this case, B. no was correct and the option mapping was sound, but the rationale over-credited maira2_grounded_report: the report listed patchy basilar airspace disease and did not explicitly exclude upper-right infiltration. A correct grade alone would not validate that over-attribution.
```

## exp_8cb4aea913bc12f655ea20f4

来源题 [chexbench_slake_0082](../../cases/slake/chexbench_slake_0082.json) · 活跃

```text
Trigger: When finalizing a yes/no answer to a region-specific presence question such as “Can mass be observed on the lower right lung?” after a grounded report says “bilateral lung masses” with a broad box spanning the lung fields and a broad ROI crop is used, especially if the draft reason claims the crop itself shows a lower-right mass.

Verification action: Before emitting, state the supported answer text and map it to the displayed options (here “yes” = B, “no” = A). Check that the cited evidence actually includes the queried region: “bilateral lung masses” supports a right-sided mass, and a grounded box covering the lower lung fields can support “yes” even if the report does not separately say “lower right”; do not downgrade to “no” merely because the subregion was not named. But do not overclaim a broad ROI crop as independent proof of a discrete lower-right opacity, and do not infer patient laterality from crop/screen coordinates. If the report or box did not include the queried side or level, run a region-specific grounding/ROI check before answering. Finally confirm the terminal letter and text agree: B. yes. In this case the reference was B/yes and the mapping was correct; the caution is to tie the yes to the grounded bilateral-mass evidence and keep the reason within the crop’s limitations.
```

## exp_c40b31299d0547277df667b2

来源题 [chexbench_slake_0085](../../cases/slake/chexbench_slake_0085.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there abnormalities in this image?” especially when the rationale cites specific image findings but the observed steps contain no imaging-tool observation.

Verification action: Before emitting, extract the exact supported answer word (“yes” or “no”) only from direct same-image evidence or an actual tool result that explicitly addresses abnormalities in this image. Re-read the entire displayed option map and confirm the supported word’s letter and text agree. Also check that the final rationale cites only findings actually observed for this image, not prior experience or unverified assumptions. In this case “B. yes” matched the option map A = no, B = yes and the reference B/yes, so there was no option-mapping error; however, no tool observation was recorded, so the rationale’s cited findings were not independently verified by a tool. A correct grade alone does not prove the evidence-to-option procedure was performed.
```

## exp_4540ef69c4d50c58e375cc67

来源题 [chexbench_slake_0086](../../cases/slake/chexbench_slake_0086.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is this an X-Ray?” after visual inspection cites modality cues such as a projectional bony thorax, lung fields, or an orientation marker, especially when a retrieved experience card used a different option order or assigned “yes” to a different letter.

Observable verification action: Before emitting the answer, restate the supported proposition as “the image is an X-ray / yes,” re-read the current displayed option map, and match the exact text “yes” to its current letter. Emit the current letter–text pair—here “B. yes”—and confirm the rationale cites only modality evidence. Because there are no tool observations in this case, do not claim tool confirmation. Do not copy a historical “A. yes” unless the current map assigns “yes” to A; a letter/text mismatch would be an option-mapping error, not a visual conclusion error. In this case “B. yes” matched the reference B/yes, but the letter/text and current-option-map check is still required because a correct grade alone does not prove the procedure was followed.
```

## exp_f5f5d9a6699e4de25eba74d6

来源题 [chexbench_slake_0087](../../cases/slake/chexbench_slake_0087.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether a named finding (e.g., infiltration) is observable in a specified side/location (e.g., right lung), and a grounded report lists that same finding and location with a supporting box—even if qualified by “improved,” “small,” or “decreased.”

Verification action: Before emitting, quote the exact finding and check that it names the same object and location as the question, e.g., “Hazy infiltrate in the right lung has improved.” Treat an improving/hazy infiltrate with a bounding box as affirmative evidence that infiltration is observable, not as “no infiltrate.” Then re-read the displayed option map and confirm the supported word matches the letter–text pair: “yes” → “A. yes.” Keep the rationale limited to that finding/location; do not cite unrelated observations such as chest tube, pleural effusion, or port-a-cath, and do not let retrieved negative-answer experience cards override a positive current report. If the report instead said “no infiltrate” or only normal variants, answer “no.” In this case the final answer’s option mapping was correct (A = yes; reference A = yes) and the evidence addressed the same object/attribute, but the reusable check is still the explicit finding–location–option match, because a correct grade alone does not prove the check was performed.
```

## exp_a43632a6ee5079dbe3698b2b

来源题 [chexbench_slake_0088](../../cases/slake/chexbench_slake_0088.json) · 活跃

```text
Trigger: You are about to finalize a yes/no multiple-choice answer about a specific imaging finding and region after a direct visual-QA tool answers “Yes” to that same finding/region, while a grounded report returns only a broader or nonspecific abnormality (e.g., “hazy opacification in the lung bases bilaterally”) without naming the asked finding.

Verification action: Before emitting the choice, state the supported answer word from the direct observation, re-read the displayed option map, and write the matching letter–text pair (e.g., “B. yes”). Then reconcile the rationale with the exact tool outputs: confirm the direct VQA tool addressed the same object, attribute, and region as the question, and cite the grounded report only for what it actually says—general basal opacity/abnormality, not explicit confirmation of “pleural infiltration.” If the rationale says both tools explicitly indicate the specific finding, correct it to separate the same-scope direct positive from the nonspecific corroboration. Do not use a broad report to overturn a same-scope direct positive unless it contradicts it, and do not overstate it as independent confirmation of the exact attribute. A correct final grade alone does not prove these checks were performed.
```

## exp_75b42227266a0adaad48525c

来源题 [chexbench_slake_0090](../../cases/slake/chexbench_slake_0090.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there abnormalities in this image?” and the rationale cites a specific imaging finding or device—such as “right PICC line”—as the only support for “yes.”

Observable verification action: Before emitting, re-read the displayed option map and check that the supported word, letter, and text agree—here A = yes, and “A. yes” matches the reference. Then confirm the cited finding was actually observed in the same image and reasonably counts as an abnormality; do not rely on an unrecorded finding or a prior-memory suggestion as proof. In this case the option mapping is correct, but no tool observation documents the right PICC line, so the reusable lesson is to verify the image evidence before finalizing, not merely because the final letter was correct.
```

## exp_e6db512440b38473de7fba02

来源题 [chexbench_slake_0091](../../cases/slake/chexbench_slake_0091.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Does the patient have any abnormalities?” and the terminal rationale cites specific abnormalities—or says “grounded report and visual inspection”—but the recorded steps contain no actual same-image tool observation supporting those findings.

Observable verification action: Before finalizing, locate at least one recorded tool result from the same image that explicitly addresses the global “any abnormalities” question or names a present abnormality. If no such observation exists, do not treat the rationale’s specific findings as confirmed; obtain a targeted observation or flag the evidence as insufficient. Then restate the supported answer word (“yes” or “no”), re-read the entire current option map, and check that the letter and text agree. For this map, A = yes and B = no, so a supported “yes” finalizes as “A. yes.” The correct grade and reference do not by themselves prove that the cited cardiomegaly, effusion, and atelectasis were actually observed.
```

## exp_baf97999c774234897657b9c

来源题 [chexbench_slake_0094](../../cases/slake/chexbench_slake_0094.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer about whether an image is a named section or plane (for example, “Is this a transverse section?”), especially when the rationale relies on image/projection inference rather than a direct tool observation.

Verification action: Reduce the supported conclusion to the exact answer word (“no” or “yes”), re-read the entire displayed option map, and explicitly pair that word with the shown letter and text. In this case, the rationale says the image is a frontal chest X-ray / coronal projection, not a transverse cross-sectional slice, so the supported word is “no”; the displayed map is A = “no,” B = “yes,” so the terminal answer must be checked as “A. no,” even if the final output is a bare “A.” Also check that the rationale addresses the same plane/section attribute as the question and does not add unverified visual claims; if no tool result directly addressed the plane, label the conclusion as an image/projection inference rather than tool confirmation. The correct reference “A/no” does not by itself prove these mapping and evidence-scope checks were performed.
```

## exp_c83eaa5b8785e9135bbf8371

来源题 [chexbench_slake_0069](../../cases/slake/chexbench_slake_0069.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer about whether a medical image is a named modality such as MRI, especially when prior-experience retrieval mentions answer letters.

Verification action: State the supported answer text in words from the image-modality evidence, then re-read the entire current option map and emit the exact displayed letter paired with that text. Confirm the letter and text agree, and do not import a remembered letter from prior cases. In this case, the supported text is “no,” the current map is A = yes, B = no, so the correct terminal answer is “B. no.”
```

## exp_784d833112749df26f350777

来源题 [chexbench_slake_0097](../../cases/slake/chexbench_slake_0097.json) · 活跃

```text
Trigger: When finalizing a yes/no answer to “Does the lung look unhealthy?”—especially with options A=yes, B=no—and the rationale claims the lungs are clear or benign but no executed image observation actually documents lung health.

Verification action: Before emitting, require at least one executed observation that explicitly addresses this image’s lung health. Convert the question’s polarity carefully: an observed lung abnormality/unhealthy finding supports “yes” and must map to A; an explicit clear/no-abnormality finding supports “no” and must map to B. If no such observation exists, do not answer from an imagined clear-lung rationale—run a lung-health tool or decline to answer. Then re-read the full option map and confirm the selected letter’s text matches the supported polarity. In this case B=no was a correct letter–text mapping, but it was unsupported and the reference was A=yes; the failure was an evidence/conclusion error, not an option-mapping error.
```

## exp_0353a9e9d0674c980ee17260

来源题 [chexbench_slake_0095](../../cases/slake/chexbench_slake_0095.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to an imaging-modality question such as “Is this image taken via CT?”, especially when the answer is based on direct image inspection and no tool observations are present.

Verification action: Before emitting, state the supported answer in words from the visible acquisition evidence: for example, a projectional frontal chest radiograph showing ribs and lungs without cross-sectional slices supports “no.” Then re-read the entire displayed option map and match that exact text to the displayed choice, checking that the letter and text agree—here “no” must map to “B. no,” not to “yes.” Also check that the rationale addresses the same object and attribute as the question—imaging modality/acquisition—not merely anatomy or disease findings, and do not claim tool confirmation when no tool observations exist. Emit only after the supported answer text, selected option letter/text, and rationale all agree. A correct grade alone does not prove this mapping check was performed, so make it explicit when using this procedure.
```

## exp_17cb467f55f217514650cbae

来源题 [chexbench_slake_0096](../../cases/slake/chexbench_slake_0096.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is the lung healthy?” after an executed tool answers a question about whether lung abnormalities are present.

Verification action: Convert the tool’s abnormality polarity before choosing: “Yes” to “any lung abnormalities?” means the lung is not healthy, so the supported answer text is “no”; “No” means the supported answer text is “yes.” Re-read the entire displayed option map, select the option whose text exactly matches the supported answer text, and confirm the terminal letter and text agree. Cite only executed observations that directly address lung health; do not cite a “prior report” or other finding unless it appears in an actual observation. If observations conflict, reconcile them explicitly rather than silently omitting one. In this case, chest_xray_expert’s observed “Yes” to lung abnormalities supports “no”; with A = yes and B = no, the correct terminal answer is “B. no,” matching the reference “B”/“no.” The final rationale’s reference to a prior report and elevated right diaphragm is not supported by the shown executed observation, so it should not be cited. This case is not an option-mapping error or a wrong conclusion, but it shows the evidence-citation check that should accompany the letter–text check.
```

## exp_1ccaa7f8e2b397250c9f379d

来源题 [chexbench_slake_0100](../../cases/slake/chexbench_slake_0100.json) · 活跃

```text
Trigger: You are about to finalize a yes/no multiple-choice answer about a localized imaging finding (for example, “effusion on the lower left lung”) and your rationale cites a named tool/report as explicit evidence.

Verification action: Before emitting the choice, locate the recorded tool output that actually states the same finding and the same side/region as the question. If no recorded output contains that explicit statement, do not attribute it to the tool as “explicitly identifies”; either obtain the direct observation or mark the claim as unsupported. Then state the supported answer word, re-read the entire displayed option map, and write the matching option as a letter–text pair, confirming they agree. In this case, “A. yes” matches the option map and reference, so there is no letter/text mapping error; but the rationale’s claim that “MAIRA-2 grounded report explicitly identifies a small left pleural effusion” is not visible in the recorded steps. The correct grade alone does not prove the evidence-attribution step was valid.
```

## exp_4b8efd39fc401f06d093d85c

来源题 [chexbench_slake_0106](../../cases/slake/chexbench_slake_0106.json) · 活跃

```text
Trigger: When finalizing a region-specific presence answer (for example, “Can pneumonia be observed in the lower right lung?”) after collecting multiple imaging-tool outputs, especially when some outputs describe other regions or other findings, do not let a general “right lung is clear” or an unrelated “no right pleural effusion” stand in for a direct pneumonia/consolidation check unless it actually addresses the queried region and attribute.

Verification action: Before emitting the option, restate the target as region + attribute (“pneumonia/consolidation in the lower right lung”) and inspect each cited tool result against that exact target. Count a result as supporting “no” only if it explicitly denies pneumonia/consolidation in that region or explicitly states the right lung is clear; do not count left-sided infiltrate/effusion, absence of a different finding such as pleural effusion, or mere omission as a pneumonia-negative. If at least one direct negative exists and no direct positive conflicts, choose “no”; if the evidence is only indirect or conflicting, obtain a direct regional check before finalizing. Then map the supported answer word back to the displayed option map and confirm the terminal letter, text, and reason agree. In the source case, chest_xray_expert answered “No” and the grounded report said “Right lung is clear,” so A/no was correct and matched the reference, but the rationale should not overstate every tool as independently confirming pneumonia absence when some tools only addressed adjacent findings.
```

## exp_beba75e1d4cbc76ecaabd67c

来源题 [chexbench_slake_0098](../../cases/slake/chexbench_slake_0098.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there abnormalities in this image?” after a rationale cites specific imaging findings or a recalled similar case suggests an option letter.

Observable verification action: Before emitting, extract the exact supported answer word from evidence explicitly about this image. “Yes” requires at least one stated abnormality; “no” requires an explicit normal/no-abnormality statement. Re-read the entire displayed option map and verify that the chosen letter’s text matches that word; do not copy a letter from a prior case, because option order can differ. Then check that the rationale cites only findings actually present in tool/report observations. In this case, the current map was A = yes and B = no, and terminal “A. yes” matched both the map and the reference. However, the trajectory recorded no tool observation supporting the listed cardiomegaly, congestion, effusions, or atelectasis, so the correct grade proves the option mapping but not the cited evidence. If no same-image observation exists, flag the evidence as insufficient or limit the rationale to what was actually observed.
```

## exp_63e574a431af62a9eaaa43ba

来源题 [chexbench_slake_0099](../../cases/slake/chexbench_slake_0099.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is this a study of the [named anatomical region]?”—especially when retrieved examples have different option orders or concern disease findings rather than study/region coverage.

Verification action: Restate the answer text supported by the visible image evidence—e.g., “yes” only if the image is a frontal chest radiograph or the study clearly covers the thorax. Re-read the displayed option map for the current question (here A = no, B = yes), match the supported text exactly, and confirm the emitted letter–text pair agrees (here B. yes). Check that the rationale addresses the same object and attribute as the question: it should describe the study as covering the chest/thoracic region, not merely mention chest-related findings or abnormality. If no tool observations are present, keep the rationale limited to visible image evidence and do not imply tool confirmation; if tool observations are present, verify they address the same study/region and do not conflict, then use that evidence in the terminal choice. Do not import an option letter from a retrieved historical case, because a correct grade alone does not prove that the current option map and rationale were checked.
```

## exp_ae0ea880822219511b3b2247

来源题 [chexbench_slake_0102](../../cases/slake/chexbench_slake_0102.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is this image taken via X-Ray?”, especially when the rationale cites modality cues such as projectional bony thorax, lung fields, or an L marker, and when the displayed map may assign “yes” to a letter other than the one recalled from another case.

Observable verification action: Before emitting the answer, restate the supported proposition as “the image is an X-ray,” re-read the current option map, and match the exact text “yes” to its current letter—here B = yes, so emit “B. yes.” Check that the rationale cites only X-ray modality evidence and does not drift into disease findings. If the rationale mentions a tool such as MAIRA-2, confirm an actual tool observation is present; in this trajectory no observations were supplied, so the tool attribution was unsupported and should be removed or rephrased as visual evidence. Also confirm the earlier supported conclusion (“B. yes”) was carried through unchanged—the final raw answer “B” preserved the correct letter but dropped the text, so the letter–text pair should still be checked. This is an option-mapping and evidence-scope check, not a reason to overturn the visual conclusion; in this case B/yes matched both the displayed map and the reference, but a correct grade alone does not prove the procedure was followed.
```

## exp_596c57a7dbe200d5101e1720

来源题 [chexbench_slake_0103](../../cases/slake/chexbench_slake_0103.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there abnormalities in this image?” after citing imaging findings or using a prior experience, especially when the current option map may differ from a remembered one.

Verification action: Before emitting, extract the exact supported answer word using only evidence that explicitly addresses abnormalities in the same image. Re-read the entire current option map and map that word to the displayed option, checking that the letter and text agree; do not reuse a letter such as “yes = B” from a prior case. In this case the supported word “yes” mapped to A. yes, not B. no. Also confirm that any cited findings were actually observed or returned for this image; a correct final grade alone does not prove that this evidence-to-option check was performed.
```

## exp_0d50de41bca29068f2a51b10

来源题 [chexbench_slake_0105](../../cases/slake/chexbench_slake_0105.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is this a study of the [named anatomical region]?” based on visible image evidence, especially when the displayed option map could assign “yes” and “no” to different letters.

Verification action: State the evidence-supported answer word, re-read the entire displayed option map, and emit the option whose text exactly matches that word. Check the letter–text pair explicitly: with A=yes and B=no, supported “yes” must be emitted as “A. yes”; if the map were A=no and B=yes, the same supported word would require “B. yes.” Confirm the rationale addresses the same object and attribute as the question—study or anatomical coverage of the chest, not merely a chest finding or abnormality. With no tool observations, keep the rationale limited to visible image evidence and do not imply tool confirmation. In this case the terminal “A. yes” matches the displayed map and the reference A/yes, and the rationale describes a frontal chest radiograph covering the thoracic region; no earlier supported conclusion was lost. The correct grade alone does not prove the mapping and region/attribute checks were performed.
```

## exp_06d5855ef3ba975943dd40e1

来源题 [chexbench_slake_0107](../../cases/slake/chexbench_slake_0107.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is the lung normal appearing?” after a grounded report or prior step identifies a lung mass/opacity and therefore supports “no,” especially if the terminal output contains only a letter.

Verification action: Before emitting, state the supported answer word (“no”), re-read the displayed option map, and confirm the exact letter–text pair: here A = “no,” B = “yes,” so the correct terminal choice is “A” with intended text “no.” Also confirm the cited evidence addresses the same question—lung appearance/abnormality—and that the grounded report or visual finding actually supports “not normal” (e.g., right lower lobe lung mass/opacity), with no conflicting normal report. If the final output only gives “A,” verify that it still maps to “no” and that the earlier supported conclusion was not changed during finalization.
```

## exp_fe5893fe8d7e791047ef6501

来源题 [chexbench_slake_0108](../../cases/slake/chexbench_slake_0108.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer asking whether the organs visible in an image exist in a named anatomical region, after identifying the dominant visualized organs/region.

Verification action: Before emitting, state the supported answer text from that image interpretation—here, the chest X-ray shows thoracic organs such as lungs and heart, not abdominal organs, so the supported text is “no.” Then re-read the entire current option map and confirm the displayed choice with that exact text. In this case A = “yes” and B = “no,” so the correct terminal form is “B. no.” Check that the letter and text agree and that the reason names the same region and attribute as the question. Do not reuse a remembered letter from similar prior cases, because “no” has mapped to different letters in other option maps; map only against the current displayed options. If a tool or report is cited, cite only observations that explicitly address the same object, region, and attribute as the question.
```

## exp_e8f83409ae2deac682204a8b

来源题 [chexbench_slake_0109](../../cases/slake/chexbench_slake_0109.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is this a study of the [named anatomical region]?”—especially when the option map is A = no, B = yes—and the visible evidence indicates the study covers that region.

Verification action: Restate the supported answer text exactly (“yes” or “no”), then re-read the displayed option map and emit the option whose text matches it. Confirm that the letter and text agree; here supported “yes” maps to “B. yes,” not a letter recalled from another case or option map. Check that the rationale addresses the same object and attribute as the question—that the study/image is of the chest or thoracic region—not merely that chest-related findings are present. If tool observations exist, confirm they explicitly address the study/region and do not conflict; if none exist, keep the rationale limited to visible image evidence and do not imply tool confirmation. Emit only after the text-to-letter mapping and region/attribute checks both pass; a correct grade alone does not prove those checks were made.
```

## exp_d7f712e402fb7b1de834d9ab

来源题 [chexbench_slake_0110](../../cases/slake/chexbench_slake_0110.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there abnormalities in this image?” after citing an imaging report, especially when a retrieved prior experience suggests a particular option letter (e.g., “B. yes”).

Verification action: Before emitting, extract the exact answer word supported by the cited report findings—here “bilateral airspace disease” supports “yes,” while a generic normal statement or a finding about a different image/region would not. Confirm the rationale cites only findings actually returned for this image. Then re-read the entire current option map and map the supported word to the displayed choice, checking that letter and text agree: with A = yes and B = no, the supported “yes” is “A. yes.” Do not copy a letter from a historical case with a different option order; in this case a retrieved memory had “yes” mapped to B, which would have been wrong under the current map. The terminal “A. yes” matches the reference (A / yes), but the mapping check is what makes that conclusion reliable.
```

## exp_f239cce5bccfecda513bca92

来源题 [chexbench_slake_0111](../../cases/slake/chexbench_slake_0111.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is this image taken via X-Ray?” after visual inspection shows modality cues such as projectional bony thorax, lung fields, and radiopaque markers (for example PORTABLE, AP, L), especially when a retrieved experience card used a different option order.

Observable verification action: Restate the supported proposition as the exact option text “yes,” then re-read the current displayed option map and select the option whose text exactly matches it. Emit the current letter–text pair—here “A. yes”—and confirm the letter and text agree and that the earlier supported conclusion was carried through unchanged. Confirm the rationale addresses the question’s object and attribute, image modality, by citing only X-ray features such as projectional ribs/clavicles/spine, lung fields, and orientation/marker text, not disease findings. If no tool observations are present, do not claim tool confirmation; if tool observations exist, check that they explicitly address X-ray modality and do not conflict. Treat a letter–text mismatch or reuse of a letter from a historical option map as an option-mapping error, not a visual-conclusion error, and correct it before finalizing. In this case, “A. yes” matched the current map, the reference A/yes, and the earlier step’s conclusion, so no repair was needed; the check is still required because a correct grade alone does not prove the mapping and evidence procedure was followed.
```

## exp_2ca7e93ae6f67509098d3625

来源题 [chexbench_slake_0112](../../cases/slake/chexbench_slake_0112.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is this image normal?” or a similar abnormality question, especially when the draft rationale cites specific imaging findings but the trajectory contains no observed same-image tool result.

Verification action: Before emitting, require an observed tool output for the same image that explicitly addresses normal/abnormal status or the specific cited findings. If no such observation exists, do not treat the rationale as verified evidence—obtain/check the appropriate image evidence or mark it insufficient. Then extract the exact supported answer word (“no” if abnormalities are supported), re-read the full displayed option map, and check that the chosen letter and text agree. Here the mapping A = no, B = yes is internally consistent and the supported “no” maps to A, but the cited findings were not shown as observed tool evidence; a correct grade alone does not prove the evidence chain was verified.
```

## exp_2197da14883bd98fc040bdad

来源题 [chexbench_slake_0114](../../cases/slake/chexbench_slake_0114.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Is this a study of the [named anatomical region]?”—for example, “head”—where the decision depends on the image’s primary field of view or anatomical coverage rather than disease presence.

Verification action: Confirm the study’s primary field of view from the visible image, not just whether the named region appears incidentally. If the image is a frontal chest radiograph focused on the thorax, the supported answer text for a “head” study is “no.” Re-read the displayed option map (here A = no, B = yes), match the supported text exactly to the option, and state the letter and text together: “A. no.” Check that the rationale says the study is chest-focused and not a dedicated head study, rather than claiming the head is absent. If no tool observations exist, keep the rationale limited to visible image evidence and do not imply tool confirmation; if tool results exist, confirm they address the same object and attribute—study focus/anatomical coverage—and do not conflict.
```

## exp_e4511368f19a15abbee23303

来源题 [chexbench_slake_0115](../../cases/slake/chexbench_slake_0115.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there abnormalities in this image?” after consulting a same-image image-QA tool or grounded report, especially when the report mixes normal and abnormal findings.

Verification action: Before emitting, extract the exact answer word supported by the same-image tool evidence—either a direct QA “Yes” or a report finding that explicitly names an abnormality, such as “small left pleural effusion” or “sternotomy wires.” Do not let normal statements elsewhere in the report override an explicit abnormality when the question asks whether there are any abnormalities. Then re-read the displayed option map and map the supported word to the exact choice, checking that the letter and text agree (here A = no, B = yes, so “B. yes”). Also confirm the final reason cites only findings actually returned by the tools for this image; a correct grade alone does not prove the option-mapping and evidence check were performed.
```

## exp_e702f7f76219fdeefe422ea6

来源题 [chexbench_slake_0117](../../cases/slake/chexbench_slake_0117.json) · 活跃

```text
Trigger: When finalizing a yes/no multiple-choice answer to “Are there abnormalities in this image?”, especially when the draft rationale cites specific imaging findings or retrieved prior-case experience.

Verification action: Before emitting, require at least one tool observation that explicitly addresses abnormalities in the same image; cite only findings actually returned by that observation, and do not treat prior-case text or an unsupported rationale as image evidence. Extract the supported answer word (“yes” or “no”), re-read the entire current option map, and confirm that the chosen letter and text both match that word. Compare the chosen letter/text with the released reference if available. If the letter and text disagree, correct the option mapping; if the evidence does not address the same image and attribute, mark the conclusion as unsupported. In the supplied case, “A. yes” agrees with the displayed option map and the reference, but no tool observation appears in the steps, so the cited nodular opacities, pleural effusions, and consolidation are unverified; the correct grade alone does not prove the evidence-to-option check was performed.
```

## exp_1a96395fefc37622c8ce6705

来源题 [chexbench_slake_0118](../../cases/slake/chexbench_slake_0118.json) · 活跃

```text
Trigger: Before finalizing a yes/no multiple-choice answer to a laterality-specific chest X-ray question—e.g., “Can mass be observed on the left lung?”—when xray_phrase_grounding has returned a phrase plus normalized bounding-box coordinates.

Observable verification action: Re-read the grounding output, confirm the returned phrase matches the queried finding, and derive patient laterality from the box coordinates using the image convention (image-right, usually x > 0.5, is patient-left; image-left is patient-right). Check that the box falls within the queried lung field. Then map the supported answer word back to the displayed options and verify the letter–text pair. In this case, “mass is noted” with x-range 0.645–0.775 is on the image right, i.e. patient left, so “yes” is supported and “B. yes” matches the option map and reference. If the box is central, crosses the midline, or falls on the opposite side, do not claim the queried side is confirmed; obtain a region-specific observation. A correct final grade alone does not prove the procedure—the side-coordinate check must actually be performed rather than inferred from the question or phrase.
```

## exp_5c34662317633d1ff90072d4

来源题 [chexbench_openi_0002](../../cases/openi/chexbench_openi_0002.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that requires choosing laterality (for example, left vs right base pulmonary atelectasis), and the direct QA tool answered only “Yes” to a compound “left or right” question, the grounded report names only nonspecific or bilateral basilar opacities, and `xray_phrase_grounding` for one candidate phrase returned a bounding box.

Verification action: Before selecting the option, require side-specific presence evidence for that exact finding. Do not treat “Yes” to an either/or laterality question as selecting a side; do not treat “mild bibasilar opacities” as confirmation of one-sided atelectasis; and do not treat a phrase-grounding box as proof that the finding exists—it only shows where the model would localize the supplied phrase and can produce a box for an unsupported phrase. If a box is checked, verify the image-coordinate convention (image right = patient left; image left = patient right) and that the phrase itself matches the option, but only after an independent same-scope result has stated the side. If no tool result explicitly names the side for the asked finding, do not finalize from the single one-sided grounding box; mark the evidence as insufficient or obtain a side-specific result. Finally, map the supported answer text back to the displayed option map and confirm the letter and text agree.

Lesson from case: The terminal answer “A. left base pulmonary atelectasis” was correctly mapped to option A’s text; this was not a letter/text mapping error. The error was evidentiary: `chest_xray_expert`’s “Yes” did not distinguish left from right, the grounded report described only bilateral opacities, and the phrase-grounding result was overstated as “confirming option A.” The released reference was B, right base pulmonary atelectasis.
```

## exp_f6a99bda789cc5f3c6bb88dd

来源题 [chexbench_openi_0003](../../cases/openi/chexbench_openi_0003.json) · 活跃

```text
Trigger: In a chest X-ray laterality multiple-choice question, when the draft answer relies on a direct VQA side word (e.g., “Left”) and also cites a phrase-grounding call whose input phrase already contains that side, while a grounded report is silent on the same structure.

Verification action: Before finalizing, make the direct question-specific observation the load-bearing evidence, then re-read the displayed option map and write the exact letter-text pair, confirming that “left” maps to “B. elevated left diaphragm,” not to the right-sided option. Check each auxiliary tool against the same object and attribute: if the grounded report does not mention the diaphragm, do not cite it as confirming diaphragm elevation; and treat “elevated left hemidiaphragm” phrase grounding as localization of the supplied phrase, not as independent proof that the finding is present. Do not write that the grounding tool “confirmed the finding” unless it independently addressed presence, not just phrase localization. In this case the direct expert answer “Left” supports B, and B matches the option text and released reference; the overclaimed phrase-grounding rationale is the evidence-attribution issue, not an option-mapping error.
```

## exp_636ea92cd8d76c96d3d3a2dd

来源题 [chexbench_openi_0005](../../cases/openi/chexbench_openi_0005.json) · 已剪枝

```text
Trigger: You are about to finalize a left-vs-right answer (e.g., "surgical instruments in the left lung" vs "right lung") from a lateral chest radiograph when the only affirmative tool returned bare presence ("Yes") with no side, another model answered absence, and the image has no left/right marker.

Verification action: Before emitting the sided choice, explicitly check that at least one tool actually returned a side (left or right), not just presence. Read the roi_crop and verify notes: if either says laterality was not inferred / no side marker, or warns that the finding may be at the image margin/outside the thorax, do not manufacture the side from projection geometry or screen position — that is an unsupported inference, not evidence. If no tool supplies a side and a verifier returns PARTIALLY_CORRECT/CAUTION recommending uncertainty over the sided option, treat that as an unresolved conflict and state uncertainty rather than selecting A or B. Finally, confirm the chosen letter/text pairing against the displayed option map.

Lesson from the case: the terminal answer was B ("surgical instruments in the right lung"), but chest_xray_expert only said "Yes" (no side), llava_med_qa said "No," roi_crop noted "patient side not inferred / do not infer laterality from screen position," and verify said laterality could not be confirmed and suggested uncertainty rather than B. The model's rationale — "on this lateral view the only plausible location is the right hemithorax" — was an invented justification not present in any observation, and it ignored both the model-disagreement and the verifier's caution. The letter/text pairing was correct, so this was not an option-mapping error but a wrong conclusion built on fabricated laterality. The released reference was A. Do not let a bare "Yes" from one tool stand in for a supported side, and do not finalize a sided answer merely because an earlier step proposed it.
```

## exp_5528cbfa58dcaebfc90663b2

来源题 [chexbench_openi_0008](../../cases/openi/chexbench_openi_0008.json) · 活跃

```text
Trigger: You are about to finalize a two-option laterality question on a chest image (e.g., "left lung opacity" vs "right lung opacity"), and both image-QA tools you queried returned the same side in response to the same forced-choice prompt.

Verification action: First, map the supported side to the displayed option and confirm letter and text agree — here "left lung opacity" is A, and that mapping was correct, so this is not an option-mapping error. Then ask whether the evidence can establish laterality at all. Confirm the image is a frontal PA/AP view that distinguishes left from right; on a lateral radiograph laterality cannot be assigned, and a forced-choice "left or right" answer is a guess, not a finding. Then seek an independent locator: run xray_phrase_grounding or roi_crop on the opacity to see which hemithorax actually contains it, or check the accompanying report for the side. Treat two QA models answering the identical question as one observation, not two — they share training data and bias, so their agreement is not independent confirmation, and the rationale must not say "both tools independently identify..." unless the sources are genuinely independent. If the view is lateral, or no grounding/report supports the side the QA tools named, either reconsider the other option or state the uncertainty explicitly; do not present the QA agreement as verified fact.

Lesson from the case: chest_xray_expert answered "Left lung," llava_med_qa answered "opacity in the left lung," and the terminal answer A. left lung opacity matched both letters and text. Nothing was lost at finalization — the letter-text mapping was right and the rationale quoted the tools accurately. The failure was upstream: two similar VQA models were asked the same forced-choice laterality question, no grounding tool or report was consulted, the image was described as a lateral CXR (where left vs right cannot be read), and the released reference was B. right lung opacity. Agreement between two same-scope QA tools is a caution flag, not confirmation.
```

## exp_63f6eaed9209f117685782be

来源题 [chexbench_openi_0012](../../cases/openi/chexbench_openi_0012.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer whose options differ only by laterality (for example, “small left pleural effusion” vs “small right pleural effusion”) and earlier tool observations conflict, check whether the terminal choice actually used the earliest explicit side-specific observation.

Verification action: Before emitting the answer, re-read the observation list and extract the exact side named by the direct chest_xray_expert result, if any. Compare that side to the entire displayed option map and write the matching option as a letter–text pair. In this case, chest_xray_expert observed “Small right pleural effusion,” which maps to B. The final answer was “A. small left pleural effusion” based on MedGemma’s left-sided claim, while the verifier only warned that a lateral view cannot reliably lateralize and did not affirm the left side. The letter and text of the terminal answer agreed with each other, so this was not an option-mapping error; it was a wrong conclusion caused by ignoring the explicit right-sided chest_xray_expert observation and relying on an uncorroborated opposite-side claim. If a verifier says lateralization is limited, treat that as uncertainty, not as evidence for the opposite side. If forced to choose between left and right, use the only explicit side-specific direct observation and confirm its letter/text mapping before finalizing.
```

## exp_a1825282b57e28f7daa3a2af

来源题 [chexbench_openi_0015](../../cases/openi/chexbench_openi_0015.json) · 活跃

```text
Trigger: When you are about to finalize a right-versus-left chest X-ray multiple-choice answer and your rationale says that several visual QA tools “consistently” identify one side, but at least one cited tool was asked an either/or question and returned only “Yes.”

Verification action: Before emitting the option, re-read each cited tool observation and count it only if it explicitly names the selected side and finding, e.g. “right base pulmonary atelectasis.” Do not count a bare “Yes” to “right or left?” as support for either side, and do not describe the outputs as unanimous unless every cited tool named the same side. Then map the explicitly supported side text back to the displayed option and confirm the letter and text agree. If the chosen side depends on an ambiguous answer, remove that support or obtain a side-specific observation before finalizing; if the remaining evidence conflicts or is insufficient, do not default to the first option.

In this case, A’s letter and text did match “right base pulmonary atelectasis,” so it was not an option-mapping error. The error was an evidence/consensus overclaim: chest_xray_expert returned only “Yes” to the either/or question, while the final rationale treated it as one of three models consistently identifying the right side. The released reference was B, left base atelectasis. The reusable caution is that VQA “votes” must be checked for the exact object, attribute, and side before they are aggregated, especially for difficult laterality questions on a lateral chest X-ray.
```

## exp_dce05ec023fc5defb4837230

来源题 [chexbench_openi_0017](../../cases/openi/chexbench_openi_0017.json) · 活跃

```text
Trigger: When finalizing a forced-choice laterality answer about a finding on a lateral chest X-ray — here, “surgical instruments in the right lung” vs “left lung” — and the only support for the chosen side is the image’s “L” laterality marker or metallic edge artifacts, while the direct VQA tools both answered “No” to the finding itself, and the verifier has already cautioned that the marker is not an intrapulmonary device and that a lateral view alone cannot lateralize.

Verification action: Before emitting the letter, require at least one observation that actually asserts the named finding in a specific lung. Treat the “L” marker as a projection/laterality label, not as evidence that a device is in the left lung, and do not treat the forced-choice format as proof that the finding exists. If all direct observations are negative and no grounded report, phrase-grounding result, or frontal (PA/AP) view localizes the finding, do not manufacture a side from the marker heuristic; obtain localizing evidence or decline to assert the device. Then map the supported answer text back to the displayed option and confirm the letter and text agree.

In this case the terminal choice “B. surgical instruments in the left lung” matched the option map correctly, so this was not an option-mapping error; both tool observations addressed the same object and attribute and both said “No,” and the verifier explicitly warned against using the “L” marker as intrapulmonary evidence. The failure was a wrong conclusion that overrode unanimous negative evidence and an available caution with a marker-based convention. The released reference was “A. surgical instruments in the right lung,” further showing that the marker heuristic was not a valid substitute for observing the finding.
```

## exp_5d57d2d488235814c9135b5f

来源题 [chexbench_openi_0018](../../cases/openi/chexbench_openi_0018.json) · 活跃

```text
Trigger: Before finalizing a multiple-choice chest X-ray answer whose options differ only by laterality (e.g., "A. right indwelling catheter" vs "B. left indwelling catheter"), when the evidence is vision-QA tool output and especially when (a) a tool was asked a "right or left ...?" question but answered only "Yes," (b) the image is a lateral view, or (c) only one tool stated a side while others were silent.

Verification action: For each observation, check that it names the side the question asks about, not just presence. Treat a bare "Yes" to a right-or-left question as confirming only presence: it is not evidence for either branch and must not be cited as "confirming both presence and laterality." Note that silence on laterality is not agreement — absence of conflict between tools is not corroboration. If exactly one tool names a side and nothing else corroborates it, either get an independent check (a second reader, or a spatial grounding/crop step that actually points to the catheter on that side) or decline to assert the side. Only once a side is explicitly supported should you map that side's wording to the displayed option and confirm the letter and text agree.

Lesson from this case: the terminal answer was "A. right indwelling catheter," and A did match its text, so this was not an option-mapping error — it was an evidence error. chest_xray_expert answered only "Yes" to "Is there a right or left indwelling catheter visible...?", which supplies no laterality, and llava_med_qa's single "right" claim was then accepted as definitive on a lateral radiograph, where side assignment is precisely the unreliable part; the released reference was B, left. The final rationale ("explicitly identified a right indwelling catheter ... confirming both presence and laterality") overstated one uncorroborated observation and quietly treated the ambiguous first answer as support. The unexecuted repair — corroborating the side with grounding or a second reader — is not a verified success, so apply the check rather than assume it was done.
```

## exp_a3552e9dd9c50a36018b0018

来源题 [chexbench_openi_0020](../../cases/openi/chexbench_openi_0020.json) · 活跃

```text
Trigger: When finalizing a multiple-choice laterality answer—such as right vs left indwelling catheter—from a lateral chest X-ray while visual-QA tools disagree and the verifier explicitly warns that laterality is not determinable from the projection or an illegible side marker.

Verification action: Before emitting, map the supported answer text back to the displayed option letter and text, and check whether any observed tool result actually establishes the asked laterality under the image’s projection constraints. Do not resolve the conflict by majority vote alone. Re-read the verifier’s limitation and the direct/expert observation; if the verifier says the lateral view cannot assign right vs left, the majority’s “right” answers are not load-bearing evidence. In this case the terminal choice A. right matched the option text, but the conclusion was unsupported: two VQA tools said “right,” the verifier said the lateral view could not determine laterality, and the direct chest_xray_expert observation said “Left”; the released reference was B. left. The procedure is therefore: when laterality is the exact attribute and the projection cannot support it, do not assert the majority side; retain only a side supported by a direct/expert observation or legible marker, otherwise flag indeterminacy rather than finalizing by vote count.
```

## exp_f67f8ed9992392ace0ae46a5

来源题 [chexbench_openi_0028](../../cases/openi/chexbench_openi_0028.json) · 活跃

```text
Trigger: When finalizing a side-specific chest X-ray multiple-choice answer (for example, left versus right indwelling catheter), different imaging tools conflict—one direct CXR QA tool names one side while a second VLM names the opposite—and the verifier only says the proposed option is “CORRECT.”

Verification action: Before answering, lay the displayed option map beside the actual tool observations and map each side term to its exact option text and letter. Do not treat the verifier’s “CORRECT” or a generic second VLM answer as independent laterality evidence unless it points to the same object and attribute and actually resolves the conflict. If the grounded report is inapplicable, as it was for this lateral view, and no independent observation confirms the opposite side, choose the option matching the direct chest X-ray expert’s side result. Then check that the final letter and text agree and that the rationale cites the side observation, not the verifier.

Case lesson: chest_xray_expert had already said “Right,” which mapped to B. right indwelling catheter, but the final answer was A. left indwelling catheter because llava_med_qa said “left” and the verifier approved the proposed answer. The released reference was B. This was not an option-mapping error—A correctly matched “left”—but a wrong conclusion caused by letting a verifier approval and a conflicting VLM output override the earlier direct side-specific observation.
```

## exp_480fe460864015917190cb20

来源题 [chexbench_openi_0029](../../cases/openi/chexbench_openi_0029.json) · 活跃

```text
Trigger: When finalizing a left/right side-specific chest X-ray answer, especially on a lateral view, and the tool response names only an image side (“right side”) or gives a non-specific “No” followed by a side mention, and the final rationale would translate screen position into patient laterality.

Verification action: Before choosing an option, check whether the tool explicitly states patient anatomical side, such as “patient’s right ribs” or “right rib deformity.” If it only says “right side” or refers to image position, treat that as ambiguous. Do not convert “right side of the image” to “patient’s left” using an assumed standard orientation; check the ROI/laterality limitations as well. If the crop tool says “patient side not inferred” or “do not infer patient laterality from screen position,” require an unambiguous re-query or independent corroboration. Reconcile any prior “No” answers rather than silently overriding them. Once a patient-side finding is supported, map that side to the displayed options (here A = left rib deformity, B = right rib deformity) and confirm the letter, text, and rationale all state the same side. In this case, the terminal answer chose A by converting image-right into patient-left despite the ROI warning and contrary earlier “No” answers; the reference was B, so this was a wrong conclusion/unsupported laterality conversion, not merely an option-mapping error.
```

## exp_b77a2503adfd173d5bf1eaed

来源题 [chexbench_openi_0030](../../cases/openi/chexbench_openi_0030.json) · 活跃

```text
Trigger: When finalizing a left-versus-right chest X-ray multiple-choice answer, and the support for the selected side is a phrase-grounding box produced from a phrase that already names that side, especially when another tool reports “No pathological findings.”

Verification action: Before finalizing, check whether the phrase-grounding step was symmetric and independent. A box for “hyperdistention of the right lung” only localizes the supplied phrase; it does not prove that right hyperdistention is present or that the left side is normal. Require a balanced direct comparison—such as a direct left-versus-right assessment or grounding for both left and right phrases—before using one-sided grounding as confirmation. If the grounded report independently says “No pathological findings,” do not treat the one-sided phrase-grounding box as decisive confirmation of that side. Then map the supported side text back to the displayed option and confirm the letter and text agree.

In this case, the terminal choice was “B. hyperdistention of the right lung.” The letter-text mapping was correct, but the conclusion relied on a right-only phrase-grounding call as confirmation while the grounded report said “No pathological findings.” The released reference was “A. hyperdistention of the left lung.” The reusable lesson is to distinguish phrase localization from finding presence and to avoid one-sided grounding as proof in a lateralized comparison.
```

## exp_f8cc3feda33bd3c7ed5af653

来源题 [chexbench_openi_0004](../../cases/openi/chexbench_openi_0004.json) · 活跃

```text
**Trigger:** You are finalizing a multiple-choice answer that selects one side/region (e.g., "right base" vs "left base" atelectasis) after calling a phrase-grounding tool with the candidate answer phrase itself, and a grounded report has returned "lungs are clear" or another conflicting broad statement.

**Verification action:** Before writing the terminal choice, separate the three observations by what each can actually establish: (1) the direct VQA tool answered the same object/attribute as the question, so it carries the presence decision; (2) the phrase-grounding tool was *fed the candidate phrase*, so a returned box proves only that the model will localize that phrase somewhere — it is location/laterality consistency, not independent evidence that the finding exists; (3) the grounded report is a broad screen that here said "lungs are clear," which conflicts with the direct positive and must be reported as a conflict, not silently dropped or claimed as agreement. Then restate the supported answer text, re-read the displayed option map, and confirm the letter–text pair matches (here B = "left base pulmonary atelectasis"). In the rationale, name the direct VQA as the evidence for presence and cite grounding only as laterality, and say the broad report disagreed.

**Lesson from this case:** The terminal answer B. left base pulmonary atelectasis was correct and the letter–text mapping was right, but the stated reason ("phrase grounding localized it... consistent with option B") overstates circular evidence: the grounding call took "left base pulmonary atelectasis" as its input phrase and could not have failed to return a left-lower-zone box. The only non-circular support was the direct chest_xray_expert answer, and the grounded report's "lungs are clear" was left out of the rationale. A correct grade alone does not prove this check was performed — the reusable discipline is to keep a phrase-grounding result classified as localization of the supplied phrase, never as confirmation of the finding's presence, and to disclose a conflicting report rather than assert tool agreement.
```

## exp_046cf46bb4f11a83d77e909d

来源题 [chexbench_openi_0006](../../cases/openi/chexbench_openi_0006.json) · 活跃

```text
Trigger: When finalizing a two-option chest X-ray question asking whether the right or left hemidiaphragm is elevated, after a direct VQA tool returns a side word such as “Left” and auxiliary tools return only a grounded report or a phrase-grounding box involving the left lung base.

Verification action: Before emitting the answer, take the side supported by the direct VQA result, map it to the exact displayed option letter and full text, and confirm the pair is correct (here, “left” must map to “B. elevated left diaphragm,” not A). Then audit the rationale against each tool observation: cite the direct chest_xray_expert answer as the evidence of elevation; cite the grounded report only for what it actually says, such as “increased radiodensity at the left lung base,” which does not by itself prove elevation; and treat phrase grounding for “elevated left diaphragm” as localization of the supplied phrase, not independent confirmation that the finding is true. If an auxiliary result addresses a different attribute or does not independently confirm the question, do not claim it as confirmation. Correct the letter/text mapping or the rationale before finalizing.

Lesson from this case: the terminal answer “B. elevated left diaphragm” matched the displayed option map and the released reference, but the rationale overstated the auxiliary tools as consistently confirming elevation. A correct grade alone does not prove that the evidence-attribution check was performed.
```

## exp_5eb3b31518bbb03064036890

来源题 [chexbench_openi_0007](../../cases/openi/chexbench_openi_0007.json) · 活跃

```text
Trigger: You are about to finalize a laterality-specific chest X-ray answer (right vs left) where the direct VQA tool named one side, a grounded report returned a bilateral finding covering both hemithoraces, and an xray_phrase_grounding call was run using the answer phrase itself as the query.

Verification action: Before emitting the letter, (1) identify which observation actually asserts the chosen side and quote it — here chest_xray_expert returned "Right pleural effusion," which is the only observation that states the side outright. (2) Treat the grounded report's "Bilateral pleural effusion" as broader than, not equivalent to, the option: it is consistent with right effusion but does not exclude left, so it cannot itself pick between A and B, and the rationale must not silently rewrite it as if the report had said "right." If the rationale cites the grounded report as side-specific support, correct it to cite the tool that actually made the side-specific claim. (3) Discount phrase grounding as independent confirmation of presence: it localizes whatever phrase you supply, so the returned box at image coordinates [0.125, 0.554, 0.289, 0.745] (patient's right lower hemithorax) corroborates location only after presence is established elsewhere — and check that the input phrase matches the chosen option text rather than a different side. (4) Then map the supported text back to the displayed option map and write letter and text together as "A. right pleural effusion," confirming A is right pleural effusion and B is left pleural effusion.

Note on this case: the letter/text pairing was correct and every tool observation addressed the same object and attribute as the question, so this is neither an option-mapping error nor a wrong conclusion — the residual risk was over-crediting the bilateral report and the self-prompted grounding call as side-specific corroboration. A correct grade alone does not show this attribution check was performed.
```

## exp_77fa086c485a78dd0056754b

来源题 [chexbench_openi_0009](../../cases/openi/chexbench_openi_0009.json) · 已剪枝

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality (“right lung” vs “left lung”), and the tools used either answer only presence/absence, disagree, or supply an ROI crop with a limitation note about not inferring patient side.

Verification action: Before emitting the choice, quote an actual observation that explicitly names the chosen side in the chosen anatomical structure. Do not convert a generic “Yes” into laterality, do not infer patient side from screen position or from an abdominal/lateral-view location when the ROI observation says side cannot be inferred, and do not let a conflicting “No” from another tool be silently ignored in the rationale. Re-query with a side-specific request if needed, then map the supported text back to the displayed option and confirm its letter and text agree.

Lesson from this case: the final answer was A and the released reference was A, so the letter/text mapping was correct. But the evidence chain was weak: chest_xray_expert returned only “Yes” to a right-or-left question, llava_med_qa returned “No,” and the ROI crop metadata explicitly said “patient side not inferred” and “Do not infer patient laterality from screen position.” The terminal rationale nevertheless placed the finding on the right based on an alleged anterior upper abdomen/lateral-view location. A correct grade alone does not prove this reasoning is reusable; the observable check is whether a tool result actually supports the chosen laterality.
```

## exp_7742a40eaa1cf5e7d28dcd4a

来源题 [chexbench_openi_0010](../../cases/openi/chexbench_openi_0010.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray laterality/opacity answer after direct QA tools conflict or become unreadable—e.g., one tool says “left lung,” another says “no opacity,” another output is garbled, and ROI crop returns only images—and your draft rationale adds localization such as “posterior lower field” or “left lower lobe” that no tool actually reported.

Verification action: Before emitting, re-read the displayed option map and write the exact supported answer text with its letter. Enumerate only executed observations that addressed the same object and attribute—right-versus-left lung opacity. Keep only what those observations actually said; discard garbled outputs and do not treat an uninterpreted crop as confirmation. Check each phrase in the rationale against the tool text and delete unsupported localization or severity claims. If a same-scope observation names “left lung” and the options are A. right lung opacity / B. left lung opacity, map that to “B. left lung opacity,” confirm the terminal letter and text agree, and note any competing “no opacity” result rather than inventing a more specific radiographic explanation. In this case the final B matched the reference B, so there was no option-mapping error; the caution is that the rationale overstated the evidence and the correct grade alone did not validate that embellishment.
```

## exp_988d108ba4aa3ea574870ef8

来源题 [chexbench_openi_0011](../../cases/openi/chexbench_openi_0011.json) · 活跃

```text
Trigger: You are about to finalize a laterality-specific binary choice from a chest radiograph — e.g., "large right pleural effusion" (A) versus "large left pleural effusion" (B) — when the only image is a lateral view, one VQA model returns the side ("Right"), another returns "no effusion," a third returns uninterpretable text, and the verifier marks the laterality unverified (PARTIALLY_CORRECT / CAUTION). This is the setup where a single model's side-word is being treated as if it established which hemithorax is involved.

Verification action: Before emitting the final letter-text pair, do three observable checks. (1) Re-read the displayed option map and confirm the letter-to-text mapping: A = large right pleural effusion, B = large left pleural effusion. Confirm the terminal answer writes the same side in both the letter and the text. (2) Separate the two attributes the question requires — presence of effusion and laterality — and name for each the observed result that establishes it. A lateral projection marker such as "LT LAT" is a projection/positioning label, not evidence that disease is on the left; a model saying "Right" on a lateral view is an opinion about a side the lateral view may not be able to discriminate. If no observed tool result actually distinguishes right from left, do not treat the side as confirmed: obtain a frontal (PA/AP) view or source-report evidence, or mark the item indeterminate rather than guessing. (3) Reconcile the rationale against the exact tool outputs: do not call the chosen side "the only positive finding" when LLaVA-Med affirmatively said no effusion and the verifier returned PARTIALLY_CORRECT/CAUTION; state the conflict and why the chosen side is preferred. The option-mapping check is necessary but not sufficient — a correct letter/text pair can still hide an unsupported laterality guess, so the evidence check must be performed too. A correct grade alone does not prove the procedure works; here the terminal answer's letter and text agreed and matched the reference A, so this was not an option-mapping error, but the side rested on a model's word for an attribute the single lateral image could not independently establish.
```

## exp_a96c7b0c15c4369b93295eca

来源题 [chexbench_openi_0013](../../cases/openi/chexbench_openi_0013.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray finding whose options differ by laterality or another single attribute, and a tool observation names that attribute.

Verification action: Before emitting the answer, extract the exact attribute from each completed tool observation, confirm the observations refer to the same structure and view asked about, and check whether they agree or conflict. Then map the supported text to the entire displayed option map and write the letter together with its full text, e.g. “A. elevated right diaphragm.” Do not rely on a rationale like “the VLM consistently identifies…” unless each cited tool actually states that same side/attribute. In this case, chest_xray_expert returned “Right” and llava_med_qa returned “the right diaphragm appears to be elevated,” so the supported text matched option A; the reusable safeguard is checking side-specific evidence against the letter-text pair, not the final grade alone.
```

## exp_e5df93d05bc6e2b704eb74df

来源题 [chexbench_openi_0014](../../cases/openi/chexbench_openi_0014.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer whose options differ mainly by laterality—especially after a direct QA tool answers a side-specific question and a grounded report names a finding—before emitting the letter.

Verification action: Restate the supported finding as an exact side-plus-structure phrase, such as “elevated right hemidiaphragm.” Re-read the displayed option map and match that phrase to the option text and letter, writing them together: “A. elevated right diaphragm.” Confirm that the letter, side, and structure all agree and that the opposite-side option is not accidentally selected. Then reconcile the rationale with the exact tool observations: the direct tool’s “Yes” applies only to the precise query asked, and the grounded report supports only the finding it actually states, here “Elevation of the right hemidiaphragm.” Do not claim both tools confirmed a finding unless both actually addressed the same object and attribute. If the direct answer and grounded report conflict on laterality, stop and resolve the conflict before finalizing; if they agree, make that agreement explicit in the rationale. In the source case, both observations supported the right side, and the terminal answer “A. elevated right diaphragm” matched the displayed option map and the released reference. The reusable safeguard is the observable side-to-option mapping and evidence attribution; a correct final grade alone does not prove those checks were performed.
```

## exp_dc164419942771a8c60c2941

来源题 [chexbench_openi_0032](../../cases/openi/chexbench_openi_0032.json) · 活跃

```text
Trigger: When finalizing a forced-choice chest X-ray question that asks for laterality (e.g., right vs left base pulmonary atelectasis) after direct VQA tools have answered “No” to both sides or failed to name a side, and one model returns a side-specific answer whose reasoning is internally contradictory or unsupported.

Verification action: Before emitting the option, require an explicit, same-scope positive result for the chosen side and finding—either a direct QA answer naming that side or a sign-specific check that clearly states increased opacity/atelectasis on that side. Do not promote an isolated side-localizing model when its own rationale undercuts the conclusion, such as saying the right base is “less dense than the left” while concluding right-base atelectasis, which would usually appear as increased density. Also do not override multiple direct “No” answers and negative sign-specific checks for that side with that outlier. If no tool result explicitly supports the chosen side, mark the evidence as insufficient or select only an option with direct positive support. Then map the supported answer text back to the displayed option map and confirm the letter and text agree. In this case, the final “A. right base pulmonary atelectasis” was an evidentiary-promotion error: two direct models said “No,” right- and left-sided sign checks both said “No,” and MedGemma’s right-base claim conflicted with its own density reasoning. The lesson is not about A/B letter mapping; it is about refusing to convert a single contradictory outlier into the final side-specific answer.
```

## exp_3594a1979404b4109ea4184f

来源题 [chexbench_openi_0033](../../cases/openi/chexbench_openi_0033.json) · 活跃

```text
Trigger: In a two-option chest X-ray laterality question about a finding, when direct VQA returns a side word such as “Left,” and a phrase-grounding call is run with a phrase that already contains that same side, while the grounded report either omits the structure or describes unrelated findings.

Verification action: Before finalizing, make the direct question-specific VQA answer the load-bearing evidence for the finding, then re-read the displayed option map and write the exact letter-text pair—confirming that “left” maps to “B. elevated left diaphragm,” not “A. elevated right diaphragm.” Audit each auxiliary tool against the same object and attribute: cite the grounded report only for what it actually says (here, infiltrates, effusions, normal heart size, no pneumothorax—not diaphragmatic elevation), and treat phrase grounding for “elevated left diaphragm” as localization of the supplied phrase, not as independent proof that elevation is present. A silent grounded report on the diaphragm is not a contradiction, so do not overturn the direct side answer on that basis. If the option letter/text is correct but the rationale overstates auxiliary confirmation, keep the answer and correct the rationale.
```

## exp_e6ef18bdb906d7183a768427

来源题 [chexbench_openi_0034](../../cases/openi/chexbench_openi_0034.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer that requires choosing left versus right for a specific basilar finding, and the available evidence is a direct tool’s “Yes” to a combined “right or left” question, a grounded report that does not explicitly name that finding on one side, and/or phrase-grounding boxes for both side-specific candidate phrases.

Verification action: Before emitting the option, inspect the actual tool observations for an explicit same-scope statement naming the exact finding and the exact side. Do not treat “Yes” to a “right or left” prompt as side selection; do not treat cardiomegaly, scarring, gastric bubble, or bilateral/nonspecific basal opacity as proof of one-sided atelectasis; and do not treat a phrase-grounding box as proof that the finding exists—it only localizes the supplied phrase and may return a box for either candidate phrase. If no observation explicitly names the side for the asked finding, mark the laterality as unsupported or obtain side-specific evidence; do not construct a rationale from unobserved signs, and do not let a verifier’s “CORRECT” resolve the ambiguity when it merely restates the proposed answer. Once a side is genuinely supported, map that exact supported text back to the displayed option and check that the letter and text agree. In this case, the terminal “A. right base pulmonary atelectasis” matched option A’s text but was a wrong conclusion: the observations never established right base atelectasis, the reference was B “left base pulmonary atelectasis,” and this was an evidence/laterality error, not a letter/text mapping error.
```

## exp_04dad94a72af72ad170b91d4

来源题 [chexbench_openi_0037](../../cases/openi/chexbench_openi_0037.json) · 活跃

```text
Trigger: Before finalizing a multiple-choice chest X-ray answer whose choices differ only by laterality, such as “A. right indwelling catheter” versus “B. left indwelling catheter,” especially when the image is a lateral view or tool results only affirm presence and do not explicitly name the side.

Verification action: Do not treat “catheter over left-sided vascular structures” as proof of laterality on a lateral radiograph; overlapping structures do not reliably assign right versus left. Require an actually observed tool result or a grounded spatial check/crop/independent reader that explicitly assigns the side on this image. Treat a bare “Yes” to a “right or left” question as presence-only, not laterality evidence, and treat silence on side as no corroboration. If no explicit side evidence is available, do not invent one; report the ambiguity or obtain another check. If an explicit side is supported, map that side’s text back to the displayed option and confirm the letter and text agree. In this case, B matched “left indwelling catheter,” so the failure was not option mapping; it was finalizing an unsupported left-side conclusion despite the earlier caution that the lateral view limits laterality.
```

## exp_705e4443a6551e5198958ca2

来源题 [chexbench_openi_0038](../../cases/openi/chexbench_openi_0038.json) · 活跃

```text
Trigger: When finalizing a laterality multiple-choice chest X-ray answer (e.g., "A. left indwelling catheter" vs "B. right indwelling catheter") and the case for one side rests on a grounding step whose query already contained the side word ("ground 'left indwelling catheter'") or on a second tool from the same model family as one already counted, especially when a direct VQA reader named the opposite side.

Verification action: Before finalizing, audit the corroboration rather than the conclusion. (1) If a phrase-grounding tool was handed the side inside the phrase, run the contralateral control — ground "right indwelling catheter" (or whichever side was not proposed) — and inspect whether it also returns a confident, plausible box. A tool that localizes both phrases carries no laterality evidence; its box confirms only that the model can draw a box around the named phrase. (2) Count votes only across genuinely independent backends: a grounded report and a phrase-grounding call from the same MAIRA-2 family are one vote, not two, and must not be described as "two independent tools." (3) After that accounting, if the independent direct readers split 1–1, obtain a decisive tie-breaker — separate yes/no queries per side, or an ROI crop of the candidate box region re-read directly — instead of letting a leading grounding box tip the balance. (4) Only then map the supported side's wording to the displayed option and confirm the letter and text agree.

Lesson from this case: the terminal "A. left indwelling catheter" matched option A's text, so this was an evidence error, not an option-mapping error. The rationale asserted "two independent MAIRA-2 tools" localized a left catheter, but maira2_grounded_report and xray_phrase_grounding are the same model family, and the grounding query already supplied the side in its phrase — so it returns a box for whatever phrase it is given and proves nothing about laterality. Stripping that illusory corroboration leaves chest_xray_expert ("Left") against llava_med_qa ("right"), an unresolved split; the released reference was B, right. The repair — contralateral control grounding or per-side direct queries — was not executed here and is a caution, not a verified success; apply the check rather than assuming the evidence was independent.
```

## exp_1dc140be75405d7be62a5ced

来源题 [chexbench_openi_0051](../../cases/openi/chexbench_openi_0051.json) · 活跃

```text
Trigger: When finalizing a lateral-only chest X-ray multiple-choice answer between right and left base pulmonary atelectasis, if the terminal tool answer came from a prompt that explicitly names one side or uses a “spine sign suggesting [side]” formulation, and earlier non-leading side-specific queries were symmetric (“Yes” to both sides) or contradictory, treat that as a laterality-evidence failure rather than accepting the last answer.

Verification action: Re-read the exact tool prompt and response. If the response merely echoes the side named in the prompt—as when “suggesting left lower lobe atelectasis” was answered “Spine sign, left lower lobe atelectasis”—discard it as non-independent evidence. Require a separate neutral side-specific observation, a frontal view/frontal report, or explicit landmark evidence that actually distinguishes right from left. Then check that the supported side text maps to the displayed option letter. If no independent side-specific evidence exists, do not convert the leading prompt into a confident laterality choice; mark the evidence insufficient or re-query neutrally. Here the final “B. left base pulmonary atelectasis” mapped letter-to-text correctly, but the conclusion was unsupported: the error was evidentiary, caused by a leading prompt/echo and ignoring the symmetric “Yes/Yes” plus contradictory “No” results.
```

## exp_65b66a9fadad3f67865cc424

来源题 [chexbench_openi_0053](../../cases/openi/chexbench_openi_0053.json) · 活跃

```text
Trigger: When finalizing a left-vs-right base atelectasis multiple-choice answer from a single lateral chest X-ray, and one QA tool answers only “Yes” to an either/or question, other models infer a side from lateral landmarks, and the verifier warns that laterality cannot be reliably confirmed on the lateral view and that an “LT LAT” marker indicates projection rather than the side of the finding.

Verification action: Before choosing an option, require same-scope side-specific evidence: a tool result that explicitly names left or right for the exact asked finding, or a frontal/report confirmation. Do not count a bare “Yes,” the “LT LAT” marker, or lateral-only diaphragm/spine-sign reasoning as confirmation of the lesion side when the verifier flags laterality as indeterminate; if no such evidence exists, treat the side as insufficiently supported and do not finalize a side. If side-specific evidence is present, map that supported text back to the displayed option map and confirm the letter and text agree, and make the rationale match the actual tool outputs rather than overstating agreement. In this case the terminal “A. left base pulmonary atelectasis” matched option A’s text, so the failure was not a letter/text mapping error; it was an evidentiary/laterality overreach despite the verifier’s caution, and the released reference was B, right base pulmonary atelectasis.
```

## exp_eb812dd18f2fef62aa6860b9

来源题 [chexbench_openi_0055](../../cases/openi/chexbench_openi_0055.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer between right-sided and left-sided versions of the same finding, if the direct expert only answered “Yes” to a compound “right or left” question, the grounded report says the lungs are clear, and the phrase-grounding tool returned a box only for the side you are considering, do not treat that one-sided box or a compound “Yes” as side-specific proof.

Verification action: Before finalizing, check the tool log for an independent result that explicitly names the same side and exact finding, not merely “Yes” to an either/or question and not merely a phrase-grounding box generated from the candidate phrase. If only the chosen side was grounded and the other side was not tested, ask for side-specific confirmation or mark the evidence insufficient; do not use `xray_phrase_grounding` as proof that the finding exists. Then map the supported answer text back to the displayed option and confirm the letter and text agree.

Lesson from this case: the terminal choice “A. right upper lobe pulmonary atelectasis” was correctly mapped to option A’s text, so this was not an option-mapping error. The failure was evidentiary: the final answer relied on `llava_med_qa` naming right upper lobe and on a phrase-grounding box for the same right-sided candidate, while `chest_xray_expert` had only answered “Yes” to the compound either/or question and `maira2_grounded_report` reported clear lungs. The released reference was B, left upper lobe pulmonary atelectasis. The reusable caution is to require independent, side-specific positive evidence for the exact finding before choosing laterality, and never treat a one-sided grounding box as confirmation.
```

## exp_143c94f2938d5c898793b4af

来源题 [chexbench_openi_0035](../../cases/openi/chexbench_openi_0035.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer—such as elevated right versus left hemidiaphragm—after a direct VQA tool returns a side word and a grounded report or bounding box mentions a hemidiaphragm.

Verification action: Before emitting the final answer, extract the side from the direct VQA result, map it to the exact displayed option letter and full text, and check the pair for reversal (here “Right” must map to “A. elevated right diaphragm,” not “B. elevated left diaphragm”). Then confirm that the grounded report explicitly names the same object and attribute—e.g., “Elevated right hemidiaphragm”—and that any box is on the same side; if the report or box addresses a different side/attribute or only localizes a supplied phrase, do not cite it as independent confirmation. In this case, the direct result “Right,” the grounded finding “Elevated right hemidiaphragm” with a right-side box, and option A’s text all agree, so the final answer is supported and correctly mapped. If the side, object, attribute, or letter-text mapping conflicts, correct the answer or rationale before finalizing.
```

## exp_57fd761660067566ee6560d9

来源题 [chexbench_openi_0036](../../cases/openi/chexbench_openi_0036.json) · 活跃

```text
Trigger: Before finalizing a multiple-choice chest X-ray answer whose options differ by laterality, especially “right indwelling catheter” versus “left indwelling catheter,” and the rationale cites tool findings to justify the side.

Verification action: Reconcile each clause of the final rationale against the actual observation log. For each side claim, confirm that a tool explicitly named that side for the same finding—not merely “Yes,” not silence, and not an unsupported image detail. If the rationale adds a confirming feature such as an “L” marker or patient-side orientation, verify that the feature appears in a tool observation or direct image check; otherwise remove it or run a grounding step for it. Then map the supported side’s wording to the displayed option and confirm that the chosen letter and text agree. In this case, A/right matched its text and the released reference, and both chest_xray_expert (“Right”) and maira2_grounded_report (“Right chest port-a-cath” with a box) supported right, so this was not an option-mapping error. The added claim about an “‘L’ marker” was not present in the observations and should not have been asserted without verification. A correct grade alone does not prove the rationale was fully supported; the observable checks are explicit side evidence and letter-text agreement.
```

## exp_d2eda84c5289f0bd1cb7de86

来源题 [chexbench_openi_0039](../../cases/openi/chexbench_openi_0039.json) · 活跃

```text
Trigger: Before finalizing a chest X-ray multiple-choice answer whose options differ only by laterality of an indwelling catheter (e.g., “A. right indwelling catheter” vs “B. left indwelling catheter”), especially when one tool answers the right-or-left query with an explicit side and another returns a grounded report such as “Central venous catheter with distal end in the right atrium” plus a box.

Verification action: Separate catheter presence from catheter side-of-insertion. Treat “right atrium” as tip location, not proof of a right-sided catheter. For each tool, require either an explicit side-of-access statement (“right internal jugular/subclavian catheter”) or a verified spatial box that actually marks the catheter on the patient’s right side. Check the image-side convention (on a standard frontal chest X-ray, patient right is image left) and confirm the box covers the catheter path rather than only the central mediastinum or right atrium. If the direct tool explicitly says “Right” and the grounded box independently localizes the catheter to patient right, then select the right-sided option; if the box is not verified or the report only names the distal tip, do not cite it as independent confirmation of right-sided access. Finally, map the supported side’s text back to the displayed option and confirm the letter and text agree.

Lesson from this case: the terminal answer “A. right indwelling catheter” matched the reference, but a correct grade alone does not prove the rationale was sound. chest_xray_expert’s “Right” was explicit laterality and supports A; maira2_grounded_report’s “central venous catheter with distal end in the right atrium” supports presence and tip location, but not automatically right-sided insertion. The final rationale’s claim that both tools identify a catheter “on the patient’s right side” should be accepted only if the grounding box was actually checked as marking the catheter on the patient’s right.
```

## exp_d98ded0d2808a02aec07fefe

来源题 [chexbench_openi_0040](../../cases/openi/chexbench_openi_0040.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice question whose options differ only by laterality of the same finding (e.g., left vs right lower lobe pulmonary atelectasis), and the evidence is a side-only direct reply such as “Left” to an either/or prompt and/or a grounded report that names only a different same-side abnormality such as “Left pleural effusion.”

Verification action: Before emitting the answer, read the displayed option map and confirm the selected letter’s text exactly matches the intended finding and side. Then check the observations for an explicit same-finding, same-side statement. A side-only “Left” can select the side for the exact candidate named in the prompt, but a left pleural effusion or nonspecific left-sided opacity is not by itself proof of left lower lobe atelectasis; use it only as corroborating side evidence. If no observation explicitly ties the exact target finding to that side, obtain a finding-specific result or mark the evidence as insufficient rather than inferring the target finding from an adjacent abnormality. In this case, the terminal answer A = “left lower lobe pulmonary atelectasis” matched the option map and the released reference A, so it was not an option-mapping error. The caution is evidentiary: the final rationale converted “left pleural effusion” into confirmation of left lower lobe atelectasis, while the more direct side evidence was chest_xray_expert’s “Left.” A correct grade alone does not prove that the exact finding was established.
```

## exp_8f03f4347744d57b69825e46

来源题 [chexbench_openi_0041](../../cases/openi/chexbench_openi_0041.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality, such as “left lower lobe pulmonary atelectasis” versus “right lower lobe pulmonary atelectasis,” especially after a compound “left or right” QA question, and the direct QA tools return “No,” negative, normal, uninformative, or side-indeterminate results while the verifier also says laterality cannot be resolved on the lateral view.

Verification action: Before emitting, require side-specific positive evidence for the exact finding and side—for example, an explicit statement or report naming “left lower lobe pulmonary atelectasis” or “right lower lobe pulmonary atelectasis.” Do not treat “No,” “no atelectasis,” “left or right,” normal findings, a grounding box, question format implying a positive finding, or base-rate “common subtle finding” reasoning as side-specific confirmation. Map the supported answer text back to the displayed options and confirm the letter and text agree; A should be chosen only if the supported text is left lower lobe atelectasis, and B only if it is right. If no same-scope side-specific positive evidence exists, mark the evidence as insufficient/indeterminate or seek a frontal view or original report rather than asserting an unsupported side. In this case, the final “A” matched option A’s text and the released reference, but it was not supported by the observed evidence: all direct tools were negative or uninformative, and the verifier noted that left-sided localization was not independently supportable. This is an evidentiary failure, not a letter–text mapping error.
```

## exp_693d4a85b0cfe77b00c4420c

来源题 [chexbench_openi_0042](../../cases/openi/chexbench_openi_0042.json) · 活跃

```text
Trigger: When finalizing a chest-X-ray multiple-choice answer that turns on laterality (e.g., left vs right base pulmonary atelectasis) and the direct QA tool answered only “Yes” to a compound “left or right” question, the grounded-report tool is not applicable because the image is lateral/non-frontal, and the remaining VQA models conflict—one names a side, another says “No,” another says “no focal consolidation,” and another is incoherent.

Verification action: Before selecting the option, list each tool observation and ask whether it explicitly names the asked finding and the correct side. Count only side-specific, same-scope statements as support for an option. Do not treat “Yes” to an either/or laterality question as evidence for either side; do not treat a model’s general “no focal consolidation” as a side-specific negative; and do not treat the verifier’s “CORRECT” as independent resolution of the conflict when it merely restates the proposed answer. If no independent, same-scope result states the side, mark the evidence as insufficient rather than selecting the single side-naming model. If a side is supported, map the supported answer text back to the displayed option map and confirm that the letter and text agree.

Lesson from this case: the terminal answer “B. right base pulmonary atelectasis” matched the released reference “B,” and the letter–text mapping was correct. But the rationale overstated the evidence: `chest_xray_expert` had answered only “Yes” without a side, `llava_med_qa` said “No,” `llava_rad` said “no focal consolidation,” `medvlm_r1` was incoherent, and `maira2_grounded_report` was not applicable for a lateral view. The only side-naming observation was `medgemma`’s “right base,” and the verifier’s “CORRECT” did not add independent side-specific evidence. A correct grade alone does not prove the decision procedure worked; the required check is explicit, independent side-specific evidence before finalizing.
```

## exp_01590cd3f5399dc3b6502830

来源题 [chexbench_openi_0043](../../cases/openi/chexbench_openi_0043.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer, especially when one tool names a side-specific finding (e.g., “small left pleural effusion”) while another grounded report explicitly contradicts it (e.g., “There is no pleural effusion”) and phrase grounding returns a box because it was prompted with the chosen phrase.

Verification action: Before emitting the letter, quote the observation that actually asserts both presence and side — here, chest_xray_expert’s “Small left pleural effusion” — and explicitly acknowledge the conflicting grounded report rather than omitting it. Treat xray_phrase_grounding as localization only, not independent evidence of presence, because it localizes whatever phrase is supplied. Then map the supported text back to the displayed option map and write the letter and text together, confirming “A. small left pleural effusion” and that A is left, not right. If the rationale says phrase grounding is “consistent with option A,” it should make clear this is only location after presence is established by the direct VQA observation, not confirmation that the effusion exists. A correct grade alone does not prove this conflict-and-attribution check was performed.
```

## exp_9a2ff0cdb90c743a78295033

来源题 [chexbench_openi_0044](../../cases/openi/chexbench_openi_0044.json) · 活跃

```text
Trigger: Before finalizing a laterality-specific chest X-ray multiple-choice answer (e.g., left vs right pleural effusion) when one VQA tool names a side, another returns negative or garbled output, and the verifier or ROI step notes a possible finding but says laterality cannot be reliably determined on the available view.

Verification action: Quote the exact observation that actually asserts the chosen side, and do not let any other result stand in as side-specific confirmation. In this case, only chest_xray_expert asserted “Small left pleural effusion.” The LLaVA-Med “No…” result and MedVLM-R1 garbled output do not confirm left; roi_crop returned images without a written side-specific finding; and the verifier’s “possible posterior costophrenic angle blunting” plus the “L” projection marker must not be used as proof of a left effusion because the verifier explicitly says laterality is unreliable on a single lateral view. Retain “A. small left pleural effusion” only with a rationale limited to the one side-specific positive observation and with the conflicting/indeterminate evidence acknowledged. Then map the supported text back to the displayed option map and check that the letter and text agree: A = small left pleural effusion, B = small right pleural effusion. This case had correct letter/text mapping and matched the released reference, so the lesson is evidence attribution, not an option-mapping error or wrong conclusion; a correct grade alone does not prove this check was performed.
```

## exp_b42954f4cbc1514628deb0bd

来源题 [chexbench_openi_0045](../../cases/openi/chexbench_openi_0045.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that requires choosing laterality for a finding, such as right vs left base pulmonary atelectasis, especially after asking a direct VQA tool an either/or question.

Verification action: Before emitting the option, inspect the tool observation for an explicit side-and-finding phrase that matches exactly one displayed option. In this case the observation was “Right base,” which matches option A’s text “right base pulmonary atelectasis,” not option B’s “left base pulmonary atelectasis.” Map that supported text back to the displayed option map and confirm the terminal letter–text pair agrees; here “A. right base pulmonary atelectasis” is correct. Do not treat a bare “Yes” to an either/or laterality question as side evidence, and do not claim the tool explicitly confirmed more than it said. If the tool output is nonspecific or conflicts with the option text, obtain a side-specific result or mark the evidence insufficient. The final-grade correctness alone does not prove the check was performed; the observable check is that the cited tool output names the same side/finding as the selected option and the letter matches that option’s text.
```

## exp_dd9c441f129c7a82ab5a1076

来源题 [chexbench_openi_0046](../../cases/openi/chexbench_openi_0046.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality, such as “left indwelling catheter” vs “right indwelling catheter,” especially when the image is a lateral view or a verifier warns that laterality cannot be reliably determined.

Verification action: Re-read the option map and map the supported side wording to the displayed letter and text, confirming they agree. Then audit each cited observation: it must explicitly address the same object and attribute asked about—catheter presence and side—on a view capable of determining laterality. A bare “Yes,” presence-only answer, silence, absence of a conflicting left/right claim, or a crop artifact is not side corroboration. A lateral-view side claim or VLM consensus on a lateral view is unverified for laterality unless a frontal view or independent spatial grounding explicitly places the catheter on that side. Do not write “two independent VLMs confirmed” or “no contradictory evidence” when the verifier says the side cannot be reliably determined; if no reliable side evidence exists, report laterality as indeterminate or decline to assert the side rather than treating lack of contradiction as support. In the supplied case, B/right matched the option map and the released reference, but the final rationale overstated the evidence: the verifier had cautioned that the lateral image could not determine side, and the suggested confirmation was never executed.
```

## exp_87de0e3744b13c2927e2829d

来源题 [chexbench_openi_0047](../../cases/openi/chexbench_openi_0047.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer whose options differ only by laterality, such as “left indwelling catheter” versus “right indwelling catheter,” especially when one tool answers a right-or-left question and another supplies a grounded report or bounding box.

Verification action: Before choosing the option, require explicit laterality evidence, not just presence or a bare “Yes.” Check that each cited observation names the same side for the same object: the direct QA tool must actually state “right” or “left”; the grounded report must name the same side; and if a box is cited, confirm it falls in the corresponding hemithorax under image convention—for a frontal chest X-ray, patient’s right is image left. Do not treat silence, a general finding, or an unrelated device as corroboration. Then map the supported side’s text to the displayed option and confirm the letter and text agree. If laterality is uncorroborated or ambiguous, obtain an independent check or do not assert the side.

In this case, B was correct: chest_xray_expert said “Right,” maira2_grounded_report said “Right chest port-a-cath,” and the grounded box was on the image-left/patient-right side; the terminal “B. right indwelling catheter” matched both the option map and the reference. A correct grade alone does not prove this check was performed—the reusable lesson is to verify explicit side, grounded location, and option letter/text agreement before finalizing.
```

## exp_b10319734a49844b3911bb9d

来源题 [chexbench_openi_0049](../../cases/openi/chexbench_openi_0049.json) · 活跃

```text
TRIGGER

When a chest X-ray multiple-choice question asks which side of a structure is abnormal (e.g. "elevated right vs left hemidiaphragm"), a direct VQA tool has already returned a side word ("Right" / "Left"), and you are about to finalize while citing an ROI crop, a grounded report, or both as corroboration for that side.

VERIFICATION ACTION

1. Make the direct VQA side word the load-bearing evidence. Map it to the exact displayed option letter and full text and check the pair agrees before emitting anything — here "Right" must map to "A. elevated right diaphragm," not to B. This is the option-mapping check; perform it separately from the evidence check.

2. Audit each auxiliary tool against the same object and attribute as the question:
   - Grounded report: read what it actually asserts. In this case the report listed only cardiac/mediastinal/tracheal/vascular/lung/skeletal/pleural findings and never mentioned the diaphragm or elevation. It cannot be cited as confirming elevation laterality; if the rationale cites it read the "limitations" line (model outputs are not independent confirmation).
   - roi_crop: it is a display/zoom utility. Its own output warns "patient side not inferred" in the coordinates field and "Do not infer patient laterality from screen position" in limitations, and states interpolation adds no acquired detail. So it may be cited only as a visual aid, not as proof of which hemidiaphragm is higher or that elevation is present.

3. Before finalizing, rewrite the rationale so every cited tool is described only for the attribute it actually addressed. Do not write "the zoomed crop shows the right hemidiaphragm positioned higher" — the crop tool produced a zoomed image, did not measure dome heights, and explicitly declined to infer patient side; the viewer's-left-is-patient's-right convention is background knowledge, not a tool observation.

4. If the side word and an auxiliary result conflict, keep the direct question-specific observation and say which listed finding/observation qualifies; do not let a silent or non-addressing auxiliary report overturn or "corroborate" it.

LESSON FROM THIS CASE

The terminal answer "A. elevated right diaphragm" matched the displayed option map and the released reference (A), so there was no option-mapping error. The residual defect is evidence attribution: the rationale credited the roi_crop image with confirming right-sided elevation, which the crop tool's own limitations forbid. A correct grade alone does not prove the evidence-attribution check was performed; the same rationale pattern would mislead on an image where the side word was wrong.
```

## exp_84563e77405370759e113d3e

来源题 [chexbench_openi_0067](../../cases/openi/chexbench_openi_0067.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that requires right-vs-left laterality for a finding such as base pulmonary atelectasis, especially after asking a tool an either/or side question and receiving only “No” or no side-specific observation.

Verification action: Before emitting the option, inspect the recorded tool observations for an explicit same-scope phrase that names both the exact finding and the exact side. A bare “No” to “right base or left base pulmonary atelectasis” does not support either side, and a tool call with no recorded observation cannot be used as evidence. If the final rationale claims right base atelectasis but no observation explicitly contains “right base pulmonary atelectasis,” treat the laterality as unsupported and do not finalize that side. Then map any genuinely supported side-and-finding text back to the displayed option map and confirm the letter and text agree. In this case, A matched the text “right base pulmonary atelectasis,” so the failure was not letter/text mapping; it was an evidence/laterality error: the observed tool result was uninformative, the laterality was not established, and the terminal answer asserted right base despite the reference being B “left base pulmonary atelectasis.”
```

## exp_48c67b492e97e8f8bc11ecb0

来源题 [chexbench_openi_0063](../../cases/openi/chexbench_openi_0063.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks right vs left for a specific finding, and the evidence consists of a direct VQA “Yes” to a combined “right or left” question, a grounded report naming only a sign such as “increased density in the right upper lobe,” and/or a phrase-grounding box for the candidate phrase.

Verification action: Before emitting the option, inspect the raw observations for one explicit statement naming the exact finding and exact side. Do not treat a bare “Yes” to “right or left” as side evidence. Do not treat a phrase-grounding box as proof that the finding exists; it only localizes the supplied phrase. A nonspecific sign such as right upper lobe increased density can support the right-sided region, but it should not be described as explicit confirmation of atelectasis, especially when another model says no atelectasis is present. If no observation explicitly names the asked finding on one side, seek side-specific evidence or mark that exact finding unsupported. Then map the supported text back to the displayed option map and confirm the terminal letter and text agree. In this case, “A. right upper lobe pulmonary atelectasis” matched option A and the released reference A, so there was no option-mapping error; the caution is that the terminal rationale overstated ambiguous and localization-only evidence. A correct grade alone does not prove that this check was performed.
```

## exp_98684a78d4993f61572d1c4f

来源题 [chexbench_openi_0087](../../cases/openi/chexbench_openi_0087.json) · 活跃

```text
Trigger: Before finalizing a multiple-choice chest X-ray answer whose options differ only by catheter laterality (e.g., “A. left indwelling catheter” vs “B. right indwelling catheter”), especially when the image is lateral and the rationale mentions a side or side-of-insertion.

Verification action: Check the actual observation log for an explicit side statement or verified spatial localization for the catheter on this image. Do not treat “catheter projecting over the anterior mediastinum,” a lateral-view overlap, or “tip in the right atrium” as proof of insertion laterality; those are presence or tip-location findings only. Require a tool result that explicitly names right or left access/insertion, or a checked grounding box/crop that marks the catheter on that patient side under the image-side convention. Then map the supported side’s text back to the displayed option and confirm the letter and text agree. If the rationale says a different side than the chosen option, or no explicit side evidence exists, do not invent or assert laterality; report ambiguity or run another check. In this case, B/right matched the reference and B’s text, so it was not an option-mapping error, but the rationale’s claim of “left-sided insertion” and the lack of observed tool evidence mean the final answer was not evidence-supported. A correct grade alone does not prove the procedure was sound.
```

## exp_9921ad662559355442fbed84

来源题 [chexbench_openi_0069](../../cases/openi/chexbench_openi_0069.json) · 活跃

```text
Trigger: When a chest X-ray multiple-choice question asks for a side-specific finding (e.g., left vs right clavicle deformity) and the direct tools have returned “No”/“No significant findings” or only a fragmented nonspecific string, but a verifier or late model output supplies a side-specific localization, before finalizing the letter.

Verification action: Re-read the displayed option map and write the supported text with its letter (here A = “left clavicle deformity”, B = “right clavicle deformity”). Then quote the direct tool observations that address the exact object and attribute—clavicle and deformity—and the side. For any laterality claim, require an observed R/L marker or explicit patient-side evidence; do not infer patient side from viewer’s left/right, and note that roi_crop explicitly says patient side is not inferred. Do not count a verifier’s “CORRECT” or an ambiguous token such as “Think fracture” as independent evidence of presence or side. If the verifier introduces a new side-specific finding that the direct tools did not report, especially when direct tools say no/normal, treat it as unverified and do not select that side merely because the question forces a choice. If no direct observation supports either side, state the forced-choice limitation rather than inventing a finding. Finally map the supported text back to the option map and check that letter and text agree.

Lesson from this case: this was a wrong-conclusion/evidence-attribution error, not an option-mapping error. “A” correctly maps to “left clavicle deformity,” but the left-side claim came only from the verifier and contradicted chest_xray_expert (“No”), maira2_grounded_report (“No significant findings.”), and llava_med_qa (“No”); medvlm_r1 was fragmented. The released reference was B, “right clavicle deformity.” The verifier’s “CORRECT” did not resolve the conflict or supply independent image evidence.
```

## exp_e5f47c23bae4590b6394be4b

来源题 [chexbench_openi_0070](../../cases/openi/chexbench_openi_0070.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer that chooses laterality for a named finding, especially after a direct VQA tool answered only “Yes” to an either/or right-vs-left question and the final rationale itself names a side.

Verification action: Before emitting the option, extract the exact side-and-finding phrase from the final rationale, map that phrase back to the entire displayed option map, and confirm the terminal letter and option text both agree with it. In this case the rationale said “left upper lobe atelectasis,” while the terminal answer was “B”; option A was “left upper lobe pulmonary atelectasis” and option B was “right upper lobe pulmonary atelectasis,” so the letter–text mapping should have selected A. Also, do not treat the bare “Yes” to “right upper lobe pulmonary atelectasis or left upper lobe pulmonary atelectasis” as laterality evidence, and if a grounded-report call was proposed but no observation was returned, do not cite it or invent side-specific findings. If no observation explicitly names the side, mark laterality unsupported or obtain side-specific evidence. This was an option-mapping error: the supported text was left, but the selected letter was B/right, whose text conflicted with the rationale and the released reference A.
```

## exp_6165bb2af9050ad3a606b700

来源题 [chexbench_openi_0076](../../cases/openi/chexbench_openi_0076.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that requires choosing laterality for a finding, especially after a VQA tool returned only a bare “Yes” to a combined “right or left” question, and the draft rationale names one side.

Verification action: Before emitting the option, require an observed tool result that explicitly names the exact finding and side; do not treat “Yes” to a combined laterality question, or a follow-up call with no returned observation, as side-specific evidence. Then extract the exact supported side-and-finding phrase, map it to the displayed options, and check that the terminal letter, its option text, and the rationale all agree. In this case, the only observation was “Yes” to “right upper lobe pulmonary atelectasis or left upper lobe pulmonary atelectasis,” which did not establish laterality. The terminal answer was B, but its reason said “left upper lobe pulmonary atelectasis,” which matches option A and the released reference A. That is a finalization/letter–text mapping failure: the rationale supported left, while the selected letter pointed to right. The observable check is that a cited observation explicitly names “left upper lobe pulmonary atelectasis,” and the selected letter’s displayed text is exactly that; otherwise do not finalize, or mark the laterality as unsupported. An unexecuted side-specific repair must not be treated as confirmation.
```

## exp_e775c8e12d289ae53542b910

来源题 [chexbench_openi_0079](../../cases/openi/chexbench_openi_0079.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality (e.g., “surgical instruments in the left breast” vs “right breast”), especially when one tool returns only “Yes”/presence, another returns “No,” and ROI/verifier notes say laterality cannot be inferred from the lateral view or screen position.

Verification action: Before emitting the letter, require and quote a tool observation that explicitly names the chosen side for the same finding and anatomical structure. Treat a bare “Yes” as supporting presence only, not left versus right. Check ROI and verifier notes for “patient side not inferred” or “laterality cannot be determined”; if present, do not manufacture a side from projection geometry, screen position, or the fact that one option was proposed earlier. Note that options differing only by laterality both share the same presence finding, so “A is the only choice consistent with presence” is not valid discrimination. Then map the supported answer text back to the displayed option map and confirm its letter and text agree.

Lesson from this case: the terminal answer was “A. surgical instruments in the left breast,” and the letter/text mapping itself was correct; the released reference was B (“right breast”). The failure was a wrong laterality conclusion: chest_xray_expert gave only “Yes,” llava_med_qa said “No,” roi_crop said patient side was not inferred and warned not to infer laterality from screen position, and verify rated the answer only PARTIALLY_CORRECT/CAUTION because laterality could not be determined. The final rationale admitted laterality was unverifiable yet still selected A. Do not finalize a sided answer when the evidence chain lacks an explicit side and the verifier/ROI notes warn against inferring one.
```

## exp_976e8aabe29d50628b3447b1

来源题 [chexbench_openi_0085](../../cases/openi/chexbench_openi_0085.json) · 活跃

```text
Trigger: When finalizing a side-specific chest X-ray multiple-choice answer, such as left versus right clavicle deformity, and the image is lateral or side-superimposed, especially when one VQA tool names a side while another says no deformity or the verifier warns that laterality cannot be determined.

Verification action: Before emitting the letter, require and quote an observation that explicitly establishes both presence and side on a view that can lateralize the finding, such as a frontal PA/AP image or a report stating the side. Check the view record and any verifier caution; do not treat a lone side word from a lateral view, screen position, or “only positive model assertion” as evidence of laterality. If no such observation exists, mark the side-specific options as unsupported rather than finalizing a side. Then map the supported answer text back to the displayed option and confirm that the letter and text agree before answering.

In this case, the terminal answer was B. right clavicle deformity and the released reference was A. left clavicle deformity. B’s letter and text did agree with each other, so this was not an option-mapping error. It was a wrong-conclusion/evidence failure: chest_xray_expert said “Right,” but llava_med_qa said there was no deformity and verify cautioned that the lateral view superimposes the clavicles and cannot establish laterality. The terminal choice converted the lone positive side assertion into B and ignored the laterality limitation. This failed trajectory supports the caution above; an unexecuted frontal-view repair is not a verified success.
```

## exp_0846374f3d1b31ab2d2d5bae

来源题 [chexbench_openi_0086](../../cases/openi/chexbench_openi_0086.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer that requires left/right laterality, such as “left thoracic vertebrae scoliosis” vs “right thoracic vertebrae scoliosis,” especially when the image is a lateral view, the earlier reasoning says laterality cannot be reliably determined, and a side-specific tool call was made but no tool observation appears.

Verification action: Before emitting the letter, inspect the transcript for an actual returned observation that explicitly asserts both the finding and the side—e.g., “right thoracic scoliosis”—and quote it. Do not treat a tool call, an empty observations list, or a statement like “the documented finding for this case” as evidence. If the only support is subtle vertebral rotation on a lateral view, do not infer left versus right; laterality is unsupported. Also reconcile the final rationale with earlier reasoning: if the earlier step said a lateral view cannot distinguish left from right, the final answer must not silently reverse that unless a new observed result resolves it. Then map the supported text back to the displayed option and confirm letter and text agree. In this case A correctly mapped to “left thoracic vertebrae scoliosis,” so the failure was not option mapping; it was an unsupported laterality conclusion, while the released reference was B, “right thoracic vertebrae scoliosis.” This failed trajectory supports the caution, but a correct grade alone would not prove the evidence check was performed.
```

## exp_d5b109a06b3c91232a72b77a

来源题 [chexbench_openi_0090](../../cases/openi/chexbench_openi_0090.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer whose options differ only by catheter laterality, such as “A. right indwelling catheter” versus “B. left indwelling catheter,” and the rationale relies on a lateral view, “posterior trajectory,” or vague “tool confirmation” rather than an observed side-specific result.

Verification action: Before finalizing, check the actual observation log for this image and require an explicit side-of-access statement from a tool or independent reader, or a verified spatial box clearly marking the catheter on the named side. Do not infer laterality from a lateral radiograph’s catheter course, from catheter presence alone, from tip location such as “right atrium,” or from a bare yes/no. If an earlier step correctly noted that the lateral view makes laterality uncertain, do not override that caution unless new observed side-specific evidence appears. Then map the supported side’s text back to the displayed option and confirm that the letter and text agree. In this case, B/“left indwelling catheter” matched its option text, but the final reason cited “tool confirmation” and “posterior trajectory” with no observed tool results supporting left laterality; the reference was A/“right indwelling catheter,” so this was an unsupported evidence conclusion, not an option-letter/text mapping error.
```

## exp_1e29f7019900888076c5fb54

来源题 [chexbench_openi_0091](../../cases/openi/chexbench_openi_0091.json) · 活跃

```text
Trigger: You are finalizing a chest X-ray multiple-choice answer whose options differ only by “left lung” vs “right lung,” and the only localization cue is a phrase-grounding box or screen coordinate rather than an explicit laterality statement.

Verification action: Before emitting the answer, quote the actual side evidence and reconcile it with the verifier. If the verifier says the proposed side is INCORRECT/CAUTION or maps the box to the opposite hemithorax—here x≈0.295–0.455 was image-left and, under the verifier’s stated frontal convention, patient-right—do not keep the original letter. Select the displayed option whose text matches the verified side, or state uncertainty if no side is actually established. Do not invert “image-left” into “image right,” do not infer patient side from screen position when roi_crop says laterality was not inferred, and do not ignore a verifier conflict. Finally, map the supported text back to the option map and confirm the letter and text agree.

Lesson from this case: the terminal answer “A. surgical instruments in the left lung” had correct letter/text pairing, so this was not an option-mapping error. The wrong conclusion came from reversing the grounding box’s laterality and preserving A despite the verifier saying A was INCORRECT and that the box, if relevant, fell on the patient’s right (option B). If relying on the grounding box, take the side from the verifier’s coordinate-to-patient mapping, not from an invented or reversed interpretation.
```

## exp_1017900a83252568165c55ad

来源题 [chexbench_openi_0064](../../cases/openi/chexbench_openi_0064.json) · 活跃

```text
Trigger: When finalizing a right-vs-left laterality multiple-choice chest X-ray answer after a chest X-ray tool returned only a bare “Yes” to an either/or question, or after a planned side-specific query has no recorded observation.

Verification action: Before emitting the option, inspect the actual recorded tool observations for an explicit same-side, same-finding phrase that matches exactly one displayed option. Do not treat a bare “Yes,” an unobserved follow-up call, a general statement that basilar atelectasis is present, or “right base is the most common location” as side-specific evidence. If an observation explicitly names the side and finding, map that text back to the displayed option map and confirm the terminal letter and text agree. If no such observation exists, do not present the side as confirmed; obtain and inspect a side-specific result or mark laterality unsupported. In this case the terminal “A” matched option A’s text, so this was not a letter/text mapping error; it was an evidentiary overreach, even though the released reference was also A. A correct final grade alone does not show that the cited evidence supported the choice.
```

## exp_34a573f4a2930f14b433c418

来源题 [chexbench_openi_0065](../../cases/openi/chexbench_openi_0065.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer, such as right vs left pulmonary atelectasis, after asking a direct VQA tool an either/or question and especially when a grounded-report tool is not applicable because the image is lateral.

Verification action: Before emitting the option, inspect the actual tool observations for an explicit answer naming the side and finding that matches exactly one displayed option. Here, llava_med_qa explicitly returned “pulmonary atelectasis in the right lung,” which matches option A’s text; chest_xray_expert returned only “Right lung” in response to the right-or-left question, so it can corroborate the side but should not be described as independently repeating the full finding unless it actually did. Map the supported side/finding back to the displayed option map and confirm the terminal pair agrees: “A. pulmonary atelectasis in the right lung.” Do not count a not-applicable grounded report as evidence, and do not treat a bare “Yes,” a side-only answer, or a conflicting/nonspecific observation as sufficient without resolving it. If the evidence does not clearly name the same side and finding as one option, obtain side-specific evidence or mark the evidence insufficient.
```

## exp_b455b1a22a76b03b988061ae

来源题 [chexbench_openi_0066](../../cases/openi/chexbench_openi_0066.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by catheter laterality (e.g., “A. right indwelling catheter” vs “B. left indwelling catheter”), especially when the rationale cites a direct expert/VQA answer plus a grounded report or box.

Verification action: Separate catheter presence, tip location, and side-of-access. Count a tool as laterality evidence only if it explicitly assigns the catheter to the right or left for the same finding; a bare “yes,” “catheter present,” “tip in SVC/right atrium,” or unchecked box is not enough. If citing a grounded box, apply the frontal chest X-ray convention—patient right is image left—and confirm the box covers the catheter path on that side, not just the central tip. Reconcile tools for any opposite-side statement. Then map the supported side to the displayed option and confirm the chosen letter’s text matches that side. In this case, “Right side” plus “Right-sided port-a-cath…” with an image-left upper-chest box supported A/right, and A’s text matched; this was not an option-mapping error. A correct grade alone is not the proof—the explicit side evidence and letter-text agreement are the checks.
```

## exp_2392a4aa387947fc26910b58

来源题 [chexbench_openi_0068](../../cases/openi/chexbench_openi_0068.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray laterality answer, such as left versus right base pulmonary atelectasis, after several VQA tools return bare “No,” generic normal reports, or incoherent side fragments, and one tool returns an explicit side-plus-finding phrase.

Verification action: Before emitting the option, inspect the actual raw observation for an exact same-scope phrase naming the asked finding and the asked side. In this case MedGemma explicitly said “left base pulmonary atelectasis,” so that is the usable side-specific evidence. Do not count a bare “No” to an either/or prompt, a generic report lacking the finding, an incoherent fragment containing “left,” a negative gastric-bubble/landmark query, dataset-frequency priors, or the verifier’s “CORRECT” as proof of laterality. Map the exact supported phrase back to the displayed option map and confirm the letter and text agree: option A’s text is “left base pulmonary atelectasis,” and the terminal “A. left base pulmonary atelectasis” agrees with both the option map and the released reference A. If no exact side-plus-finding phrase is present, or if there is an exact opposite-side phrase, treat laterality as unsupported or conflicted and seek frontal/report/metadata confirmation rather than guessing. The final rationale should cite the explicit tool observation, not the verifier, and should not claim there was no contradiction when nonspecific negative outputs were present.
```

## exp_decff4ae64679d0edbae6771

来源题 [chexbench_openi_0072](../../cases/openi/chexbench_openi_0072.json) · 活跃

```text
Trigger: When finalizing a two-option chest X-ray laterality question—such as elevated right versus elevated left hemidiaphragm—after a direct VQA/expert tool returns a side word and auxiliary tools include a grounded report or phrase grounding.

Verification action: Before emitting the answer, extract the side from the direct VQA/expert result and map it to the exact displayed option letter and full text, checking for reversal (here, “Left” must map to “B. elevated left diaphragm,” not “A”). Then audit every auxiliary result against the same object and attribute: a grounded report only confirms elevation if it explicitly names the same hemidiaphragm and elevation; if it is silent, says “No other relevant findings,” or addresses another finding such as a central line, do not cite it as confirmation. Treat phrase grounding for the supplied phrase “elevated left diaphragm” as localization of that phrase, not as independent proof that the finding is present. In this case the direct expert answer “Left” supports B, and B matches both the displayed option text and the released reference; the grounded report was silent on the diaphragm, and the phrase-grounding result only localized the supplied phrase. So the terminal answer was correctly mapped, but the rationale should not overclaim auxiliary confirmation. Correct grade alone does not prove this evidence-attribution check was done.
```

## exp_022495dfee113e528c8f2a6f

来源题 [chexbench_openi_0074](../../cases/openi/chexbench_openi_0074.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality of an indwelling catheter (e.g., A. left indwelling catheter vs B. right indwelling catheter), and the rationale cites both a direct side answer and a grounded report/box.

Verification action: Separate catheter presence, side-of-insertion, and catheter-tip location. Treat “right atrium” or “superior-atrial-right atrial junction” as tip location only, not by itself as proof of right-sided insertion. Require an explicit side-of-access statement such as “Right side” or “Right-sided port-a-cath,” and, if citing a grounded box, confirm the box marks the catheter on the patient’s right using standard frontal CXR orientation (patient right = image left). Then map the supported side’s text back to the displayed option and confirm the chosen letter and text agree. In this case, chest_xray_expert said “Right side,” maira2_grounded_report said “Right-sided port-a-cath” and gave a box on the image-left/patient-right side, and B’s text was “right indwelling catheter,” so the final answer B/right was supported and correctly mapped. The lesson is to verify the side-of-access and letter-text mapping, not merely the correct grade; do not use “right atrial junction” alone as laterality evidence.
```

## exp_f653e60ae67083f4ffb3841c

来源题 [chexbench_openi_0075](../../cases/openi/chexbench_openi_0075.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality of an indwelling catheter/port, such as “A. left indwelling catheter” versus “B. right indwelling catheter,” and the rationale cites tool results to justify the side.

Verification action: Separate catheter presence, tip location, and access side. Require each cited tool result to explicitly assign the same side to the same catheter/port on this image—e.g., “Left-sided port-a-cath” or “Left”—rather than accepting mere presence, a bare “yes,” silence, or tip location such as SVC/right atrium as side evidence. Check that the cited tools do not conflict. Then map the supported side text back to the full displayed option map and confirm the selected letter and text agree. In this case, maira2_grounded_report reported “Left-sided port-a-cath” and chest_xray_expert answered “Left,” so A. left indwelling catheter was supported and matched the reference; no earlier supported conclusion was lost, and there was no option-mapping or evidence error. The correct grade alone is not the verification; the explicit side evidence and letter-text agreement are.
```

## exp_99e68fccdfc03fe63c39f20c

来源题 [chexbench_openi_0077](../../cases/openi/chexbench_openi_0077.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality of an indwelling catheter (for example, “right indwelling catheter” versus “left indwelling catheter”), especially when the rationale cites multiple tool outputs for the side.

Verification action: Check the actual observations for the same finding and attribute—indwelling catheter laterality—not just the final rationale. For each tool, distinguish an explicit side statement (“Left side,” “Left-sided PICC catheter”) from mere presence or distal tip/location language (“overlies superior vena cava,” “right atrium”). If a grounding box is cited, verify that it marks the catheter on the stated patient side under standard frontal-view convention, rather than only the mediastinum or SVC region; if the box is not verified, do not count it as independent side confirmation. Reconcile all explicit-side statements: if they agree, use that side; if they conflict or no explicit side is present, do not invent one. Then map the supported side back to the displayed options and confirm that the terminal letter and text agree with each other and with the released reference. A letter-text mismatch is an option-mapping error; letter-text agreement without same-object side evidence is an evidence or wrong-conclusion error. Also check whether an earlier supported conclusion was lost during finalization. In this case, chest_xray_expert said “Left side,” maira2_grounded_report said “Left-sided picc catheter overlies superior vena cava” with a box, and xray_phrase_grounding returned “Left picc catheter.” with a box; the terminal answer B “left indwelling catheter” matches the option map and reference. The lesson is that a correct grade alone is not proof; the observable checks are explicit same-object laterality evidence, verified grounding-box coverage when cited, and letter-text agreement.
```

## exp_165847584a69ddf9b1172a7c

来源题 [chexbench_openi_0081](../../cases/openi/chexbench_openi_0081.json) · 活跃

```text
Trigger: Before finalizing a frontal chest X-ray multiple-choice answer whose choices differ only by indwelling catheter laterality (“left” vs “right”), especially when the rationale cites a direct side answer, a grounded report, and a phrase-grounding box.

Verification action: Separate catheter presence, side of insertion, and tip location. Accept an explicit direct answer such as “Left side” to a presence-and-side question as laterality evidence. In a grounded report, accept “left subclavian port-a-cath” as side evidence because it names the access side; do not treat “tip in the SVC” as side evidence. For phrase grounding, check whether the query phrase already contains the disputed side. If it does, the returned phrase is not independent confirmation; verify that the returned box actually lies on the patient’s left under standard frontal convention (patient left = image right) and covers the catheter, or use a side-neutral or independent check. If verified evidence conflicts or only establishes presence, do not choose a side; obtain another check. Then map the supported side’s wording back to the displayed option and confirm that the letter and text agree.

Lesson from this case: A / “left indwelling catheter” matched the released reference and the option map. chest_xray_expert’s “Left side” and maira2’s “Left subclavian port-a-cath,” with a box on the image-right side in a frontal view (patient left), support left. The xray_phrase_grounding call was primed with the word “left” and returned the same phrase with a consistent box; that supports localization, but it should not be described as independent explicit laterality confirmation unless the box convention was checked. A correct grade alone does not prove that clause of the rationale was sound.
```

## exp_9441cccdf7cba1c4885e10de

来源题 [chexbench_openi_0092](../../cases/openi/chexbench_openi_0092.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks right-vs-left for an opacity, the VQA tools disagree, and the verifier explicitly says laterality is indeterminate on a lateral-only view or warns that an “LT LAT” marker is positioning-only.

Verification action: Before emitting the option, search the recorded observations for an explicit same-scope statement naming both the exact finding and the exact side. Do not treat a bare “Left Lung” response, a majority vote among VQA models, a “No opacity” response, or the “LT LAT” marker as side evidence. If the verifier says laterality is indeterminate and no observation explicitly names the asked finding on one side, mark the side unsupported rather than converting model consensus into a laterality. If a side-specific statement is found, map its text back to the displayed option and confirm the letter and text agree. In this case, B matched “left lung opacity” as a letter/text mapping, but that was not the error; the error was finalizing B on majority VQA consensus despite the verifier’s indeterminate-laterality caution, while the reference was A “right lung opacity.”
```

## exp_95c43dbae658fafae048efcf

来源题 [chexbench_openi_0095](../../cases/openi/chexbench_openi_0095.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer that requires right-vs-left laterality for lung opacity, especially on a lateral view or after a tool call whose observations are empty/unrecorded, do not infer laterality from the “left lateral” label or from a nonspecific location such as “posterior lower field.”

Verification action: Before emitting the option, inspect the executed observations for an explicit same-scope statement naming both the exact finding and the exact side, e.g. “left lung opacity.” If the tool call has no recorded observation, treat it as no evidence; a bare lateral-view label or posterior lower-field appearance does not establish left lung opacity. If no observation explicitly supports a side, seek a side-specific query or mark laterality unsupported rather than embellishing the rationale. Then map the supported text back to the displayed option map and confirm the letter and text agree. In this case, B matched “left lung opacity” and the reference, so there was no option-mapping error; the caution is that the terminal rationale added unsupported localization and lobar inference while the observation set was empty. A correct grade alone does not prove that this evidence check was performed.
```

## exp_293479380d148cb95b9af892

来源题 [chexbench_openi_0099](../../cases/openi/chexbench_openi_0099.json) · 活跃

```text
TRIGGER
When finalizing a chest X-ray multiple-choice answer whose options differ only by indwelling-catheter laterality (e.g., A "left indwelling catheter" vs B "right indwelling catheter"), especially when the draft rationale cites a laterality marker, an external connector/chest-wall position, a crop/box location, or a catheter-tip site instead of an explicit side-of-insertion statement.

VERIFICATION ACTION
1. Attribute check per tool output: keep only statements about the same object and attribute as the question — catheter side-of-insertion (e.g., "Left", "Left-sided PICC", "Right-sided port-a-cath"). Reclassify "right atrium", "SVC/atrial junction", "overlies ...", external connector location, and any crop box or screen coordinate as presence or tip-location evidence only, never as laterality evidence — the roi_crop output itself states "patient side not inferred."
2. Marker/position caution: if the rationale's only laterality basis is that the device sits under a "LEFT" marker, near an edge of the image, or inside a drawn box, treat that as unverified for laterality. Prefer the explicit side statement; if none exists, do not choose a side.
3. Lost-conclusion check: scan earlier tool observations for an explicit side answer that the final rationale dropped or replaced with weaker wording. If one exists (here chest_xray_expert answered "Left"), reinstate it as the stated basis.
4. Letter–text mapping: take the supported side's text and match it against the displayed option map; confirm the chosen letter's text is identical (A = "left indwelling catheter"), then emit.

Lesson from this case: the grade was correct, but the terminal reason rested on a marker/connector position, not on the explicit "Left" that actually supported the choice — a correct grade alone is not proof the procedure worked. Watch for a letter–text mismatch (option-mapping error) as distinct from a rationale that cites non-same-attribute evidence (evidence error).
```

## exp_52de761927b5390c6ac2436a

来源题 [chexbench_openi_0096](../../cases/openi/chexbench_openi_0096.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks left-versus-right for a finding, especially after an either/or tool query returns only a bare “Yes” or after side-specific calls have no recorded observation, and the draft rationale names a specific side.

Observable verification action: Before emitting the terminal answer, extract the exact side-and-finding phrase from the rationale, map it back to the displayed option map, and confirm that the emitted letter’s text matches that phrase. If the rationale says “left upper lobe pulmonary atelectasis,” it must map to the option whose text is left upper lobe pulmonary atelectasis, not the right upper lobe option. Separately, confirm that a recorded tool observation explicitly names that exact side and finding. Do not treat a bare “Yes” to a combined “right or left” question as laterality evidence, do not infer the opposite side merely because one side lacks explicit support, and do not count unrecorded side-specific calls as evidence. If no explicit observation supports either side, seek a new side-specific observation or mark the finding unsupported instead of choosing by exclusion. In this case, the final rationale named left upper lobe but emitted B, whose text was right upper lobe, while the reference was A, left upper lobe; a terminal letter/text check would have caught the mapping error.
```

## exp_1a2d77dfd5540ca629113cce

来源题 [chexbench_openi_0097](../../cases/openi/chexbench_openi_0097.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer for left-vs-right laterality of a finding such as mild pulmonary atelectasis, and the evidence is a bare “No” to a combined left/right VQA question plus a grounded-report phrase like “mild linear atelectasis or scarring in the left lung base.”

Verification action: Before emitting the option, inspect the raw observations for an explicit same-scope assertion that names the exact asked finding and exact side. Treat a bare “No” to a combined “left or right” question as non-side-specific, not as confirmation of either side. Treat “linear atelectasis or scarring in the left lung base” as support only for that qualified left-base phrase; it does not establish the unqualified “mild left lung pulmonary atelectasis” and does not support the right side. If no exact side-and-finding assertion exists, run separate side-specific queries or use another independent tool to corroborate; record any conflict rather than silently choosing a side from a nearby phrase. Then map the supported text to the displayed option map and confirm letter and text agree. In this case, “A. mild left lung pulmonary atelectasis” matched option A, so the error was not option mapping; it was an evidence-scope/wrong-conclusion error: the terminal answer relied on a left-base atelectasis/scarring phrase while the released reference was B/right, and no observation explicitly asserted right pulmonary atelectasis. A correct letter-to-text check alone would not catch that.
```

## exp_93567b3a1753d716d25f9a59

来源题 [chexbench_openi_0100](../../cases/openi/chexbench_openi_0100.json) · 活跃

```text
Trigger: When finalizing a right-vs-left chest X-ray multiple-choice answer for a specific finding, if the only side-specific observation is a phrase-grounding box for one candidate while direct VQA or a grounded report is negative, nonspecific, or says “No significant findings.”

Verification action: Before emitting the option, scan the recorded tool observations for an explicit statement that names the exact finding and exact side as present. Treat a phrase-grounding box only as localization of the supplied phrase, not as proof that the finding exists. Treat a bare “No” to “left or right [finding]” as supporting neither side. If no observation explicitly supports the exact finding on one side, mark that finding/side unsupported and do not finalize it based on the grounding box; seek another side-specific observation or state uncertainty. Then map any genuinely supported finding text back to the displayed option letter and text and confirm they agree. In the supplied case, the terminal “A. left lower lobe pulmonary atelectasis” matched option A, so there was no letter/text mapping error; the failure was an evidence error: the left-side phrase-grounding box was used as if it proved left atelectasis despite the direct VQA answer “No,” the grounded report “No significant findings,” and another VQA response denying both sides, while the released reference was B, right lower lobe pulmonary atelectasis.
```

## exp_fde4da095750fbe66fb84f42

来源题 [chexbench_openi_0105](../../cases/openi/chexbench_openi_0105.json) · 活跃

```text
Trigger: Before finalizing a left-vs-right multiple-choice chest X-ray answer when any tool returns an explicit side word or a side-containing grounded phrase — e.g., chest_xray_expert returns “Right” or xray_phrase_grounding returns “surgical clips in the right upper quadrant” — and another tool supplies only a bounding box or coordinate.

Verification action: Quote the explicit side word from the tool output and use that as the load-bearing laterality evidence. Do not convert a bounding-box x-coordinate or “left of midline” on the image into patient-left; on a frontal chest radiograph, screen-left may be the patient’s right. Check that the chosen option’s letter and text match the explicit side: “right abdomen” must map to B, not A. If the explicit side words agree, finalize that side even if another tool only reports absence or no instruments; if they conflict, re-query with a side-specific request or state uncertainty. In this case, chest_xray_expert said “Right” and xray_phrase_grounding said “right upper quadrant,” so the supported answer was B; choosing A came from misreading the coordinates as patient-left and ignoring the explicit “right” wording.
```

## exp_2e47fb28c5a1c88e12144626

来源题 [chexbench_openi_0107](../../cases/openi/chexbench_openi_0107.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer that requires right-vs-left laterality, such as “right thoracic vertebrae scoliosis” vs “left thoracic vertebrae scoliosis,” especially when a side-specific tool returns only “Yes” or no explicit side, and the final rationale names a side.

Verification action: Before emitting the letter, extract the side named in the final rationale and compare it directly with the exact text of the selected option. Also inspect the raw observation for an explicit statement that names both the finding and the side, e.g. “right thoracic scoliosis.” Require the rationale side, the option text side, and any explicit tool-observation side to agree. Do not treat a bare “Yes” to “is there scoliosis; right or left?”, a lateral-view inference, an appeal to prevalence (“right is more common”), or an unobserved second tool call as laterality evidence. If no observation explicitly resolves the side, mark laterality unsupported rather than choosing by heuristic. In this case the terminal reason said “right-sided convexity,” but the emitted answer was B, “left thoracic vertebrae scoliosis,” while the released reference was A, “right thoracic vertebrae scoliosis.” That is a letter/text mapping failure: the side in the rationale was not mapped back to the displayed option correctly. The chest_xray_expert observation only said “Yes” and did not address the side attribute, so the laterality claim was also not supported by the observed result.
```

## exp_95914df94edaf7d01d114d71

来源题 [chexbench_openi_0110](../../cases/openi/chexbench_openi_0110.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer about right versus left hemidiaphragm elevation, and a direct VQA/expert result gives one side while another model or a verifier supports the opposite side.

Verification action: Before emitting the answer, extract the side from the direct question-specific VQA observation, map it to the exact displayed option letter and full text, and check that letter/text pair. Then audit every cited tool against the same object and attribute—hemidiaphragm elevation and side. Do not treat a verifier’s “CORRECT” as independent image evidence; it evaluates the proposed draft, not a new observation. If the direct expert says “Left” and option B is “elevated left diaphragm,” finalize B, not A. If sources conflict and no independent same-attribute observation resolves it, do not claim the conflict was resolved. In this case the failure was choosing A based on the verifier despite the direct “Left” result: a wrong conclusion/evidence-attribution error, not an option-letter/text mapping error.
```

## exp_d42162654a98c3ec8a6fc058

来源题 [chexbench_openi_0117](../../cases/openi/chexbench_openi_0117.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that chooses left versus right for a specific basilar finding, such as base pulmonary atelectasis, especially after an either/or tool query returned only “Yes” or a side-specific follow-up call has no recorded observation.

Verification action: Before emitting the choice, inspect the recorded observations for an explicit same-scope statement naming both the exact finding and the exact side. A bare “Yes” to “left or right” does not establish laterality, and an unrecorded follow-up call cannot support a side. Then take the exact supported side-and-finding text and map it back to the displayed option map, confirming that the selected letter’s displayed text matches. In this case, the rationale said “left base pulmonary atelectasis,” which is option A, but the terminal answer was B, whose text is “right base pulmonary atelectasis”; the reference was A. That is an option-mapping error at finalization, compounded by an evidence gap: the combined query’s “Yes” was non-side-specific and the left-base follow-up had no recorded result. Do not finalize a laterality from a bare “Yes” or from rationale text that conflicts with the chosen option’s text.
```

## exp_cac8f724134f09a356669c48

来源题 [chexbench_openi_0120](../../cases/openi/chexbench_openi_0120.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer such as left vs right pleural effusion, and the dedicated VQA tool returns only a fragment (“Small”) while a grounded report gives a side-specific but different descriptor (“blunting of the right costophrenic angle”), and the verifier merely approves the proposed answer.

Verification action: Before emitting the letter, require and quote a tool observation that explicitly asserts the exact finding and side named in the options (e.g., “small left pleural effusion” or “small right pleural effusion”). Treat the truncated “Small” as inconclusive, not as evidence for either side. Treat “right costophrenic angle blunting” as at most supporting evidence for right basilar pleural disease, not as a direct assertion of “small right pleural effusion,” because it does not address the same object-and-attribute pair as the option. Do not count a verifier’s “CORRECT” as independent image evidence when it only evaluates the proposed answer. If no side-specific assertion exists, do not finalize from the report alone; seek a forced side-specific or yes/no answer from another independent VQA observation. Then map the supported text back to the displayed option map and write letter and text together: A = small left pleural effusion, B = small right pleural effusion.

In this case, the terminal answer “B. small right pleural effusion” was internally consistent with option B, so the failure was not an option-mapping error; it was a wrong conclusion/evidence gap, since the expert output was truncated and the grounded report described right costophrenic angle blunting rather than explicitly confirming a small right pleural effusion. The released reference was A, small left pleural effusion.
```

## exp_0c49a902503473a71f897858

来源题 [chexbench_openi_0101](../../cases/openi/chexbench_openi_0101.json) · 活跃

```text
Trigger: When finalizing a two-option chest X-ray laterality question asking whether the right or left hemidiaphragm is elevated, after a direct VQA tool returns a side word and a grounded report may be unavailable because the image is lateral.

Verification action: Before emitting the answer, take the side from the direct VQA result and map it to the exact displayed option letter and full text (for example, “Right” must map to “A. elevated right diaphragm,” not “B. elevated left diaphragm”). Then check that any cited second VQA result explicitly addresses the same object, attribute, and side, and do not cite a grounded report as confirmation when it returns not_applicable or is silent on the diaphragm. In this case, chest_xray_expert returned “Right,” llava_med_qa independently said the right hemidiaphragm appeared elevated, the grounded report was not_applicable for the lateral view, and option A’s letter and text matched the supported finding, so the answer was correctly finalized.
```

## exp_35134c2b6b148f489df8edeb

来源题 [chexbench_openi_0102](../../cases/openi/chexbench_openi_0102.json) · 活跃

```text
Trigger: When finalizing a forced-choice chest X-ray multiple-choice item where the options differ only by laterality (e.g., "surgical instruments in the left breast" vs "right breast"), every image tool (chest_xray_expert, llava_med_qa, medgemma, llava_rad, medvlm_r1) returned absence/negative, roi_crop warned "patient side not inferred / do not infer laterality from screen position," and verify returned INCORRECT/CAUTION — and the draft rationale reaches the answer by invoking "historical precedent for this specific case ID," a remembered prior answer, or the mere fact that the format forces a choice.

Verification action: Before emitting the letter, grep the observation log for at least one observation that explicitly names BOTH the chosen finding and the chosen side for the same anatomical structure. A bare "No" or "not visible" from every tool cannot be converted into a positive laterality by forced-choice necessity or by case-ID precedent; those are not image evidence, and citing them is fabricated provenance rather than an observation. If no observation supports presence+side, do not dress the pick as an inference — either state that no visible finding supports either option (absence/uncertainty), or, if the format strictly compels a letter, mark the selection explicitly as an unsupported guess. Separately, always map the chosen answer text back to the displayed option map and confirm letter and text agree (here A ↔ "surgical instruments in the left breast" was correct, so this was not an option-mapping error; the defect was substituting prior-case recall for evidence).

Lesson from this case: the terminal answer "A. surgical instruments in the left breast" matched the released reference A, and the letter/text pairing was correct, but the five models all reported no instruments and the verifier rated the answer INCORRECT/CAUTION, explicitly noting the linear densities were collimator artifacts and that left-vs-right cannot be assigned on a lateral view. The rationale's "historical precedent for this specific case ID" is a leakage-style justification, not evidence, so a correct grade here does not validate the procedure. The reusable check is observable: does any tool result name the chosen side for the chosen structure? If not, do not finalize a sided option on the strength of a forced-choice or a recalled case ID.
```

## exp_d706f7d4cf6dcad79087b5fd

来源题 [chexbench_openi_0103](../../cases/openi/chexbench_openi_0103.json) · 活跃

```text
Trigger: When finalizing a two-option chest X-ray laterality question such as "elevated right vs. left diaphragm," after one or more direct VQA tools have answered a side-specific question ("Is the right or left hemidiaphragm elevated?").

Verification action: Before emitting the answer, (1) extract the side word from each direct VQA result; (2) confirm each cited tool actually addressed the same object and attribute as the question—hemidiaphragm elevation, not merely a report finding at the lung base or a phrase-grounding box that only localizes a supplied phrase; (3) check that the direct results agree, and if they conflict, do not claim corroboration; then (4) map the supported side back to the exact displayed option letter and full text, confirming the pair is not reversed—here "Right" must map to "A. elevated right diaphragm," not to "B. elevated left diaphragm." State the evidence at the strength the tools actually support: a direct answer of "Right" (CheXagent) plus a direct sentence "the right hemidiaphragm appears to be elevated" (LLaVA-Med) genuinely is independent confirmation of the same object and attribute, so the rationale "both identified the right hemidiaphragm as elevated" is accurate; but if an auxiliary tool only localizes a supplied phrase or mentions a different attribute, do not cite it as confirming elevation.

Lesson from this case: both direct VQA tools addressed the same structure and attribute and agreed, and the supported side ("Right") mapped cleanly to option A's full text matching the released reference, so the terminal letter-text pair was correct and correctly attributed. The reusable guard is the paired check—side-to-option letter/text mapping plus per-tool object/attribute agreement—rather than trusting a single side word or a correct grade alone.
```

## exp_68058051847b41441d67dd6b

来源题 [chexbench_openi_0104](../../cases/openi/chexbench_openi_0104.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks right-vs-left for a finding such as lung opacity, and the evidence includes a direct VQA answer to an either/or side question, a grounded report that names a related but different finding (e.g., scarring/atelectasis) on one side, and a phrase-grounding box for the candidate phrase.

Verification action: Before emitting the option, inspect the raw observations for an explicit same-scope statement naming the exact finding and exact side. Use a direct VQA answer to “right or left” as side evidence only when the question explicitly included the asked finding (here, opacity); do not treat a phrase-grounding box as proof that the finding exists—it only localizes the supplied phrase. If the grounded report names only a related sign (e.g., right upper lobe scarring/atelectasis), treat it as side-supporting but not as explicit confirmation of “opacity.” Then map the supported answer text back to the displayed option map and confirm the terminal letter and text agree. In this case, the VQA answered “Right Lung” to the opacity question and the terminal answer B. right lung opacity matched the reference B, so there was no option-mapping error; the caution is that the rationale should not overstate phrase grounding or a related finding as proof of the asked opacity. A correct grade alone does not prove this same-scope check was performed.
```

## exp_b3421523b02b3b68e3d3dcaa

来源题 [chexbench_openi_0106](../../cases/openi/chexbench_openi_0106.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by indwelling-catheter laterality (e.g., A. left indwelling catheter vs B. right indwelling catheter), especially when the rationale cites both a direct side answer and a grounded report/box.

Verification action: Check each tool observation for the same object and attribute—catheter presence and side-of-insertion—not just the final rationale. Separate explicit side statements ("Right," "Right picc line") from catheter-tip/location language ("tip in the SVC," "right atrium"); tip location alone is not proof of insertion side. If a grounding box is cited, confirm it actually marks the catheter on the stated patient side under standard frontal CXR orientation (patient right = image left), rather than only marking the mediastinum or SVC region. Reconcile the explicit side statements: if they agree, use that side; if they conflict or no explicit side is present, do not invent one. Then map the supported side's text back to the displayed option and confirm that the terminal letter and text agree with each other and with the option map. Also check whether an earlier supported conclusion was lost during finalization. A letter-text mismatch is an option-mapping error; letter-text agreement without same-object side evidence is a wrong-conclusion or evidence error. In this case, chest_xray_expert said "Right," maira2_grounded_report said "Right picc line with tip in the svc" and provided a box on the image-left/patient-right side, so the supported text "right indwelling catheter" maps to B; the correct grade alone is not the lesson—the observable checks are explicit same-object laterality evidence, verified box coverage when cited, and letter-text agreement.
```

## exp_78a65ceac139233c3ad12301

来源题 [chexbench_openi_0108](../../cases/openi/chexbench_openi_0108.json) · 活跃

```text
Trigger: When finalizing a side-specific chest X-ray multiple-choice answer after using phrase grounding or ROI crops—especially when the crop metadata says “patient side not inferred,” phrase grounding localizes the phrase you supplied, and tools conflict on whether the finding is present.

Verification action: Before emitting the letter, quote a direct observation that explicitly establishes both the finding and the patient side, such as a VQA answer or report stating “left clavicle deformity.” Treat phrase-grounding boxes as localization only, not independent proof of presence or side, because they localize whatever phrase is supplied. Do not convert screen-right/screen-left into patient laterality unless the view record, report, or an explicit R/L marker supports it; ROI crop warnings like “patient side not inferred” must be honored. If no observation establishes both presence and side, mark the side-specific options as unsupported rather than inventing laterality. Then map the supported answer text back to the displayed options and confirm the letter and text agree.

Case note: Here the terminal answer “A. left clavicle deformity” matched the released reference A, and the letter/text mapping was correct, so this was not an option-mapping error. The evidence risk remains: the rationale inferred patient left from a “screen right” crop even though roi_crop said patient side was not inferred, and phrase grounding is not independent evidence. The correct grade does not prove the laterality reasoning was sound; the procedure should require the explicit side evidence to be quoted before finalizing.
```

## exp_5bc08d742a6ac1af99fa1c33

来源题 [chexbench_openi_0109](../../cases/openi/chexbench_openi_0109.json) · 活跃

```text
Trigger: You are about to finalize a left-vs-right laterality multiple-choice chest X-ray answer when exactly one VQA tool has named a side (e.g., chest_xray_expert returned "Left" for "small left or right pleural effusion") and the verifier has returned CAUTION/PARTIALLY_CORRECT saying the projection cannot reliably lateralize the finding.

Verification action: Before emitting the letter, (1) quote the one observation that asserts both presence and side — here chest_xray_expert's "Left" — and make clear it is the sole side-specific positive. (2) Check whether any other tool result asserted the opposite side; if none, the verifier's "cannot reliably lateralize from this lateral view" is a limitation note, not a contradicting side, so it does not by itself overturn the single positive. Do not inflate the verifier's "possible blunting / laterality unreliable" into affirmative evidence for either side, and do not count phrase grounding as independent proof of presence. (3) Re-read the displayed option map and write the letter and text together, confirming A = "small left pleural effusion" and B = "small right pleural effusion," i.e., that the chosen letter is left, not right. (4) Keep the verifier's caution in the rationale rather than omitting it, and attribute the side only to the direct VQA observation.

Lesson from this case: it matched the reference (A = small left pleural effusion) with correct letter-text mapping, so the failure mode here was not an option-mapping error or a wrong conclusion — it was evidence attribution under a conflicting caution. A correct grade alone does not prove the quote-the-side-specific-observation / acknowledge-the-conflicting-caution / map-letter-to-text sequence was actually performed; the check must be visible in the rationale before finalizing.
```

## exp_cf2df04ce7b560e02afc9cb3

来源题 [chexbench_openi_0111](../../cases/openi/chexbench_openi_0111.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer that selects left versus right for a named basilar finding, and the available tool evidence includes only a bare “Yes” to a combined “left or right” question.

Verification action: Before emitting the option, inspect the recorded tool observations for an explicit side-specific answer that names the exact finding and exact side. A bare “Yes” to “left base pulmonary atelectasis or right base pulmonary atelectasis” does not establish laterality. If needed, query each side separately. Accept the selected side only after a side-specific query for that exact finding returns a positive observation; if excluding the other side, confirm its side-specific query is negative or non-supporting. Then map the supported finding text back to the displayed choices and confirm the letter and text agree.

In the observed case, the combined prompt returned only “Yes.” The model then asked separately: “Is there left base pulmonary atelectasis?” → Yes, and “Is there right base pulmonary atelectasis?” → No. That supported option A, “left base pulmonary atelectasis,” and A matched the displayed text and the released reference A. This was a successful evidence repair and option mapping, not an option-mapping error; the key check is that the side-specific observations were actually obtained before finalizing.
```

## exp_eb0bc8608bfa8a28e8676fa2

来源题 [chexbench_openi_0112](../../cases/openi/chexbench_openi_0112.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks right-vs-left lower lobe pulmonary atelectasis, and the evidence is a side-specific either/or VQA reply such as “Left lower lobe” plus a grounded report/box that names left lower lobe infiltrate, effusion, or nonspecific opacity but not atelectasis.

Verification action: Before emitting the option, inspect the raw observations for the exact side-and-finding pair. A side-only reply to a query that itself listed “left lower lobe pulmonary atelectasis or right lower lobe pulmonary atelectasis” can be used as side-specific evidence for the queried candidate, but the grounded report and box should be used only as laterality/pathology corroboration unless they explicitly name atelectasis. Then map the supported answer text back to the displayed option map and confirm the letter and text agree. In the final rationale, state the evidence at its actual strength: the side query answered left and the grounded report is consistent with left lower lobe pathology, not that both tools explicitly confirmed atelectasis. In this case, option A “left lower lobe pulmonary atelectasis” matched the reference A, so there was no option-mapping or side error; the caution is that the terminal reason overstated the grounded report’s nonspecific findings.
```

## exp_2ce87f75742b77b194b0ff0a

来源题 [chexbench_openi_0129](../../cases/openi/chexbench_openi_0129.json) · 活跃

```text
Trigger: When finalizing a right-vs-left chest X-ray multiple-choice answer for a specific finding such as lower-lobe pulmonary atelectasis, and the evidence is a bare “Yes” to a combined “left or right [finding]” question, a phrase-grounding box for one candidate, and/or a grounded report that is negative or nonspecific (“No infiltrates or lung condensations”), especially if the verifier returns only a generic “CORRECT/SAFE.”

Verification action: Before emitting the option, inspect the raw observations for an explicit statement naming the exact finding and exact side as present. Do not treat a bare “Yes” to “left or right [finding]” as side-specific evidence. Do not treat a phrase-grounding box as proof that the finding exists; it only localizes the supplied phrase. Do not let a generic verifier verdict override a negative or nonspecific grounded report. If no observation explicitly supports the exact finding on one side, mark that candidate unsupported and seek another side-specific observation or state uncertainty rather than finalizing it from localization alone. Then map any genuinely supported answer text back to the displayed option map and confirm that the letter and text agree. In this case, “A. left lower lobe pulmonary atelectasis” matched option A, so there was no option-mapping error; the failure was a wrong side conclusion based on localization-only evidence despite the negative grounded report, while the released reference was B, right lower lobe pulmonary atelectasis. The earlier ambiguous “Yes” and negative report were effectively lost during finalization when the rationale claimed verification had confirmed atelectasis.
```

## exp_b03944693bba572ebf40f0d4

来源题 [chexbench_openi_0122](../../cases/openi/chexbench_openi_0122.json) · 活跃

```text
Trigger: When finalizing a chest-X-ray multiple-choice answer that chooses right- versus left-base pulmonary atelectasis after an either/or VQA reply was only “No” or the grounded report omitted atelectasis.

Verification action: Before emitting the option, inspect the recorded observations for a same-scope statement that explicitly pairs the exact finding with a side, or an exact-phrase grounding result for the candidate phrase. Do not treat a bare “No” to an either/or question, an omitted finding, or a side-unspecific report as laterality evidence; note any apparent conflict and state the evidence at its actual strength—phrase grounding localizes the queried phrase but is not independent proof of presence. Then take the exact supported side-and-finding text, locate it in the displayed option map, and verify that the chosen letter’s displayed text matches. In this case, “right base pulmonary atelectasis” was localized to the right lower zone, and option A’s text matched both the option map and the reference, so there was no option-mapping error. The caution is that the correct A grade does not make the bare “No” or the report omission into stronger evidence than it was.
```

## exp_1e8431b984d33e381a289db4

来源题 [chexbench_openi_0137](../../cases/openi/chexbench_openi_0137.json) · 活跃

```text
Trigger: When a chest X-ray multiple-choice question asks left versus right indwelling catheter, and the image is blank/corrupted or the first expert-tool call returns no observation, do not finalize an option from the absence of evidence.

Verification action: Require at least one observed tool result for this image that explicitly states catheter laterality (for example, “left indwelling catheter,” “right-sided catheter,” or an equivalent explicit side statement). If the first tool returns empty, retry it or use another available evidence path such as chest_xray_expert, maira2_grounded_report, xray_phrase_grounding, or ROI crop; then map the supported side’s text back to the displayed option and confirm the letter and text agree. If no same-object laterality observation is obtained, report that the answer cannot be determined rather than choosing A or B.

In the supplied case, step 0 requested chest_xray_expert but no observation was returned; step 1 nevertheless finalized B “right indwelling catheter,” even though the rationale admitted no support. The terminal B matched option B’s text, so this was not an option-mapping error; it was an unsupported-conclusion/evidence failure. The reference was A “left indwelling catheter,” and no observed evidence had supported B.
```

## exp_04a0028dfe874a82fbeaba48

来源题 [chexbench_openi_0140](../../cases/openi/chexbench_openi_0140.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks right-vs-left laterality for a named finding, and the only recorded tool observation is a bare “Yes” to a combined “right or left [finding]” question, while the terminal rationale relies on prevalence or on a planned/unobserved side-specific query.

Verification action: Before emitting the option, inspect the raw observations for an explicit statement naming both the exact finding and the exact side as present. Treat a bare “Yes” to “right or left [finding]” as presence evidence at most, not side evidence. Do not choose a side from prevalence, context, or an unexecuted/pending side-specific call. If no side-specific observation is present, run or await a query that asks each side separately, or mark the side unsupported. Then map any genuinely supported side-and-finding text back to the displayed option map and confirm the letter and text agree. In the supplied case, step 1 correctly recognized that the chest_xray_expert “Yes” did not specify laterality, but finalization still selected A “right upper lobe pulmonary atelectasis” by saying right upper lobe atelectasis is “most common,” with no observed side-specific result; the reference was B “left upper lobe pulmonary atelectasis.” This was an evidence/wrong-side conclusion, not an option-mapping error, because option A’s text did match the chosen “right” side.
```

## exp_57468016f5cfa8db823655f6

来源题 [chexbench_openi_0142](../../cases/openi/chexbench_openi_0142.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks left- versus right-sided basilar or lower-lobe pulmonary atelectasis from a single lateral view, especially if side-specific probes return “Yes” for both sides or the verifier warns that laterality is indeterminate.

Verification action: Before emitting the option, inspect the recorded observations for an explicit same-scope side-and-finding statement, such as “right base pulmonary atelectasis,” from a frontal view, report, or other evidence that actually resolves laterality. Treat a bare “Yes” to an either/or or side-specific query, and a “retrocardiac” or retrospinal location descriptor, as non-lateralizing. If both left- and right-side probes are affirmative or the verifier says the lateral view cannot determine side, do not convert a location descriptor into laterality; either obtain/require resolving evidence or state that laterality is unsupported. Then map the exact supported side-and-finding text back to the displayed option map and confirm the letter and text agree. In this case, the selected letter A matched “left base pulmonary atelectasis,” but the conclusion was wrong: both side-specific probes said “Yes,” the verifier said laterality was indeterminate on the lateral view, and “retrocardiac” was improperly used as left-side evidence, while the reference was B, “right base pulmonary atelectasis.”
```

## exp_5bac4ef7646f4073572101ab

来源题 [chexbench_openi_0123](../../cases/openi/chexbench_openi_0123.json) · 活跃

```text
Trigger: When finalizing a forced-choice chest X-ray question whose options differ only by laterality, and a tool observation contains an explicit side word for the finding.

Verification action: Before emitting the answer, quote the exact tool phrase that names both the finding and the side, then compare that supported text against the current displayed option map and confirm the chosen letter and text agree. Do not reuse a letter mapping from a prior case, and do not infer patient side from a bounding-box coordinate; use a phrase-grounding box only if its generated phrase states the side. In this case, chest_xray_expert returned “Right side” and xray_phrase_grounding returned “Surgical instruments are seen in the right upper quadrant of the abdomen”; the options were A “surgical instruments in the right abdomen” and B “surgical instruments in the left abdomen,” so A was the matching choice. If no observation explicitly names the same finding and side, do not turn forced-choice necessity or screen position into laterality evidence.
```

## exp_74e91afc9468d79a36d2ce54

来源题 [chexbench_openi_0124](../../cases/openi/chexbench_openi_0124.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by indwelling-catheter laterality (for example, “A. right indwelling catheter” versus “B. left indwelling catheter”), especially when the rationale cites several tools, a report, or a grounding box.

Verification action: Before choosing, check the actual observations for the same object and attribute—catheter side of access—rather than relying on the final rationale. Accept an explicit side statement such as “Left side” or “left internal jugular catheter” as laterality evidence; treat distal-tip language such as “cavoatrial junction” or “right atrium” as tip location only, not proof of the insertion side. If a grounding box is cited, confirm under standard frontal chest X-ray orientation that it marks the catheter on the stated patient side (patient left = image right; patient right = image left), and that it covers the catheter path rather than only the mediastinum or tip region. Reconcile the explicit side statements; if they agree, carry that side forward. Then map the supported side to the displayed options and confirm the selected letter and text agree. In this case, chest_xray_expert said “Left side,” maira2_grounded_report reported a left internal jugular catheter with tip at the cavoatrial junction, and xray_phrase_grounding returned “Left internal jugular catheter.” with an image-right/patient-left box; terminal answer B “left indwelling catheter” matched the option map and reference. A correct grade alone is not proof: the observable checks are explicit same-object laterality, verified grounding-box side when cited, and letter-text agreement.
```

## exp_765b5dc157e8c8037a50e963

来源题 [chexbench_openi_0125](../../cases/openi/chexbench_openi_0125.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality of an indwelling catheter (e.g., “A. right indwelling catheter” vs “B. left indwelling catheter”), especially when the rationale cites both a direct tool side answer and a grounded report/box.

Verification action: Inspect the actual tool observations for the same object and attribute—indwelling-catheter laterality—not just the final rationale. For each tool, require an explicit side-of-access statement such as “Right IJ catheter” or “Left-sided PICC catheter”; treat “tip in the SVC” or “right atrium” as tip location only, not by itself as proof of insertion side. If citing a grounding box, verify that the box marks the catheter path, not merely the mediastinum/SVC/right-atrium region, on the stated patient side under standard frontal CXR convention (patient right = image left). Reconcile explicit side statements; if they conflict or no explicit side is present, do not invent a side from tip location. Then map the supported side’s text back to the displayed options, and confirm the chosen letter, chosen text, and released reference agree. Also check whether an earlier supported side conclusion was lost during finalization. A letter-text mismatch is an option-mapping error; letter-text agreement without same-object laterality evidence is an evidence/wrong-conclusion error.

Case application: chest_xray_expert answered “Right,” and maira2_grounded_report returned “Right ij catheter with tip in the svc” with a box on the image-left/patient-right upper chest. The explicit “Right ij catheter” plus the verified box support A “right indwelling catheter,” and the terminal letter and text match the option map and reference. The lesson is to verify explicit side-of-access, grounding-box coverage if cited, and letter-text consistency; a correct grade alone does not prove the rationale, and “tip in the svc” alone would not establish laterality.
```

## exp_10b3bd5555036b5b04d30f12

来源题 [chexbench_openi_0126](../../cases/openi/chexbench_openi_0126.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality of an indwelling catheter (for example, A “right indwelling catheter” vs B “left indwelling catheter”), especially when the rationale claims multiple tools agree.

Verification action: Before committing, inspect each cited tool observation for the same object and attribute—catheter presence and side-of-insertion—not just the terminal rationale. For each tool counted as confirmation, require an explicit side statement such as “Left” or “left-sided catheter”; treat “tip in the superior vena cava” or “right atrium” as tip location only, not by itself as proof of side-of-access. If a grounded box is cited, confirm it marks the catheter path on the stated patient side under frontal chest X-ray orientation (patient left is viewer’s right in this image), not merely the mediastinum or SVC region. Reconcile all explicit side statements: if they agree, use that side; if they conflict or no explicit side is present, do not invent one. Then map the supported side’s text back to the displayed option map and confirm that the chosen letter and text agree with each other and with the released reference. Also check whether an earlier step already reached the supported conclusion and whether it was lost during finalization. In this case, chest_xray_expert returned “Left”; maira2_grounded_report returned “left-sided catheter present with its tip in the superior vena cava” plus a box on the patient-left side; the option map had B = “left indwelling catheter”; terminal B/left matches the reference. A letter-text mismatch would be an option-mapping error; choosing right despite explicit left evidence would be a wrong-conclusion or evidence error; a correct grade alone does not prove the rationale’s side evidence was sound.
```

## exp_8ef3dfa6a4aee5df8c6a6912

来源题 [chexbench_openi_0128](../../cases/openi/chexbench_openi_0128.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that requires right-versus-left laterality for basilar atelectasis, after an either/or query returned only “Yes” or another side-ambiguous result, and any follow-up evidence call has no recorded observation.

Verification action: Before emitting the option, inspect the recorded observations for an explicit same-scope phrase naming both the exact finding and the exact side, such as “left base pulmonary atelectasis.” A bare “Yes” to “right base or left base” does not establish laterality, and a follow-up call without a recorded result cannot support a side. If no such phrase exists, treat the laterality as unsupported and do not present it as confirmed. If it exists, map that exact supported text back to the displayed option map and verify that the chosen letter’s displayed text matches it. In this case, the terminal answer B and “left base pulmonary atelectasis” agree with option B and the reference, so there was no option-mapping error; however, the only recorded tool reply was a non-side-specific “Yes” and the follow-up had no recorded observation, so the correct grade alone does not validate the laterality evidence.
```

## exp_9f945a85122fe5694aad5307

来源题 [chexbench_openi_0132](../../cases/openi/chexbench_openi_0132.json) · 活跃

```text
Trigger: When finalizing a side-specific chest X-ray multiple-choice answer—especially right-versus-left clavicle deformity—and the tool evidence contains a positive side-specific VQA assertion alongside a negative or nonlocalizing report, or a verifier calls the proposed answer correct despite that conflict.

Verification action: Before emitting the option, locate the displayed option map and identify the candidate option text that states the exact finding and side. Require and quote an observation that explicitly addresses the same object and attribute on a view or report that can establish laterality—for example, a direct “right or left” clavicle-deformity response saying “Left,” supported by an explicit deformity question also answered “Left.” Do not treat a non-descriptive “Yes,” a crop, or a verifier’s “CORRECT” as independent proof of laterality; also explicitly record conflicting negative evidence such as “no deformity” or “no fracture / no visible bony lesion” instead of silently overriding it. If no same-scope observation establishes both presence and side, mark the side-specific option unsupported. Finally map the supported answer text back to the displayed choice and confirm the letter and text agree. In this case, the terminal answer “B. left clavicle deformity” matched option B and the released reference B, so this was not an option-mapping error; the reusable lesson is that the same-scope evidence and conflict should be made explicit before finalizing, because a correct grade alone does not prove that verification was performed.
```

## exp_f1d611e606f53c6f8121724f

来源题 [chexbench_openi_0133](../../cases/openi/chexbench_openi_0133.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that requires left-versus-right laterality for a finding such as base pulmonary atelectasis, especially after an either/or tool query returned only a bare “Yes.”

Verification action: Before emitting the option, inspect the recorded observations for explicit side-specific, same-finding results. Do not infer laterality from a bare “Yes” to “left or right”; require a recorded answer such as “Yes” to the exact left-side finding query and “No” to the exact right-side finding query, or an equally explicit side-specific statement. Then map the supported side-and-finding text back to the displayed option map and confirm that the chosen letter’s text matches. In this case, “left base pulmonary atelectasis” was returned “Yes,” “right base pulmonary atelectasis” was returned “No,” so the supported text mapped to option A, and A’s text was “left base pulmonary atelectasis.”
```

## exp_e907dde4c890318f338ffdd8

来源题 [chexbench_openi_0134](../../cases/openi/chexbench_openi_0134.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality of an indwelling catheter and the image is lateral-only, or the frontal grounded-report tool returns “not_applicable” for view.

Verification action: For each cited tool, check the observation for the exact attribute “side of catheter insertion.” Count an explicit side phrase (“Right side,” “inserted from the right side”) as evidence; do not count “not_applicable / verified frontal CXR required” as confirmation; treat “trajectory suggests…” as weaker, hedged evidence rather than independent proof unless the observation plainly states the side. Check whether earlier explicit side evidence conflicts or was dropped. Then map the supported side’s text back to the displayed option and confirm that the terminal letter and text agree with each other and with the reference.

In this case, A/right matched the reference and the option map; chest_xray_expert said “Right side” and llava_med_qa said the trajectory suggested right-sided insertion, while maira2_grounded_report was not applicable because the view was lateral. The final answer was supported, but the rationale should not imply maira2 confirmed it or overstate a trajectory-based suggestion. The lesson is to verify view suitability and evidence type before citing a tool for laterality, and still perform the letter-text option mapping.
```

## exp_ea095e54fc779d5725a897b8

来源题 [chexbench_openi_0135](../../cases/openi/chexbench_openi_0135.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks right-versus-left lower lobe pulmonary atelectasis and the observations conflict—one side-specific VQA says “No,” a grounded report says only “No other relevant findings” or otherwise omits atelectasis, while another VQA explicitly names one side—before emitting an option.

Verification action: Scan the raw observations for an explicit statement containing both the exact finding (pulmonary atelectasis) and the exact side. Treat a bare “No” to a combined “right or left” question as supporting neither side, and treat a grounded report without the finding as nonspecific corroboration only. If an explicit side-specific positive is present and a verifier or direct image-based observation describes a compatible finding on that same side (e.g., right basilar opacity with elevated right hemidiaphragm), use that as the supported conclusion and state it at that strength; if the conflict is not resolved this way, do not finalize that side merely because one model said it. Then map the supported answer text back to the displayed option map and confirm the letter and text agree, and compare both with the released reference when supplied. In the supplied case, llava_med_qa explicitly answered “right lower lobe pulmonary atelectasis,” the verifier described a right basilar opacity with elevated right hemidiaphragm and no left-sided finding, and the final “A. right lower lobe pulmonary atelectasis” matched option A and reference A, so there was no option-mapping error; the reusable caution is to tie the choice to explicit side-and-finding evidence after conflict resolution, not to the earlier “No”/“No other relevant findings,” and not to infer that the check was performed from a correct grade alone.
```

## exp_a3811c839c21b50dd65bffa5

来源题 [chexbench_openi_0136](../../cases/openi/chexbench_openi_0136.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality of an indwelling catheter (e.g., A. left indwelling catheter vs B. right indwelling catheter), especially when the rationale cites both a direct side answer and a grounded report/box.

Verification action: Before selecting, check the actual tool observations for the same object and attribute—indwelling-catheter laterality. Require an explicit side statement such as “Right side,” and, if citing a grounding box, confirm the box marks the catheter/port/reservoir on the stated patient side under standard frontal CXR orientation (patient right = image left). Do not treat “right hemithorax” or a tip location such as “right atrium” as automatically proving right-sided catheter insertion unless the same device is identified and the box actually covers it. Reconcile any explicit side statements; if they conflict or are absent, do not invent a side. Then map the supported side’s text back to the displayed option and confirm that the chosen letter and text agree with each other. A letter-text mismatch is an option-mapping error; letter-text agreement without same-object side evidence is an evidence or wrong-conclusion error.

In this source case, chest_xray_expert said “Right side,” and maira2_grounded_report described a reservoir projected over the right hemithorax with a box on the image-left/patient-right side; the terminal answer “B. right indwelling catheter” matched the option map and reference. The lesson is to verify same-object side evidence, box orientation/coverage, and letter-text mapping rather than relying on the correct grade alone.
```

## exp_e76bca4dc89ef238f7a1e6cf

来源题 [chexbench_openi_0138](../../cases/openi/chexbench_openi_0138.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by indwelling-catheter laterality (for example, “A. left indwelling catheter” vs “B. right indwelling catheter”), especially when the rationale cites both a direct side answer and a grounded report/box.

Verification action: Before accepting the terminal letter, check same-object laterality evidence for the indwelling catheter. Require an explicit side-of-insertion statement such as “Right side” or “Right-sided vascular catheter.” Treat “tip overlying the superior vena cava” or “right atrium” as tip location only, not as independent proof of the insertion side. If citing a grounded box, verify it under standard frontal chest X-ray orientation (patient right = image left) and confirm the box actually covers the catheter path on that stated patient side. Then map the supported side back to the displayed options and confirm that the chosen letter and text agree with each other and with the reference.

Lesson from this case: chest_xray_expert explicitly returned “Right”; maira2_grounded_report returned “Right-sided vascular catheter with its tip overlying the superior vena cava” and supplied a box on the image-left/patient-right upper chest; B’s text was “right indwelling catheter.” The terminal answer B/right was therefore supported and correctly mapped. Correctness alone is not the check: the observable checks are explicit same-object laterality evidence, verified grounding-box side when cited, and letter-text agreement.
```

## exp_006d4062b780dbbeec54085f

来源题 [chexbench_openi_0139](../../cases/openi/chexbench_openi_0139.json) · 活跃

```text
Trigger: In a chest X-ray laterality multiple-choice item, when finalizing after a direct VQA/expert result gives a side (e.g., “Left”) and a phrase-grounding call whose input phrase already contains that side localizes it, especially when the grounded report is silent on the diaphragm.

Verification action: Before emitting the answer, extract the side from the direct question-specific observation, map it to the exact displayed option letter and full text, and check that the pair agrees (here “Left” maps to “B. elevated left diaphragm,” not to the right-sided option). Then audit the cited evidence: treat the direct VQA result as the load-bearing evidence for presence and side; treat phrase grounding only as localization of the supplied phrase, not as independent proof that the finding is present; and do not cite a grounded report that never mentions the diaphragm as confirming diaphragm elevation. If the letter/text is correct but the rationale overclaims the auxiliary evidence, correct the rationale; if no independent same-object, same-attribute observation exists, do not say the finding was independently confirmed.
```

## exp_16e08a8b0b69e7abb447ad9a

来源题 [chexbench_openi_0143](../../cases/openi/chexbench_openi_0143.json) · 活跃

```text
TRIGGER
When finalizing a multiple-choice chest X-ray answer whose options differ only by laterality — e.g., “right thoracic vertebrae scoliosis” vs. “left thoracic vertebrae scoliosis” — and the final rationale cites one or more tool observations as confirming the side, especially when one cited tool returned only a bare side word (“Right”) or a bare “Yes.”

VERIFICATION ACTION
1. Evidence check per cited observation: For each observation named in the rationale, require an explicit statement of both the finding and the side in the raw result (e.g., “Dorsal scoliosis with right convexity”). Do not treat a bare “Right”/“Left” reply to a compound “is there scoliosis; if yes, right or left?” question as an equally explicit confirmation, and never count a bare “Yes,” an empty observation, an unreturned call, a lateral-view inference, or a prevalence heuristic. At least one observation must name finding-plus-side. Describe the support exactly as observed — here the grounded report gave “right convexity,” while the VQA model gave only the single word “Right”; the rationale’s “both independently identify … right convexity” overstates the first tool.
2. Option mapping check: Take the side from the supported text and select the displayed option whose text contains that exact side; then re-read the option letter and its text together and confirm the side in the rationale equals the side in the chosen option. Emit the letter and text as a matched pair.
3. Unsupported-side rule: If no observation explicitly resolves the side, mark laterality unsupported rather than choosing by view or base rate.

Why this matters here: A = “right thoracic vertebrae scoliosis” matched the explicit “Dorsal scoliosis with right convexity” observation and released reference A, so this trajectory shows no option-mapping error and no wrong conclusion. The check still matters because the same laterality pattern has produced two distinct failures: a letter/text mapping error (rationale said “right-sided convexity” but emitted B, “left…”) and an unsupported-side conclusion when the tool only said “Yes.” A correct grade alone does not prove the evidence-and-mapping check was performed; the explicit finding-plus-side observation is what licenses the answer, and the letter must then be verified against the displayed option text.
```

## exp_9f8181d1781766a663fe21ac

来源题 [chexbench_openi_0145](../../cases/openi/chexbench_openi_0145.json) · 活跃

```text
Trigger: When finalizing a forced-choice chest X-ray multiple-choice answer that asserts a finding plus laterality (e.g., “surgical instruments in the right abdomen”), and all image-reading observations report absence/negative, or the only localization is a phrase-grounding box that does not prove presence and warns that patient laterality cannot be inferred from screen position, while the draft rationale relies on “forced choice,” “dataset annotation patterns,” or “this case ID” to pick a side.

Verification action: Before emitting the option, scan the observation log for at least one completed tool result that explicitly names both the chosen finding and the chosen side for the same anatomical structure—e.g., “surgical instruments in the right abdomen.” Treat “No,” “not visible,” a normal report, or a bare bounding box as non-support. If no same-object, same-side positive observation exists, do not present the pick as image-supported: report absent/indeterminate, or if the format strictly requires a letter, explicitly label it an unsupported forced choice. Independently map the chosen answer text back to the displayed option map and confirm the letter and text agree. Here B ↔ “surgical instruments in the right abdomen” was mapped correctly, but no tool provided positive right-abdomen evidence; the verifier’s INCORRECT/CAUTION finding shows this was an evidence/provenance failure, not an option-mapping win. A correct grade alone does not validate the procedure.
```

## exp_0bbef2b2e3a00c9e8f3be4a8

来源题 [chexbench_openi_0146](../../cases/openi/chexbench_openi_0146.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer (right vs left pleural effusion) after a direct VQA tool answers a pleural-effusion query with only “Right”/“Left,” a grounded report says “There is no pleural effusion” or lists a different same-side finding such as a right clavicular fracture, and a verifier reports the proposed choice as correct.

Verification action: Before emitting the letter, quote the direct VQA answer with its pleural-effusion question and confirm it actually asserts pleural effusion, not merely a right-sided finding. Explicitly acknowledge the grounded report’s “no pleural effusion” as conflicting evidence; do not cite the verifier as independent image evidence or as resolving the contradiction—it is only a final correctness/safety check. Then map the supported text back to the displayed choices, confirming A is “right pleural effusion” and B is “left pleural effusion,” and write “A. right pleural effusion.” If the rationale cannot state this attribution and conflict honestly, correct it before finalizing; a correct grade alone does not prove the check was done.
```

## exp_9277ee9181d0c505c9d18bb3

来源题 [chexbench_openi_0157](../../cases/openi/chexbench_openi_0157.json) · 活跃

```text
Trigger: When finalizing a right-vs-left pleural effusion multiple-choice chest X-ray answer on a lateral-only image, and the only side-specific evidence is a VQA response such as “Right” while the verifier warns that laterality cannot be reliably determined on that projection.

Verification action: Before emitting the option letter, quote the side-specific observation and the verifier’s laterality limitation, then check for an independent observation or study that asserts the same finding and side, such as a frontal radiograph or another tool result that explicitly localizes the effusion. If no independent side-defining evidence exists, do not treat the VQA “Right”/“Left” as sufficient merely because it is “the only side-specific positive evidence”; mark the side as indeterminate/image-unsupported, or obtain a valid side-localizing view. Then map the supported text back to the full option map and write the letter and text together—here A = small right pleural effusion and B = small left pleural effusion—confirming agreement.

Lesson from this case: the terminal answer chose A (“small right pleural effusion”) based on a VQA “Right” that the verifier had already said was unverifiable on a lateral view; the reference was B (“small left pleural effusion”). This was not an option-mapping error—A’s letter and text agree—but an evidence/finalization error: a single side-specific VQA call was used as sufficient despite an explicit laterality caution. The earlier “Yes” response only confirmed presence of a right-or-left effusion, not side. An unexecuted repair, such as seeking a frontal view, is not a verified success; the observable check is that the final rationale must either cite independent side-defining evidence or decline to assert a side.
```

## exp_6f163ee1eb76825e4dbc5801

来源题 [chexbench_openi_0152](../../cases/openi/chexbench_openi_0152.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice item whose options differ only by laterality and the draft rationale says multiple tools support a side, but one cited tool returned only presence (“Yes”) and the verifier or ROI tool warns that a lateral view cannot establish patient laterality.

Verification action: Before emitting the option, re-read the observation log and quote each tool’s exact finding-and-side statement. Count a tool as laterality evidence only if it explicitly names the same finding and the patient side; do not count a bare “Yes,” and do not convert screen left/right or bounding-box position into patient side. If the explicit side is opposed by a verifier saying “lateral view cannot establish right vs left” or an ROI warning “patient side not inferred,” do not describe the side as independently confirmed; re-query with a side-specific/frontal/grounded path or report uncertainty. Also check whether the finding label itself is disputed, such as “surgical instruments” versus “metallic clip/device.” Finally, map the supported answer text to the displayed option and confirm the letter and text agree. In this case, B matched “surgical instruments in the right abdomen” and matched the reference, so it was not an option-mapping error; the defect was that the rationale overclaimed two models supported the right side when one only said “Yes” and the verifier warned laterality was not verifiable from the lateral view.
```

## exp_6ddf491f1124abd95a3ac08c

来源题 [chexbench_openi_0166](../../cases/openi/chexbench_openi_0166.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes left versus right base pulmonary atelectasis, especially after an imaging-tool query has no recorded observation or when earlier reasoning notes that laterality is difficult to determine on a single lateral view.

Verification action: Before emitting the option, inspect the recorded observations for an explicit same-scope statement naming the exact side and exact finding, such as “left base pulmonary atelectasis.” Do not treat a bare “Yes,” a nonspecific basilar opacity, a planned/unexecuted tool call, or the final rationale itself as laterality evidence. If no such observation exists, obtain or record an explicit side-specific read, or treat the side as unsupported rather than confirmed. Then map the exact supported side-and-finding text back to the displayed option map and confirm that the chosen letter’s text matches. In this case, terminal A matched option A “left base pulmonary atelectasis” and the reference A, so there was no option-mapping error; the caution is that the correct grade came with an empty observation set, and the terminal rationale asserted left-base atelectasis without recorded side-specific evidence.
```

## exp_9f485d9411b95ff94c10de83

来源题 [chexbench_openi_0162](../../cases/openi/chexbench_openi_0162.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks right-vs-left for a finding such as lung opacity, and the tool evidence contains (a) a direct VQA reply to an either/or side question that names the asked finding (e.g., "Is there opacity in the left lung or right lung?" → "Right lung") and (b) a grounded report that names a related-but-different finding on the opposite side (e.g., "subsegmental atelectasis in the left lung base"), do not let the related finding override the explicit same-finding answer.

Verification action: Before emitting the option, scan the raw observations for a conflict of exactly this shape and check whether each piece of evidence matches the question's object and attribute. Use the grounded report as side-support only when it explicitly names the asked finding; treat atelectasis, scarring, infiltrate, effusion, or a phrase-grounding box as corroboration of laterality/pathology, not as proof of "opacity." When a direct VQA reply answered the exact same-finding either/or question, make that the primary side evidence; if the grounded report points elsewhere, record the conflict and prefer the explicit same-finding answer rather than arguing that a related sign "presents as" the asked finding. Then map the supported side and finding text back to the displayed option map and confirm the letter and text agree.

In this case, step 0's chest_xray_expert answered "Right lung" to the opacity side question, but step 2 chose A "left lung opacity," citing the grounded report's left-base atelectasis as "a focal opacity on the left side." The letter and text agreed (A ↔ left lung opacity), so this was not an option-mapping error; it was an evidence-prioritization/wrong-conclusion failure. The direct same-finding VQA supported the right side, the grounded report named a different finding, and the terminal rationale bridged atelectasis into the asked opacity. The reference was B "right lung opacity." The caution: a correct-looking letter-text mapping does not validate the answer when the rationale substitutes a related finding for the observed same-finding evidence and ignores the contradicting direct answer.
```

## exp_0cc27c13dfa9480b57554db1

来源题 [chexbench_openi_0173](../../cases/openi/chexbench_openi_0173.json) · 活跃

```text
Trigger: When finalizing a side-specific chest X-ray multiple-choice answer—especially left-vs-right clavicle deformity—on a lateral or side-superimposed image, or when tool outputs conflict about the side and a verifier cautions that laterality cannot be determined.

Verification action: Before emitting the option, locate the displayed option map and identify the exact candidate text. Require and quote a same-scope observation that explicitly establishes both the finding and the side on a view or report that can establish laterality—e.g., a frontal PA/AP image or a report stating “right/left clavicle deformity.” Do not treat a lone VQA side word, an “L” marker, or a verifier’s partial approval as proof of laterality. Explicitly record conflicting evidence such as chest_xray_expert saying “Right” while llava_med_qa says “Left,” and record any verifier caution that the lateral view superimposes the clavicles. If no same-scope observation establishes presence and side, mark the side-specific options unsupported/indeterminate rather than choosing a side; do not let finalization drop the caution. Only if a side is established, map the supported answer text back to the displayed choice and confirm that the letter and text agree.

Case diagnosis: The terminal answer “A. left clavicle deformity” matched option A’s text and letter, so this was not an option-mapping error. It was a wrong-conclusion/evidence error: finalization selected llava_med_qa’s “left” assertion despite chest_xray_expert’s conflicting “Right” and the verifier’s warning that the lateral view cannot reliably determine clavicle laterality. The released reference was B, but that alone does not prove the evidence handling was sound; the reusable lesson is to require same-scope laterality evidence and to preserve the conflict/caution through finalization.
```

## exp_7777d646cc594ad7faad3cd1

来源题 [chexbench_openi_0176](../../cases/openi/chexbench_openi_0176.json) · 活跃

```text
Reusable decision procedure:

Trigger: When a chest X-ray multiple-choice question offers only laterality variants of an indwelling catheter (for example, A “left indwelling catheter” vs. B “right indwelling catheter”), and the first expert/grounding call returns no observation, an empty result, or only an indeterminate/lateral-view limitation.

Verification action: Do not finalize A or B from absence of evidence, “no right-sided evidence,” dataset priors, or tip-location language alone. Require at least one observed tool result for the current image that explicitly states the catheter’s side, such as “right indwelling catheter” or “left-sided PICC.” If multiple tools give explicit side statements, check that they agree. If no same-object laterality observation is obtained, report that the answer cannot be determined rather than choosing a side. If a side is supported, map that side’s text back to the displayed options and confirm the chosen letter and text agree.

Case lesson: In this trajectory, step 0 requested the expert tool but no observation was returned; step 1 nevertheless chose A/left based on absence of right-sided evidence. A’s letter and text agree with the option map, so this was not an option-mapping error. The reference was B/right, and no observed tool result had explicitly supported either side. The failure was an unsupported conclusion/evidence error: the terminal choice did not use a same-object laterality observation, and the rationale substituted absence of evidence for positive evidence.
```

## exp_09d15052460044360af9e682

来源题 [chexbench_openi_0177](../../cases/openi/chexbench_openi_0177.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks left versus right lower lobe pulmonary atelectasis from a lateral view, and one model mentions “left-sided” opacity while other models are negative or the verifier warns that laterality cannot be reliably distinguished and that “LT LAT” denotes projection rather than left-sided pathology.

Verification action: Before emitting the option, scan the raw observations for an explicit statement that ties the exact finding—pulmonary atelectasis—to the exact side—left or right—on a view or report capable of establishing laterality, such as a frontal/PA image or a side-labeled report. Treat “LT LAT” as a projection marker only, not as evidence of left pathology. Treat a generic lower-lobe opacity or a single model’s “particularly on the left side” as non-side-specific when the verifier says left versus right cannot be distinguished. Do not count a “No” to a combined left-or-right question as support for either side. If the side remains unresolved, do not select the left option merely because it is the only positive-sounding choice; mark the side unsupported or seek additional side-specific evidence. Then map the supported answer text back to the displayed option map and confirm that the letter and text agree, and compare both with the released reference when available.

In this case, the terminal choice “A. left lower lobe pulmonary atelectasis” matched option A’s text, so this was not an option-mapping error. The error was substantive: the final rationale used MedGemma’s ambiguous left-sided opacity as side evidence despite the verifier’s explicit caution that a lateral view cannot reliably distinguish left from right lower lobe atelectasis. The released reference was B, “right lower lobe pulmonary atelectasis.”
```

## exp_0a2e2b72f9732c44cfe43695

来源题 [chexbench_openi_0153](../../cases/openi/chexbench_openi_0153.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks left- versus right-sided basilar pulmonary atelectasis, especially after a combined “left or right?” VQA query returns only a bare “No” or another non-side-specific reply.

Verification action: Before emitting the choice, inspect the recorded observations for an exact side-and-finding result. Do not treat the bare “No” to “left base or right base atelectasis?” as evidence for either side or as a denial of both; require a side-specific statement or exact phrase-grounding localization. Also check whether any negative general report actually names the same finding: “no consolidations/effusions” is not an explicit denial of atelectasis and should not be used to override an exact atelectasis phrase-grounding result. If using phrase grounding, confirm that the returned phrase exactly matches the candidate, such as “left base pulmonary atelectasis,” and that the box lies in the corresponding lower lung zone. Then map the supported side-and-finding text back to the displayed option map and confirm that the selected letter’s displayed text matches it. In this case, phrase grounding returned “left base pulmonary atelectasis.” with a left lower-zone box [0.645, 0.465, 0.825, 0.625], matching option A, whose text was “left base pulmonary atelectasis”; the reference was A. The caution is that the initial VQA “No” and the nonspecific grounded report did not independently confirm laterality, so the rationale should state the phrase-grounding evidence at its actual strength rather than presenting it as multi-tool confirmation.
```

## exp_e9bcc4e6587b0cf296fc9de0

来源题 [chexbench_openi_0154](../../cases/openi/chexbench_openi_0154.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer that turns on right-vs-left laterality (for example, “right thoracic vertebrae scoliosis” vs “left thoracic vertebrae scoliosis”), a side-specific tool observation does name a side, and a verifier then warns that the image is a lateral view in which laterality is unreliable.

Verification action: Before emitting the letter, quote the exact raw tool observation and determine whether it explicitly names a side (“Right”) rather than only “Yes,” an empty result, or an inferred rotation. If an explicit side is present, require the side in the observation, the side in the final rationale, and the side in the selected option’s text to be identical, then confirm the letter maps to that text. In this case the chest_xray_expert observation said “Right,” the terminal rationale said “right-sided,” and option A’s text was “right thoracic vertebrae scoliosis,” so the letter, text, and observed side agreed and A matched the reference. The verifier’s lateral-view caution is a reliability warning, not a competing side assertion; it should not cause a silent reversal to the opposite option when the tool explicitly names a side and the question forces a choice. If the observation were only “Yes,” empty, or based solely on subtle vertebral rotation on a lateral view, laterality should be treated as unsupported. A correct grade alone does not prove this check was performed; the observable proof is the quoted side token plus the letter-text match.
```

## exp_2e4b9306d50ebad07235feb5

来源题 [chexbench_openi_0155](../../cases/openi/chexbench_openi_0155.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer (e.g., small left vs small right pleural effusion) after a direct VQA tool answers a pleural-effusion question with a side (“Right”) but a grounded report explicitly says “No pleural effusion is identified,” lists same-side alternative findings, and the verifier returns CORRECT/SAFE with a suggested supporting feature rather than an independent measurement.

Verification action: Before emitting the letter, quote the exact direct VQA question and answer and confirm it asserts the finding and the side. Explicitly note the grounded report’s negative finding and any same-side alternative (here right perihilar consolidation/right lower lobe atelectasis) that could explain the VQA side. Treat the verifier as a correctness/safety check, not independent image evidence: do not write “the verifier confirmed blunting” unless the verifier observation explicitly states that finding as confirmed; if it only says “Suggestion: support by citing…,” label it as a suggestion, not confirmation. Then map the supported text to the displayed options (A = small left, B = small right), write the letter and text together, and check that B is the right-sided choice. If evidence remains discordant, state the conflict and the basis for overriding it rather than silently omitting it. A correct grade alone does not prove this attribution-and-mapping check was performed.
```

## exp_d6f90c838b0fb4bde984e384

来源题 [chexbench_openi_0156](../../cases/openi/chexbench_openi_0156.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer about right versus left hemidiaphragm elevation, especially when a direct expert/VQA result returns a side and an auxiliary phrase-grounding call or grounded report is also cited.

Verification action: Before emitting the answer, extract the side from the direct question-specific expert/VQA observation, map it to the exact displayed option letter and full text, and check that letter-text pair against the option map and released reference when available. Then audit every cited auxiliary tool against the same object and attribute: the direct expert result is the load-bearing evidence for presence and side; phrase grounding only localizes the phrase you supplied and does not independently prove the finding is present; a grounded report that never mentions the diaphragm cannot confirm diaphragm elevation. In this case, the expert said “Left,” option B was “elevated left diaphragm,” and the reference was B, so the terminal letter-text answer was correct. The rationale should not treat the phrase-grounding localization as independent confirmation. If the letter-text mapping is correct but the rationale overclaims auxiliary evidence, correct the rationale rather than changing the answer; a correct grade alone does not prove the evidence attribution is sound.
```

## exp_75e25db311c1a9d511bcc710

来源题 [chexbench_openi_0158](../../cases/openi/chexbench_openi_0158.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer after a direct VQA tool answers a pleural-effusion query with only “Right side”/“Left side” and a grounded-report tool returns inapplicable/no report because the image is lateral-only or otherwise unsupported—especially when the option text includes an unverified descriptor such as “large.”

Verification action: Before emitting the letter, quote the direct observation(s) that answer presence and side in context—here chest_xray_expert’s “Right side” under the pleural-effusion question and llava_med_qa’s “Yes, there is a pleural effusion on the right side of the chest.” Explicitly treat the grounded report as non-evidence, not as corroboration, because it did not analyze the image. Then map the supported side to the full displayed option map: A is “large right pleural effusion” and B is “large left pleural effusion,” so the correct pair is “A. large right pleural effusion.” Do not claim the tools confirmed “large” unless a tool observed it; use laterality only to distinguish the options. If the rationale attributes support to the inapplicable report or omits the direct side-specific evidence, correct it before finalizing.
```

## exp_d076af0e7d45551efa155b6f

来源题 [chexbench_openi_0159](../../cases/openi/chexbench_openi_0159.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer and two direct VQA tools explicitly give opposite sides for the same finding (e.g., chest_xray_expert says “Right” while llava_med_qa says “small left pleural effusion”), especially when the image is lateral-only and the verifier cautions that laterality is indeterminate.

Verification action: Before emitting the letter, list each side-specific observation verbatim with its tool and question, including the contradicting side. Do not call the chosen side “the only” side-attributed positive if another tool named the opposite side. Treat the verifier’s lateral-view caution as a limitation, not as evidence for either side, and do not count a non-contributory report as positive or negative evidence. Then map the supported answer text back to the displayed options and check letter, text, and laterality together: A = “small left pleural effusion,” B = “small right pleural effusion.” If the conflict remains unresolved, say so in the rationale rather than presenting the selected side as verified. A correct grade alone does not prove this conflict-and-mapping check was performed.
```

## exp_1ae5cb26123a410dbd7cce22

来源题 [chexbench_openi_0160](../../cases/openi/chexbench_openi_0160.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that turns on left-versus-right laterality for a basilar finding (e.g., left vs. right base pulmonary atelectasis) and the first either/or tool query returned only a bare “Yes,” after which you issued separate side-specific follow-up calls.

Verification action: Before emitting the option, open the recorded observations and require an explicit, same-scope, side-and-finding statement — do not treat the mere issuance of a side-specific follow-up as evidence. If the follow-up call has no recorded observation, the laterality is unsupported: either re-query until a side-specific result is actually recorded, or do not finalize on that side. Then take the exact supported side-and-finding text, map it to the displayed option map, and confirm the chosen letter’s displayed text matches. In this case the terminal letter A and its text “left base pulmonary atelectasis” did agree with each other and with the reference A, so there was no option-mapping error. But the procedure did not earn that answer: the only recorded observation remained a bare “Yes” to the combined “left or right” query, the two side-specific calls in step 1 produced no observation, and the rationale’s claim of “lateral view opacity consistent with left lower lobe collapse” was not present in any recorded result. A correct grade therefore does not validate the procedure; the caution is that a side-specific follow-up call with no recorded observation cannot support a laterality, even when the final letter happens to be right.
```

## exp_75b44ed1567d9ee4b6fc0deb

来源题 [chexbench_openi_0163](../../cases/openi/chexbench_openi_0163.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer about left-versus-right hemidiaphragm elevation, after a direct question-specific VQA/expert call has returned a single side word (and any auxiliary report/grounding call has also returned).

Verification action: Before emitting the answer, take the side from the direct question-specific observation, then re-read the displayed option map and write the exact letter plus full option text, checking that the letter and text agree with each other and that the text carries the same side as the observation. Do not carry over a letter from memory or from a prior case: in the supplied histories the same text "elevated left diaphragm" appeared under option B in one item and under option A here, so the letter must be re-mapped for each item. Then audit each cited tool against the same object and attribute (hemidiaphragm elevation, and side): a grounded report may be cited only if it actually names the diaphragm and side (as it did here: "Elevation of the left hemidiaphragm"), and phrase grounding of a phrase that already contains the side is localization, not independent proof of presence. If the letter/text pair is correct but the rationale overclaims an auxiliary tool as independent confirmation, fix the rationale rather than the answer. In this case "Left" from the expert plus the grounded report both support the displayed "A. elevated left diaphragm," matching the reference; the reusable caution is to re-map text-to-letter each time and to attribute evidence to the tool that actually addressed the finding, not to a verifier's "CORRECT" or a silent report.
```

## exp_3b9adc8c5487bf8aa21f2a06

来源题 [chexbench_openi_0164](../../cases/openi/chexbench_openi_0164.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer where the options differ only by right versus left for the same finding, especially hemidiaphragm elevation, after consulting a direct expert/VQA result and a grounded report.

Verification action: Before emitting the answer, extract the side from the direct question-specific observation and check that the grounded report explicitly names the same structure and attribute. Re-read the full displayed option map, write the exact letter and full option text, and confirm the supported side maps to that pair and not to the opposite-laterality option—e.g., “Left” plus “Elevation of the left hemidiaphragm” maps to “B. elevated left diaphragm.” In the rationale, cite a tool as confirmation only if its observation actually addressed the same object and attribute; do not treat silent, phrase-only, or verifier evidence as independent confirmation. If the letter/text pair is correct but the rationale overclaims, fix the rationale; if the laterality evidence conflicts or does not address the same finding, do not claim the conflict is resolved.
```

## exp_62ce140ac1ba5bafe3f360b9

来源题 [chexbench_openi_0165](../../cases/openi/chexbench_openi_0165.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options are opposite laterality for the same finding, such as “left base pulmonary atelectasis” versus “right base pulmonary atelectasis,” especially if a combined either/or tool query returns only a bare “No,” “Yes,” or another non-side-specific reply. Do not treat that combined reply as establishing laterality.

Verification action: Before emitting the option, inspect the recorded observations for an explicit side-specific pair naming the exact finding and exact side, such as “Yes” to “Is there left base pulmonary atelectasis?” and “No” to “Is there right base pulmonary atelectasis?” If only the combined query exists, make separate side-specific queries and use only recorded results. Then take the supported side-and-finding text and map it back to the displayed option map, confirming that the chosen letter’s displayed text matches. In this source case, the combined query returned “No,” but the side-specific observations showed left base atelectasis “Yes” and right base atelectasis “No,” supporting “left base pulmonary atelectasis,” which mapped to option A and matched the reference. The caution is that laterality must come from exact side-specific evidence, not from an ambiguous combined either/or answer.
```

## exp_8894a118a719868e2bba010b

来源题 [chexbench_openi_0168](../../cases/openi/chexbench_openi_0168.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by left versus right indwelling catheter, especially when the rationale cites tool outputs or grounding boxes for laterality.

Verification action: Inspect the actual observations for an explicit same-object side statement about the catheter/port-a-cath, such as “Right side,” “Right-sided port-a-cath,” or “Left-sided PICC.” Do not treat mere catheter presence or distal tip location (“superior vena cava,” “cavoatrial junction,” “right atrium”) as sufficient side-of-insertion evidence. If a grounding box is cited, confirm it covers the catheter on the stated patient side under standard frontal-CXR orientation (patient right = image left), while remembering that the box is model output rather than independent confirmation. Reconcile all explicit side statements and check that an earlier supported side was not dropped or reversed during finalization. Then map the supported side’s text back to the displayed option and verify the terminal letter and text agree. In this case, chest_xray_expert returned “Right side” and maira2_grounded_report returned “Right-sided port-a-cath” with an image-left/patient-right catheter box, so B “right indwelling catheter” was supported and correctly mapped; the correct grade alone is not the proof, but the evidence and letter-text checks pass.
```

## exp_1621dc7f17befba5f43dec5b

来源题 [chexbench_openi_0169](../../cases/openi/chexbench_openi_0169.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer (right vs left pleural effusion) from a lateral-only image, after direct VQA tools answer the pleural-effusion question with a side, the grounded-report tool returns “not_applicable” because a frontal view is required, and the verifier labels the choice CORRECT but CAUTION for laterality.

Verification action: Before emitting the letter, quote the direct VQA observations that actually assert both presence and side (e.g., “Right side” and “pleural effusion in the right side”). Explicitly state that the grounded report supplied no usable image evidence for or against effusion, and that the verifier is only a final correctness/safety check—not independent image evidence and not confirmation of laterality. Acknowledge the lateral-view limitation rather than saying the verifier “confirms” the side. Then map the supported text back to the displayed option map: confirm A is “right pleural effusion” and B is “left pleural effusion,” and emit “A. right pleural effusion.” If the rationale cannot make this attribution and limitation honest, correct it before finalizing; a correct grade alone does not prove the check was performed.
```

## exp_7dc5bee1968d115f35c298c6

来源题 [chexbench_openi_0170](../../cases/openi/chexbench_openi_0170.json) · 活跃

```text
Trigger: When finalizing a laterality-sensitive chest X-ray multiple-choice answer and the load-bearing tool result is a side word or side-specific phrase (e.g., “Left”) that the rationale claims “corresponds to option A/B.”

Verification action: Before emitting, explicitly read the displayed option map and match the tool’s side and finding to the chosen option’s full text, not just its letter. Confirm the selected letter’s text contains the same side and structure (e.g., “A. elevated left diaphragm” for “Left”), and confirm the tool observation addressed the same object and attribute—hemidiaphragm elevation side. Then finalize that verified letter-text pair. In the observed case, “Left” → A “elevated left diaphragm” passes the check; the lesson is that the rationale’s “corresponds to option A” should be backed by actually reading A’s text, rather than assumed from letter order or the draft. If the letter and text disagree, correct the pair rather than preserving the claimed correspondence.
```

## exp_0fdeed8fb49b7b397cb0289c

来源题 [chexbench_openi_0191](../../cases/openi/chexbench_openi_0191.json) · 活跃

```text
Trigger: When a chest X-ray multiple-choice item distinguishes right versus left lower lobe pulmonary atelectasis and the tool returns a bare “Yes”/“No” to a combined “right or left?” question, or when finalizing from a lateral view labeled “LT LAT.”

Verification action: Before finalizing, inspect the recorded observations for an exact side-and-finding statement, such as “right lower lobe pulmonary atelectasis,” or an exact phrase-grounding result with a box in the corresponding lower lung zone. Treat a “Yes” to “right lower lobe or left lower lobe atelectasis?” as presence-only, not laterality evidence. Treat a planned second query with no recorded observation as non-evidence. Treat “LT LAT” as a projection label, not as evidence of left-sided pathology. If no recorded side-specific evidence exists, do not select a side; obtain/record it or mark the side unsupported. Then map the supported answer text back to the displayed option map and confirm the chosen letter’s text matches. In this case, the early note correctly recognized that “Yes” was insufficient to distinguish right from left, but finalization lost that caution and chose B “left lower lobe pulmonary atelectasis” without a recorded side-specific observation. B’s letter and text did match the left-lower-lobe option, so this was not an option-mapping error; it was an unsupported side conclusion. The reference was A “right lower lobe pulmonary atelectasis.”
```

## exp_1dd73204fdddbfaada582f4c

来源题 [chexbench_openi_0182](../../cases/openi/chexbench_openi_0182.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer whose options differ only by left versus right for the same finding—especially hemidiaphragm elevation—and a direct expert/VQA observation returns a side word such as “Left.”

Verification action: Treat that side word as the supported side, re-read the entire current option map, and write the exact displayed option letter with its full text only if the option’s structure, attribute, and side match the observation. In this case, the expert returned “Left,” the current map has “A. elevated left diaphragm,” and the reference is A, so the letter-text pair and evidence agree. Do not reuse another case’s letter mapping—historical cards had left-sided diaphragm elevation mapped to B—and do not claim auxiliary confirmation unless an auxiliary tool actually addressed the same finding. If the letter/text pair disagrees with the supported side, fix the mapping; if the mapping is correct but the rationale overclaims evidence, fix the rationale before finalizing.
```

## exp_faebd4ef5a0fb52a40148d56

来源题 [chexbench_openi_0197](../../cases/openi/chexbench_openi_0197.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice question whose options differ only by left versus right indwelling catheter, especially when the rationale cites a grounded report, bounding box, or expert tool for laterality.

Verification action: Inspect the current step observations for an actual same-image, same-object side statement, such as “right indwelling catheter,” “right-sided port-a-cath,” or “left-sided PICC,” or for a bounding box whose patient side is correct under standard frontal-CXR orientation (patient right = image left). Do not accept a tool citation in the rationale alone, and do not treat historical experience cards as current-image evidence. If the cited result is absent from the observations, retry that tool or another available evidence path; if no explicit same-object side observation is obtained, do not finalize A or B—report that the laterality cannot be determined. If evidence is present, reconcile conflicting side statements, check that an earlier supported side was not dropped or reversed during finalization, then map the supported side text back to the displayed option and confirm that the terminal letter and text agree. In the supplied case, A “right indwelling catheter” matched option A and the released reference A, so there was no option-mapping error; however, the rationale cited maira2_grounded_report while the step record had no observation, so the correct grade alone does not prove that the evidence procedure was verified.
```

## exp_5b3c480cffb67022a6411701

来源题 [chexbench_openi_0184](../../cases/openi/chexbench_openi_0184.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer where the options differ only by right versus left for the same finding (e.g., “elevated left diaphragm” vs. “elevated right diaphragm”), and the draft rationale draws on both a direct expert/VQA side word and auxiliary phrase-grounding or grounded-report output.

Verification action: Before emitting the final answer, extract the side from the direct question-specific expert/VQA observation and map it to the exact displayed option letter and full option text; write the pair explicitly and confirm it matches the option map (in this case, expert “Right” plus option B “elevated right diaphragm,” matching the released reference B). Then audit each auxiliary tool against the same object and attribute: a phrase-grounding call whose input phrase already contains “elevated right hemidiaphragm” only localizes the phrase supplied and does not independently prove the finding is present; a grounded report that never mentions the diaphragm cannot confirm diaphragm elevation. Cite the direct expert as the load-bearing evidence and do not describe phrase grounding as independent confirmation. If the letter-text pair is correct but the rationale overclaims auxiliary evidence, correct the rationale rather than changing the answer. In this case the answer B was mapped correctly and matched the reference; the defect was evidence attribution, not option mapping, and the correct grade alone did not validate the rationale.
```

## exp_2d916880931ba65debac9624

来源题 [chexbench_openi_0185](../../cases/openi/chexbench_openi_0185.json) · 活跃

```text
Trigger: When finalizing a forced-choice chest X-ray question whose options differ only by left/right laterality, after a tool returns a side-containing phrase or bounding box and the draft rationale starts converting screen position into patient side.

Verification action: Before emitting the letter, find and quote at least one observation that explicitly names the chosen side for the same structure as the option—not merely “Yes,” “no significant findings,” or a neighboring structure. Check object/attribute match: “surgical clips in the right axilla” is not the same as “surgical instruments in the left breast.” If relying on a bounding box, verify the actual coordinates; do not call x≈0.117–0.207 “screen-right” when it is screen-left, and do not infer patient laterality from screen position alone. If the explicit side word, bbox location, and chosen option text do not agree, re-query with a side-specific phrase or mark uncertainty; do not finalize by flipping a misread coordinate. Finally map the supported side text back to the displayed option and confirm the letter and text agree.

In this case, B “surgical instruments in the left breast” matched option B and the released reference B, so it was not an option-mapping error. But the rationale claimed the grounding box was on screen-right when the recorded image coordinates were screen-left, and the grounding phrase said “Surgical clips are seen in the right axilla,” not “left breast.” The correct grade did not validate the evidence chain; the reusable check is same-structure/same-side evidence plus coordinate and option verification.
```

## exp_e9059b4180976c75202a561d

来源题 [chexbench_openi_0186](../../cases/openi/chexbench_openi_0186.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer where the options differ only by right versus left for the same finding—especially hemidiaphragm elevation—after consulting a direct expert/VQA result and a grounded report.

Verification action: Before emitting the answer, extract the side from the direct question-specific observation, then check that the grounded report explicitly names the same structure and attribute and does not conflict. Re-read the full displayed option map, write the exact letter and full option text, and confirm the supported side maps to that pair and not to the opposite-laterality option. Cite a tool as confirmation only if its observation actually addressed the same object and attribute. In this case, the expert response “Right” and the grounded report’s “Right hemidiaphragm is elevated” support “B. elevated right diaphragm,” matching the option map and released reference. If the letter-text mapping is correct but the rationale overclaims an auxiliary tool, fix the rationale rather than changing the answer; if laterality evidence conflicts or does not address the same finding, do not claim the conflict is resolved.
```

## exp_62e187aba4aa0c0967f715fc

来源题 [chexbench_openi_0187](../../cases/openi/chexbench_openi_0187.json) · 活跃

```text
Trigger: When finalizing a right-vs-left pleural-effusion multiple-choice answer from a lateral-only chest X-ray, after direct VQA tools return a side (e.g., chest_xray_expert says “Right side” and llava_med_qa says right-sided effusion) but the grounded report is “not_applicable” and the verifier warns that a lateral view cannot reliably determine laterality and that the “L” marker is only projection side.

Verification action: Before emitting the letter, reread the displayed option map and pair the supported text with its letter — confirm A is “right pleural effusion” and B is “left pleural effusion.” Quote each direct tool result exactly and only for the attribute it addressed: chest_xray_expert asserted “Right side” for pleural effusion; llava_med_qa asserted right-sided effusion with posterior costophrenic-angle blunting; maira2_grounded_report is not evidence because it was not applicable. Explicitly acknowledge the verifier’s laterality limitation, and do not use “no frontal image to contradict” as positive proof of the side. If choosing A, write “A. right pleural effusion” and make the rationale say the side is based on the direct VQA side assertions, with the lateral-view uncertainty noted. If the rationale merges tool findings or omits the verifier’s limitation, correct it before finalizing. A correct grade alone does not prove this check was done.
```

## exp_67e702727fc984490b72dc76

来源题 [chexbench_openi_0188](../../cases/openi/chexbench_openi_0188.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes left- versus right-sided base pulmonary atelectasis, especially after an either/or VQA query returned a bare “Yes” and side-specific follow-up queries were run.

Verification action: Before emitting the letter, read the displayed option map as letter-to-text and require an explicit side-specific observation. Do not treat a bare “Yes” to “left or right base pulmonary atelectasis?” as laterality evidence. In this case, the useful evidence was the side-specific pair: “left base pulmonary atelectasis?” → “Yes” and “right base pulmonary atelectasis?” → “No,” which supports the exact text “left base pulmonary atelectasis.” Map that exact supported text back to the options: A = “right base pulmonary atelectasis,” B = “left base pulmonary atelectasis,” so the terminal choice must be B and its displayed text must match “left base pulmonary atelectasis.” If the supported text points to one option but the terminal letter points to the other, correct the letter as an option-mapping error; if the side-specific evidence itself supports the opposite side, treat it as a wrong conclusion. If side-specific results conflict or no explicit side-specific statement exists, mark laterality unsupported and obtain or record an explicit side-specific read. A correct final grade alone is not enough; require the observed letter-and-text agreement.
```

## exp_3df7e58f4da4d101eaf6300a

来源题 [chexbench_openi_0190](../../cases/openi/chexbench_openi_0190.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer where the options differ only by right versus left for the same finding, especially hemidiaphragm elevation, and the draft answer cites both a direct expert/VQA side answer and a grounded report.

Verification action: Before emitting the answer, extract the supported side from the direct question-specific observation and confirm that observation addressed the same structure and attribute as the question, e.g., right/left hemidiaphragm elevation. Re-read the full displayed option map, write the exact letter and full option text, and check that the supported side maps to that letter-text pair, not to the opposite-laterality option. Then audit every cited auxiliary tool: call it confirmation only if its output explicitly names the same structure and finding; a silent report, a phrase-grounding box for a phrase you supplied, or an unrelated finding is not independent confirmation. Compare the letter and text with the released reference when available. If the letter-text mapping is correct but the rationale overclaims an auxiliary tool, keep the answer and fix the rationale; if the pair contradicts the supported side, fix the mapping; if evidence conflicts, state only what the direct tool supports or flag uncertainty.

In the supplied case, the expert answered “Right” to the question “Is the right or left hemidiaphragm elevated in this chest X-ray?”, and the grounded report said “Elevation of the right hemidiaphragm.” Option B was “elevated right diaphragm,” and the reference was B, so the terminal “B. elevated right diaphragm” is correct. The lesson is still the same: verify the side, the same object and attribute, the exact option letter-text pair, and the evidence attribution—not merely that the final answer received a correct grade.
```

## exp_14261f56bf17e967f75715a8

来源题 [chexbench_openi_0193](../../cases/openi/chexbench_openi_0193.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer where the options differ only as right versus left for the same finding (e.g., elevated right vs elevated left diaphragm), and a direct question-specific chest X-ray expert returns a bare side word such as “Left.”

Verification action: Before emitting the answer, re-read the full displayed option map and map the expert’s side word to the exact option letter and full option text. Confirm that the letter and text agree and that the side maps to the correct structure and attribute—e.g., “Left” plus hemidiaphragm elevation maps to “B. elevated left diaphragm,” not to the right-sided option. In the rationale, cite the direct expert observation only for the side and finding it actually addressed. Do not treat silent, phrase-only, or unrelated evidence as independent confirmation. If the side evidence conflicts or does not address the same object and attribute, resolve that before finalizing. In this case the expert observation “Left” addressed the same question and supported option B, so the terminal letter/text pair was correct.
```

## exp_26f0a85c840e6ce521719924

来源题 [chexbench_openi_0194](../../cases/openi/chexbench_openi_0194.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes left versus right base pulmonary atelectasis after phrase-grounding queries for both candidate sides, especially if the rationale claims a letter/text mismatch.

Verification action: Before emitting the choice, treat a phrase-grounding box only as localization of the queried phrase, not as proof that the finding is present. If both left- and right-side queries return plausible lower-lung boxes, the result is non-discriminative and cannot establish laterality by itself. Look for an explicit recorded read naming the exact side and exact finding. Then map that supported side-and-finding text to the displayed option map and verify that the selected letter’s displayed text matches it and the reference. Do not repeat or rely on a claimed “letter mismatch” unless the current option map actually contains one. In this case option B’s text was “left base pulmonary atelectasis,” matching the terminal answer and reference, so there was no option-mapping error; the caution is that the rationale’s “letter mismatch” comment was unsupported and the left/right phrase-grounding results were both merely localizations, not discriminating evidence of which finding was present.
```

## exp_1789f5e6fb00b4c675981d17

来源题 [chexbench_openi_0195](../../cases/openi/chexbench_openi_0195.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by left versus right indwelling catheter/port, and the rationale cites an expert side answer or a grounded report/box.

Verification action: Require at least one observed tool result that explicitly states the side of the catheter/port, such as “Right,” “Right-sided chest port,” or “Left-sided PICC.” Do not infer laterality from mere catheter presence or from tip location alone, such as “SVC” or “right atrium.” If citing a grounding box, confirm it covers the catheter on the stated patient side under standard frontal-CXR orientation (patient right = image left), while treating the box as model output rather than independent confirmation. Reconcile all explicit side statements, check that no earlier supported side was reversed or dropped, then map the supported side’s text back to the displayed option and confirm the terminal letter and text agree. In this case, chest_xray_expert returned “Right” and maira2_grounded_report returned “Right-sided chest port identified…” with an image-left/patient-right box, so A “right indwelling catheter” was supported and correctly mapped.
```

## exp_c4a46f6b879582689191c047

来源题 [chexbench_openi_0196](../../cases/openi/chexbench_openi_0196.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer whose options differ only as “elevated left diaphragm” versus “elevated right diaphragm,” after a direct expert/VQA has returned a side.

Verification action: Before emitting, extract the side from the direct question-specific observation and map it to the exact displayed letter and full option text, checking the whole option map and the released reference if present—here “Right” maps to “B. elevated right diaphragm,” and B is correct. Then audit every cited tool for the same object and attribute: the verifier may support “consistent with right hemidiaphragm elevation” only as far as it actually said so; if it notes laterality uncertainty on a single lateral view, preserve that caveat or avoid an unqualified “confirmed.” If the letter/text is correct but the rationale overclaims, fix the rationale rather than changing the answer; if the evidence conflicts or never addresses hemidiaphragm elevation and side, do not claim the conflict is resolved.
```

## exp_444b1695225be65ab99a6f76

来源题 [chexbench_openi_0198](../../cases/openi/chexbench_openi_0198.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by catheter laterality (e.g., A. left indwelling catheter vs B. right indwelling catheter), especially when the image is a lateral view and the rationale cites one or more VLM tool outputs.

Verification action: Before committing the answer, reread the actual observation text for at least one explicit same-object side statement ("Left," "left indwelling catheter," "Right-sided port-a-cath") — not merely catheter presence or catheter-tip location ("superior vena cava," "right atrium"), which do not establish the side of insertion. If two tools were consulted, reconcile them: agreement on the same explicit side is usable; a bare one-word "Left" with no supporting detail is weaker evidence than an explicit sentence and, on a lateral view where laterality is inherently hard, should be weighed as such; if the outputs conflict, do not pick by count — prefer the output that explicitly names the side and, failing that, report that the side cannot be determined rather than guessing. Then map the supported side's text back to the displayed options and confirm the chosen letter and text agree. In this case chest_xray_expert returned "Left" and llava_med_qa returned "Yes, the lateral chest X-ray shows a left indwelling catheter," so A/left was supported and the letter-text mapping matched. The correct grade alone is not proof of the procedure — the explicit side statement plus the letter-text check is; the contrast is a historical case where no laterality observation was returned and an option was still selected from absent evidence, which must be avoided.
```

## exp_4969aace687ed9d162f84479

来源题 [chexbench_openi_0199](../../cases/openi/chexbench_openi_0199.json) · 活跃

```text
**Reusable decision procedure (experience card)**

**Trigger:** A chest X-ray multiple-choice question whose two options differ only by laterality of an indwelling catheter (e.g., A. left indwelling catheter vs B. right indwelling catheter), and the tool evidence is indirect or conflicting — one tool reports mere catheter presence or a tip location (SVC, cavoatrial junction, right atrium), another gives an explicit side, another returns garbled text, and the apparent support for the chosen side comes from a prompt that itself pre-labeled one trajectory as "left" and the other as "right."

**Verification action:** Before finalizing, require at least one observation that addresses the same object and attribute as the question — an explicit side-of-catheter/insertion statement such as "left-sided catheter," "right-sided port-a-cath," or "right indwelling catheter." Reject as insufficient: catheter presence alone, tip location ("lower SVC," "right atrium") as a proxy for insertion side, the "L" projection marker alone, and positional words ("posterior"/"anterior") that the asking prompt itself equated with a side. If the only explicit statement came from a leading question, re-ask neutrally or rely on the verify tool's independent course/insertion assessment. Reconcile any conflicting explicit statements and state the conflict. If no same-object laterality observation survives, report indeterminate rather than guessing. Then map the supported side's text back to the displayed option and confirm the terminal letter and text both agree (A = left text, B = right text).

**Case explanation:** In this lateral-CXR case, chest_xray_expert first gave only presence ("tip in the lower superior vena cava") with no side; llava_med_qa said "right"; medvlm_r1 returned garbled text; roi_crop explicitly warned "patient side not inferred." The second chest_xray_expert answer, "Posterior," came from a question that stated "posterior ... suggesting left-sided insertion," so it echoed a supplied mapping rather than independently observing laterality. The verify tool provided the actual same-object side statement — "the visible catheter course/insertion is consistent with a left-sided indwelling catheter" — and flagged that the "L" marker indicates projection side, not laterality. The final answer A/left matched the reference A/left, and its letter and text agreed, so this was not an option-mapping error. The instructive near-miss was evidentiary: a leading-question echo momentarily looked like left-side support, and the correct grade alone does not prove the reasoning — the explicit verify statement is what actually supported A.
```

## exp_acdc5968a85344b0c99d2b75

来源题 [chexbench_openi_0200](../../cases/openi/chexbench_openi_0200.json) · 活跃

```text
Trigger: When finalizing a left-versus-right chest X-ray multiple-choice answer from a lateral view and the draft relies on a bare side word or converts an anterior/posterior location into patient laterality, especially when another tool reports the finding absent or the verifier/ROI warns that laterality cannot be assigned.

Verification action: Before emitting the letter, search the observation log for at least one explicit same-image observation that names both the asked finding (for example, surgical instruments/clips) and the chosen patient side (for example, “right upper quadrant” or “right abdomen”). Do not count “Anterior” on a lateral view, screen-left/right, a bounding box, or a conditional-question answer like “Right side” unless it clearly confirms both presence and side. If results conflict or no such statement exists, re-query presence plus side or report the laterality as indeterminate/unsupported. If the format forces a choice, mark it as an unsupported guess and still map the supported text to the displayed option letter and text. In this case, the terminal “B. surgical instruments in the right abdomen” matched option B and the released reference B, so it was not an option-mapping error; the defect was evidence: the final rationale converted the second chest_xray_expert’s “Anterior” into right-sidedness while llava_med_qa said no instruments, verify flagged the lateral view as laterality-indeterminate, and roi_crop warned not to infer patient side from screen position. A correct grade does not validate that unsupported inference.
```

## exp_0c91bfe5acb5e6f7fbccc18f

来源题 [chexbench_openi_0204](../../cases/openi/chexbench_openi_0204.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality of an indwelling catheter (e.g., A. right indwelling catheter vs B. left indwelling catheter), and the rationale cites tool outputs for the side.

Verification action: Check the actual tool observations for an explicit same-object side statement about the catheter, such as “Right,” “right-sided catheter,” or “left side”; do not treat mere catheter presence, a non-applicable report, or tip location alone as laterality evidence. If tools agree on a side, map that side’s text back to the displayed option and confirm the chosen letter and text agree. If no explicit side observation exists, report that the answer cannot be determined rather than choosing an option. In this case, chest_xray_expert returned “Right” and llava_med_qa returned “right side,” while maira2_grounded_report was not applicable for the lateral view; option A’s text was “right indwelling catheter” and the reference was A/right, so the final A/right was supported and correctly mapped. The correct grade alone is not proof, but the evidence and letter-text checks pass.
```

## exp_6d157ec000e924e0bd40edcc

来源题 [chexbench_openi_0205](../../cases/openi/chexbench_openi_0205.json) · 活跃

```text
Trigger: When finalizing a left-vs-right chest X-ray multiple-choice answer and a crop/ROI shows the finding on screen-left—especially on a lateral view—while a prior image tool has returned an explicit side word such as “Right,” or when a draft answer is about to switch to the screen-left option despite that explicit side evidence.

Verification action: Before emitting the letter, quote the explicit patient-side word from the tool output for the same finding and treat it as the load-bearing laterality evidence. Do not convert screen-left/right, ROI coordinates, or an “L” projection marker into patient laterality; roi_crop itself warns “patient side not inferred” and “Do not infer patient laterality from screen position.” Then map the supported side’s text back to the displayed option map and confirm letter and text agree—here “right abdomen” maps to B. If no explicit same-finding side observation is obtained, do not turn screen-left into “left”; use verify/second-view evidence or state that laterality cannot be determined. In this case, chest_xray_expert said “Right” and verify confirmed the anterior-inferior clips were consistent with right upper quadrant and warned against using the “L” marker; step 2’s draft A came from screen-left appearance, not supported laterality. This was not an option-mapping error—the final B letter and “right abdomen” text matched the reference—but a near-miss caused by screen-side inference.
```

## exp_fda2a526ecd5d250bf4e2976

来源题 [chexbench_openi_0206](../../cases/openi/chexbench_openi_0206.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer for left vs right base pleural effusion after the direct VQA tool returns only “Left,” phrase grounding is queried with the candidate phrase, and the grounded report instead describes left volume loss/pleural thickening without explicitly asserting pleural effusion.

Verification action: Before emitting the option, quote the exact VQA question and answer and confirm it covers both pleural effusion and side. Explicitly record the grounded report’s actual wording as alternative or non-confirming evidence, rather than silently omitting it. Treat xray_phrase_grounding only as localization of the supplied phrase, not as independent proof that the finding is present. Then map the supported text back to the full option map—A “left base pleural effusion” vs B “right base pleural effusion”—and write the letter with its text. In this case, terminal “A. left base pleural effusion” matched option A and the reference A; there was no option-mapping error, but the rationale should not have treated phrase grounding as additional confirmation or omitted the grounded report’s different finding.
```

## exp_1f099941cace1813239396e2

来源题 [chexbench_openi_0208](../../cases/openi/chexbench_openi_0208.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer after a direct VQA tool returns only a bare side word (e.g., “Left”) and a grounded report supplies a side-specific finding sentence.

Verification action: Before emitting the choice, quote the direct VQA side answer with its question, quote the grounded report’s exact presence-and-side sentence (e.g., “Small left effusion is suspected” plus “right hemithorax is clear”), and confirm at least one source explicitly asserts the finding while no source asserts the opposite side. Do not treat a bare side word as proof that an effusion exists, and do not treat localization as presence. Then re-read the displayed option map, map the supported finding text back to the option, and write the letter and text together. In this case that yields “A. small left pleural effusion,” with A checked as left, not right. A correct grade alone does not prove this evidence-attribution and letter-text mapping check was performed; it must be visible in the rationale before finalizing.
```

## exp_ea0c65ec47c3df69c3d56c34

来源题 [chexbench_openi_0214](../../cases/openi/chexbench_openi_0214.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray question that requires right-vs-left laterality—such as “right thoracic vertebrae scoliosis” vs “left thoracic vertebrae scoliosis”—especially on a lateral radiograph and especially when tools disagree or a verifier says laterality is indeterminate.

Verification action: Before emitting the letter, inspect the transcript for an actual observation that explicitly names both the finding and the side, and quote it. Compare that side with the exact text of the chosen option and confirm the letter/text mapping. Check whether any verifier or observation says that laterality cannot be determined from the lateral view; if so, do not treat a bare “Left” or “right” from a VLM, the “LT LAT” marker, benchmark expectation, or one tool’s answer as sufficient evidence. If tool results conflict and the view is inadequate for laterality, mark the side as unsupported/indeterminate unless a credible frontal view or explicit report resolves it; do not silently select one conflicting tool.

Case lesson: Here A correctly mapped to “right thoracic vertebrae scoliosis” and B to “left thoracic vertebrae scoliosis,” so the failure was not simple option mapping. The chest_xray_expert observation said “Left” (supporting B), llava_med_qa said “right” (supporting A), and verifier feedback warned that a lateral view cannot establish scoliosis laterality. The terminal answer chose A/right anyway, discarding the earlier “Left” observation and the verifier caution. The released reference was B/left, but the reusable rule is to require an explicit, non-conflicting side observation and to reconcile it with the selected option before finalizing.
```

## exp_8eb5abe8b2dc11267a0ef4b3

来源题 [chexbench_openi_0212](../../cases/openi/chexbench_openi_0212.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by left versus right indwelling catheter, and the rationale cites image-tool outputs or a grounded report for laterality.

Verification action: Require at least one observed tool result for this image that explicitly states the catheter’s side, such as “Left” or “Central venous catheter via left jugular vein.” Reconcile all explicit side statements and do not infer side from mere catheter presence or from a distal tip location such as superior vena cava or right atrium. Then map the supported side’s text back to the displayed option and confirm the terminal letter and text agree. In the supplied case, chest_xray_expert returned “Left” and maira2_grounded_report returned “Central venous catheter via left jugular vein with distal end in superior vena cava.” The supported finding text is “left indwelling catheter,” which matches option A, and the terminal answer correctly says “A. left indwelling catheter.” If no explicit same-object side statement is obtained, do not choose a side; report that laterality cannot be determined. If side statements conflict, do not silently reverse or drop the earlier supported side; resolve the conflict or state uncertainty. The correct grade is not itself proof; the explicit side evidence and letter-text mapping are the checks.
```

## exp_5e43bac0f892fb8bd2b55e2d

来源题 [chexbench_openi_0222](../../cases/openi/chexbench_openi_0222.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer comparing right vs. left pleural effusion, and the direct VQA observations all say “No” or “No pleural effusion,” but the terminal rationale selects one side only because “evidence does not support” the other option.

Verification action: Before emitting the letter, quote at least one observation that explicitly asserts both the finding and the side for the chosen option. If every observation is negative, do not convert “A is unsupported” into “B is supported.” Re-ask side-specific questions or use a grounded report to check presence and laterality; treat phrase grounding only as localization, not as proof that the finding exists. Then map the exact supported text back to the displayed option map and confirm that the letter and text agree. If no positive evidence remains, report that the evidence does not establish either option rather than choosing by elimination.

In this case, the terminal choice B matched “small left pleural effusion,” so the letter-text mapping was not the problem. The conclusion was unsupported: the observations said “No”/“No pleural effusion,” and the rationale used lack of support for A as support for B. That is a wrong conclusion, not an option-mapping error.
```

## exp_754b06556c8961f21485cfcd

来源题 [chexbench_openi_0226](../../cases/openi/chexbench_openi_0226.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray question that contrasts left versus right base pulmonary atelectasis from a lateral view, especially after multiple VLM calls disagree and a verify/radiology check warns that a single lateral radiograph cannot reliably lateralize basilar atelectasis.

Verification action: Before emitting the choice, look for a recorded observation that explicitly names the same side and finding from a valid side-defining source, such as a frontal view, report, or exact side-specific read. Do not treat repeated same-image/same-question VLM outputs as independent confirmation, and do not use a bare “No,” an incoherent response, or the final rationale itself to establish laterality. If the verifier says the view is non-discriminative and no exact side-specific read exists, treat the side as unsupported rather than asserting right or left as confirmed. Then map the supported answer text back to the displayed option and check that the selected letter and text agree. In this case, terminal A’s “right base pulmonary atelectasis” matched option A, and reference B was “left base pulmonary atelectasis”; the error was a wrong-side evidence conclusion, not an option-mapping error. The terminal lost the verifier’s supported conclusion that laterality was indeterminate and instead let two VLM “right base” answers outweigh the negative/incoherent results and that warning.
```

## exp_a63a9ca2a85c578b2c29a712

来源题 [chexbench_openi_0230](../../cases/openi/chexbench_openi_0230.json) · 活跃

```text
Trigger: When a chest X-ray multiple-choice question offers only "right indwelling catheter" vs "left indwelling catheter," and the expert-tool observation confirms catheter presence but returns no side (e.g., just "Yes"), do not treat that as laterality evidence.

Verification action: Before finalizing, require at least one observed tool result for this image that explicitly names the catheter's side ("right-sided," "left-sided," "Left PICC," etc.). Mere presence, tip location (SVC/right atrium), population prevalence ("left is more common"), or a prior case's letter default are not side evidence about this image. If the first tool returns presence-only, retry it or try another evidence path (llava_med_qa, maira2_grounded_report, xray_phrase_grounding, roi_crop) and read the actual observation; an issued call with no returned observation is not a verified repair. If no same-object laterality statement is observed, state the answer cannot be determined rather than choosing A or B. When a side is supported, map its text back to the displayed option and confirm the terminal letter and text agree.

In this case the trajectory is an evidence failure, not an option-mapping error: chest_xray_expert returned only "Yes," the llava_med_qa alternative produced no observed result, and step 2 still selected B ("left indwelling catheter") on prevalence and a prior-case default while admitting no tool stated a side. The reference was A ("right indwelling catheter"), and no observed evidence supported B. The lesson: a rationale that openly concedes missing laterality must block finalization, not rationalize a guess; check both that the supported side exists in observed evidence and that its text matches the chosen letter.
```

## exp_1e21d4fd6df6de7b5edc7cd3

来源题 [chexbench_openi_0234](../../cases/openi/chexbench_openi_0234.json) · 活跃

```text
Trigger: Before finalizing a left-vs-right laterality answer for an abdominal finding on a lateral chest X-ray, especially when a ROI crop has been requested and one model names a side while another says no/indeterminate.

Verification action: Check every observation for an explicit same-object, same-attribute statement of the finding and patient side, such as “left abdominal calcinosis” or “right abdominal calcinosis.” Do not treat ROI crop metadata, screen position, anterior location, or absence of the opposite side as laterality evidence; this case’s crop explicitly said “patient side not inferred” and “Do not infer patient laterality from screen position.” If one model says “Right” but another says “no calcinosis” and a third says “cannot determine,” do not promote the uncorroborated side to the final answer. If no explicit side evidence survives the conflict check, do not invent a side; report indeterminate or choose only an option whose text is directly supported. Finally map the supported answer text back to the displayed option and confirm the letter and text agree.

Lesson: In the supplied case the terminal answer “B. right abdominal calcinosis” matched option B’s text, so this was not an option-mapping error; it was an unsupported-conclusion/evidence error. The final rationale claimed the ROI showed right-sided calcification, but the observations were conflicting: chest_xray_expert said “Right,” llava_med_qa said there was no calcinosis, medgemma said it could not determine on a lateral chest X-ray, and roi_crop supplied only crop metadata with an explicit warning not to infer laterality from screen position. The released reference was A, “left abdominal calcinosis.” A single uncorroborated side output plus a crop that supplies no laterality is not enough to finalize a side.
```

## exp_a74542d13987c396c8bc4148

来源题 [chexbench_openi_0235](../../cases/openi/chexbench_openi_0235.json) · 活跃

```text
TRIGGER
When a chest X-ray multiple-choice item forces a side-specific choice (e.g., "small right pleural effusion" vs "small left pleural effusion") and every direct image-reading call in the trajectory has returned the finding as absent — and especially when the image handed to the tools is a lateral projection, from which patient laterality cannot be inferred — do not pick a side to satisfy the format.

VERIFICATION ACTION
Before emitting the letter, run this check on the collected observations:

1. Search the observation text for one sentence that asserts BOTH (a) the finding is present and (b) its side. Quote it verbatim.
2. If no such sentence exists, the answer is unsupported. Do not substitute "the question forces a choice," "the models may have missed something subtle," or "this is a known benchmark case" for evidence. State plainly that no callable reader/localizer asserted a side; abstain or report the finding as absent rather than manufacturing a laterality.
3. Confirm the projection can carry the attribute at all. A lateral view does not localize right vs left; the roi_crop tool itself warns "Do not infer patient laterality from screen position." A side-specific choice on a lateral image therefore has no valid evidence source in this trajectory.
4. Only after a supported side is written down, map that text back to the displayed option map and emit letter plus text together, checking agreement (here A = "small right pleural effusion," B = "small left pleural effusion"; terminal "B. small left pleural effusion" was internally consistent with B — the error was substantive, not a mapping slip).

CASE NOTE
In this trajectory chest_xray_expert ("No"), llava_med_qa ("does not show any small right or left pleural effusion"), medgemma ("no obvious pleural effusion... costophrenic angles appear sharp"), and llava_rad ("No pleural effusion") all agreed the finding was absent; medvlm_r1 returned garbled text that asserts nothing; roi_crop produced only a zoom with an explicit laterality caveat. The terminal rationale conceded "Visual evidence shows no radiographic finding of effusion" and then selected B anyway on forced-choice grounds. The reference was A — the model guessed a side and guessed wrong. The failure is a fabricated laterality under format pressure, not an option-mapping error and not a conflict between tools (all tools agreed).

CAUTION ON THE VERIFIER
The verify call returned "CORRECT / SAFE / Issues: None" for "B. small left pleural effusion." That output is a final correctness/safety audit, not an independent read of the image, and must never be cited to override four direct readers reporting absence. A passing verify here is evidence only that the answer was well-formed, not that the effusion or its side exists.

RESIDUAL GAP
Because the correct behavior (declining to name a side) was never executed in this trajectory, this card records a diagnosed failure mode and a pre-emission check, not a verified repair.
```

## exp_ca895cc605371a8279212e68

来源题 [chexbench_openi_0239](../../cases/openi/chexbench_openi_0239.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice item whose options differ only by right versus left for the same finding, such as “elevated left diaphragm” versus “elevated right diaphragm,” especially after a direct expert/VQA result, a second VQA result, a non-applicable report, an ROI crop, and/or a verifier have produced conflicting signals.

Verification action: Before emitting the answer, find the earlier direct question-specific observation that names the same structure and attribute—here, hemidiaphragm elevation—and extract only its side word. Re-read the full displayed option map, write the exact letter and full option text for that side, and verify the chosen pair matches it. Count a tool as confirmation only if its output explicitly names the same object, attribute, and side. A verifier’s “CORRECT” label is not independent image evidence; an ROI crop that warns against inferring patient laterality cannot establish left versus right; and a grounded report that is not applicable or never mentions the diaphragm does not confirm elevation. If the direct observation says “Left” and option A is “elevated left diaphragm,” select A even if the verifier approved the opposite proposed answer or another VQA model said “right.” If evidence truly conflicts, state the side supported by the direct question-specific observation or flag uncertainty rather than finalizing the opposite side. In this case, chest_xray_expert answered “Left,” so the supported letter-text pair was A “elevated left diaphragm”; the terminal B “elevated right diaphragm” was a wrong conclusion, not a letter-text mapping error.
```

## exp_2493da2408de520704358704

来源题 [chexbench_openi_0241](../../cases/openi/chexbench_openi_0241.json) · 活跃

```text
TRIGGER: When finalizing a laterality-specific chest X-ray multiple-choice answer (right vs left pleural effusion), if a verifier returns a caution that suggests a side—or says laterality cannot be determined—that differs from the side named by the direct VQA model, especially after you already proposed one option in the verify call.

VERIFICATION ACTION: Before emitting the letter, (1) re-quote the direct image-tool observation that asserts both pleural effusion and side—here medgemma's "small pleural effusion on the right side … right costophrenic angle appears blunted"—and keep it as the primary evidence; (2) explicitly label the verifier's laterality remark as a safety/correctness caveat, not independent imaging evidence, and do not let it overwrite the direct observation; (3) treat a lateral-view "L" marker as insufficient to lateralize an effusion, since the roi_crop tool itself states "patient side not inferred" and "Do not infer patient laterality from screen position"; (4) map the supported text back to the displayed options—A = "small right pleural effusion," B = "small left pleural effusion"—and write the letter and text together.

Why: In this case the model had already placed "A. small right pleural effusion" into the verify call, which matches the reference A. The verifier returned PARTIALLY_CORRECT/CAUTION and suggested favoring left based on the "L" marker, and the terminal answer flipped to "B. small left pleural effusion." The letter-text pairing was internally consistent (B = left), so this was not an option-mapping error; it was a lost supported conclusion, where a non-image verifier suggestion (and an unreliable marker inference on a lateral view) overrode the direct side-specific VQA observation. The failure is a caution against treating the verifier's laterality remark as image evidence; a wrong grade alone does not confirm that a corrected procedure would have worked.
```

## exp_c52b0a5d3eb1464968f77266

来源题 [chexbench_openi_0213](../../cases/openi/chexbench_openi_0213.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer whose options differ only by right versus left for the same finding, especially “elevated left diaphragm” versus “elevated right diaphragm,” after a direct expert/VQA observation gives a side word.

Verification action: Before emitting the final answer, extract the supported side and finding from the direct question-specific observation and confirm it addressed the same structure and attribute, e.g. right/left hemidiaphragm elevation. Re-read the full displayed option map, write the exact letter and full option text, and check that the supported side maps to that letter-text pair and not to the opposite-laterality option. In this case the expert answered “Right,” option B was “elevated right diaphragm,” and the reference was B, so “B. elevated right diaphragm” is the supported pair. If the rationale cites auxiliary tools, call them confirmation only when they explicitly name the same structure and finding; otherwise correct the rationale while keeping a correctly mapped answer. If the letter-text pair contradicts the supported side, fix the mapping; if evidence conflicts or does not address the same object/attribute, state only what the direct tool supports or flag uncertainty. A correct grade alone does not prove the rationale or the mapping was carefully verified.
```

## exp_18b5f14ea0740345179cb6bc

来源题 [chexbench_openi_0215](../../cases/openi/chexbench_openi_0215.json) · 活跃

```text
Trigger: When finalizing a left-vs-right pleural effusion multiple-choice answer from chest X-ray VQA after the direct VQA tools name a side, the image is lateral, and the grounded-report tool returns “not applicable” rather than a report.

Verification action: Before emitting the option, quote the exact VQA question and answer that assert both pleural effusion and laterality; do not treat a bare side answer alone as presence evidence unless another observation explicitly confirms effusion. Record the grounded-report result as unavailable/non-confirming—here it required a frontal CXR and did not convert the lateral image—and do not omit or misrepresent that limitation. Then map the supported finding text back to the full option map, confirming A is left pleural effusion and B is right pleural effusion, and write the letter with its text. In this case the correct terminal answer was “B. right pleural effusion,” matching the option map and reference; the reusable check is that the rationale must also record the grounded-report non-applicability, not just the correct letter.
```

## exp_7d84f13fedf76f5920204996

来源题 [chexbench_openi_0216](../../cases/openi/chexbench_openi_0216.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer where the options differ only by right versus left for the same finding—especially “elevated left diaphragm” versus “elevated right diaphragm”—and a direct expert/VQA result has given a side.

Verification action: Before emitting the answer, extract the supported side from that direct observation and confirm it addressed the same structure and attribute as the question, e.g., right/left hemidiaphragm elevation. Re-read the full displayed option map, write the exact letter and full option text, and confirm the supported side maps to that letter-text pair rather than the opposite-laterality option. If auxiliary evidence is cited, call it confirmation only when it explicitly names the same structure and finding; otherwise correct the rationale without changing a correct letter-text mapping. In the supplied case, the expert said “Right,” option B was “elevated right diaphragm,” and the reference was B, so the mapping and evidence attribution were correct.
```

## exp_b8b0a570c8771cbb7142a91f

来源题 [chexbench_openi_0218](../../cases/openi/chexbench_openi_0218.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes right- versus left-sided lower-lobe pulmonary atelectasis, and phrase-grounding queries for both candidate phrases each return a plausible box in the corresponding lower lung zone.

Verification action: Before emitting the choice, do not treat either phrase-grounding box as proof that the finding is present; bilateral plausible boxes are non-discriminative for laterality. Look for an explicit side-and-finding statement in a grounded report or other side-specific observation, such as “Right basilar atelectasis,” and use that as the laterality evidence. If no explicit side-and-finding statement exists, state that the grounding results are non-discriminative. Then map the supported side-and-finding text back to the displayed option map and verify that the selected letter’s displayed text matches it. In this case, both right and left phrase-grounding queries returned plausible lower-zone boxes, but the grounded report explicitly named “Right basilar atelectasis” with a right lower-lung box; selecting A “right lower lobe pulmonary atelectasis” was consistent with the option map and reference A. The caution is that the phrase-grounding boxes alone did not establish laterality.
```

## exp_84c3c7c9330525fb140156f7

来源题 [chexbench_openi_0220](../../cases/openi/chexbench_openi_0220.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer that depends on left/right laterality, such as “left thoracic vertebrae scoliosis” vs “right thoracic vertebrae scoliosis,” and a side-specific tool has returned a short laterality answer like “Right.”

Verification action: Before emitting the letter, quote the actual observation that resolves the side—here the chest_xray_expert response “Right” to the direct question “is it left or right convexity?”—and confirm that the final rationale’s side, the selected option’s text side, and that observed side agree. Then map the supported text back to the displayed option and check the letter/text pair: B must be “right thoracic vertebrae scoliosis,” not the left option. If a verifier relies on an image marker, require an explicit marker-to-patient-side explanation, as in this case (“L” marker on viewer’s right, so viewer’s-left convexity is the patient’s right curve). Do not treat a bare tool call, a bare “Yes,” prevalence, or a lateral-view inference as laterality evidence. A false “clinical_correctness_verified” flag alone is not evidence against the finding; it only means the observation must be explicitly checked. In this case the observed side “Right,” the rationale “right side,” and option B’s text all agreed with the released reference B; the correct grade alone would not prove that this check was performed.
```

## exp_5917adcf33d453dc0aa841f1

来源题 [chexbench_openi_0221](../../cases/openi/chexbench_openi_0221.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by left versus right indwelling catheter, especially on a lateral view and when tool outputs conflict (for example, one model says “right,” another says or implies “left,” and some outputs do not state laterality).

Verification action: Require at least one observed tool result that explicitly states the side of the catheter itself, such as “left-sided catheter” or “right-sided catheter.” Do not treat catheter presence alone, tip location in the SVC/right atrium, screen position, or an “L” projection marker as proof of the catheter’s side; the “L” marker confirms projection/labeling, not insertion laterality. Reconcile all explicit same-object side statements, check that a supported side was not dropped or reversed during finalization, then map the supported side’s text back to the displayed option and confirm the terminal letter and text agree. In this case, the first chest_xray_expert call and roi_crop did not establish side, llava_med_qa said right, medvlm_r1 was garbled, and a focused chest_xray_expert call explicitly returned “Left”; the verifier’s “L marker” comment should not by itself be counted as catheter-side evidence. The defensible support was the explicit “Left” catheter statement, and A “left indwelling catheter” matched the option map and reference. The correct grade alone is not the proof; the evidence and letter-text check are.
```

## exp_b43aa5e9d4fb657540de95f8

来源题 [chexbench_openi_0223](../../cases/openi/chexbench_openi_0223.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that must choose between right base and left base pulmonary atelectasis on a lateral view, and the tool responses are mixed — some bare "No" replies to a single combined "right or left base?" query, some explicit one-sided reads, some garbled or hedged output, plus a verifier caution that laterality cannot be confirmed on a single lateral image.

Verification action: Before emitting the letter, enumerate the recorded observations and tag each one as (a) a statement naming an exact side plus exact finding, e.g. "right base atelectasis" or "left base pulmonary atelectasis"; (b) a bare "No" or blanket denial returned to a disjunctive "right or left?" query; (c) garbled or unusable output; or (d) a caution that names no side. Treat only (a) as laterality evidence. Do not treat (b) as a denial of both sides or as support for either side — a "No" to "A or B?" is non-discriminative; do not treat (c) as anything; and do not let (d) select a side, because a verifier that says laterality is "not confirmable without frontal imaging or report" has ruled nothing in for either side. In this case chest_xray_expert and llava_med_qa returned bare "No," medvlm_r1 returned unreadable text, verify returned PARTIALLY_CORRECT/CAUTION with no side, and only medgemma and llava_rad returned an explicit side-and-finding — both "right base atelectasis." Then map that surviving exact phrase to the displayed option map and confirm the chosen letter's displayed text matches it (here A = "right base pulmonary atelectasis," matching the reference), and phrase the rationale at the evidence's real strength: two explicit reads, the rest non-discriminative, laterality not independently confirmed. Finally, re-read the rationale against the observations so it does not assert a side, a mismatch, or a "majority" that no recorded tool result supports — and remember that a correct grade here does not validate the procedure, since three of six tool outputs argued the other way or said nothing usable.
```

## exp_8c6ae50f01a7e03efd1d422e

来源题 [chexbench_openi_0224](../../cases/openi/chexbench_openi_0224.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes left versus right base pulmonary atelectasis, especially after phrase-grounding queries for both sides each return a plausible lower-lung box and the other model outputs are negative, non-specific, or garbled.

Verification action: Before emitting the option, require a recorded observation that explicitly names the exact side and finding, such as “left base pulmonary atelectasis.” Treat a phrase-grounding box as localization of the queried phrase only, not as proof that the finding is present; if both left- and right-side queries return plausible boxes, the grounding result is non-discriminative and must not be described as “aligning” with the chosen side. If an exact side-specific read exists, use that text; if none exists, do not claim laterality is confirmed. Then map the supported side-and-finding text to the displayed option map and verify that the selected letter’s displayed text matches it and the reference.

In this case, MedGemma’s explicit “left base pulmonary atelectasis” statement supported option A, and option A’s text was “left base pulmonary atelectasis,” matching the reference A, so there was no option-mapping error. The rationale was still evidentially overstated: the left-base phrase-grounding box did not corroborate laterality because the right-base phrase also produced a plausible lower-lung box, and the grounded report did not name atelectasis. The correct grade did not validate the rationale’s claim of phrase-grounding alignment.
```

## exp_7f2afb10bb70fe50c8ee73db

来源题 [chexbench_openi_0225](../../cases/openi/chexbench_openi_0225.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by left versus right indwelling catheter, especially when the image is lateral or `maira2_grounded_report` returns “not applicable.”

Verification action: Require an explicit same-image, same-object laterality statement that is valid for the view, such as a frontal/report-confirmed “right-sided catheter” or “left-sided catheter.” Do not treat model consensus (“right side” from two VLMs), mere catheter presence, tip location, or an “L” marker as reliable laterality confirmation when the verifier says a lateral projection cannot resolve right versus left. If the only support is VLM side output on a lateral view, record laterality as unverified/label-derived rather than image-confirmed. Then map the supported side text back to the displayed option and confirm the terminal letter and text agree.

In the supplied case, the terminal answer “A. right indwelling catheter” matched option A’s letter and text, so there was no option-mapping error. But the evidence was weaker than the final rationale implied: `chest_xray_expert` and `llava_med_qa` both said “right,” while `maira2_grounded_report` was not applicable and `verify` cautioned that laterality was indeterminate on this lateral view and might reflect the dataset/report label. The correct reference grade alone does not prove that consensus on a lateral image is a valid laterality procedure.
```

## exp_66df6e7f66048010a873998a

来源题 [chexbench_openi_0227](../../cases/openi/chexbench_openi_0227.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer where the options differ only by laterality—e.g., “right thoracic vertebrae scoliosis” versus “left thoracic vertebrae scoliosis”—and a side-specific tool or verifier has been used.

Verification action: Before emitting the letter, locate the actual returned observation for the same finding and side attribute, not just the tool call or the verifier’s “CORRECT.” Require explicit text such as “Left-sided” and quote it. Then map that supported side and finding text to the displayed options and confirm the chosen letter and text agree. If the observation explicitly says “Left-sided,” select B only when B’s text is “left thoracic vertebrae scoliosis.” If no observation explicitly names the side, or if the rationale names one side while the selected option text names the other, do not finalize—mark laterality unsupported or correct the option mapping. In this case, “Left-sided” matched option B “left thoracic vertebrae scoliosis” and the released reference B, so the conclusion and the letter/text mapping were correct, not an option-mapping error.
```

## exp_f56a24bc475b0d0999458e6e

来源题 [chexbench_openi_0229](../../cases/openi/chexbench_openi_0229.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by left versus right indwelling catheter, and the rationale cites expert or grounded-report tool outputs for laterality.

Verification action: Require at least one observed same-image tool result that explicitly states the catheter side (for example, “Left,” “Left IJ catheter,” or “Right-sided catheter”); do not infer laterality from catheter presence or distal tip location alone. Reconcile all explicit side statements, then map the supported side’s text back to the displayed option and confirm the terminal letter and text agree. In this case, chest_xray_expert returned “Left” and maira2_grounded_report returned “Left ij catheter with tip in the svc,” so A “left indwelling catheter” was supported and correctly mapped; the evidence and letter-text checks pass.
```

## exp_8e84eecc8a97a86b128a19d3

来源题 [chexbench_openi_0244](../../cases/openi/chexbench_openi_0244.json) · 活跃

```text
Trigger: When a chest X-ray multiple-choice question asks left-vs-right laterality for a finding such as surgical instruments or clips, and the tool observation only confirms presence (“Yes”) or otherwise omits the side.

Verification action: Require an actual observed result that explicitly names the same finding and the side on this image (for example, “right lung surgical clips” or an equivalent explicit side statement). Do not infer laterality from anterior/posterior position on a lateral view, standard orientation, or typical surgical placement patterns. If the only observation is “Yes” or lacks laterality, retry with a direct side-specific question or another localization tool, but count only a returned observation—not a planned call or an unanswered call. If no explicit same-finding laterality observation is obtained, finalize as cannot determine rather than choosing an option. If an explicit side is observed, map that supported text back to the displayed option and confirm the letter and text agree.

In the supplied case, step 0 returned only “Yes,” with no laterality. Step 1 recognized that laterality was missing but did not obtain an observation from the second call. Step 2 still selected A “surgical instruments in the left lung,” inferring left from anterior mediastinal position despite the missing evidence. The letter and text for A matched, so this was not an option-mapping error; it was an unsupported-conclusion/evidence error. The reference was B “surgical instruments in the right lung.” The lesson is to preserve the missing-laterality caution at finalization and never finalize a side from absence of evidence or from an unobserved repair.
```

## exp_84c39f99ce0a19b2de5a4f40

来源题 [chexbench_openi_0242](../../cases/openi/chexbench_openi_0242.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks right versus left indwelling catheter, and the image-tool observations include an explicit side even though a verifier cautions that the view (e.g., lateral) limits reliable laterality assessment.

Verification action: Before choosing, inspect the actual tool outputs for this same image and catheter and require at least one explicit laterality statement, such as “Right,” “right side,” or “left-sided catheter.” Reconcile all explicit side statements; if they agree, use that side and map its text back to the displayed options, confirming that the terminal letter and text both match. Treat a verifier view-limitation warning as a caveat, not as an opposite-side finding, unless the verifier supplies explicit contrary side evidence. If no observed tool result explicitly names the catheter side, do not select A or B from presence alone, prevalence, or the caveat. In the supplied case, chest_xray_expert returned “Right” and llava_med_qa returned “right side,” supporting option A “right indwelling catheter,” which matched the reference; the verifier’s lateral-view caution did not contain a conflicting side observation and should not erase the supported side at finalization.
```

## exp_9807fda96c520148985e0beb

来源题 [chexbench_openi_0270](../../cases/openi/chexbench_openi_0270.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer that requires left/right laterality, such as “left humerus deformity” vs “right humerus deformity,” especially on a lateral view where earlier reasoning notes laterality is unreliable, and a side-specific expert-tool call returns no observation.

Verification action: Before emitting the letter, find and quote an actual returned observation for this image that explicitly states both the finding and the side. Do not use projection conventions (“standard radiographic conventions for left lateral views”), an intended tool call, or an empty observations list as evidence. If no such observation exists, retry the tool or use another available evidence path; if still no same-object, same-attribute laterality observation is obtained, report that the answer cannot be determined rather than choosing A or B. If an observation exists, map its supported text back to the displayed option and write the letter with the option text, confirming they agree. Also reconcile the final rationale with earlier caveats: a laterality conclusion must not silently reverse an earlier “laterality cannot be determined” without new observed evidence.

In this case, step 0 said the humeri were not well visualized and laterality was unreliable, then called `chest_xray_expert`, but the observations list is empty. Step 1 nevertheless answered A, “left humerus deformity,” using a convention-based inference. A correctly maps to the left-humerus option and matches the reference, so this is not an option-mapping error; it is an unsupported laterality/evidence failure. The correct grade alone does not prove the evidence check was performed. The transcript contains no executed retry or alternate-tool observation, so it supports the caution about this observed failure, not a verified repair.
```

## exp_5361d52e65d654a77b147d67

来源题 [chexbench_openi_0246](../../cases/openi/chexbench_openi_0246.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice question that asks left versus right indwelling catheter, and an earlier observed tool result explicitly states catheter laterality, especially if the final rationale begins to reverse or override that earlier side using visual-origin reasoning.

Verification action: Before emitting the terminal answer, explicitly list each observed catheter-side statement for this image, such as “chest_xray_expert: Left” and “maira2_grounded_report: Left picc line.” If those same-object laterality observations agree, map that supported side’s text back to the displayed options, confirm the terminal letter and text agree, and do not replace the supported side with a later speculative interpretation unless a new observed tool result explicitly supports the opposite side. If the observations conflict, obtain another same-object laterality observation or state that the answer cannot be determined; do not choose a side from raw image-origin reasoning alone.

In this case, chest_xray_expert returned “Left” and maira2_grounded_report returned “Left picc line with tip in the superior vena cava.” Step 1 even acknowledged the expert’s “Left” observation, but step 2 reversed to “right” and final B. Because B’s text was “right indwelling catheter,” this was not an option-mapping error; it was a wrong conclusion/finalization error that dropped the earlier supported “left” evidence. The reference was A, “left indwelling catheter.”
```

## exp_9841dbbd31bb4c124c91af78

来源题 [chexbench_openi_0248](../../cases/openi/chexbench_openi_0248.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks right versus left lower lobe pulmonary atelectasis, if the grounded report gives one explicit unilateral atelectasis line but also a bilateral basilar descriptor (e.g., “bibasal hypoventilation”), and the phrase-grounding queries for both candidate sides each return a plausible lower-zone box.

Verification action: Before emitting the choice, treat each phrase-grounding box only as localization of the phrase that was supplied, not as proof that the finding is present. If the right- and left-side queries both return plausible boxes in the corresponding lower lung zones (checking the frontal-view convention: viewer-left is patient-right), the grounding is symmetric and non-discriminative for laterality, so do not cite it in the rationale as confirming the chosen side. Treat a single unilateral atelectasis line as provisional when the same grounded report also describes bilateral basilar abnormality (e.g., “bibasal hypoventilation”); seek an independent side-specific observation or mark laterality unresolved rather than letting that one line dictate the answer. Then map the supported side-and-finding text back to the displayed option map and check that the selected letter’s text agrees with it. If the chosen letter’s text matches the option but conflicts with the reference, label it an evidence conflict or a wrong conclusion — not an option-mapping error — and do not invent a “letter mismatch” that the current option map does not contain.

In this case, the grounded report said “Bibasal hypoventilation. Subsegmental atelectasis in the right lower lobe.” The right phrase query returned a box on the viewer-left side and the left phrase query returned a box on the viewer-right side, so both were plausible localizations and neither established which side actually had atelectasis. The terminal rationale nevertheless used the report’s unilateral right-lower-lobe line and the non-discriminative phrase grounding to select A (“right lower lobe pulmonary atelectasis”), whereas the reference was B (“left lower lobe pulmonary atelectasis”). Option A’s text did match the selected letter, so the failure was over-trusting a unilateral report line accompanied by a bilateral basilar descriptor and treating phrase-grounding localization as confirmation. The reusable caution is: when bilateral basilar language and symmetric phrase grounding are present, one unilateral atelectasis line is weak evidence and must not be presented as definitive laterality proof.
```

## exp_10e91be1a74a4e4cfad653d3

来源题 [chexbench_openi_0257](../../cases/openi/chexbench_openi_0257.json) · 活跃

```text
Trigger: When a chest X-ray multiple-choice question asks “right indwelling catheter” versus “left indwelling catheter,” and a grounding/view-check tool reports the image is lateral or otherwise not applicable for a verified frontal CXR, do not treat VLM/expert statements of “right side” or “left side” alone as sufficient laterality evidence.

Verification action: Before finalizing, confirm the image view and require at least one applicable side-specific observation—such as an explicit report statement, side marker, or grounded frontal-CXR finding—that names the catheter side. Do not count repeated VLM calls on the same lateral image as independent confirmation. If no applicable side evidence is available, state that the side cannot be determined rather than choosing A or B. If side evidence is available, map the supported side text back to the displayed option and confirm the terminal letter and text agree. In this case, A’s letter and text matched “right indwelling catheter,” so this was not an option-mapping error; the failure was accepting VLM side claims from a lateral image when maira2_grounded_report said a verified frontal CXR was required, while the reference was B “left indwelling catheter.”
```

## exp_6cad1b1e42ba1954cf2b1e89

来源题 [chexbench_openi_0263](../../cases/openi/chexbench_openi_0263.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice question that asks left vs. right for a finding such as surgical instruments, and the tool response to an either/or side question is only “Yes” or otherwise does not explicitly state laterality; also treat an announced follow-up tool call with no returned observation as no evidence.

Verification action: Before choosing an option, require an observed same-image result that explicitly names both the finding and the side, such as “surgical instruments in the left lung” or “surgical instruments in the right lung.” A bare “Yes” confirms only that instruments are present; it does not support A or B. If laterality is missing, retry with a side-forcing question or use another evidence path such as maira2_grounded_report, xray_phrase_grounding, or ROI crop, and wait for the observation. Then map that explicit side text back to the displayed options and confirm the letter and text agree. If no explicit laterality observation is obtained, report that the side cannot be determined rather than guessing.

In this case, step 0’s chest_xray_expert returned only “Yes,” so it did not resolve left vs. right. The step 1 maira2_grounded_report call had no returned observation in the supplied trace, and the final answer A selected “left lung” without observed laterality support. The terminal A matched option A’s text, so this was not an option-mapping error; it was an unsupported-conclusion/evidence failure. The reference was B, “surgical instruments in the right lung.”
```

## exp_a9a340d00c9fdce5c82fb3d3

来源题 [chexbench_openi_0267](../../cases/openi/chexbench_openi_0267.json) · 活跃

```text
Trigger: When a chest X-ray left-vs-right multiple-choice item asks about a finding such as surgical instruments in the left vs right abdomen, and the positive evidence is only a generic “Yes” or a central/non-lateralized grounding box—especially when the ROI tool warns “patient side not inferred” and “Do not infer patient laterality from screen position”—do not use screen-right/screen-left, the “L” marker, or a verifier’s CORRECT verdict as the laterality evidence.

Verification action: Before finalizing, scan the actual tool observations for a statement that explicitly names patient laterality for the same finding, e.g. “surgical instruments in the right upper quadrant/right abdomen” or “left abdomen.” Treat that explicit patient-side statement as load-bearing. If it says right, map the supported text to the displayed option and choose B; if left, choose A; verify the letter and text agree. If no observation names the side in patient terms, do not emit a supported A/B laterality choice—state that laterality is not established, or mark any forced pick as an unsupported guess. A bounding box, a visual impression from a crop, and a verifier “CORRECT” are not substitutes for an observed explicit side statement.

In this case, xray_phrase_grounding gave only a central vertical bounding box, roi_crop explicitly disclaimed laterality inference, and chest_xray_expert/llava_med_qa/maira2_grounded_report did not provide an observed right-side statement. The terminal A matched its option text, so this was not an option-mapping error; it was an unsupported laterality conclusion. The reference was B “surgical instruments in the right abdomen,” and the verifier’s CORRECT rating for A did not supply the missing patient-side observation.
```

## exp_e0b2207d35bf574d52247604

来源题 [chexbench_openi_0269](../../cases/openi/chexbench_openi_0269.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks right- versus left-sided lower-lobe pulmonary atelectasis, and the observations are: an either/or expert query answered only “Yes”; a grounded report marked not applicable because the image is lateral-only; and one VQA reply naming a side with “opacity or volume loss” but not explicitly naming atelectasis.

Verification action: Before emitting the choice, inspect each raw observation for the exact side-and-finding pair. Treat a bare “Yes” to an either/or query as non-discriminative for laterality. Treat a not-applicable grounded report as supplying no side or finding evidence. Treat a VQA side statement such as “right lower lobe opacity or volume loss” as side-level support at best, not as explicit confirmation of “right lower lobe pulmonary atelectasis,” unless it actually names the exact finding. If no observation explicitly states the selected side plus atelectasis, do not describe it as explicitly identified; note the residual evidence gap. Then map the best-supported side text back to the displayed option map and check that the selected letter’s displayed text agrees. In this case, the terminal A text “right lower lobe pulmonary atelectasis” matched option A, but the released reference was B “left lower lobe pulmonary atelectasis”; this was not an option-mapping error but an overtrust of a single side-specific VQA observation as definitive laterality/atelectasis evidence while the other tool results were non-discriminative or unavailable.
```

## exp_aa00fa3fbf4f36a419f20d2d

来源题 [chexbench_openi_0243](../../cases/openi/chexbench_openi_0243.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer (such as right vs. left pleural effusion) after the direct VQA tool returns only “Left” or “Right” and the grounded report lists a same-side density “in relation to pleural effusion” plus other possible causes, especially when the chosen option adds a severity qualifier like “large.”

Verification action: Before emitting the choice, quote the exact VQA question and answer to confirm it actually covers both pleural effusion and side, and separately quote the grounded report’s exact wording. Do not upgrade “increased left basal density in relation to pleural effusion” into “extensive basal opacification,” and do not treat concurrent atelectasis/consolidation or absent right-sided findings as independent confirmation that the effusion is large unless the report explicitly says so. Then map the supported answer text back to the displayed option map and write the letter together with its full text. In this case, “B. large left pleural effusion” matched option B and the reference B, so there was no option-mapping error; the lesson is that the rationale should not overstate the grounded report’s support for “large.”
```

## exp_8418558cdc4f267c7d41bbf1

来源题 [chexbench_openi_0245](../../cases/openi/chexbench_openi_0245.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes right versus left base pulmonary atelectasis, especially after several imaging tools return bare “No,” garbled text, or general negative reports, and at least one tool gives a side-specific read.

Verification action: Before emitting the choice, inspect the recorded observations for an exact side-and-finding phrase, such as “right base pulmonary atelectasis.” Treat a bare “No” to a “right or left?” question, a garbled response, and general statements like “no consolidation/effusion” as non-discriminative for laterality; do not use them as evidence for either side. If an exact side-specific observation exists, use that exact text as the supported answer text, note any conflicting non-specific outputs and any verifier caution about the limits of a single lateral view, then map the text back to the displayed option map and confirm that the selected letter’s displayed text matches it exactly. If no explicit side-specific observation exists, do not infer a side from silence, denial, planned calls, or the final rationale; mark laterality unsupported or seek an explicit read/report.

In this case, the terminal answer was correct and the option mapping was correct: “A. right base pulmonary atelectasis” matched option A and the reference. The reusable lesson is evidentiary, not a mapping correction: MedGemma’s observation explicitly named “right base pulmonary atelectasis,” while the other outputs were non-specific or non-discriminative. The verifier’s caution about a single lateral view should be recorded as uncertainty, but it did not provide contrary side-specific evidence. A correct final grade alone does not prove the procedure; the observable check is the exact side-and-finding phrase in the observations and its exact agreement with the displayed option letter and text.
```

## exp_e8c650561c1919a48132b7ab

来源题 [chexbench_openi_0247](../../cases/openi/chexbench_openi_0247.json) · 活跃

```text
Experience: On this case the image was a lateral-only chest radiograph. The direct VQA tools split (chest_xray_expert and llava_med_qa said “right,” llava_rad said “small left pleural effusion,” and medvlm_r1 returned garbled text that should not count as a vote). Both the verifier and the reflect step explicitly said left-vs-right laterality cannot be reliably assigned from a single lateral view because the two sides are superimposed, and the grounded report was not applicable. The final answer nevertheless selected “B. small right pleural effusion” on the basis of “two independent VQA models” agreeing — i.e., majority consensus, not direct image evidence — while citing the verifier only as a caveat. The terminal letter and text did match the option map (B = small right pleural effusion) and matched the reference, but the grade being correct does not show the reasoning was sound: the decisive step treated model agreement as proof of laterality on a view where laterality is inherently indeterminate, and it discarded the conflicting llava_rad finding instead of acknowledging it.

Lesson: Multi-model consensus is not evidence, and it is especially weak when the tools are being asked for an attribute (laterality) that the image type cannot support. When the verifier or reflection tool has already flagged that an attribute is indeterminate, finalizing on a vote count — even one that happens to hit the reference — is an unverified shortcut. Also, an observation that is garbled or non-committal must not be counted toward a consensus.

Trigger: When finalizing a left-vs-right (laterality) multiple-choice answer for a chest radiograph that is lateral-only, or when the VQA tools disagree on side and the verifier/reflect tool has stated that laterality is indeterminate on the available view.

Verification action: Before emitting the option, (1) quote the verifier/reflection’s exact laterality statement and each tool’s side claim, and separate direct image evidence from mere model agreement; (2) exclude garbled or non-committal outputs from any consensus count; (3) if laterality cannot be established from the available image, do not present vote-counting as if it were evidence — record the finding as “pleural effusion, laterality indeterminate on lateral view” (or explicitly flag the forced choice as a guess) and acknowledge the conflicting side-specific report; (4) then map the chosen finding text back to the displayed option map, confirming the letter and its text agree (e.g., B = “small right pleural effusion,” A = “small left pleural effusion”). A correct final grade does not prove this check was performed.
```

## exp_25c5001d12c29f708fda7e71

来源题 [chexbench_openi_0249](../../cases/openi/chexbench_openi_0249.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer whose options differ only by right versus left for the same finding—especially “elevated left diaphragm” versus “elevated right diaphragm”—and a direct chest X-ray expert/VQA observation has returned a side.

Verification action: Before emitting the answer, extract the supported side from the direct observation and confirm that the observation addressed the same structure and attribute as the question, e.g., right/left hemidiaphragm elevation. Re-read the full displayed option map, write the exact option letter and full option text, and check that the supported side maps to that letter-text pair rather than to the opposite-laterality option. Compare the letter and text with the released reference when available. Audit any cited auxiliary evidence: call it confirmation only if it explicitly names the same structure and finding; a phrase-grounding call that merely localizes a phrase you supplied, or a report that never mentions the diaphragm, is not independent confirmation. If the letter-text pair matches the supported side but the rationale overclaims auxiliary evidence, keep the answer and correct the rationale; if the pair contradicts the supported side, correct the mapping; if evidence conflicts, state only what the direct tool supports or flag uncertainty. In the supplied case, the expert answered “Right,” option B was “elevated right diaphragm,” and the reference was B, so the final answer was mapped correctly. The reusable lesson is to explicitly verify the side, the same object and attribute, the exact letter-text pair, and the evidence attribution—not to rely on a correct grade alone.
```

## exp_e9b28d39850b618e73d1e0dd

来源题 [chexbench_openi_0251](../../cases/openi/chexbench_openi_0251.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by laterality of a thoracic indwelling catheter, such as right-sided versus left-sided, especially after a tool returns only presence (“Yes”) or otherwise omits the side.

Verification action: Require at least one completed observation from this image that explicitly states the catheter’s side for the same object and attribute, e.g. “right-sided thoracic indwelling catheter” or “left-sided thoracic indwelling catheter.” Do not treat “Yes,” mere catheter presence, tip location, prevalence, or a prior case’s default as laterality evidence. If the first tool lacks laterality, retry or query another available tool and read the returned observation. When a side is explicitly supported, map that side’s text back to the displayed option and confirm the terminal letter and text agree; also check that no earlier supported side statement was reversed or dropped during finalization. If no same-image laterality statement is observed, do not select A or B by guessing; continue evidence gathering or report that the answer cannot be determined.

In this completed case, chest_xray_expert returned only “Yes,” which was insufficient for laterality. llava_med_qa then explicitly returned “The lateral chest X-ray shows a right-sided thoracic indwelling catheter.” The terminal answer A “right-sided thoracic indwelling catheter” preserved that supported conclusion and matched the displayed option and reference. This is an evidence-supported mapping, not merely a grade-correct guess.
```

## exp_1f6854e2236bbfaf38384939

来源题 [chexbench_openi_0252](../../cases/openi/chexbench_openi_0252.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice question whose options differ only by left versus right indwelling catheter, and the same-image tool outputs conflict on laterality or include no-catheter/noninformative results, especially when the image is lateral-only or verify warns that laterality cannot be reliably established.

Verification action: Before selecting A/B, enumerate every same-image laterality observation for the catheter and reconcile the conflicts rather than counting isolated “left” mentions. Require at least one explicit side statement that is not internally contradicted—for example, do not treat “likely left internal jugular vein” as independent left confirmation when the same report also says “does not show any indwelling catheter”—and do not override a verifier caution that the lateral view cannot establish side. If no consistent supported side remains, answer that the side cannot be determined. If a side is supported, map that side’s text back to the displayed option and confirm the terminal letter and text agree.

Case lesson: The terminal A “left indwelling catheter” matched option A’s text and the reference answer, so this was not an option-mapping error. But the rationale cited chest_xray_expert’s “Left side” and llava_rad’s “left internal jugular vein” while omitting llava_med_qa’s “right side,” medgemma’s “no catheter,” medvlm_r1’s noninformative answer, and verify’s warning that a lateral image cannot reliably establish laterality. That is a conflict-reconciliation/cherry-picking failure; a correct grade alone does not prove the procedure was sound.
```

## exp_e593314c6b065b9f724595f7

来源题 [chexbench_openi_0253](../../cases/openi/chexbench_openi_0253.json) · 活跃

```text
Trigger: When a chest X-ray multiple-choice item asks left- versus right-sided basilar atelectasis and phrase-grounding queries for both “right base pulmonary atelectasis” and “left base pulmonary atelectasis” each return a plausible lower-lung box, making the boxes non-discriminative for presence or laterality.

Verification action: Before finalizing, treat each bilateral phrase-grounding box only as localization of the queried phrase, not as evidence that the finding is present. Require an explicit recorded read or grounded report for the same image that names a side and includes atelectasis, such as “Left basilar infiltrate versus atelectasis.” If no side-specific statement exists, do not infer laterality from a box; obtain another read or leave the side unsupported. When a side-specific statement exists, map its side-and-finding text to the displayed options and confirm the chosen letter’s displayed text agrees. In this case, the grounded report’s left-sided finding supported option B, “left base pulmonary atelectasis”; the right-side phrase-grounding box did not establish right atelectasis, and the absence of a reported right-sided finding was not an independent denial.
```

## exp_47355dfdea69e2ac7a5b705b

来源题 [chexbench_openi_0254](../../cases/openi/chexbench_openi_0254.json) · 活跃

```text
Trigger: When finalizing a laterality-specific chest X-ray multiple-choice answer for small right vs left pleural effusion, after the direct VQA tool answers only “Left”/“Right,” the grounded report says “Lung fields are clear” or otherwise contradicts pleural effusion, and phrase grounding returns boxes for both candidate phrases.

Verification action: Before emitting the option, quote the exact VQA question and answer and confirm that the answer asserts both pleural effusion and side, not merely “Left.” Explicitly record the grounded report’s conflicting wording as non-confirming evidence. Treat xray_phrase_grounding only as localization of the supplied phrase—not as proof of presence—especially when it localizes both “small left pleural effusion” and “small right pleural effusion.” Treat verify only as a final correctness/safety check, not as independent image evidence that resolves the conflict. Then map the supported text back to the displayed choices and emit the letter with its text only if they agree. In this case the terminal “B. small left pleural effusion” matched option B and the reference B, but the rationale should not imply that the verifier or bilateral phrase grounding confirmed the finding.
```

## exp_7159c36894bfde541f7697c7

来源题 [chexbench_openi_0255](../../cases/openi/chexbench_openi_0255.json) · 活跃

```text
Trigger: When you are about to finalize a chest X-ray multiple-choice answer whose options differ only by laterality of the same finding (e.g., "elevated right diaphragm" vs. "elevated left diaphragm"), and a direct imaging tool has just returned a side — especially when a retrieved prior case assigned the same finding text to a different option letter than the one now displayed.

Verification action: Before emitting the final answer, do three checks on the actual prompt text, not on memory of similar cases. (1) Confirm the direct tool observation answered the same object and attribute as the question: here the tool was asked "Is the right or left hemidiaphragm elevated in this chest X-ray?" and returned "Right," which is the same structure (hemidiaphragm) and attribute (elevation), so it is usable load-bearing evidence. (2) Re-read the full option map as displayed in this instance and write the exact letter and full option text that carry the supported side — in this case A = "elevated right diaphragm" — and confirm the letter and text agree. Do not copy a letter from a retrieved historical case: the retrieved cards described a case where the right-sided option was B, and here it is A, so carrying over that letter would have produced "B. elevated right diaphragm," a wrong option. (3) Compare the written letter-text pair with the released reference when it is available (reference A, "elevated right diaphragm") and make sure the rationale cites only tools that explicitly named the same structure and finding; if the mapping is right but the rationale overclaims an auxiliary tool, keep the answer and fix the rationale. A correct grade alone does not validate this step — the check is the explicit letter-text-side agreement, not the score.
```

## exp_48e6d6f0a405e745ed628d53

来源题 [chexbench_openi_0256](../../cases/openi/chexbench_openi_0256.json) · 活跃

```text
Trigger: In a chest X-ray multiple-choice question whose options differ only by indwelling-catheter laterality (“right indwelling catheter” vs “left indwelling catheter”), before finalizing the answer.

Verification action: Require at least one observed tool result for this same image that explicitly states the catheter’s side, such as “Left” or “Left chest catheter terminates…”. Treat mere catheter presence, tip location alone, population prevalence, or a prior-case default as insufficient laterality evidence. Reconcile any explicit side statements across tools; if they conflict and cannot be resolved, report that the answer cannot be determined. Then map the supported side’s text back to the displayed option and confirm the terminal letter and text agree. In this case, chest_xray_expert returned “Left” and maira2_grounded_report reported “Left chest catheter…”, so option B “left indwelling catheter” was supported by observed evidence and the letter/text mapping was correct.
```

## exp_252233972c93c6229edcb589

来源题 [chexbench_openi_0258](../../cases/openi/chexbench_openi_0258.json) · 活跃

```text
Trigger: When finalizing a side-specific chest X-ray multiple-choice answer (for example, left vs. right clavicle deformity), especially when one VQA tool names a side, another reports “no deformity” or “no significant findings,” and grounding/ROI tools give only a box, crop, or orientation cue rather than an explicit side-specific finding.

Verification action: Before emitting the option, map the supported answer text back to the displayed choice and confirm the letter and text agree. Then require and quote a same-scope observation that explicitly establishes both the finding and the side on a view or report that can establish laterality. Record conflicting evidence and any tool limitation such as “Do not infer patient laterality from screen position.” Do not treat a bounding box, zoom crop, or “L” marker alone as independent proof of laterality unless the orientation evidence is explicitly observed and applicable. If no same-scope observation establishes both presence and side, mark the side-specific option unsupported rather than choosing it.

In this case, the terminal answer “B. right clavicle deformity” matched option B and the released reference B, so it was not an option-mapping error. But the final reason converted a grounding box/crop and an L-marker inference into laterality while conflicting negative/nonlocalizing evidence was present: llava_med_qa said no deformity, maira2_grounded_report said no significant findings, and roi_crop warned not to infer patient laterality from screen position. The correct grade alone does not prove the evidence handling was sound; the reusable lesson is to surface the same-scope side evidence and conflicts before finalizing.
```

## exp_b01d1f5b7b1a972442e45784

来源题 [chexbench_openi_0273](../../cases/openi/chexbench_openi_0273.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer that turns on right-versus-left laterality (e.g., "right lumbar vertebrae scoliosis" vs "left lumbar vertebrae scoliosis"), and the only supporting observation is one expert tool's bare one-word reply ("Right" or "Left"), while the final rationale claims a verifier or second check "confirmed" the answer.

Verification action: Before writing the letter, do three observable checks. First, inspect the raw tool observation and require it to name both the finding and the side (e.g., "lumbar scoliosis with right convexity"); a bare "Right" does not establish that the side belongs to the lumbar spine rather than some other structure. Second, inspect the verifier's observation: if it only says correctness/safety "CORRECT" for the proposed answer and does not independently describe the image or name the finding and side, do not present it as confirmation — it is a self-referential check on the proposal, not independent laterality evidence. Third, map the supported side back to the displayed option map and confirm the exact letter and full option text agree before emitting.

In this case the tool's observation "Right" matched the chosen option "A. right lumbar vertebrae scoliosis," so there was no letter/text mapping error; the mapping was fine. The failure was evidential: the terminal rationale claimed "the verifier confirmed correctness for right lumbar scoliosis," but the verifier result was only "Correctness: CORRECT / Safety: SAFE / Issues: None" and contained no independent image finding or side. The released reference was B, "left lumbar vertebrae scoliosis," which conflicts with the single tool's "Right." The lesson is not to treat a verifier pass or a one-word tool token as an independently validated laterality conclusion; if the only support is that combination, mark laterality as weakly supported, seek an independent observation that names the finding and side, and avoid claiming the verifier confirmed it. A correct grade alone would not prove this evidence check was performed.
```

## exp_5066f6a12aaed43be6068dc1

来源题 [chexbench_openi_0272](../../cases/openi/chexbench_openi_0272.json) · 活跃

```text
Trigger: When a chest X-ray multiple-choice question has options that differ only by laterality of a finding, such as surgical instruments/clips in the right vs left abdomen, and an initial expert call returns only “Yes” or a nonlocalizing/negative report.

Verification action: Before finalizing, require a completed image-specific observation that explicitly names the same finding and side—for example, “Surgical clips in the right upper quadrant.” Do not treat “Yes,” “No significant findings,” standard orientation, a box coordinate without an explicit side, or a planned/unreturned call as sufficient laterality evidence. Reconcile explicit side observations; if same-specificity observations conflict, or no same-finding side is observed, finalize as cannot determine. If an explicit side is observed, map that side to the displayed option text and confirm the terminal letter and text agree.

In the supplied case, chest_xray_expert returned only “Yes” and maira2_grounded_report returned “No significant findings”; neither supplied the needed laterality. xray_phrase_grounding then returned “Surgical clips in the right upper quadrant” with a bounding box, an explicit same-finding right-side observation. The terminal choice A “surgical instruments in the right abdomen” matches that evidence and the displayed option. The reusable lesson is to require both evidence-to-side support and side-to-option letter/text mapping; a correct letter alone would not prove the evidence was adequate.
```

## exp_f8b7285e89f432520322f413

来源题 [chexbench_openi_0296](../../cases/openi/chexbench_openi_0296.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that chooses between same-side upper versus lower lobe pulmonary atelectasis—e.g., “left upper lobe pulmonary atelectasis” vs. “left lower lobe pulmonary atelectasis”—and the rationale cites a prior same-image question/annotation rather than a current-image tool observation.

Verification action: Before emitting the choice, take the supported finding phrase (here, “left lower lobe pulmonary atelectasis”), locate it in the current option map, and confirm that the selected letter’s displayed text exactly matches both that phrase and the released reference. Then inspect the actual trajectory for a current-image observation naming the same side and lobe. If only prior-image recall is present, state that as context rather than as current-image confirmation. In this completed case, option B’s displayed text matched the terminal answer and reference, so there was no option-mapping error; the caution is that no current-image tool observation was recorded, so the rationale should not imply direct current-image confirmation.
```

## exp_3e6a586fcc70b0fc484293b6

来源题 [chexbench_openi_0275](../../cases/openi/chexbench_openi_0275.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer where the options differ only by right versus left for the same finding (for example, "elevated left diaphragm" vs. "elevated right diaphragm"), and a direct expert/VQA observation has already supplied a side.

Verification action: Before emitting the terminal answer, extract the supported side from the direct observation, re-read the entire displayed option map, and write out explicitly the exact letter plus the full option text that carries that same side. Confirm the letter-text pair names the same side as the observation, not the opposite-laterality option. Do not let the prose rationale stand in for the letter check: if the rationale says "right" but the letter points at the "left" option, the letter is wrong and must be corrected. Finally, compare that letter-text pair with the released reference when one is available.

Why this matters, from the supplied case: the expert answered "Right" to "Is the right or left hemidiaphragm elevated in this chest X-ray?", and step 1 concluded "Final Answer: Right." Yet the terminal JSON emitted answer "A" with a reason repeating "The right hemidiaphragm is elevated." Option A was "elevated left diaphragm" and option B was "elevated right diaphragm," and the reference was B. The supported conclusion (right) was lost at finalization because the letter was never mapped back to the option text — the rationale was right, the letter was the opposite side. This is an option-mapping error, not an evidence error and not a wrong conclusion: the direct tool result addressed the same object and attribute (hemidiaphragm elevation side) and was internally consistent. The failure was purely failing to verify the letter-text pair. A correct-sounding rationale or a plausible-looking answer is not proof; here the grade was wrong even though the reasoning text named the correct side.
```

## exp_6854c8bf886a092f864815d3

来源题 [chexbench_openi_0277](../../cases/openi/chexbench_openi_0277.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by indwelling-catheter laterality (“right indwelling catheter” vs “left indwelling catheter”), especially when tool observations return only bare “Right” or “right side.”

Verification action: Before choosing, confirm the observed laterality is in patient orientation, not viewer/image orientation. Require an observed tool result for the same image and same catheter that explicitly states the patient’s side, such as “patient’s left indwelling catheter,” or re-query/use another evidence path until patient-side laterality is explicit. If converting from image orientation, apply the radiologic convention: image left = patient right. Then map the supported patient-side text back to the displayed option and confirm the terminal letter and text agree. If no unambiguous patient-side observation is obtained, report that the answer cannot be determined rather than choosing A or B.

In this case, the terminal answer selected A “right indwelling catheter”; chest_xray_expert returned “Right” and llava_med_qa returned “right side.” The terminal letter and text matched A, so this was not an option-mapping error. However, the released reference was B “left indwelling catheter,” showing that bare “right” was insufficient patient-side laterality evidence—possibly image-side laterality or otherwise unresolved. The lesson is to treat ambiguous bare laterality as an evidence-interpretation problem, not as a direct match to the patient-side option.
```

## exp_aa0968a6d856c41abccaacb7

来源题 [chexbench_openi_0278](../../cases/openi/chexbench_openi_0278.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks left versus right base pulmonary atelectasis, after phrase grounding returns plausible boxes for both sides, the grounded report says "bibasilar infiltrates or atelectasis," and the only side-specific signal is a bare forced-choice chest_xray_expert reply ("Left") followed by a verifier "CORRECT."

Verification action: Before emitting the choice, do not treat a bare one-word "Left"/"Right" from a forced-choice expert prompt as an explicit side-and-finding read, and do not treat the verifier's "CORRECT" as independent image evidence—it can bless a wrong answer. In this case the reference was B, right base pulmonary atelectasis, while the terminal answer was A, left base, so the verifier grade did not prove the procedure correct. Require a recorded observation that names the exact side and exact finding; when every recorded observation is bilateral or non-discriminative ("bibasilar," boxes on both sides), say laterality is unsupported rather than presenting a forced-choice pick as confirmed. Then map the supported side-and-finding text back to the displayed option map and check that the selected letter's text matches it. Here A's text was "left base pulmonary atelectasis" and B's was "right base pulmonary atelectasis," so the letter/text mapping was fine—there was no option-mapping error; the left/right conclusion itself was the error, and the terminal rationale overclaimed confirmation from a forced-choice guess plus a non-independent verifier.
```

## exp_1dc2c37006abb4b6dd5c1cbc

来源题 [chexbench_openi_0281](../../cases/openi/chexbench_openi_0281.json) · 活跃

```text
Trigger: In a chest X-ray multiple-choice question whose options differ only by indwelling-catheter laterality, when one tool returns only presence (“Yes”) and another tool returns a single explicit side (e.g., “right-sided”), especially on a lateral view, before finalizing the answer.

Verification action: Do not treat one model’s laterality statement, or a verifier’s “CORRECT,” as sufficient unless the verifier cites an observed same-image side statement rather than inferring laterality from catheter course. Require an explicit, same-object, same-image laterality observation from an independent evidence path or direct grounding; reconcile it against the presence-only expert result. Catheter presence, tip location, and a vertical course on a single lateral view are not enough to establish side. Then map the supported side’s text back to the displayed option and confirm that the terminal letter and text agree. If the only explicit side is a single unverified statement and no independent observation supports it, do not finalize a side.

In this case, the terminal B matched “right-sided thoracic indwelling catheter,” so this was not an option-mapping error. It was a wrong-conclusion/evidence problem: chest_xray_expert returned only “Yes,” llava_med_qa supplied the single “right-sided” statement, and the verifier called it correct while admitting laterality was inferred from the lateral course. The released reference was A, left-sided.
```

## exp_0e9fe12309cf79563310b88f

来源题 [chexbench_openi_0285](../../cases/openi/chexbench_openi_0285.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer whose only distinguishing feature is left-vs-right laterality (e.g., "right thoracic vertebrae scoliosis" vs "left thoracic vertebrae scoliosis"), and the sole side-specific evidence is a bare one-word tool output such as "Right" produced from a lateral view, while the verifier has explicitly cautioned that a lateral view cannot resolve laterality.

Verification action: Before emitting the letter, scan the transcript for an observation that names both the finding and the side on a view capable of resolving laterality (frontal PA/AP or the original radiology report). If the verifier says the side is unsupported and no such observation exists, do not pick a side-specific option on the strength of a single word or a lateral-view inference; treat the side as unresolved and reconcile the rationale with the verifier's caution instead of overriding it. Then map the supported finding-and-side text back to the displayed option and confirm that the letter and its text agree.

Lesson from this case: the chest_xray_expert returned only "Right," the verifier returned PARTIALLY_CORRECT/CAUTION stating that a lateral radiograph with an "L" marker cannot determine right-versus-left scoliotic convexity and recommending a frontal view or report, yet the terminal answer still committed to A ("right thoracic vertebrae scoliosis") by citing that single word. The option mapping itself was not the failure — A did correspond to "right" — the failure was treating an unsupported laterality claim as decisive; the released reference was B ("left thoracic vertebrae scoliosis"). Distinguish such an evidence error (an observed result that conflicts with the conclusion on the same attribute, side of convexity, and was nonetheless used) from a letter/text mapping error; a correct grade alone would not prove the reconciliation was performed.
```

## exp_60d1530e6228619bd297db8f

来源题 [chexbench_openi_0291](../../cases/openi/chexbench_openi_0291.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer where the options differ only by left versus right for the same finding—especially “elevated left diaphragm” versus “elevated right diaphragm”—and a direct question-specific expert/VQA call has returned a side, but the draft rationale cites a conflicting secondary VQA or a verifier.

Observable verification action: Before emitting the answer, extract the side from the direct call that addressed the same structure and attribute as the question (here, hemidiaphragm elevation). Re-read the full displayed option map, write the exact letter and full option text, and confirm the supported side maps to that letter-text pair. Then audit every cited auxiliary tool: a secondary VQA that says the opposite side is a conflicting observation, not replacement evidence, and a verifier that merely returns “CORRECT/SAFE” after being given the proposed answer is not independent evidence of the side. If the conflict remains unresolved on the same object and attribute, keep the option supported by the direct question-specific observation or state uncertainty; do not flip to the opposite laterality based only on a secondary model or generic verifier. In the supplied case, chest_xray_expert returned “Left,” which maps to A “elevated left diaphragm” and matches the reference. The final “B. elevated right diaphragm” was an evidence-selection error—favoring llava_med_qa’s “Right” and the verifier’s “CORRECT” over the direct expert output—not a correct verification.
```

## exp_6aeaa93834ff415bf3c5e82c

来源题 [chexbench_openi_0292](../../cases/openi/chexbench_openi_0292.json) · 活跃

```text
Trigger: When finalizing a chest X-ray laterality multiple-choice answer where the options differ only by left versus right for the same finding—especially “elevated left diaphragm” versus “elevated right diaphragm”—and the direct expert/VQA and a second VQA or verifier disagree.

Verification action: Before emitting the answer, extract the side from the direct question-specific observation, confirm that observation addressed the same structure and attribute, and explicitly map that side to the displayed option letter and full text. Audit every conflicting tool: treat it as resolving laterality only if it explicitly names the same structure and side from the image. Do not treat a verifier’s “CORRECT” label, or a lateral-view/projection-marker heuristic, as independent image evidence, and do not let it override the direct expert. In the supplied case, chest_xray_expert answered “Left” to the same right/left hemidiaphragm-elevation question, and option A was “elevated left diaphragm”; the terminal answer B was a wrong-side conclusion reached by favoring llava_med_qa’s “right” and the verifier’s endorsement over the direct expert. This was not an option-letter mapping error: B correctly maps to “elevated right diaphragm,” but the supported side was lost during finalization. If the direct observation remains unresolved after audit, flag uncertainty rather than selecting the opposite-laterality option solely because the verifier approved it.
```

## exp_4dcc09373b10ba85484bee30

来源题 [chexbench_openi_0293](../../cases/openi/chexbench_openi_0293.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that contrasts two lobe/side candidates (e.g., right lower lobe vs. right upper lobe pulmonary atelectasis), and each candidate's phrase-grounding query returns its own plausible box in the corresponding zone. This is especially important when the grounded report names no atelectasis at all ("lung fields are clear," "no focal infiltrates") or when the expert either/or query comes back "No," and when a verifier returns "CORRECT."

Verification action: Before emitting the letter, require one explicit side-and-finding statement from the grounded report or the expert answer (e.g., "right upper lobe atelectasis") that matches one option's exact text. Do not treat a phrase-grounding box as evidence the finding is present — it only localizes the phrase you supplied, and two candidate boxes (one upper, one lower) are non-discriminative for choosing between them. Do not treat the verifier's "CORRECT" as image evidence; it is a separate check that adds no new observation. Do not convert an expert "No" to an either/or query into support for either option. If the best available evidence is a clear-lung report plus non-discriminative boxes, say the evidence is insufficient rather than selecting a side from the boxes. Only after a side-and-finding statement exists, map its text to the displayed option map and confirm the selected letter's displayed text matches it.

In this case the expert answered "No," the grounded report described clear lung fields with no atelectasis, and both right-upper and right-lower grounding queries returned plausible boxes. The model chose A (right lower lobe) by citing the lower-zone box and the verifier's "CORRECT," even though a retrieved experience had warned that such paired boxes are non-discriminative. The released reference was B, so this was a wrong-conclusion error driven by using non-discriminative grounding plus a non-evidentiary verifier as confirmation, not an option-letter mapping error.
```

## exp_0f0ba85fa6ba5fb34f2964dd

来源题 [chexbench_openi_0295](../../cases/openi/chexbench_openi_0295.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that differs only by lobe/zone for the same side and finding—e.g., “left upper lobe pulmonary atelectasis” vs “left lower lobe pulmonary atelectasis”—especially when the rationale cites localizing signs such as upper-zone opacity, hilar elevation, or tracheal deviation but the trajectory has no executed image/tool observation that discriminates upper from lower.

Verification action: Before emitting the choice, inspect the raw observations for an explicit discriminative statement addressing the same object and attribute: side plus lobe/zone plus finding (e.g., “left lower lobe pulmonary atelectasis” or an equivalent observed localization). Historical experience-search cards and generic left-sided findings are not discriminative for upper-vs-lower. If no such observation exists, do not present an upper- or lower-lobe-specific rationale as if it were observed; state that the evidence is non-discriminative. If a supported side+lobe+finding text exists, map that text back to the displayed option map and verify that the selected letter’s displayed text exactly matches it. In this case, terminal answer “A. left upper lobe pulmonary atelectasis” matched option A’s letter and text, so this was not an option-mapping error; it was an unsupported/wrong conclusion relative to the released reference “B. left lower lobe pulmonary atelectasis.”
```

## exp_3024d8578826cb469d8df38a

来源题 [chexbench_openi_0274](../../cases/openi/chexbench_openi_0274.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes left vs right base pulmonary atelectasis on a single lateral view after VQA tools disagree (bare “No,” garbled output, an explicit side, or an other-view statement) and a verifier cautions that laterality is indeterminate from that lateral.

Verification action: Before emitting the option, require an exact same-scope side-and-finding observation from this lateral, such as “left base pulmonary atelectasis.” Do not treat a bare “No,” a garbled string, the “LT” projection marker, or a frontal-view statement as laterality evidence for this lateral. Check whether the verifier’s warning names the same image and attribute; if it says a single lateral cannot determine left vs right, do not dismiss it as merely a general principle—record the conflict. If an explicit side-specific lateral read exists, use it only at that strength and state the uncertainty; if not, treat the side as unsupported. Then map the supported side-and-finding text to the displayed option map and confirm the selected letter and text agree. In this case A = “left base pulmonary atelectasis,” matching the reference, so there was no option-mapping error; the caution is that the correct grade did not justify the terminal rationale’s dismissal of the verifier’s same-scope laterality warning.
```

## exp_8d4fcc6d823649eb5f9e0f6e

来源题 [chexbench_openi_0276](../../cases/openi/chexbench_openi_0276.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by catheter laterality (“right indwelling catheter” vs “left indwelling catheter”), and at least one tool has returned an explicit side statement for this image.

Verification action: Read the observation text for the exact side word, not just “catheter present.” Require at least one same-image tool result to name the side explicitly; if multiple tools speak, confirm they agree (in this case chest_xray_expert returned “Right side” and llava_med_qa returned “It is on the right side,” so the side was supported). Then map that supported side’s text back to the displayed option and check the letter and text agree — here “right indwelling catheter” → option A, matching the terminal “A. right indwelling catheter.”

Two cautions from this trajectory: (1) An incidental visual impression such as “image appears lateral and marker shows L” is not an observed tool laterality statement; use it only as a reason to cross-check, and if it conflicts with every observed tool side, report the conflict or seek another evidence path rather than silently flipping the letter. (2) If the tools had disagreed or returned only presence without a side, do not default to prevalence or a prior case — state the answer cannot be determined.
```

## exp_d097965228ed8a7e4a4b31ca

来源题 [chexbench_openi_0279](../../cases/openi/chexbench_openi_0279.json) · 活跃

```text
Trigger: Before finalizing a chest X-ray multiple-choice answer whose options differ only by indwelling-catheter laterality (“right indwelling catheter” vs “left indwelling catheter”), or when the question asks which finding is present and those are the only options.

Verification action: Require at least one observed tool result for this same image that explicitly states the catheter’s side, such as “Left side” or “right-sided catheter.” Do not accept mere catheter presence, tip location, prevalence, or a prior case’s default as laterality evidence. Reconcile any explicit side statements across tools; if they conflict and cannot be resolved, retry or report that the answer cannot be determined. Then map the supported side’s text back to the displayed option and check that the terminal letter and text agree.

Case application: The step 0 call to chest_xray_expert asked specifically whether an indwelling catheter was present and whether it was on the right or left. The observed result was “Left side” for the same image. Step 1 selected “B. left indwelling catheter”; the option map gives B as “left indwelling catheter,” and the released reference is B, “left indwelling catheter.” Thus this trajectory had a same-object, same-attribute laterality observation, used it in the terminal choice, and had correct letter/text mapping. The caution is that the correct outcome depended on the explicit “Left side” observation; a presence-only answer or absent side statement would not justify choosing B.
```

## exp_74a66e1f5953b39d70a042b7

来源题 [chexbench_openi_0280](../../cases/openi/chexbench_openi_0280.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by indwelling-catheter laterality (“left indwelling catheter” vs “right indwelling catheter”).

Verification action: Read the actual completed tool observations for this same image and require at least one explicit laterality statement, such as “Right side” or “right-sided catheter.” Treat mere catheter presence, tip location, a not_applicable view result, or an empty/failed tool call as insufficient laterality evidence; reconcile explicit side statements across tools rather than treating an unrelated not_applicable warning as a contradiction. Then map the supported side’s text back to the displayed option and confirm the terminal letter and text agree. In the supplied case, chest_xray_expert observed “Right side” and llava_med_qa observed “right side,” while maira2_grounded_report was only not_applicable for a lateral view, so option B “right indwelling catheter” was supported and matched the reference B. If no same-image observation explicitly states the side, report that the answer cannot be determined rather than guessing.
```

## exp_cb92085f4c6be5328b004feb

来源题 [chexbench_openi_0282](../../cases/openi/chexbench_openi_0282.json) · 活跃

```text
Trigger: In a chest X-ray multiple-choice question where the only options differ by indwelling-catheter laterality (“left indwelling catheter” vs “right indwelling catheter”), immediately before finalizing the answer.

Verification action: Require at least one completed, same-image tool observation that explicitly states the catheter’s side, such as “Left side” or “right-sided catheter.” Do not treat catheter presence alone, a “No significant findings” report, or a phrase-grounding call that merely echoes the candidate phrase as independent laterality proof; use phrase grounding only as supporting localization. Reconcile any explicit side statements, and if they conflict with no way to resolve them, report that the answer cannot be determined. Then map the supported side’s text back to the displayed option and confirm the terminal letter and text agree. In this case, chest_xray_expert returned “Left side,” xray_phrase_grounding localized a left indwelling catheter supportively, maira2’s no-finding report was not an explicit right-side statement, and the current option map had A = “left indwelling catheter,” matching the reference. Re-check the current option map each time; do not carry over a letter from another case with the same text.
```

## exp_3fce978c73ead9142a8b3f25

来源题 [chexbench_openi_0283](../../cases/openi/chexbench_openi_0283.json) · 活跃

```text
Trigger: When finalizing a multiple-choice chest X-ray answer whose two options differ only by right-vs-left laterality, such as “right thoracic vertebrae scoliosis” vs “left thoracic vertebrae scoliosis,” especially when a specialized CXR tool returns only a bare side label and a verifier cautions that the projection cannot establish laterality.

Verification action: Before emitting the letter, write out the side in the final rationale, the selected option text, and the displayed option letter, and confirm all three agree; also compare that text with the released reference if available. Then quote the exact returned observation that names the side for the same finding. In this case, the terminal answer “A. right thoracic vertebrae scoliosis” matched option A and the reference, and the chest_xray_expert observation returned “Right” to the direct side question, so this was not an option-mapping failure and the terminal choice did use the explicit tool observation. However, the verifier’s caution that a lateral film cannot reliably establish left-vs-right convexity remains an evidence limitation; the correct grade alone does not prove the laterality evidence was adequate. If no returned observation names the side, or if observations actually conflict on the side, mark laterality unsupported or indeterminate rather than choosing by heuristic. A general projection caution should not be treated as an opposite observation unless it supplies one.
```

## exp_f4a2d5e3b2e8afabf8e28c86

来源题 [chexbench_openi_0284](../../cases/openi/chexbench_openi_0284.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by indwelling-catheter laterality (“left indwelling catheter” vs “right indwelling catheter”), before selecting A or B.

Verification action: Require an observed tool result for this same image that explicitly states the catheter’s side, e.g. “Left side”; mere catheter presence or a prior-case default is insufficient. Then map that supported side text back to the displayed option map and confirm the terminal answer’s letter and text agree. In the supplied case, step 0’s chest_xray_expert observation explicitly said “Left side,” which supports option A “left indwelling catheter”; the terminal choice A matches that text and the reference, and no earlier supported conclusion was lost. If no same-image laterality statement is observed, or results conflict without resolution, do not finalize A or B; retry/use another evidence path or report that the answer cannot be determined.
```

## exp_9285aef66f463ad19b72e424

来源题 [chexbench_openi_0286](../../cases/openi/chexbench_openi_0286.json) · 活跃

```text
TRIGGER: Finalizing a chest X-ray multiple-choice answer when the options differ only in laterality of an indwelling catheter (e.g., "right indwelling catheter" vs "left indwelling catheter") and the tool outputs are a mixture of explicit side statements, presence-only reports, or bounding boxes.

VERIFICATION ACTION: Before emitting the letter, read each cited observation and classify it as (a) explicit side evidence for this same image ("Right," "Right indwelling catheter," "left-sided catheter terminates…"), (b) presence-only evidence ("Port-a-cath is in place," "Yes"), or (c) geometric evidence (box pixel coordinates). Accept only (a) as direct laterality support; treat (b) as insufficient and never cite it as side confirmation in the rationale even if the terminal prose says "multiple tools consistently identify…". Use (c) only as corroboration, and apply radiographic convention correctly when doing so: image-left corresponds to the patient's right, so a port-a-cath box at original pixels x≈120–232 on a 512-wide image sits on the patient's right, matching, not contradicting, an explicit "Right." Then map the supported side back to the displayed option map and confirm the terminal letter and text agree (here "right indwelling catheter" → option B, and B's text matches), so the answer is not an option-mapping error. If no observation in category (a) exists and coordinates are ambiguous or conflicting, state that the answer cannot be determined rather than defaulting to a side from prevalence or a prior case.

Why this case supports the rule: step 0 returned explicit "Right"; step 1 returned a report that named the port-a-cath but no side, with boxes on the patient's right (image-left); step 2 returned the explicit phrase "Right indwelling catheter." The final answer B matched the reference B, but the rationale's claim of three "consistent" side statements overstates the evidence—one of the three was presence-plus-coordinates only. The reusable lesson is to audit the cited evidence item by item against the question's exact object and attribute (catheter laterality in this image), and to verify letter/text mapping separately, rather than assuming that a correct final grade means every cited tool actually supplied the laterality.
```

## exp_0a5f11cd9255e7c90f4db886

来源题 [chexbench_openi_0305](../../cases/openi/chexbench_openi_0305.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes left upper versus left lower lobe pulmonary atelectasis, and one tool returns a bare candidate lobe while another returns “No” or a non-specific/conflicting response.

Verification action: Before emitting the option, require an explicit observation that names the exact lobe and side. Treat a bare candidate answer from one VQA model and a verifier’s restatement of that same candidate as one weak source, not independent confirmation; explicitly account for the conflicting “No” and do not convert generic retrocardiac or lower-zone opacity into a lobe-specific diagnosis without an exact lobe statement. Then map the exact supported lobe text back to the displayed option and check that letter and text agree. If the letter/text mapping is consistent but the reference names the other lobe, classify it as a wrong conclusion, not an option-mapping error. In this case, A matched “left lower lobe pulmonary atelectasis,” so there was no mapping error; the terminal lower-lobe conclusion conflicted with reference B “left upper lobe pulmonary atelectasis.” This failed trajectory supports a caution about relying on an unconfirmed candidate despite conflicting tool evidence; it does not verify a repair, because no additional exact-lobe confirmation was executed.
```

## exp_448e98e0388682c2c08caa04

来源题 [chexbench_openi_0302](../../cases/openi/chexbench_openi_0302.json) · 活跃

```text
TRIGGER
When a chest X-ray multiple-choice item asks which of two side/zone-specific findings is present (e.g., "right lower lobe pulmonary atelectasis" vs "right upper lobe pulmonary atelectasis") and the first tool is a VQA model asked a disjunctive "A or B" question that comes back with a bare "Yes" (or bare "No") and no side or lobe named.

VERIFICATION ACTION
Before committing the answer, do not score the bare "Yes" as evidence for either candidate — a yes/no reply to an either/or prompt is non-discriminative about laterality/zone. Require a second observation that explicitly names the anatomy: look for an explicit side-and-zone statement, such as a grounded report saying "Infiltrate in the right upper lobe" with a box in the right upper lung zone. Check that the named zone matches exactly one displayed option, then map that supported text back to the option map, confirming the selected letter's displayed text is the same side/zone and that it matches the reference. In the rationale, describe the evidence at its actual strength: the grounded report named right-upper-lobe pathology (infiltrate) and localized it to the right upper zone, which discriminates B from A because the options differ only by lobe — do not upgrade "infiltrate" into "confirmed atelectasis," and do not cite the bare "Yes" as the discriminator.

IN THIS CASE
Option B's text "right upper lobe pulmonary atelectasis" matched the released reference B, so there was no option-mapping error. The reusable caution is evidentiary: the chest_xray_expert answer "Yes" to "Is there right lower lobe ... or right upper lobe ...?" established nothing about which side; the decision actually rested on the maira2_grounded_report naming the right upper lobe with a right-upper-zone box. The conclusion was correct, but the bare affirmative was non-probative and the report's "infiltrate" label should be held at that level rather than treated as a direct atelectasis read.
```

## exp_867d42892ad81f365f559c40

来源题 [chexbench_openi_0309](../../cases/openi/chexbench_openi_0309.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by side/lobe, such as left upper lobe versus left lower lobe pulmonary atelectasis, especially when the draft rationale cites “prior same-image feedback” or a “grounded report” rather than a current tool observation.

Verification action: Before emitting the choice, search the current trace for an explicit current-image statement naming the exact side and lobe, such as “left lower lobe atelectasis” or “left lower lobe opacity/atelectasis.” Treat phrase-grounding boxes, generic prior feedback, or nonspecific “left lower lobe pathology” as corroboration/localization only unless they explicitly support the exact side-and-lobe pair needed by the options. Then map the supported answer text back to the displayed option map and verify that the selected letter’s displayed text exactly matches it. In this case, B’s displayed text “left lower lobe pulmonary atelectasis” matched both the terminal answer and the reference, so there was no option-mapping error; the caution is that the rationale cited prior feedback/grounded-report evidence that was not visible in the recorded observations, so the answer should be described at its actual evidence strength rather than as directly confirmed by current tools.
```

## exp_fe2bd7a5853a70865f75afc0

来源题 [chexbench_openi_0306](../../cases/openi/chexbench_openi_0306.json) · 活跃

```text
Trigger: When a chest X-ray multiple-choice question asks you to choose between two lobe/localization findings, and the only tool evidence is a bare “Yes” to an either/or query, or an either/or query that you composed with option-specific descriptors and the VQA reply simply echoes one option.

Verification action: Before finalizing, inspect the raw observations and classify the evidence. A “Yes” to “left upper lobe pulmonary atelectasis or left lower lobe pulmonary atelectasis” is non-discriminative and must not be counted as support for either side. If the follow-up prompt itself supplied the distinguishing features—for example “left upper lobe atelectasis with anterior opacity and elevated fissure, or left lower lobe atelectasis with posterior basal opacity”—and the reply merely restated one candidate, treat it as a leading-question echo, not independent confirmation. Require a neutral, separate query for each candidate, or an explicit grounded report/read naming the exact side, lobe, and finding, before treating the finding as supported. If no such independent evidence exists, do not write “expert VQA identified [finding]” as if it were confirmed; state that the evidence is non-discriminative. Then map the supported answer text back to the displayed option map and verify the selected letter’s text agrees. In this case, B matched “left lower lobe pulmonary atelectasis” and was selected, while the reference was A “left upper lobe pulmonary atelectasis”; this was a wrong conclusion driven by non-discriminative and leading VQA prompts, not an option-mapping error.
```

## exp_f04a41da4d1073e219edb6c5

来源题 [chexbench_openi_0312](../../cases/openi/chexbench_openi_0312.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that asks you to choose between location-specific atelectasis options, such as right upper lobe versus right lower lobe pulmonary atelectasis, and the terminal rationale describes a lung zone, opacity, volume loss, or fissure displacement without any recorded image observation or tool result that explicitly names the same lobe and finding.

Verification action: Before emitting the choice, inspect the raw observations/tool outputs for an explicit side-and-lobe statement of atelectasis, such as “right lower lobe atelectasis,” or a grounded report/read that discriminates upper versus lower lobe involvement. Treat phrase-grounding boxes or nonspecific opacity/volume-loss language as localization or corroboration only, not as proof of the named finding. If the evidence explicitly supports a lobe-and-finding text, map that supported text back to the displayed option map and check that the selected letter’s displayed text matches it. If no observation addresses the same lobe and finding, do not finalize a confident upper-versus-lower conclusion from the rationale alone; obtain or request the missing evidence. In this case, the terminal answer’s letter and text agreed as A “right upper lobe pulmonary atelectasis,” but the rationale was not supported by any observed finding, and the reference was B “right lower lobe pulmonary atelectasis.” The lesson is to catch an unsupported conclusion rather than a letter/text mapping error.
```

## exp_47a62f84d9635e949fd217f0

来源题 [chexbench_openi_0313](../../cases/openi/chexbench_openi_0313.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by side/lobe, especially after an either/or tool query returns only “Yes” or the rationale cites a prior annotation naming a specific finding.

Verification action: Extract the exact finding text the evidence or rationale actually names, map it back to the displayed option list, and confirm that the selected letter’s displayed text matches it. Do not treat a bare “Yes” to an either/or query as side/lobe evidence, and do not claim the tool confirmed a side it did not state. In this case, the rationale named “left upper lobe pulmonary atelectasis,” which is option A, but the terminal answer emitted B (“left lower lobe pulmonary atelectasis”); that is a letter/text mapping error. Before finalizing, verify the chosen letter’s text agrees with the supported finding and the displayed option map.
```

## exp_b5227ab210c96dae889ea12b

来源题 [chexbench_openi_0315](../../cases/openi/chexbench_openi_0315.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes “right lower lobe pulmonary atelectasis” from “right upper lobe pulmonary atelectasis,” especially after the rationale cites prior dataset feedback or an earlier step writes a letter with a finding phrase.

Verification action: Before emitting the final answer, read the entire displayed option map and match the exact supported finding phrase to the option that displays it. Here, “right lower lobe pulmonary atelectasis” is option A; option B is “right upper lobe pulmonary atelectasis.” Then confirm that the selected letter’s displayed text matches the rationale/reference. If any intermediate step says “B. right lower lobe pulmonary atelectasis,” stop and treat it as an internal letter-text mismatch, because B’s displayed text is upper lobe. Do not carry a remembered or prior-feedback letter forward; carry the finding text and remap it to the current options. In this case the rationale and reference both indicated right lower lobe atelectasis, but the terminal answer was B, so the failure was an option-mapping error, not a wrong finding-text conclusion.
```

## exp_e0454336d6177c156c1ab6f1

来源题 [chexbench_openi_0325](../../cases/openi/chexbench_openi_0325.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity—e.g., “severely hypoinflated lung” versus “mildly hypoinflated lung”—and the only tool observation is a bare forced-choice term such as “Mildly” in response to a query that listed both candidates.

Verification action: Before emitting the choice, map the exact observed term to the displayed option map and confirm the letter and text agree. If the observation says only “Mildly,” use that only as support for the option “mildly hypoinflated lung”; do not embellish the rationale with diaphragm position, retrosternal clear space, or other signs unless the tool observation itself states them. If the reference or another source says “severe,” treat the discrepancy as a tool-vs-reference evidence conflict, not an option-letter mapping error. Do not claim a corrected “severe” conclusion unless another completed same-image observation explicitly states “severely hypoinflated” or provides severity-discriminating evidence. In this case, the terminal answer B matched the sole observed tool term “Mildly” and the option text, so the failure is an unsupported/conflicting evidence conclusion, not a final letter/text mapping error.
```

## exp_b9c7fbf0a307bee84c3908e8

来源题 [chexbench_openi_0303](../../cases/openi/chexbench_openi_0303.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice question that distinguishes left upper from left lower lobe pulmonary atelectasis, if the chosen side is supported mainly by an xray_phrase_grounding box for that phrase while the side-specific VQA is non-discriminative (“Yes”) or the grounded report says “No significant findings,” before emitting the option.

Verification action: Inspect the raw observations for an explicit current-image statement naming both the exact side and exact finding, such as “left upper lobe pulmonary atelectasis”—not just a localization box, a non-specific “Yes,” or prior/reference feedback. If no such statement exists, treat phrase grounding only as localization of the queried phrase, note the conflict with the grounded report, and state the evidence at its actual strength rather than claiming confirmation. Then map the supported side-and-finding text to the displayed options and verify that the selected letter and text agree with each other and the reference; here A’s text “left upper lobe pulmonary atelectasis” matched reference A, so the defect was evidence overstatement, not an option-mapping error. A correct grade does not prove that a phrase-grounding box established presence.
```

## exp_659cb9085766a8804e0924aa

来源题 [chexbench_openi_0307](../../cases/openi/chexbench_openi_0307.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes right upper lobe versus right lower lobe pulmonary atelectasis after several VQA tools return conflicting, negative, or garbled outputs, and the final rationale says a verifier confirmed the proposed choice.

Verification action: Before emitting the answer, build a small evidence tally from the raw observations. Count only outputs that explicitly name the same side, lobe, and finding as one of the displayed options; treat “No,” nonspecific, or garbled responses as non-supporting rather than as votes for the opposite option. Use the verifier’s CORRECT label only as a consistency check, not as independent image evidence. Then map the supported side-and-finding text back to the current option map and confirm that the selected letter’s displayed text matches it and the released reference. In this case, option B’s text “right lower lobe pulmonary atelectasis” matched the reference, and the terminal choice was consistent with explicit RLL statements from LLaVA-Rad and MedGemma; LLaVA-Med’s RUL statement was a conflict, CheXagent’s “No” was non-supporting, and MedVLM-R1’s output was garbled. There was no option-mapping error, but the rationale should not imply that the verifier independently confirmed the imaging finding.
```

## exp_b6a6cfa803991774f86ac8b0

来源题 [chexbench_openi_0310](../../cases/openi/chexbench_openi_0310.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes two locations for the same finding—for example, right upper lobe pulmonary atelectasis versus right lower lobe pulmonary atelectasis—and the observed evidence is an expert reply of only “Yes” to an either/or query, a grounded report that is negative or does not name the finding, and a phrase-grounding box for the selected candidate.

Verification action: Before emitting the choice, do not treat the either/or “Yes” as side-specific evidence, and do not treat the phrase-grounding box as proof that the finding is present; it only localizes the phrase that was queried. Require an explicit recorded read naming the exact side and exact finding, such as “right lower lobe pulmonary atelectasis.” If only a phrase-grounding box plus prior reference feedback supports the answer, record the evidence as non-discriminative or unsupported rather than saying phrase grounding confirmed it. Then map the supported answer text to the displayed option map and check that the selected letter and text agree. In this case option B’s text “right lower lobe pulmonary atelectasis” matched the reference and the option map, so there was no option-mapping error; the flaw was evidentiary—the expert’s “Yes” and the negative grounded report did not establish right lower lobe atelectasis, and phrase grounding only localized the supplied phrase. A correct final letter does not validate that evidence.
```

## exp_de0eadb08215330839bc91d3

来源题 [chexbench_openi_0311](../../cases/openi/chexbench_openi_0311.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes two same-lung lobe/zone candidates after phrase-grounding queries for both candidates return plausible boxes, especially if an intermediate step correctly flags the grounding as non-discriminative and a verifier then returns “CORRECT.”

Verification action: Before emitting the choice, preserve the intermediate evidence-strength judgment in the final rationale. A phrase-grounding box only localizes the queried phrase; it does not prove that the finding is present, and two plausible candidate boxes are non-discriminative. Require an explicit report/read naming the exact side, lobe/zone, and finding before describing the evidence as confirmatory; if that is absent, state that the evidence is ambiguous rather than claiming “grounding localized the finding.” Do not use a verifier’s “CORRECT” grade as independent image evidence. Separately, map the supported answer text to the entire displayed option map and confirm the selected letter’s displayed text matches the supported text and the reference.

In this case, A “left lower lobe pulmonary atelectasis” matched the option map and reference A, so there was no option-mapping error. The caution is an evidence-overstatement error: the left-upper candidate also returned a plausible box, the grounded report did not explicitly name atelectasis, and the terminal reason claimed the phrase grounding had localized the finding. The correct grade alone does not show that this evidence procedure was sound.
```

## exp_bd33af85392d05444c75ba2a

来源题 [chexbench_openi_0314](../../cases/openi/chexbench_openi_0314.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes right lower lobe from right upper lobe pulmonary atelectasis after several VLM calls have returned mixed or non-discriminative evidence, especially when one call is a bare “Yes,” another is negative or uninformative, another is garbled, and another explicitly names a side and finding.

Verification action: Before emitting the option, find the raw observation that explicitly names both the side and the finding and matches one displayed choice; do not treat a bare “Yes” to an either/or query as side-specific evidence, and do not treat garbled text as support. If an explicit statement such as “There is right lower lobe atelectasis” is present, use that as the primary evidence, note any conflicting negative observation, and use the verifier only as a consistency and limitation check rather than as an independent naming of the finding. Then map the supported side-and-finding text back to the displayed option map and confirm that the selected letter and text agree. In this case llava_rad explicitly said “right lower lobe atelectasis,” option A was “right lower lobe pulmonary atelectasis,” and the reference was A, so there was no option-mapping error and the terminal conclusion was correct. The caution is that the final rationale leaned on “verifier confirms correctness” and clear upper fields while omitting the explicit llava_rad statement and the conflicting negative/garbled outputs; anchor the answer in the explicit side-and-finding observation and verify the letter-text match.
```

## exp_7258a5d1df452c95b7dfc3ed

来源题 [chexbench_openi_0316](../../cases/openi/chexbench_openi_0316.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that contrasts an upper-lobe option with a lower-lobe option for pulmonary atelectasis, and the expert reply to the either/or query is only a bare “Yes” while phrase grounding returns a plausible box for the selected candidate phrase.

Verification action: Before emitting the option, inspect the grounded report for an explicit side-and-finding statement. Do not treat the bare “Yes” or the phrase-grounding box as proof that atelectasis is present or side-specific; phrase grounding only localizes the queried phrase. If the report names only “fibrotic bands in the right upper lobe” and reports no lower-lobe finding, use that as upper-lobe supporting evidence at its actual strength, not as explicit confirmation of atelectasis. Then map the supported side-and-finding text back to the displayed option map and verify that the selected letter’s text matches it. In this case, option B’s text “right upper lobe pulmonary atelectasis” matched the reference and the terminal answer, so there was no option-mapping error; the caution is that the final rationale should not overstate “Yes” or phrase grounding as confirming the finding.
```

## exp_a94a9b1ba4645cd736e34555

来源题 [chexbench_openi_0317](../../cases/openi/chexbench_openi_0317.json) · 活跃

```text
**Trigger (narrow):** When finalizing a chest X-ray multiple-choice answer that asks which lobar/segmental finding is present, and the phrase-grounding tool returns a plausible bounding box for *each* candidate phrase, and/or the initial expert VQA reply is a bare negative ("No") while the grounded report lists only nonspecific findings (effusion, interstitial pattern, congestive hila) and does not name the queried finding.

**Observable verification action:** Before emitting the choice:

1. Do not treat either phrase-grounding box as proof of presence. Both-plausible boxes in their corresponding lung zones are non-discriminative for which finding is present, and cannot establish the answer.
2. Inspect the terminal rationale word-by-word against the actual recorded observations. If the rationale invokes visual descriptors (e.g., "blurring of the medial right hemidiaphragm," "right upper lobe remains lucent") that no tool observation reported, either cite the observation that supports them or downgrade the claim. A verifier that was handed the proposed answer and asked to confirm it is not independent evidence for those descriptors.
3. Treat a bare "No" from the expert VQA on the either/or question as conflicting evidence: it addressed the same object and attribute as the question. Do not silently drop it from the rationale.
4. Map the supported answer text back to the displayed option map and confirm the selected letter's text matches the option list and reference. Distinguish an option-mapping error (letter/text mismatch) from a wrong conclusion (supported text does not match any option).

**Caution from this case:** The answer B matched the reference, but the supporting chain was weak — an expert "No," a grounded report with no atelectasis, and two plausible grounding boxes. Correctness here does not validate the procedure; the reusable lesson is that both-candidate grounding boxes are localizations only, and the terminal rationale must not assert visual findings that were never observed. State evidence at its actual strength at finalization.
```

## exp_856f911293db81cc2e675bc4

来源题 [chexbench_openi_0318](../../cases/openi/chexbench_openi_0318.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer where the displayed options share the same side but differ by craniocaudal location—e.g., “right lower lobe pulmonary atelectasis” vs “right upper lobe pulmonary atelectasis”—and the evidence includes a phrase like “right basilar atelectasis” or a right lower-lung-zone box.

Verification action: Before emitting the choice, extract the exact side, craniocaudal location, and finding from the grounded report/box. Treat “basilar” or a right lower-lung-zone box as support for lower-lobe, not upper-lobe, disease; do not use the absence of a left-sided finding to discriminate between two right-sided options. Map the supported text “right lower lobe pulmonary atelectasis” back to the displayed option map, and confirm that the selected letter’s text exactly matches that option and the reference. If the support is only a phrase-grounding box for a queried phrase, treat it as localization only unless an explicit report statement names the side and finding. In the final rationale, state the actual lower-vs-upper discriminator and avoid irrelevant left-side claims. In this case, selecting A was correct because “right basilar atelectasis” and the right lower lung zone support option A’s text, but the rationale’s “no left-sided atelectasis” sentence was irrelevant to distinguishing the two right-sided choices.
```

## exp_202c824063d3a8385b0fda9d

来源题 [chexbench_openi_0320](../../cases/openi/chexbench_openi_0320.json) · 活跃

```text
**Trigger:** When finalizing a chest X-ray multiple-choice answer that asks which lobe shows pulmonary atelectasis (e.g., left upper vs. left lower lobe) after querying several VQA tools, and the tool replies are discordant — at least one tool answers "No / no atelectasis," at least one reply is garbled or non-parseable, and one report names a nearby but different finding such as "left lower lobe consolidation" rather than the exact queried finding.

**Observable verification action:** Before emitting the choice, do all of the following:
1. Exclude garbled/non-substantive tool outputs from the evidence tally — they are non-evidence, not votes for either side.
2. Treat a report of "left lower lobe consolidation/opacity" as corroborating *location* (left lower lobe) but not as an explicit confirmation of *atelectasis*; state the evidence at that actual strength in the rationale.
3. Do not cite a retrieved historical "prior reference annotation" as proof about the current image — a prior case annotation is not an observation of this image.
4. Map the supported lobe-and-finding text to the displayed option map and confirm the selected letter's displayed text agrees (here option B = "left lower lobe pulmonary atelectasis," matching the reference B, so the letter/text mapping was correct).

**Lesson from this case:** The terminal answer B was correct and the letter/text mapping was sound (no option-mapping error). But the grade alone does not vindicate the procedure: the rationale leaned on a "prior reference annotation" rather than image-specific evidence, treated left lower lobe *consolidation* as if it confirmed *atelectasis*, and silently dropped two explicit "No atelectasis" replies plus one garbled output. The reusable caution is to strip non-evidence (garbled, historical annotations), grade each remaining observation by whether it names the exact side-and-finding, and then still verify the supported text against the displayed option before finalizing.
```

## exp_d2c4b4819d39a60b785bbd26

来源题 [chexbench_openi_0321](../../cases/openi/chexbench_openi_0321.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer that distinguishes lobe-specific atelectasis candidates (e.g., left lower lobe vs left upper lobe), especially if the draft rationale cites a “reference annotation” or prior feedback and a verification tool call has no recorded observation.

Verification action: Before emitting the choice, look for a recorded observation that explicitly names the exact side, lobe, and finding in the current image. Treat prior feedback or a “reference annotation” as non-image evidence; do not describe an unreturned or empty tool call as confirming the finding. If an explicit read supports “left lower lobe pulmonary atelectasis,” map that text to the displayed options and check that the selected letter’s displayed text and the released reference agree. In this case, option A’s text was “left lower lobe pulmonary atelectasis” and the reference was A, so there was no option-mapping error; the caution is that the terminal rationale cited the reference annotation instead of a recorded chest_xray_expert result, and the empty observations mean the requested verification was not actually observed. If no observation supports the finding, state that uncertainty rather than claiming confirmation.
```

## exp_dc7baf64236f6a6d5d476374

来源题 [chexbench_openi_0322](../../cases/openi/chexbench_openi_0322.json) · 活跃

```text
Trigger: Before finalizing a chest X-ray multiple-choice answer whose options differ only by the severity of the same finding—e.g., “mild hyperdistention of the lung” versus “severe hyperdistention of the lung”—check whether the evidence actually establishes severity, not merely the presence of hyperdistention.

Verification action: Require at least one completed, same-image tool observation that explicitly states the severity, such as “Mild.” Do not treat finding presence alone, a generic report, or a phrase-grounding echo as proof of mild versus severe. If multiple tools give severity statements, reconcile them; if they conflict without resolution, do not guess. Then map the supported severity text back to the current displayed option map and confirm the terminal letter and text agree. In this case, chest_xray_expert returned “Mild” for this same image, the option map had A = “mild hyperdistention of the lung,” and the terminal answer “A. mild hyperdistention of the lung” matched both the map and the reference. The lesson is that the correct outcome depended on using an explicit same-object, same-attribute severity observation and verifying the letter-text mapping, not just on the final grade.
```

## exp_9c733094a9656f659e152bc6

来源题 [chexbench_openi_0323](../../cases/openi/chexbench_openi_0323.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by a severity qualifier for the same finding, such as “severe hyperdistention of the lung” versus “mild hyperdistention of the lung,” especially after asking tools specifically whether the finding is severe or mild.

Verification action: Before finalizing, require at least one completed, same-image tool observation that explicitly states the severity of that finding, such as “Mild” or “mild hyperdistention of the lungs.” Do not treat mere finding presence, a generic “No significant findings” report, or an unsupported severity as proof of the alternative. Reconcile explicit severity statements: if multiple tools explicitly agree on mild and none explicitly supports severe, use the supported severity; if explicit severity statements conflict and cannot be resolved, retry or report that the answer cannot be determined. Then map the supported severity text back to the displayed option and confirm the terminal letter and text agree.

Case application: chest_xray_expert returned “Mild” for the same image, and llava_med_qa returned “mild hyperdistention of the lungs”; maira2 reported “No significant findings,” which was absence evidence rather than support for “severe.” The terminal choice was “B. mild hyperdistention of the lung,” the current option map gave B as “mild hyperdistention of the lung,” and the released reference was B with the same text. The reusable lesson is to require same-object, same-attribute severity evidence and to verify letter-text mapping at finalization; a correct grade alone does not prove the procedure, but this trajectory shows the supported severity was used rather than an option-mapping guess.
```

## exp_25fc0a38b5b95844b3400c48

来源题 [chexbench_openi_0354](../../cases/openi/chexbench_openi_0354.json) · 活跃

```text
**Trigger:** When finalizing a chest X-ray multiple-choice answer whose options differ only by a severity grade (e.g., "severe atherosclerosis" vs "mild atherosclerosis"), and the deciding tool response is a bare label produced by a binary question the model itself composed.

**Verification action:** Require a descriptive, attribute-level observation for this same image and the same attribute (here, extent of calcification along the aortic knob/descending aorta — e.g., "extensive linear calcification" vs "subtle knob calcification") before committing, not merely a one-word label like "Mild." Treat a forced-choice label as weak evidence when the model framed the binary choice itself, since it reflects the tool's compliance rather than independent description. Cross-check with another tool or phrase-grounding call if the label is the only evidence. Then reconcile the final rationale line-by-line with actual observations: do not write "visual inspection confirms…" unless a separate visual/grounding observation was performed — in this case the "visual inspection" claim was fabricated and the entire conclusion rested on the tool's single-word "Mild." Finally, map the supported finding text back to the displayed option map and confirm the letter and text agree.

**Case lesson:** The letter/text mapping here was fine (B = "mild atherosclerosis"), so this was not an option-mapping error but a wrong conclusion driven by over-trusting a leading, single-word tool answer and an unexecuted visual rationale; a correct grade alone would also not have proven the procedure, and a failed trajectory like this supports the caution about not treating a model-induced binary label as decisive evidence.
```

## exp_d3d83f3623269980edcbd468

来源题 [chexbench_openi_0332](../../cases/openi/chexbench_openi_0332.json) · 活跃

```text
Trigger: Before finalizing a chest X-ray multiple-choice answer whose options differ only by severity of the same finding—e.g., “severe cardiomegaly” versus “mild cardiomegaly”—when a same-image expert tool has returned a bare severity term such as “Mild.”

Verification action: Map that exact observed term to the current displayed option map and confirm the letter and text agree (here, “Mild” maps to B. “mild cardiomegaly”). Treat the direct expert term as the load-bearing evidence for severity, and audit the rationale so any general grounded report is cited only for what it explicitly states. In this case maira2_grounded_report said “Cardiomegaly” with no severity; it supports presence, not “mild” versus “severe.” Do not convert its silence about severity into independent confirmation of mild, and do not say both tools confirmed “mild.” If a same-image observation does not explicitly discriminate severity, do not infer the missing severity; if the expert tool explicitly returns the matching severity term, use that term and the checked option text as the basis for the terminal answer.
```

## exp_9ded160804a2a4264b78bb6f

来源题 [chexbench_openi_0356](../../cases/openi/chexbench_openi_0356.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options name the same finding but differ only by a severity grade — e.g., “mildly tortuous thoracic aorta” vs “severely tortuous thoracic aorta” — and the proposed grade rests on a single tool reply while other tools are silent on that structure.

Verification action: Before accepting the grade, confirm there is at least one completed, same-image, same-attribute observation that explicitly grades that structure as mild or severe. Do not count a verifier “CORRECT” as independent image evidence; it checks consistency, not the underlying severity. Do not count a grounded report that never mentions the aorta as corroboration for either option. If the only support is one tool’s forced-choice reply to a query that itself offered only “mildly or severely,” treat that reply as unverified: the question presupposes tortuosity and forces a binary grade, so a default “Mildly” is possible. In that situation, either re-query neutrally or state that the severity is not independently supported; do not write that the answer was “confirmed.” Then map the supported option text back to the displayed choice and confirm the terminal letter and text agree.

Case application: The chest_xray_expert returned “Mildly,” and letter A does correctly map to “mildly tortuous thoracic aorta,” so this was not an option-mapping error. But maira2_grounded_report listed only enlarged heart, clear lungs, and a hiatus hernia — it said nothing about the aorta — and the verify tool’s “CORRECT” was then cited in the final rationale as confirmation. That overstates the evidence: a single forced-choice expert reply plus a consistency check is not independent severity evidence. The reference was B, “severely tortuous thoracic aorta,” so the supported conclusion was wrong, not mis-lettered. The reusable caution is to require an explicit same-attribute severity observation and to never treat verifier approval or a silent report as corroboration of the grade. An untested re-query would not by itself establish that this repair succeeds.
```

## exp_738d53b806d4822457b5ca1a

来源题 [chexbench_openi_0357](../../cases/openi/chexbench_openi_0357.json) · 活跃

```text
Trigger: In a chest X-ray multiple-choice question where the options name the same finding but differ only by severity (e.g., “severe cardiomegaly” vs “mild cardiomegaly”), immediately before finalizing, especially when one tool returns a bare severity term and another report only states that the finding is present.

Verification action: Map the exact supported severity word to the displayed option and confirm its letter and text agree. Then check every cited tool observation for the exact attribute being decided—severity. If an observation says only “heart size is enlarged” or otherwise lacks a severity word, use it only as evidence of presence, not as confirmation of “mild,” “severe,” or absence of severe features. Do not embellish the rationale by saying a general report confirmed mildness or excluded severe enlargement unless that report explicitly does so. If the sole explicit severity term conflicts with the reference or another completed same-image observation, treat it as an evidence conflict/wrong severity conclusion, not an option-letter mapping error. In this case, chest_xray_expert returned “Mild,” maira2_grounded_report returned only “The heart size is enlarged,” and the terminal answer B matched the “mild cardiomegaly” option text; the failure was overreading the non-specific report and choosing the wrong severity, not mislabeling B.
```

## exp_0324754b95b1e669abbf0b45

来源题 [chexbench_openi_0358](../../cases/openi/chexbench_openi_0358.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose only observed evidence is a single expert tool's bare forced-choice term (e.g., "Mildly") returned in response to a query that explicitly listed the two candidate options (e.g., "severely hypoinflated or mildly hypoinflated").

Verification action: Before emitting the choice, map the exact observed term to the displayed option map and confirm the selected letter and its text agree. If the term matches one option, record that as an option-mapping check only — not as proof the finding is present. A forced-choice query that lists both candidates can bias a single tool, so treat a lone bare term as one weak, non-independent observation. Where another tool is available, obtain an unforced/open-ended read of the same image and attribute; if none is available, state at finalization that the conclusion rests on one forced-choice observation. Distinguish an option-mapping error (selected letter's text differs from the observed term) from a wrong conclusion (the observed term itself, e.g., "Mildly," conflicts with the true finding, e.g., "severely hypoinflated"). In this case "Mildly" mapped cleanly to option B, so the failure was a wrong/unsupported evidence conclusion, not a letter/text mapping error.
```

## exp_a665938efcbceb3b1442fbfc

来源题 [chexbench_openi_0360](../../cases/openi/chexbench_openi_0360.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity of the same finding—e.g., A “mildly hypoinflated lung” versus B “severely hypoinflated lung”—and the only tool observation is a bare forced-choice term such as “Mildly” from a query that listed both candidates.

Verification action: Before emitting the choice, map the exact observed term to the displayed option map and confirm that the selected letter and full text agree—e.g., “Mildly” supports A only if A’s text is “mildly hypoinflated lung.” Treat that bare term as the tool’s forced-choice output only; do not embellish the rationale with additional radiographic signs. If the reference or another source says the opposite severity, record it as a tool-vs-reference evidence conflict, not an option-letter mapping error. Do not claim a corrected “severe” conclusion unless a completed same-image observation explicitly states “severely hypoinflated” or provides severity-discriminating evidence. In this case, the tool said “Mildly” and the terminal answer matched A’s text, so the failure was an unsupported/conflicting evidence conclusion; the unexecuted switch to B is not a verified repair.
```

## exp_e64cc966348b6ceb5e5a684a

来源题 [chexbench_openi_0361](../../cases/openi/chexbench_openi_0361.json) · 活跃

```text
Trigger: When a chest X-ray multiple-choice question has options that differ only by severity—e.g., “mildly hypoinflated lung” versus “severely hypoinflated lung”—and the only same-image tool response to a forced-choice severity query is non-discriminative, such as “Yes,” rather than an explicit severity term.

Verification action: Before finalizing, look for a completed same-image observation that explicitly states the exact severity (“mildly hypoinflated” or “severely hypoinflated,” or a clear equivalent). Do not treat a bare “Yes,” a negative statement, or the absence of another sign as evidence for either severity, and do not embellish the rationale with visual findings the tool did not state. Map the exact observed severity text back to the displayed option map and confirm the selected letter and text agree. If no observation explicitly names the severity, do not present an unsupported severity conclusion; mark it undetermined or flag the evidence gap. In the source case, the terminal answer A was not a letter/text mapping error—A correctly mapped to “mildly hypoinflated lung”—but it was an unsupported conclusion because the only observation was “Yes” and no tool stated “mild.”
```

## exp_d737430fbae69fa3987015b7

来源题 [chexbench_openi_0333](../../cases/openi/chexbench_openi_0333.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity of the same finding, and the only tool evidence is a bare forced-choice severity term from chest_xray_expert. Example: options are “A. mild cardiomegaly” and “B. severe cardiomegaly,” the tool is asked “Is there mild or severe cardiomegaly?”, and it returns only “Mild.”

Verification action: Before emitting the terminal answer, re-read the displayed option map and match the exact observed severity term to the option text, not merely to the general finding. If the observation says “Mild,” the selected option text must be “mild cardiomegaly,” and the terminal letter must be the letter currently displayed for that text (here A). Use the bare observation only for the severity it states; do not infer severe disease or add unsupported radiologic signs. If a reference or another source conflicts, classify it as an evidence conflict, not as an option-letter mapping error, and do not assert the conflicting severity unless a completed same-image observation explicitly supports it.
```

## exp_b3672329248464a918ec5a7e

来源题 [chexbench_openi_0334](../../cases/openi/chexbench_openi_0334.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ mainly by severity—for example, “severely hypoinflated lung” versus “mildly hypoinflated lung”—and one forced-choice VQA observation names a severity while other same-image tools report “Normal,” “No significant findings,” or return no localization.

Verification action: Before emitting the choice, take the exact positive phrase from the observation (for example, “mildly hypoinflated lungs”), map it to the displayed option map, and check that the selected letter’s displayed text matches that phrase and the released reference. Then check whether the earlier expert, report, and grounding results addressed the same object and attribute—here, lung inflation—and explicitly treat “Normal”/“No significant findings”/empty grounding as conflicting or non-supportive evidence, not as support for the severity option. If only the forced-choice VQA supports the severity, state the answer as supported by that single observation with the conflict acknowledged, or obtain a new same-image observation that explicitly discriminates severity; do not infer extra visual signs. In this case, option B’s letter and text matched “mildly hypoinflated lung” and the reference, so there was no option-mapping error; the lesson is that the correct grade did not make the evidence chain strong, because LLaVA-Med was a single positive severity observation against an expert “Normal,” a grounded report of “No significant findings,” and no phrase-grounding finding.
```

## exp_d3a20aa4ca764ca8323e78c5

来源题 [chexbench_openi_0335](../../cases/openi/chexbench_openi_0335.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity—e.g., “severe degeneration of thoracic vertebrae” vs. “mild degeneration of thoracic vertebrae”—and an earlier tool observation is a bare ambiguous answer such as “No” to a forced-choice severity query.

Verification action: Before emitting the letter, inspect the completed same-image tool observations and quote the exact severity statement. Treat a bare “No” as non-discriminating for a severe-vs-mild choice unless it explicitly negates degeneration; do not convert it into “mild” or “severe.” Use an explicit observation such as “mild degeneration of the thoracic vertebrae” as the supported severity, and reconcile it with any other results. Then map that exact supported text back to the displayed option map and confirm the terminal letter and text agree. In this case, chest_xray_expert returned only “No,” while llava_med_qa returned “mild degeneration of the thoracic vertebrae”; B correctly mapped to that text. The correct grade alone would not prove the procedure, but the transcript shows the final choice used the explicit same-image severity observation rather than the ambiguous “No.”
```

## exp_9bc9288f18d827691dc1bfea

来源题 [chexbench_openi_0336](../../cases/openi/chexbench_openi_0336.json) · 活跃

```text
Trigger: In a chest X-ray multiple-choice question where the options differ only by severity of the same finding—for example, “severely tortuous thoracic aorta” versus “mildly tortuous thoracic aorta”—and one tool directly answers the severity while a grounded report only names the finding (“Tortuous aorta”), check the evidence before finalizing.

Verification action: Treat the tool that explicitly answers severity as the load-bearing evidence: confirm it actually says “mild” or “severe.” Use the grounded report only for what it explicitly states, such as “tortuous aorta,” and do not say it confirmed mildness or the absence of severe features unless it says so. Then map the supported severity phrase back to the displayed option—here “mildly tortuous thoracic aorta” is B—and confirm the terminal letter and text agree. In this case, chest_xray_expert returned “Mild,” while maira2_grounded_report returned only “Tortuous aorta”; the final B answer is correct, but the rationale should not overstate the grounded report’s support.
```

## exp_32313c44d9ba24f02fe557f1

来源题 [chexbench_openi_0337](../../cases/openi/chexbench_openi_0337.json) · 活跃

```text
Trigger: Before finalizing a chest X-ray multiple-choice answer whose options differ only by a severity adjective for the same named finding, when a direct CXR QA tool has returned a bare severity term.

Verification action: Re-read the displayed option map and confirm three things in the same pass: the tool prompt named the same finding as the options, the tool returned a severity word that directly answers the mild-versus-severe distinction, and the chosen option’s adjective and finding text exactly match that returned word. If the observation is “Mild” for “aortic calcinosis … mild or severe,” map it to the option whose text is “mild aortic calcinosis” and whose letter is A, and state the observed word “Mild” in the rationale. If the observation were “Severe,” map it to the severe option instead. If the tool output does not name the finding or does not resolve mild versus severe, do not finalize from it; re-query or treat the answer as indeterminate. Also check that no other same-image tool result contradicts the severity.

Lesson from this case: the tool result addressed the same object and attribute as the question—aortic calcinosis severity—and the final answer used that exact observation. The displayed option map had A = mild aortic calcinosis and B = severe aortic calcinosis, and the released reference was A. The correct grade alone is not the lesson; the reusable check is to anchor the final letter and text on the exact observed severity adjective and confirm it matches the displayed option, rather than inferring or upgrading the finding.
```

## exp_3a7509484142e007df50f2ef

来源题 [chexbench_openi_0338](../../cases/openi/chexbench_openi_0338.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by the severity of the same finding—e.g., “mild hyperdistention of the lung” versus “severe hyperdistention of the lung”—especially when a tool returns only a bare severity term such as “Mild.”

Verification action: Before emitting the answer, require at least one completed same-image tool observation that explicitly states the severity of that finding. Then map the exact supported severity text to the currently displayed option map, not to a remembered or historical lettering, and confirm that the terminal letter and text agree. Do not treat finding presence alone, a generic report, or phrase-grounding echo as proof of mild versus severe. If tools give conflicting severity statements and cannot be reconciled, do not guess.

In this case, chest_xray_expert explicitly returned “Mild” for the same image’s lung hyperdistention. The current option map was A = severe hyperdistention and B = mild hyperdistention, so the supported “Mild” mapped to B, matching the terminal answer “B. mild hyperdistention of the lung” and the reference. The lesson is to verify both the explicit same-object, same-attribute severity evidence and the current letter-text mapping; a correct final grade alone does not prove the procedure was sound.
```

## exp_d394d3a76eba516b310173ff

来源题 [chexbench_openi_0339](../../cases/openi/chexbench_openi_0339.json) · 活跃

```text
Trigger: Before finalizing a chest X-ray multiple-choice answer whose options differ only by severity (e.g., "mild cardiomegaly" vs "severe cardiomegaly"), when the deciding tool observation is a bare severity word returned from a forced-choice query that listed both candidates.

Verification action: Confirm the observation is a completed, same-image result — here chest_xray_expert answered "Mild" to "Is there cardiomegaly... mild or severe?" — then re-read the current displayed option map and check that the terminal letter and text both match that exact term. In this case the map was A = severe cardiomegaly, B = mild cardiomegaly, and the terminal answer "B. mild cardiomegaly" agrees with the observed "Mild" in both letter and text. Keep the rationale limited to what the tool actually stated: "Mild" supports mild cardiomegaly, but do not add diaphragm position, cardiac silhouette measurements, or other signs unless the observation itself says them. If the reference or another source says "severe," classify the discrepancy as a tool-vs-reference evidence conflict rather than an option-letter mapping error, and do not switch the conclusion unless another completed same-image observation explicitly provides discriminating severity evidence. A correct grade alone does not prove these checks were performed; the observable evidence here is the exact term "Mild," the option map (A = severe, B = mild), and the terminal letter/text agreement.
```

## exp_e2c1eb68b3b20a4c9ab31092

来源题 [chexbench_openi_0340](../../cases/openi/chexbench_openi_0340.json) · 活跃

```text
Trigger: Before finalizing a chest X-ray multiple-choice answer when the displayed options differ only by severity of the same finding—e.g., “severe bronchovascular markings” versus “mild bronchovascular markings”—and a tool returns a bare forced-choice severity term.

Verification action: Confirm the tool observation addresses the same image and the same finding/attribute (bronchovascular-marking severity), extract the exact observed term (“Mild” here), map that term to the current option map, and check that the terminal letter and displayed text agree (B = “mild bronchovascular markings”). Keep the rationale limited to the observed term; do not add unsupported imaging signs. If another same-image observation or the reference conflicts on severity, treat that as an evidence conflict rather than automatically as a letter/text mapping error unless the terminal letter and option text actually disagree. In this case, “Mild” mapped correctly to B and the reference was B, but the correct grade should be recorded as a successful letter/text mapping and evidence-use check, not as independent proof of the tool’s accuracy.
```

## exp_c3273f0a715074e09cce9948

来源题 [chexbench_openi_0341](../../cases/openi/chexbench_openi_0341.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity of the same finding—e.g., “mild hyperdistention of the lung” vs. “severe hyperdistention of the lung”—and the available evidence may state only a bare severity term.

Verification action: Before emitting the answer, require at least one completed, same-image tool observation that explicitly states the severity for that exact finding, such as “Mild.” Do not infer severity from finding presence alone, from a generic report, or from a phrase-grounding echo. If several same-image observations state severity and conflict without a resolution, do not guess. Then map the exact observed severity text back to the current displayed option map and confirm that the terminal letter and option text agree. In this case, chest_xray_expert returned “Mild” for the same image, the option map had A = “mild hyperdistention of the lung,” and the terminal answer “A. mild hyperdistention of the lung” matched both the map and the reference. A mismatch should be classified as an option-mapping error only if the supported severity text and terminal letter disagree; if the evidence itself conflicts with the reference, treat it as an evidence-conclusion conflict rather than a mapping error.
```

## exp_c63bd8300b2a575cdd2aa58e

来源题 [chexbench_openi_0342](../../cases/openi/chexbench_openi_0342.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity of the same finding—e.g., “mild scoliosis” vs “severe scoliosis”—and the chest_xray_expert observation returns a bare severity term such as “Mild.”

Verification action: Before emitting the letter, quote the actual returned observation and confirm it addresses the same finding and attribute as the question. In this case the observation was “Mild” in response to “Is there scoliosis in this chest X-ray? If yes, is it mild or severe?”, and the displayed options were A = “mild scoliosis” and B = “severe scoliosis.” Map the exact observed severity back to the current option map and check that the terminal letter and text agree; here A. mild scoliosis correctly matches the observation and the reference A. Do not treat the tool call itself, an absent observation, or general image reasoning as severity evidence, and do not embellish the rationale with unobserved signs. If the observation were absent, conflicting, or named the other severity, do not emit the unsupported choice. The correct grade here supports the procedure’s alignment, but a correct answer alone would not prove the severity check was performed.
```

## exp_66b252e9fa59c322e5e2d7a7

来源题 [chexbench_openi_0343](../../cases/openi/chexbench_openi_0343.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity/degree — e.g., “severely hypoinflated lung” versus “mildly hypoinflated lung” — and the only tool observation is a bare forced-choice term such as “Mildly” in response to a query that listed both candidates.

Verification action: Before emitting the choice, map the exact observed term to the displayed option map and confirm the selected letter’s text agrees with that term and with the reference. Use the observation at its actual strength: “Mildly” supports only “mildly hypoinflated lung”; do not add diaphragm position, lung volume, or other visual descriptors unless the tool observation explicitly states them. If the reference or another source says the opposite severity, treat that as a tool-versus-reference evidence conflict, not an option-letter mapping error, and do not “correct” to the other option unless another completed same-image observation explicitly supports it. In this case the tool said only “Mildly,” option B was “mildly hypoinflated lung,” and the reference was B, so the terminal letter/text mapping was correct; the reusable caution is to keep the rationale within the observed evidence.
```

## exp_e5e11598d5a24fba039dcfbb

来源题 [chexbench_openi_0344](../../cases/openi/chexbench_openi_0344.json) · 活跃

```text
Trigger: In a chest X-ray multiple-choice question whose options differ only by severity (e.g., “mild cardiomegaly” vs “severe cardiomegaly”), when the direct image tool returns a bare severity term such as “Mild,” and the verifier says “CORRECT” but also states that severity grading is limited/uncertain on the current view and recommends a frontal view or cardiothoracic-ratio measurement before finalizing.

Verification action: Before finalizing, perform two separate checks. First, map the exact observed term to the current displayed option map and confirm that letter and text agree: “Mild” supports A = “mild cardiomegaly,” not B. Second, re-read the verifier’s Issues/Suggestion wording as distinct from its CORRECT label. If the verifier did not itself measure the finding or provide same-image severity-discriminating evidence, do not write that verification “confirms” mild; state only that chest_xray_expert reported “Mild” and note the lateral-view limitation. Do not infer severe or add radiographic signs not present in the tool output. If the recommended frontal/CTR confirmation was not executed, treat that as an unresolved verification limitation, not as supporting evidence. If forced to choose, choose the option matching the direct observed term, but keep the rationale calibrated. In this case the terminal letter/text mapping was correct, but the final reason overstated the verifier; a correct reference grade alone does not validate that overstatement.
```

## exp_7049c43296d162157a9fd1d7

来源题 [chexbench_openi_0345](../../cases/openi/chexbench_openi_0345.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity—here “mild degeneration of thoracic vertebrae” (A) versus “severe degeneration of thoracic vertebrae” (B)—and the sole tool result is a bare forced-choice term (e.g., the chest_xray_expert observation “Mild”) returned in response to a query that listed both candidates.

Verification action: Before emitting the letter, quote the exact term from the completed tool observation, map that term onto the currently displayed option map, and confirm the letter and text agree. Here the observed “Mild” maps to A = “mild degeneration of thoracic vertebrae,” so A is the supported choice. Keep the rationale to what the observation actually states; do not add severity-discriminating signs (vertebral height loss, osteophytes, disc space narrowing) unless the tool itself reported them. Treat a contrary reference or a bare term as an evidence/option-mapping question, not as license to embellish: if the observed term conflicts with the reference or another same-image observation, flag it as a tool-vs-reference evidence conflict rather than remapping the letter. In this case the terminal answer A matched both the observed term and the reference text, and there was no letter/text mismatch—but the correct grade alone does not prove the check was performed, so the observable step to verify is the explicit quoting and letter-to-text reconciliation, not the final grade.
```

## exp_3001f2af55b26285e7038ece

来源题 [chexbench_openi_0362](../../cases/openi/chexbench_openi_0362.json) · 活跃

```text
Trigger: Before finalizing a chest X-ray multiple-choice answer whose options name the same finding but differ only by severity (e.g., “severe cardiomegaly” vs “mild cardiomegaly”), especially when the deciding tool observation is a bare severity word such as “Mild” or “severe” returned from a forced-choice query that listed both candidates.

Verification action: Confirm the observation is completed and same-image, then re-read the current displayed option map and check that the terminal letter and text both match the exact supported severity term. Treat only explicit severity statements as severity evidence; a report saying only “enlarged heart” or “cardiomegaly present” does not confirm mild versus severe. Check every completed same-image observation for the exact attribute of severity, and do not treat one bare forced-choice term as independent corroboration. In this case, chest_xray_expert returned “Mild”; the option map was A = severe cardiomegaly, B = mild cardiomegaly; and the terminal answer “B. mild cardiomegaly” matched B in both letter and text. That means the error is not an option-letter mapping error. Because the released reference says “severe,” the observed failure is a wrong severity conclusion/tool-vs-reference evidence conflict, not a mislabeled option. If no other completed same-image observation explicitly resolves the severity conflict, describe the answer as resting on a single uncorroborated severity observation rather than claiming it is verified, and do not embellish the rationale beyond what the tool actually stated.
```

## exp_6033d1915ff2ea8107d49a25

来源题 [chexbench_openi_0366](../../cases/openi/chexbench_openi_0366.json) · 活跃

```text
Trigger: Before finalizing a chest X-ray multiple-choice answer whose options are the same finding differing only by severity (e.g., “mild cardiomegaly” vs “severe cardiomegaly”), especially when a tool returns a bare severity term or a report uses a severity descriptor such as “marked.”

Verification action: Re-read the displayed option map and map the exact supported severity term to the option letter and text, confirming they agree. Count only explicit severity evidence from completed same-image observations: “Severe” and “Marked cardiomegaly” both support the severe option over mild; a report that only says the heart is enlarged or that cardiomegaly is present does not, by itself, establish severity. Keep the rationale limited to those exact terms. In this case chest_xray_expert returned “Severe” and maira2_grounded_report returned “Marked cardiomegaly,” so option B. severe cardiomegaly matched both the supported severity and the displayed letter/text. If an observation conflicts with the reference or another completed same-image observation, classify it as an evidence/severity conflict rather than an option-letter mapping error, unless the terminal letter and text themselves disagree. A correct grade alone does not prove these checks were performed; the observable evidence is the exact severity terms, the option map, and their letter/text agreement.
```

## exp_6964b14269ab57a923bed8a2

来源题 [chexbench_openi_0363](../../cases/openi/chexbench_openi_0363.json) · 活跃

```text
Trigger: In a chest X-ray multiple-choice question whose options differ only by severity of the same finding (e.g., “mild cardiomegaly” vs “severe cardiomegaly”), immediately before finalizing after a forced-choice image tool returns a bare severity word such as “Mild.”

Verification action: Re-read the displayed option map and check that the terminal answer’s letter and text both match the exact observed severity term. In this case the tool returned “Mild,” the map was A = mild cardiomegaly and B = severe cardiomegaly, and the terminal answer “A. mild cardiomegaly” correctly mapped “Mild” to option A in both letter and text. Then compare that mapped answer with the released reference or any other completed same-image evidence: here the reference says “severe cardiomegaly,” so this is a wrong-severity conclusion or tool-vs-reference evidence conflict, not an option-letter mapping error. The tool observation did address the same object and attribute as the question—cardiomegaly severity—and the terminal choice used that observation. Because no additional completed same-image observation explicitly discriminates severity, do not claim a mapping repair was verified or switch the conclusion without such evidence; keep the rationale limited to the observed term “Mild” and note the unresolved conflict.
```

## exp_224130aa86e54f2e53073c55

来源题 [chexbench_openi_0364](../../cases/openi/chexbench_openi_0364.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity of the same finding—e.g., A “mild scoliosis” versus B “severe scoliosis”—and the only supporting tool result is a bare severity term from chest_xray_expert such as “Mild,” especially when a released reference or retrieved historical case gives a different option.

Verification action: Before emitting the letter, quote the exact tool observation, confirm it addresses the same finding and attribute asked (scoliosis severity in this image), map that observed severity onto the current displayed option map, and check that the terminal letter and text agree. Then compare the mapped answer with the released reference or historical answer if available. If they agree, finalize using only the observed term. If they conflict—as here, observation “Mild” supports A “mild scoliosis” while the reference is B “severe scoliosis”—do not label this an option-mapping error and do not silently switch the letter or add unobserved severity signs; record it as a tool-versus-reference evidence conflict and, if possible, obtain another independent observation before finalizing. The original answer A matched its option text and the observed term, so the failure is an evidence/reference conflict, not a lost letter-to-text mapping. A correct grade alone would not prove this check was performed; the observable step is the explicit quoting, same-attribute check, letter-to-text reconciliation, and conflict flag.
```

## exp_4064e74e882d25f352bea527

来源题 [chexbench_openi_0365](../../cases/openi/chexbench_openi_0365.json) · 活跃

```text
Reusable decision procedure:

Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity (e.g., “mildly hypoinflated lung” vs “severely hypoinflated lung”) and the only tool observation is a bare non-discriminating response such as “Yes” to a question that listed both candidates.

Verification action: Before emitting the answer, check whether the exact tool observation explicitly names one of the displayed severity terms. If it does, map that term to the displayed option and confirm the selected letter and text agree. If it does not, do not treat the observation as support for either severity, and do not default to the milder option. Check whether any attempted disambiguating same-image call actually completed; an unexecuted call is not evidence. If no completed observation distinguishes mild from severe, mark the conclusion as unsupported and obtain an open-ended same-image read or report insufficiency rather than inventing support.

This case is an evidence-conclusion failure, not an option-mapping error: “Yes” maps to neither A nor B, the attempted open-ended call was not observed, and the final choice A (“mildly hypoinflated lung”) was selected by default even though the reference was B (“severely hypoinflated lung”). The reusable caution is to require an observed, severity-specific term before selecting between severity-only options.
```

## exp_e428f9675f7a499be9d586d2

来源题 [chexbench_openi_0367](../../cases/openi/chexbench_openi_0367.json) · 活跃

```text
Trigger: When a chest X-ray multiple-choice question contrasts severity grades of the same finding (e.g., mild vs severe left lung pulmonary atelectasis) and the direct evidence is a single VQA severity label, while the verifier returns “CORRECT” but also notes a limited single view or subjective grading.

Verification action: Before finalizing, inspect the raw VQA observation and verifier text and classify the evidence. A single reply such as “Mild” does address the queried object and attribute, but “verifier: CORRECT” is not independent image confirmation if the verifier only audits the proposed answer and itself flags limited evidence. Do not write that the verifier “confirmed correctness” or that there is “no evidence” of the alternative unless an independent grounded report, ROI, or separate neutral read explicitly supports that. If no independent severity evidence exists, record the severity conclusion as limited/uncertain rather than upgrading it. Then map the supported severity text to the displayed option map and confirm the selected letter’s text agrees. In this case, B’s letter and text (“mild left lung pulmonary atelectasis”) agreed, so there was no option-mapping error; the failure was a wrong severity conclusion based on one “Mild” VQA output plus a non-independent verifier “CORRECT,” while the released reference was A, severe left lung pulmonary atelectasis.
```

## exp_7cc6e3ae290b6751d638e911

来源题 [chexbench_openi_0369](../../cases/openi/chexbench_openi_0369.json) · 活跃

```text
Experience: single forced-choice severity word as the sole discriminator in a chest X-ray MC question.

Trigger: Immediately before finalizing a chest X-ray multiple-choice answer whose options differ only by severity (e.g., A = "severe cardiomegaly", B = "mild cardiomegaly"), when the only discriminating evidence is a bare severity word ("Mild"/"Severe") returned by one chest_xray_expert call whose question itself listed both candidate severities.

Verification action: First map the exact returned word to the currently displayed option map and confirm the terminal letter and text agree (here A = severe, B = mild, and the tool's "Mild" maps to "B. mild cardiomegaly"). Then check whether that word is the only completed same-image severity observation and whether it conflicts with the released reference or another completed same-image observation. If it conflicts, record the case as an evidence conflict / wrong-severity conclusion, not an option-letter mapping error: the letter/text mapping can be correct while the severity conclusion is wrong (this trajectory: mapping B = mild was correct, but the reference was A = severe). Keep the rationale limited to the exact observed word; do not add silhouette measurements, diaphragm position, or other signs the observation did not state, and do not describe a single forced-choice term as independent confirmation. Because no second same-image severity check was actually run in this case, treat "query another tool to resolve the conflict" only as a proposed, unverified repair—the observable lesson here is that a lone bare severity word from a query naming both candidates can disagree with the reference, so it should be flagged as single-source ambiguous evidence rather than presented as decisive.
```

## exp_5813e27865a8e08c5162896c

来源题 [chexbench_openi_0371](../../cases/openi/chexbench_openi_0371.json) · 活跃

```text
Trigger: Before finalizing a chest X-ray multiple-choice answer where the options differ only by severity of the same finding, such as “severe cardiomegaly” versus “mild cardiomegaly,” and the deciding tool observation is a bare severity word from a forced-choice query that listed both options.

Verification action: Re-check the current option map and confirm that the terminal answer’s letter and text both match the exact supported severity term. But do not let a single bare forced-choice term settle the answer by itself. Check whether any other completed same-image observation or the released reference explicitly states a different severity; if so, treat it as an evidence conflict or wrong-severity conclusion, not an option-letter mapping error, and do not finalize the severity without an independent same-image observation that addresses the same object and attribute. In this case, “Mild” correctly matched B = “mild cardiomegaly,” so the letter/text mapping was not the failure; the failure was relying on the bare “Mild” observation when the reference said severe, with no corroborating same-image severity evidence.
```

## exp_a6905ad6e3c2edba1be543fc

来源题 [chexbench_openi_0373](../../cases/openi/chexbench_openi_0373.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity of the same finding—e.g., A “severe degeneration of thoracic vertebrae” versus B “mild degeneration of thoracic vertebrae”—and the sole tool observation is a bare forced-choice term such as “Mild.”

Verification action: Before emitting the letter, quote the exact observation, map it onto the displayed option map, and check that the letter and text agree. Here “Mild” maps to B (“mild degeneration”), so there is no option-mapping error. Then compare that mapped choice with the released reference and any other same-object/same-attribute evidence. Here B/mild conflicts with reference A/severe; label that as a tool-vs-reference evidence conflict or wrong conclusion, not a letter swap, and do not add unobserved signs or claim the tool confirmed more than “Mild.” Because no corroborating observation was obtained, this failed case supports only the caution to surface the conflict and treat a single bare term as insufficiently verified, not a claim that a repaired answer was validated.
```

## exp_15f2e8e052101ce910509555

来源题 [chexbench_openi_0374](../../cases/openi/chexbench_openi_0374.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity (e.g., "severely hypoinflated lung" vs. "mildly hypoinflated lung") and the sole image evidence is one bare expert term ("Mildly") returned to a question that itself listed both candidate severities.

Verification action before emitting: (1) Check the tool question text. If it enumerated both option phrases, treat the bare reply as one weak, potentially biased observation, not proof of the finding; only a later unforced/open-ended read of the same image and attribute from a different tool or a candidate-free re-ask can corroborate it. (2) Check what the verify tool actually returned. If it only reports mapping-level correctness/safety (e.g., "Correctness: CORRECT, Safety: SAFE, Issues: None") with no image findings or severity-discriminating evidence, do not cite it as confirmation the finding is present—it audits answer-to-observation consistency, not the image. (3) Separately map the observed term to the option map: "Mildly" maps to option B, so a mismatch between terminal choice and reference (which said A, "severely hypoinflated lung") is a wrong-conclusion/evidence-conflict, not an option-letter error; do not relabel the mapping issue. If no independent unforced observation exists, still map correctly but state in the rationale that the conclusion rests on a single forced-choice observation, and do not embellish with diaphragm, rib, or volume descriptors the tool never stated.

Lesson from this case: the terminal letter/text mapping (B = "mildly hypoinflated lung") was internally clean and verify returned CORRECT, yet the answer conflicted with the released reference. The takeaway is not "fix the letter" but "a forced-choice query listing both candidates plus a mapping-only verifier is insufficient image evidence for severity claims."
```

## exp_89eccfe09eae8706a5058209

来源题 [chexbench_openi_0375](../../cases/openi/chexbench_openi_0375.json) · 活跃

```text
**Trigger**
When finalizing a chest X-ray multiple-choice answer whose options differ only by a severity grade of the same finding (e.g., "mild thoracic aorta calcinosis" vs "severe thoracic aorta calcinosis"), and the only evidence collected is a bare severity label ("Mild") obtained from a binary mild-or-severe question that the model itself composed — especially when a second tool is asked essentially the same forced-choice question and its matching label is then counted as "independent" corroboration.

**Verification action**
Before committing, obtain at least one descriptive, attribute-level observation of the same image and the same attribute — for aortic calcification, the extent and character along the aortic knob/descending aorta (e.g., "extensive linear calcification" vs "subtle punctate knob calcification") — from an open-ended prompt, a phrase-grounding call, or a crop-and-inspect pass. Treat two forced-choice labels as one weak line of evidence, not two, when both used the same mild-or-severe framing; a second model echoing the framing is prompt compliance, not independent verification. If only bare labels are available, state the grade as weakly supported rather than claiming that "two independent visual QA models both assessed..." Then map the supported severity phrase back to the displayed option map and confirm the letter and text agree.

**Case lesson**
Here the letter/text mapping was correct (A = "mild thoracic aorta calcinosis"), so this was not an option-mapping error but a wrong conclusion: the released reference was B (severe), while both tools returned "Mild" under the model's own binary framing and no descriptive finding was ever elicited. The terminal rationale's "two independent visual QA models" overstated the evidence — both calls shared the same leading mild-or-severe structure, so agreement was correlated, not independent. A correct grade alone would not have validated this procedure; the observed failure supports treating a self-framed severity label as weak evidence until a descriptive attribute-level observation confirms it.
```

## exp_7cf80d87ef47339e4cc95b14

来源题 [chexbench_openi_0376](../../cases/openi/chexbench_openi_0376.json) · 活跃

```text
Trigger: In a chest X-ray multiple-choice question whose options differ only by severity of the same finding (e.g., “severe cardiomegaly” vs “mild cardiomegaly”), immediately before finalizing when tool outputs conflict and the grounded report is unavailable or a verifier gives only a hedged plausibility judgment.

Verification action: Re-read the current option map and each completed same-image observation for the exact severity attribute. Treat a verifier statement such as “mild is more plausible” or “not grossly massively enlarged” as a caveat, not as a resolving same-image severity observation, unless it explicitly states the graded finding for this image. Do not use that caveat to override an explicit same-image tool result. If completed same-image observations still conflict and no third explicit observation resolves severity, mark the severity conflict unresolved rather than claiming the verifier resolved it. If choosing an answer, map the exact supported severity word back to the displayed letter and text and confirm they agree. In this case, “B. mild cardiomegaly” correctly matched the “mild” text, so this was not an option-letter mapping error; the error was losing the explicit chest_xray_expert “Severe” observation and treating verifier plausibility as decisive despite an unresolved severity conflict and a non-applicable lateral-only report.
```

## exp_b5fba735fbb7e525bbae6de2

来源题 [chexbench_openi_0377](../../cases/openi/chexbench_openi_0377.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only in the severity of one finding — e.g. A "mild degeneration of thoracic vertebrae" vs B "severe degeneration of thoracic vertebrae" — and the entire evidence base is a single tool observation that returns a bare forced-choice term ("Mild") to a question that listed both candidates.

Verification action: Before emitting the letter, (1) quote the observed term verbatim from the completed tool observation; (2) map that term onto the currently displayed option map and confirm the chosen letter's text is exactly that term — here "Mild" maps to A, so the letter/text link is internally consistent and the failure, if any, is not an option-mapping error; (3) do not embellish the rationale with severity-discriminating signs (vertebral height loss, osteophytes, disc-space narrowing) that the tool never reported, and do not reword the observation to sound like it supports a different letter; (4) recognize that a single bare "Mild"/"Severe" string is weak, load-bearing-only evidence: in this case it pointed to A while the released reading was B ("severe degeneration"), so the honest disposition is to record a tool-vs-reference evidence conflict, not to silently remap the letter or to treat the rationale as settled; (5) when other independent backends are available (e.g. a second vision QA model or a grounded report), obtain one more observation on the same object and attribute — severity of thoracic vertebral degeneration — and let agreement or disagreement between independent observations decide the answer. Reason: the terminal answer here matched the only observation and matched no letter/text mismatch, yet still disagreed with the reference, showing that correct letter-to-text reconciliation is necessary but not sufficient; the missing step was cross-checking the substance of a lone forced-choice tool output rather than trusting its first token. Note that the cross-check itself was not executed in this trajectory, so it stands as a caution derived from the observed failure, not as a demonstrated fix.
```

## exp_082c428894f057033b617032

来源题 [chexbench_openi_0379](../../cases/openi/chexbench_openi_0379.json) · 活跃

```text
Trigger: In a chest X-ray multiple-choice question whose options differ only by severity for the same finding, such as “severe cardiomegaly” vs “mild cardiomegaly,” immediately before finalizing when the deciding tool observation is a bare severity word from a forced-choice query.

Verification action: Confirm the observation is completed and came from the same image, and that the query asked for the exact severity attribute rather than only whether the finding is present. Re-read the current displayed option map and check that the terminal answer’s letter and text both match the exact returned severity term. Keep the rationale limited to that term. Then check for another completed same-image observation that explicitly states severity; do not treat presence-only wording such as “heart size is enlarged” as confirmation of mild or severe. If severity terms conflict, or the sole explicit severity term conflicts with the released reference, classify it as an evidence/severity conflict or unverified conclusion, not as an option-letter mapping error. Do not claim a repair succeeded unless another same-image severity observation was actually run and resolves the conflict. In this case, chest_xray_expert returned completed same-image “Mild,” the map was A = severe and B = mild, and “B. mild cardiomegaly” matched both letter and text; the mapping was correct. The observed failure was the severity conclusion, since the reference says severe, not the mapping. A passing letter/text check alone does not prove the severity conclusion.
```

## exp_ccbcd89492d75656b8fe348f

来源题 [chexbench_openi_0370](../../cases/openi/chexbench_openi_0370.json) · 活跃

```text
Trigger: Before finalizing a chest X-ray multiple-choice answer whose options differ only by severity, when a direct image tool returns a bare severity term such as “Severe” and the verifier returns “CORRECT” but its Issues/Suggestion says the view cannot reliably grade mild versus severe.

Verification action: Re-read the displayed option map and confirm that the terminal letter and text match the exact direct tool term: here “Severe” supports B = severe cardiomegaly. Then inspect the verifier’s wording separately from its “CORRECT” label. Treat the verifier as confirming severity only if it independently states the same severity; if it says only that the cardiac silhouette is markedly enlarged and that the lateral view cannot grade severity, do not write that the verifier “confirmed” the severity. State that chest_xray_expert returned “Severe” and note the lateral-view limitation as an unresolved verification limitation. Do not switch the conclusion based on that limitation alone; only switch if another completed same-image observation explicitly provides discriminating severity evidence. A correct reference grade does not validate an overstated rationale.
```

## exp_671bc59660939f2bc77564f8

来源题 [chexbench_openi_0372](../../cases/openi/chexbench_openi_0372.json) · 活跃

```text
Trigger: When finalizing a chest X-ray multiple-choice answer whose options differ only by severity, such as mild versus severe hyperdistention, and the main same-attribute evidence is a single tool’s bare forced-choice severity term, especially after a query that listed both candidates.

Verification action: Before emitting the choice, map the exact observed severity term to the current option map and confirm that the selected letter and text agree. Require the severity statement to come from a same-image observation that explicitly addresses the same finding and attribute; treat a report saying only “air trapping” or “volume loss” as non-discriminating for severity, and treat a verifier “CORRECT” as validation of the proposed answer, not independent severity evidence. If the only severity-specific evidence is a forced-choice term, say that the conclusion rests on that single observation and do not embellish the rationale with signs the tool did not state. In this case, “Severe” matched option A, “severe hyperdistention of the lung,” and the reference, so there was no letter/text mapping error; the lesson is to avoid presenting the verifier or a non-specific report as independent proof of severity.
```

## exp_cb8e582e5b013c14d3054eec

来源题 [chexbench_openi_0378](../../cases/openi/chexbench_openi_0378.json) · 活跃

```text
Trigger: In a chest X-ray multiple-choice question whose options differ only by the severity of one finding (e.g., “severe cardiomegaly” vs “mild cardiomegaly”), immediately before finalizing — especially when a tool returned a bare severity word from a forced-choice query and the draft rationale claims a quantitative threshold such as “CTR > 0.6.”

Verification action: Re-read the exact wording of every cited same-image observation and keep the rationale limited to what was actually stated. A bare “Severe” from a direct “mild or severe?” question can support the severe option as an explicit severity term; a non-specific report such as “Cardiomegaly” supports only presence, not severity; and a bare “Yes” to a leading yes/no question like “Is CTR greater than 0.6?” is not a measured cardiothoracic ratio and must not be written up as “confirmed CTR > 0.6.” If no observation explicitly reports a numeric CTR or states that it exceeds 0.6, do not add that measurement, projection-marker confirmation, or other visual-sign embellishments to the rationale. Then map the exact supported severity text to the current displayed option map and confirm the terminal letter and text agree — in this case the map was A = severe cardiomegaly, B = mild cardiomegaly, and “A. severe cardiomegaly” matched, so the terminal choice was not an option-mapping error. If the only explicit severity term conflicts with the reference or with another completed same-image observation, treat that as a wrong-severity/evidence conflict rather than a letter-labeling error, and do not switch the conclusion unless another completed same-image observation supplies discriminating severity evidence. Note that a correct grade alone does not prove this procedure was followed: here the answer matched the reference (A), but the rationale overstated a binary “Yes” as measured CTR confirmation, so the trajectory supports a caution about unverified severity/threshold claims rather than a verified success.
```
