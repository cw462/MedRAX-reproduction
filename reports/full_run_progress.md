# Execution checkpoint

Updated 2026-10-28 (Asia/Shanghai). The full experiment is **still incomplete**: there is no
paper reproduction, no heldout evaluation and no demonstrated general improvement. The first
end-to-end run of the memory pipeline on a hosted Qwen model is complete enough to report.

## What changed since the 2026-10-27 checkpoint

- The Codex execution budget was exhausted; work continued in the DeepSeek Harness.
- The central model is now `qwen3-vl-plus` (DashScope compatible endpoint) instead of
  `gpt-4o-2024-11-20`. Provider facts, capability probes and the account-arrears incident are
  in [qwen-provider-2026-10-28.md](qwen-provider-2026-10-28.md).
- A memory-agent runner, a provider ledger, a prompt-block renderer, an independent scorer and
  a paired comparison script were added (`experiments/memory_agent_eval.py`,
  `provider_ledger.py`, `provider_profile.py`, `memory_pipeline/injection.py`,
  `score_memory_runs.py`, `compare_memory_arms.py`).
- A 60-question training pool run and a 30-question validation baseline were completed; a
  frozen success pool (59 trajectories) was compiled. See
  [memory-agent-qwen-2026-10-28.md](memory-agent-qwen-2026-10-28.md).
- One server image flipped content in place (same size, same inode) and was healed; the
  compiler now counts such questions as `image_read_integrity_failure` instead of rejecting
  the whole run. See [data-read-integrity-2026-10-28.md](data-read-integrity-2026-10-28.md).

| Phase | Evidence and current state |
|---|---|
| P0 audit | Complete image integrity/overlap audit; splits unchanged; validation30 frozen. [Data audit](data-audit-v3-2026-10-27.md). |
| P1 protocol | Qwen profile frozen and hash-pinned; output ceiling caused two aborted R1 attempts (documented). Classifier-description control still not rerun. |
| P1 real multiple tools | Classifier + report verified with the Qwen Agent; segmentation available but not used in these runs. CheXagent/LLaVA-Med/MAIRA-2 remain unverified and unused. |
| P2 trajectory pool | **First real success pool built**: 60 training questions, 59 compiled trajectories, 34 successful / 25 failed outcomes, one integrity-skipped question. `success_retrieval_ready = true`. |
| P3 success retrieval | **Implemented and exercised**: protocol/tool-version-checked retrieval, same-case exclusion, bounded structural prompt block, per-question retrieval log. |
| P4 summaries / credit | Deterministic rule summary mode exists (`r2`), LLM summarisation does not. No paired step-credit experiment; `clinical_evidence` is `unknown` and `step_credit` is `null` throughout. |
| P5 actions / conflicts / capacity | Not implemented. No candidate selection, conflict review or capacity-limited update. |
| P6 heldout | Not run; `heldout_test` untouched. |
| P7 external | Not run; authorization still required. |

## Open issues

1. The output ceiling in the frozen provider profile (2048 completion tokens) is lower than
   Qwen3-VL-Plus occasionally produces; the ledger permanently blocks on such a call. Raising
   it changes the protocol hash and would require rebuilding the pool.
2. One validation question triggers the ceiling deterministically and was removed from the R1
   input (documented deviation, not an outcome-based exclusion).
3. Step credit, action selection, conflict review and capacity updates remain unimplemented, so
   R4-R7 in the plan have no result.
4. Pricing is an assumption (4 / 12 CNY per million tokens), not a provider quote.
5. The server is not a trusted bit-exact store; hashes must be re-verified before every stage.
