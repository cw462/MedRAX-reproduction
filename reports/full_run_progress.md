# V3 execution checkpoint

Updated 2026-10-27. The full experiment is **in progress**, with no complete paper reproduction, heldout memory comparison or demonstrated memory gain. Existing results remain unchanged.

**Current priority, clarified by the user:** stop new paid question answering until all remaining tools are downloaded, integrity-verified and tested with real server inference. The completed two/three-tool five-case batches are functional checks only and will not be included as the formal full-tool baseline.

| Phase | Evidence and current state |
|---|---|
| P0 audit | Complete image integrity/overlap audit; original case splits retained; validation30 frozen. GPU, fixed sources, environments, API pricing and the existing budget ledger checked. [Data audit](data-audit-v3-2026-10-27.md). |
| P1 protocol | Historical 50 paired questions and selected ten-question cap follow-up retained. New validation30 repetitions and classifier-description control have not run. |
| P1 real multiple tools | Two-tool and three-tool functional checks completed on the same five train cases. The second run exposed a batch-tool request exceeding the inherited limit and ending the arm; [details](three-tool-functional-check-2026-10-27.md). No formal full-tool baseline is claimed. |
| Remaining tool deployment | Original segmentation has an earlier real standalone smoke. CheXagent, LLaVA-Med and MAIRA-2 loaders have offline checks; large fixed-revision weights are downloading. Their real GPU inference and Agent integration are not yet verified. |
| P2 trajectory pool | Target is at least 150 eligible training cases when resources permit. The two-tool functional batch has zero successful Agent outcomes and the three-tool check has one; neither is presented as the formal full-tool R0 pool. No success pool is claimed. |
| P3 success retrieval | Not run. Strict real-trace ingestion and frozen retrieval are being implemented. Historical single-tool outcomes cannot be presented as full-tool R0 trajectories. |
| P4 summaries / credit | No real summarizer or paired credit experiment. Clinical evidence remains unknown; credit remains null. |
| P5 actions / conflicts / capacity | No real ablations. Candidate selection, comparable conflicts and capacity controls remain required. |
| P6 heldout / full paper benchmark | Not run; see [heldout status](heldout_results.md). |
| P7 external / online | Not run; see [external status](external_results.md). |

The earlier first-ten training-repeat proposal was superseded before execution by V3's validation protocol. No paid calls were made under that superseded proposal. Tool availability is always reported separately from actual selection and valid return.

Large tool dependencies use separate environments to preserve the already executed report/classifier runtime: CheXagent Transformers 4.40.0, LLaVA-Med 4.45.2, MAIRA-2 4.51.3. Import checks do not establish successful model inference. MAIRA-2 access was granted following the user's explicit authorization; its scoped read credential is stored privately outside the repository and is never published.

The next sequence is to finish/download-verify the remaining assets, run their real standalone checks, integrate the complete tool registry with explicit process/GPU management, freeze a common protocol, then build and evaluate memory using the predeclared development controls. Stop and preserve pending work when the original budget cannot reserve the next request. See [budget and time](budget_and_runtime.md) and [known deviations](reproduction_deviations.md).
