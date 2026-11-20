# M5-RRSI-Acc-TTL v4: preliminary results

The run was paused on 2026-11-20 at 11:20 Beijing time. It saved **15 first-pass predictions with scoring and memory updates** out of **848 planned questions**. It completed **14 search rounds**, and **4 rounds promoted a new program version**. The search after question 15 was incomplete when the run paused.

| Dataset | Completed first-pass questions | Planned questions | Published first-pass accuracy |
| --- | ---: | ---: | --- |
| SLAKE | 15 | 114 | Pending retrieval from the paused instance |
| VQA-RAD | 0 | 116 | Pending |
| CheXBench | 0 | 618 | Pending |
| **Total** | **15** | **848** | **Pending** |

## Accepted program versions

Round numbers start at one.

| Completed search round | Promoted program commit |
| ---: | --- |
| 7 | `fbe933dd04c3a143f18e0721257a36f9abe75613` |
| 11 | `246cc8c8923df70fc1e7624bf5f851960037b789` |
| 12 | `0ecf4115a64298dbb7e12cee840d0384c64e1df0` |
| 13 | `97187f534acb0c2517496566b00796a6b5e079f3` |

The version promoted in round 13 remained active through the pause. These promotions passed the within-round historical replay comparison. The first-pass accuracy records remain on the instance, which was shut down after the pause receipt was saved. Full-stream performance remains unevaluated.

## Run protocol

The experiment ran one Qwen3.7-Plus M5-RRSI-Acc-TTL arm with the original 11-tool setup, frozen R55 question order, original images, and the aligned-correct scorer. Memory started empty. For each question, the system locked its first-pass prediction before reading the reference answer and immediately updating memory.

The search adapter called the official `rrsi.loop.Run.round()` from [Google Research RRSI](https://github.com/google-research/rrsi/tree/be50316e1db05914068a973f322770ef08ed7ba1). A round compared candidate programs to the current program using up to 20 previously completed questions and two replay trials per program. Each trial followed the original question order. The budget allowed two candidate slots per round and at most 847 rounds. Only the locked first-pass predictions enter the primary denominator.

The initial M5 program commit was `eef4215e5eeee83f71b1a679fddd8922c062df8a`. The parallel execution version inherited the first 13 predictions and 13 completed rounds. From question 14, it could draft two candidates concurrently and evaluate two candidates with two independent replay trials each. Question order within each replay trial remained sequential.

[Checkpoint summary](checkpoint_summary.json) records the counts from the pause receipt and the accepted commit lineage from the completed-round records. Program commits identify revisions in the experiment's upstream checkout.
