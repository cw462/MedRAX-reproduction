# R55 EvolveR 30-question pilot with unvalidated experience admission

A fresh GPU0 run used the same first 30 OpenI293 cases and started with an empty bank. It finished in 41 minutes 30 seconds. Generation, scoring, runner and controller each exited with code 0.

| Scope | Saved D | Previous E | New E |
| --- | ---: | ---: | ---: |
| All 30 | 21/30 (70.0%) | 18/30 (60.0%) | 22/30 (73.3%) |
| Questions 1–10, empty bank | 8/10 | 6/10 | 8/10 |
| Questions 11–30, new E received experience | 13/20 | 12/20 | 14/20 |

Relative to previous E, new E corrected four answers and lost zero. Two corrections were in the first ten questions, before any cards could be retrieved. Relative to saved D, new E corrected four and lost three. D has one case with different available same-image history (OpenI 0025). D uses saved online rewards and the two E runs use their saved full-pilot scores. The runs took place at different times and changed both the writer prompt and its admission policy. This comparison describes the observed runs. It does not isolate the effect of retrieving experience.

The pre-answer check ran on every question. The first ten checks saw an empty bank. Each of questions 11–30 received three cards before its first answer request. The writer sent 29 requests with 29 received replies and added 29 cards, with cumulative totals of 9, 19 and 29 after the three ten-case windows. New E kept returned writer text in the bank with no content or schema gate. Embedding uses the first 2,000 characters. Retrieval delivers the full card. Cards may mention benchmark case details and released answers from previous cases.

[Per-question CSV](per_question.csv) · [Questions, options, answers, tool traces](case_details.json) · [Cards and writer receipts](experience_receipts.json) · [Summary and usage](summary.json) · [Protocol](protocol.json) · [Source](source)

Run python verify_saved.py to verify the published aggregates and retrieval receipts without inference. The included scorer depends on the experiment's shared MedRAX modules. The recorded cost proxy is not a provider invoice.

The benchmark is [Stanford AIMI CheXBench](https://huggingface.co/datasets/StanfordAIMI/chexbench), OpenI subset. Original images are referenced by [source link](outgoing_scope.json). Image files remain local under the [Open-i sharing guidance](https://openi-vip.nlm.nih.gov/faq) and [Indiana collection terms](https://openi.nlm.nih.gov/contactus).
