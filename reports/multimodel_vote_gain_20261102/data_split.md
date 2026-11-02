# Frozen data split

This publication prepares the experiment and freezes its split. It does **not** report a completed experiment or start inference. No held-out question text, image bytes, or reference labels are included here.

| Partition | Explicit cases | Questions |
| --- | ---: | ---: |
| Source metadata | 609 | 2,500 |
| Historically exposed cases excluded | 187 | 758 |
| Eligible after exclusions | 422 | 1,742 |
| Tuning | 99 | 402 |
| Frozen held-out test | 241 | 1,002 |
| Unassigned eligible reserve | 82 | 338 |

The deterministic seed is `20261102`. Selection shuffles whole case groups and retains every question from each selected case. The requested approximately 400/1,000-question sizes therefore become **402/1,002**, without trimming questions from a case. The actual split has not been changed for publication. Exact shared image paths or source URLs are grouped across case IDs before assignment; none caused an additional historical exclusion in this data. Case `548` has a question with no image path and is explicitly marked incomplete; that case was already excluded by historical exposure.

The source is the complete `metadata.jsonl.new`: 2,500 valid question records with 609 distinct explicit `case_id` values. The older `metadata.jsonl` has 2,363 valid records followed by a truncated record and was not used. The paper reports 675 cases, whereas this supplied metadata yields 609 explicit IDs; the reason for that discrepancy has not been established. We do not invent 66 case IDs, infer them from question-ID prefixes, or describe this source as a confirmed identical case inventory to the paper.

“Historically exposed” means actual benchmark question/image content used in model calls, training seeds or reflections, retrieved candidate content (including candidates not ultimately injected), injected experiences, or published historical reports. The exclusion union includes actual experience-pool records and older validation subsets. Merely storing or preprocessing a full source-data partition is not model exposure. The complete content-free boundary registry and isolated source reference stores are recorded separately, rather than treating every indexed ID as exposed. Actual scored predictions, feedback, seed reflections, and retrieval records remain exposure evidence. There are no unresolved historical references in the frozen manifest. Legacy fields named `case_hash` that actually held other hashes were resolved only through explicit question-ID context.

These exclusions establish case separation under the supplied explicit IDs and available historical records. They **do not** exclude model pretraining contamination, prove patient-level independence, or establish that the 609-case inventory matches the paper's 675-case inventory. Image contents were not hashed or scanned to infer duplicate patients. The selected tuning/test images were checked only for local availability: all 222/540 unique image paths existed. No correctness or cumulative evaluation score was used to select the split.

The generation inputs retain only `question_id`, `case_id`, the complete question/options, relative image paths, and aligned figure labels. References are saved separately for the scorer; they are not published here or supplied as model inputs. This is process/file separation, not a claim of an operating-system access boundary.

Published records:

- [manifest.json](splits/manifest.json): complete frozen case assignment, counts, ordering policy, and limitations.
- [history_exclusions.json](splits/history_exclusions.json): all 187 excluded cases and their relative historical evidence paths. Schema 2 interns repeated paths in `source_files`; each `case_source_indices` integer is a zero-based index into that table. The transformation is lossless and reduces the approximately 8 MB original without changing exclusions.
- [tune.question_ids.json](splits/tune.question_ids.json) and [test.question_ids.json](splits/test.question_ids.json): exact question membership, without question text, images, or labels.

In the provenance table, paths beginning with `reports/` refer to this repository. Other root names identify archived historical exports; they are provenance aliases, not public download links. Private absolute filesystem paths and credentials are not included.
