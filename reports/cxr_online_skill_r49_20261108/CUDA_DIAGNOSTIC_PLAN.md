# R49: one isolated CheXagent CUDA diagnostic

Status: **prepared, not executed**. The current R49 stream remains stopped after 40 committed questions. Execution requires the actual completed DeepSeek diagnostic review and a recorded scope under the user's existing R49 authorization. No new user approval is claimed, and this plan does not authorize automatic R49 recovery.

## Purpose and current evidence

The expert tool for ordinal 41, `chexbench_rad_restruct_0163`, failed with `CUDA error: device kernel image is invalid` during a recorded CheXagent generation. Its current prediction and feedback were not saved. All 94 Agent, 13 META and two embedding requests are closed. The original failed tool result, 40 predictions, first completed window, original exits and dependency-repair history remain intact; no scores, rewards or Skill contents were consulted for this diagnostic decision.

Read-only metadata identifies RTX 3090 / compute 8.6, driver 535.230.02, PyTorch 2.2.1 with CUDA 12.1, Transformers 4.40.0 and compiled PyTorch architectures including sm_86. Forty earlier R49 expert generations completed, including the preceding q0162. This does not prove why q0163 failed. Driver/runtime family versions and architecture metadata do not establish compatibility of every loaded operator.

The complete failed stderr exists (416,615 bytes); its earlier omission from the small local snapshot was a download-size limit. Both the failed and preceding healthy logs contain 1,584 no-op meta-parameter warning entries of the same type. Those warnings are not a failure-specific diagnosis. Neither stderr contains the swallowed CUDA traceback. The original tool catches the generation exception and returns it as failed analysis metadata.

The existing `visual_forward_calls=0` counter cannot locate the failure: pinned model code calls `visual.encode`, which invokes `self.forward` directly and can bypass an ordinary module forward hook. The diagnostic will preserve and expose the actual generation exception rather than infer a location from that counter. [Pinned visual source](https://huggingface.co/StanfordAIMI/CheXagent-2-3b/blob/8f19b53a2eceda4c33b0acec6c81fbc293ad80d0/modeling_visual.py), [PyTorch hook invocation](https://docs.pytorch.org/docs/main/generated/torch.nn.Module.html#torch.nn.Module.forward).

## Exact action

| Item | Fixed diagnostic scope |
|---|---|
| New directory | `/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r49_cuda_diagnostic_20261108/attempt_1` |
| Interpreter / worker | Existing `.venv-chexagent/bin/python` and existing R49 `cxr_vqa_tool_worker.py` execution function |
| Backend | `chest_xray_expert` |
| Image | The original failed selection's `CXR729_IM-2288-1001.png`, at its unchanged bound path |
| Exact tool question | “Are there any signs of pleural effusion, pneumothorax, or pleural thickening in the image?” |
| Model / vision revision | CheXagent `8f19b53a2eceda4c33b0acec6c81fbc293ad80d0`; XraySigLIP `f0edbf5d90dba44edb7f4f96d8663537cb0749bf` |
| Generation | Original BF16 / deterministic one-beam generation / 512 new-token limit |
| Resource | Physical GPU1 only; refuse launch if used memory is at least 500 MiB or free disk is below 3 GiB |
| Wall-time guard | Preserve the existing tool timeout (600 seconds by default); terminate only this isolated attempt on timeout, with no reissue |
| Added debug flags | Subprocess-only `CUDA_LAUNCH_BLOCKING=1`, `TORCH_SHOW_CPP_STACKTRACES=1` |
| Calls | Exactly one local tool invocation; **zero Agent, META, embedding or other model API calls** |
| Network | Socket and Requests network access blocked; local snapshots only; no API credential supplied |
| Records | Unique request/plan/scope/review/started/PID/exit, full stdout/stderr, raw result/events/provenance and captured generation traceback |

CUDA's asynchronous execution can report an error later than its launch. Synchronous launching is used here only to improve localization; it is not a demonstrated repair. A diagnostic-only wrapper records the generation traceback and re-raises the original exception without changing the model result, arguments or failure predicate. [PyTorch CUDA execution semantics](https://docs.pytorch.org/docs/main/notes/cuda.html#asynchronous-execution).

## Execution controls

The private helper is `local_assets/diagnose_r49_chexagent_cuda_once.py`, with `stage`, `launch` and read-only `status` modes. Staging prepares a new request/runner; it performs no inference. Before launch, the root must supply the actual review record `local_assets/r49_cuda_failure_20261108/DIAGNOSTIC_REVIEW_READY.json` and `DIAGNOSTIC_EXECUTION_SCOPE.json`. The latter records existing R49 technical-diagnosis authorization, zero API calls, one isolated tool call, no original-run modifications and no automatic resume. These records must not claim a new explicit user approval.

Launch uses an exclusive lock and an atomic send-intent record. A previous `started.json` forbids another launch even if no result or exit was saved. Busy-resource rejection occurs before this intent, so no attempted tool invocation is hidden. The helper does not reset a GPU, kill a task, install packages, change precision/attention, clear caches, alter model assets, edit the frozen worker, read annotation vaults or add byte/pixel/hash gates. Existing record-only tool-cache naming mechanisms are not rewritten.

## Interpretation and next decision

On failure, preserve the new evidence and stop; there is no retry loop. On success, report only one completed fresh diagnostic process. Neither outcome supplies a replacement answer or silently converts the original failed tool record into usable evidence. The diagnostic output is not fed into current R49 inference, Skill learning or scoring.

Any later restoration of the R49 stream needs a separate concrete protocol decision and actual review that preserves the original failed attempt. Changes to libraries, model versions, environment behavior or paid comparison arms are outside this diagnostic's scope. R48 remains independently stopped and is not modified by this work.
