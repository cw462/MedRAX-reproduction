# Execution checkpoint

Updated 2026-10-29 (Asia/Shanghai). The seven-tool memory comparison has now run end to end.
It is still **not** a paper reproduction, not a heldout evaluation and not clinical validation.

## Seven-tool phase (2026-10-29)

- Registry: classifier, report generator, segmentation, CheXagent-2-3B VQA, LLaVA-Med 7B,
  image visualizer, DICOM processor 鈥?7 of the paper's 9 tools.
- Missing: `xray_phrase_grounding` (MAIRA-2 loads in bf16 but its grounding post-processing
  fails on the pinned transformers 4.45 runtime) and `chest_xray_generator` (no public
  RoentGen weights).
- Pool: 60 training questions 鈫?60 trajectories, 173 real tool steps, 25 successful.
- Validation: the same 29 questions under four arms (R0/R1/R2/R3), same model, prompts, tools
  and limits. Raw accuracy 37.9% / 48.3% / 41.4% / 55.2%; among answered cases 55.0% / 51.8% /
  46.2% / 57.1%. R0 failed 9 cases on the call budget, R3 only 1.
- Report: [memory-agent-qwen-7tools-2026-10-29.md](memory-agent-qwen-7tools-2026-10-29.md).

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
| P1 real multiple tools | **Seven tools wired and exercised**: classifier, report, segmentation, CheXagent VQA, LLaVA-Med, image visualizer, DICOM processor. MAIRA-2 grounding and chest-X-ray generation remain blocked (see above). |
| P1 real multiple tools | Classifier + report verified with the Qwen Agent; segmentation available but not used in these runs. CheXagent/LLaVA-Med/MAIRA-2 remain unverified and unused. |
| P2 trajectory pool | Seven-tool pool: 60 training questions, 60 compiled trajectories, 173 tool steps, 25 successful / 20 incorrect / 15 budget-truncated. `success_retrieval_ready = true`. |
| P3 success retrieval | Implemented and exercised in R1/R3: tool-version- and same-case-filtered retrieval, bounded structural block, 29/29 questions hit. |
| P4 summaries / credit | Deterministic rule summary arm (R2) run; no LLM summarisation and no step-credit experiment. `clinical_evidence` unknown, `step_credit` null throughout. |
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
