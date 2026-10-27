# Isolated real-tool workers

`worker_bridge.py` and `medical_tool_worker.py` connect a main Agent to local
LLaVA-Med, MAIRA-2 and CheXagent processes through private stdin/stdout JSONL.
They do not implement a substitute model, HTTP endpoint, clinical fallback, or
paid API client. The existing `multi_tool_eval.py`, `diagnostic_eval.py` and
tool/ledger sources are unchanged. New six-tool orchestration must explicitly
integrate these proxies; the older three-tool argument validator cannot simply
accept them as additional entries.

Current implementation status is synthetic integration tests only. Before a
six-tool Agent run, require complete asset verification and a real standalone
smoke for each large tool, then a real bridge invocation for each. A successful
`describe` handshake only proves class metadata can be imported; it explicitly
reports `model_loaded=False`.

## Minimal caller interface

In the main Agent environment (generic path placeholders):

```python
from pathlib import Path
from worker_bridge import WorkerSpec, WorkerPool, make_proxy

specs = [
    WorkerSpec('llava', '/envs/llava/bin/python', '/official/MedRAX',
               cache_dir='/models/hf_llava'),
    WorkerSpec('maira', '/envs/maira/bin/python', '/official/MedRAX',
               cache_dir='/models/hf_maira'),
    WorkerSpec('chexagent', '/envs/chexagent/bin/python', '/official/MedRAX',
               snapshot='/models/chexagent/main-fixed-snapshot',
               vision_snapshot='/models/chexagent/vision-fixed-snapshot',
               asset_manifest='/private/chexagent_approved_source_manifest.json'),
]
# Construct only from frozen inference inputs; never include gold/explanations.
cases = {'current-case': {'/authorized/image.png': PRE_RECORDED_SHA256}}

with WorkerPool(specs, cases=cases, run_root='/private-runs/new-bridge-session',
                gpu_lock='/private-locks/physical-gpu-1.lock', gpu='1',
                startup_timeout=120, timeout=600) as pool:
    proxies = [make_proxy(pool, name) for name in
               ('llava_med_qa', 'xray_phrase_grounding', 'chest_xray_expert')]
    pool.set_case('current-case')  # trusted runner selects the current case
    # Bind these BaseTools alongside the three original small tools.
    # The original Agent can call proxy.invoke(params) synchronously.
    result = proxies[0].invoke({'image_path': '/authorized/image.png',
                               'question': 'Describe the visible findings.'})
    audit = proxies[0].last_worker_audit
```

`WorkerPool.invoke(name, params, request_id=...)` returns `(original_result,
safe_audit)` and lets the runner supply a stable logical tool-request ID.
`make_proxy` returns a BaseTool that returns only the original result; its
`last_worker_audit` holds the matching safe audit and is cleared before every
attempt, including failed attempts. The official name, description, JSON
argument schema and `return_direct` flag are obtained from the official class
in its correct environment. The reconstructed main-process Pydantic schema
must have exactly the same canonical hash or binding fails. The worker's
verified JSON can also be used with `official_function_schema(descriptor)`.

The main runner must keep one shared per-case tool/model budget, wrap every
external model invocation in the existing MoneyGuard, preserve original
prompts/tool results, and attach each worker audit to the corresponding actual
tool call. Worker-local inference does not consume the external API ledger.
Do not give each proxy its own independent copy of the case tool budget.

## Resource and failure behavior

Use GPU 0 for the small tools if resources permit. The large-model pool owns
one OS file lock for physical GPU 1 and permits one active child at a time.
Switching tools sends shutdown, waits for process exit, and only then starts
the replacement. If needed it terminates/kills only its own child and waits
again. Process exit releases CUDA allocations; `empty_cache()` alone is not
used as an unload. LLaVA and MAIRA reuse their model for consecutive calls.
CheXagent's existing audited entry point couples loading and inference, so
this first bridge starts a new process and reloads it for **every call**;
initialization time is recorded separately from inference.

Timeout, child death, malformed/oversized JSON, changed schema/source, invalid
serialization, response identity mismatch and invalid input raise
`WorkerFailure`. They are never converted into a medical answer. Original
tool returns with `analysis_status='failed'` remain original tool returns.
There is no automatic retry. A durable request intent is written before
execution; duplicate request IDs in that pool session are refused. Failures
record whether execution may have started. The trusted experiment runner owns
cross-session resume and must not silently replay unresolved intents in a new
pool root. Every pool root is new, so previous private outputs are not replaced.
Freeze `pool.policy_snapshot()` in the run manifest; it records the image,
token, single-image, text, timeout and loading restrictions without private
paths. It does not contain mutable current-case or model-loaded state.

All worker subprocesses receive a small environment allowlist without parent
API keys/HF tokens. Network connects are blocked. Library stdout is redirected
to a private stderr file; only framed protocol messages reach stdout. Typed
JSON preserves tuple/list distinctions, dictionary order and finite scalar
types, so `str(original_result)` is preserved after transport. No pickle or
arbitrary object reconstruction is used. Raw results/private paths remain in
private pipe/journal files; public traces should only contain the returned
safe audit, which keeps clinical evidence `unknown`.
`raw_content_logged=False` refers only to that safe audit. The ignored
`.private.json` evidence files do contain full original tool results and must
not be uploaded as public summaries.

## Explicit execution restrictions

The proxy advertises the original schema, while the runner enforces these
additional frozen execution policies. They are protocol restrictions, not
claims of unrestricted original-tool equivalence:

- Every image must belong to the current case's pre-recorded path/SHA256 map.
  Checks occur in parent and child, at actual Pillow image open, and after the
  invocation. No additional kwargs, labels, or explanations are accepted.
- Text is treated as inference text only. Model image/control-tag injection is
  rejected, and Pillow cannot read a path supplied solely inside text.
- LLaVA must receive an explicit image despite its upstream optional field.
  Its fixed upstream 500-token generation setting is unchanged.
- MAIRA uses synchronous invocation with exactly 300 output tokens. Constant
  grayscale images are rejected to avoid its original normalization divide by
  zero. Upstream async behavior is not patched.
- CheXagent is restricted to one image, a nonempty prompt of at most 512
  characters and a requested output bound of 1–512 tokens. Multi-image support
  requires a separately audited adapter; it is not silently reduced to the
  first image.

No-finding returns, nonempty text, coordinate consistency and successful
execution remain distinct from medical correctness. Tool availability does
not force the Agent to call every tool on every question.

```bash
python -B -m unittest discover -s experiments -p 'test_worker_bridge.py' -v
```
