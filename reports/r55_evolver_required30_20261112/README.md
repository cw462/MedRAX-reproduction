# R55 EvolveR required-search pilot

The pilot started with an empty experience bank and used the first 30 questions in the OpenI293 order. It ran on GPU0 in 36 minutes 42 seconds. Generation, scoring, runner and controller all exited with code zero.

| Matched questions | Saved D | EvolveR |
| --- | ---: | ---: |
| All 30 | 21/30 (70.0%) | 18/30 (60.0%) |
| Same previous-image context (29) | 20/29 | 17/29 |
| Different previous-image context (1, OpenI 0025) | 1/1 | 1/1 |

EvolveR got three D errors right and missed six questions D got right. D outcomes are saved online rewards. E outcomes come from the complete-pilot scorer. Qwen 3.7 Plus, 11 tools, Qwen reflect and the DeepSeek verifier were shared by configuration. The GPU assignment, time window and one case's available same-image context differed.

The pre-answer check ran 30 times and recorded 30 empty banks. There were zero embedding lookups, experience deliveries and follow-up searches. Distillation selected 26 candidates in three ten-case windows. All 52 received replies failed validation. Offline replay found 46 invalid experience schemas and 6 JSON parse errors. No card entered the bank. The pilot verifies the required check and empty-bank path. It does not measure the effect of a delivered experience.

[Summary](summary.json) · [CSV](per_question.csv) · [Questions, answers, and tool traces](case_details.json) · [Writer validation and window records](experience_receipts.json) · [Protocol](protocol.json) · [Source](source)

Run python verify_saved.py to check the aggregates and saved receipts without inference. The original scorer is included under source and uses shared MedRAX modules. Token cost proxies in the summary are distinct from provider invoices.

Questions come from [Stanford AIMI CheXBench](https://huggingface.co/datasets/StanfordAIMI/chexbench), OpenI subset. Images originate from the Indiana University collection. [Image source links](outgoing_scope.json) preserve the case mapping. Image bytes remain local in light of the [Open-i sharing guidance](https://openi-vip.nlm.nih.gov/faq) and [Indiana image reuse terms](https://openi.nlm.nih.gov/contactus).
