# Three-tool functional check: an exposed budget-handling problem

This run is a **functional check only**, not a formal full-tool baseline. Following the user's clarification, no new paid evaluation will run until the remaining tools finish downloading, pass integrity checks and execute successfully on the server. The two- and three-tool five-case batches remain separate diagnostic records and must not be merged into a formal baseline.

The same predeclared first five memory-training cases were run with original classifier, original report generation and original segmentation available. The 1024 output cap, four model-call limit, two total tool-call limit, original arm ordering and two-stage prompts were unchanged. Tool selection remained autonomous. Execution ran from **22:58:44 to 23:02:36 Asia/Shanghai**, about **3m51s**, excluding initialization.

| Observation | Direct | Three-tool Agent |
|---|---:|---:|
| Correct / fixed planned denominator | 2/5 | 1/5 |
| Valid final answers | 5 | 4 |
| API errors | 0 | 0 |
| Tool-budget-exceeded outcomes | 0 | 1 |
| Actual API requests | 10 | 13 |
| Actual validated classifier calls | 0 | 5 |
| Actual validated report calls | 0 | 4 |
| Actual validated segmentation calls | 0 | 1 |

The fifth Agent case requested classifier, segmentation and report in one response. The first two tools executed and returned valid structures; the third request was blocked by the inherited two-tool limit. The exception ended the arm before a final answer. Thus the old single-tool-era limit and exception handling are unsuitable as an unexamined full-tool protocol. The trace distinguishes the third **requested** tool from an actual execution; no blocked call is counted as a tool return. No remaining medical result or final answer was fabricated.

This is a concrete execution issue to address before a formal comparison. A revised protocol must explicitly handle an exhausted tool budget, preserve valid earlier observations where possible, keep hard resource limits, record unexecuted requests honestly, and be applied equally to all compared methods. Existing results will not be rewritten after that change.

The Agent's 1/5 versus the earlier two-tool 0/5 is not a segmentation benefit: the samples were repeated without a controlled repetition design, most Agent cases selected only classifier and report, and one arm ended early. Clinical evidence remains unknown and step credit remains null. One successful outcome is not a validated memory-method result.

The independent process wrapper measured CUDA allocation from initialization through completion: **1,059,137,024 bytes peak PyTorch allocated memory** and **1,312,817,152 bytes peak PyTorch reserved memory** on one RTX 3090. This measures this process's PyTorch memory, not every process or driver allocation on the card. Wrapper timing including initialization was approximately 240 seconds. The other GPU was not used by this run.

Incremental conservative occupancy was **CNY 0.98522**, taking the shared total from **20.04406 to 21.02928**, with **78.97072 remaining**. The earlier unknown-timeout reservation remains included; actual provider billing is still unavailable.

| Artifact | SHA256 |
|---|---|
| Manifest | `8f07fbaa6b1f8342485bab0f490ccd0c966988e86a8cc64004bd141484dce4c1` |
| Result journal | `7fee8d3eb54a15f0b4894273617e5c18f3580df0c9f6a40efbf98bbf6c162112` |
| Summary | `208131aaa23943eccf7c279cbd783eea7908c7c0e644c2f053ad6f97dd0084f5` |
| GPU wrapper source | `8df194cd62b71b2c07c587a254c25b862fe75fd96b1f73255d107cf5957faa23` |

`experiments/profile_entry.py` wraps `multi_tool_eval.py` without changing inference parameters. This batch adds `--segmentation-checkpoint` and uses its own new output directory. All reference scoring occurred afterward in the separate offline scorer; no heldout evaluation occurred.
