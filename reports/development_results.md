# Development results

All current paid results use memory-training development cases. They are not heldout estimates. Original denominators and failures are retained.

The recent two/three-tool five-case batches are functional checks only. Formal full-tool comparisons are deferred until all tools pass real server validation, following the user's clarification.

| Configuration | Planned questions per arm | Direct correct | Agent correct | Interpretation |
|---|---:|---:|---:|---|
| Single classifier, 512 cap | 50 | 24/50 | 24/50 | [Historical restricted diagnostic](diagnostic50-2026-10-27.md) |
| Single classifier, selected truncation cases, 1024 cap | 10 | 5/10 | 6/10 | [Selected diagnostic follow-up](length-cap-followup-2026-10-27.md); no repeated-512 control |
| Classifier + report, original first five, 1024 cap | 5 | 1/5 | 0/5 | [Real two-tool execution check](multi-tool-first5-2026-10-27.md); one direct timeout |
| Classifier + report + segmentation, same first five | 5 | 2/5 | 1/5 | [Three-tool functional check](three-tool-functional-check-2026-10-27.md); one Agent tool-budget failure |
| Qwen3-VL-Plus, classifier + report, 60 training questions (pool build) | 60 | – | 35/60 (58.3%) | [Memory pipeline run](memory-agent-qwen-2026-10-28.md); pool source, not a test estimate |
| Qwen3-VL-Plus, same tools, 30 validation questions (R0 baseline) | 30 | – | 12/29 (41.4%) | Same report; one provider timeout |
| Qwen3-VL-Plus, same tools, 29 validation questions + success-trajectory memory (R1) | 29 | – | see report | Paired against R0 on shared questions |

These rows use different selected subsets and are not a single accuracy-improvement curve. The two-tool Agent executed both tools successfully on all five cases but answered all five incorrectly. This is evidence against equating tool execution with task success, not evidence that the report tool caused an accuracy decrease. The batch supplies zero successful Agent examples for success retrieval.

The frozen validation30 protocol, classifier-description single-factor control, true multi-tool training pool, R1 retrieval, R2/R3 summaries, R4 step-credit estimation, R5 action choices, R6 conflict review and R7 capacity/update comparisons have no completed real result yet. Synthetic tests validate software boundaries only.
