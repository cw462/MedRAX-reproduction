# Train-only execution memory foundation

This module compiles completed, auditable tool executions into an immutable local
pool. It does not call an API, read reference-label files, modify an Agent, or claim
an accuracy improvement. It is an execution-fact foundation for the V3 experiment,
not a completed implementation of its memory ablations.

Status at this delivery: offline tests and a read-only in-memory compilation check
of the completed two-tool first-five logs have passed. No real pool snapshot was
created, no memory-assisted Agent experiment was run, and no formal successful
trajectory pool is available. The compilation check established five trajectories
and ten tool executions, with task outcomes left unknown inside this module.

The compiler currently understands the original classifier/report multi-tool
first-five format (optionally segmentation) and the separate historical
single-classifier diagnostic format. `multitool_original` means that the declared
tools used their original implementations; it does **not** mean the complete
paper tool set was available. Those two pool families cannot be mixed. A future
worker-backed or full-tool run requires an explicitly reviewed format adapter and
a new protocol/pool version.

## Admission and evidence

- The split manifest, audit index, and strict three-field inference inputs are
  verified with the existing `memory_core` registry. No labels are opened.
- The caller must independently pin the V3 leakage-exclusion manifest SHA-256.
  Its bound `image_audit.jsonl` is checked too. Each run question's image byte
  hashes must match that question's frozen input, even if execution renamed files.
  Cross-split exact-duplicate case exclusions apply to new pools; membership in
  the original training split alone is insufficient.
- Only completed runs with consistent manifest, summary, started/terminal pairs,
  thread IDs, denominator, and actual per-tool counters are accepted. Each actual
  step must have argument/image hashes, execution timing, and the initialized
  tool's provenance version. Zero tool calls create no trajectory. An argument
  rejected before invocation is not counted as an execution.
- Tool output validity describes execution and output structure. Clinical
  evidence is always `unknown`; step credit is always JSON `null`. A correct final
  answer never turns an individual step into medically verified evidence.
- Original reasoning and report text were not retained by these source runs.
  Their hashes cannot reconstruct that text. The compiler stores safe structures
  and source references; it does not invent the missing content.
- File hashes establish consistency with supplied artifacts, not authenticity of
  an external producer. The independently pinned artifacts remain the trust root.

Task outcomes default to `unknown`. A separate evaluator may supply this strict
sidecar; reference answers, predicted letters, and explanations are forbidden:

```json
{
  "schema_version": 1,
  "source_run_manifest_sha256": "64 hexadecimal characters",
  "source_results_sha256": "64 hexadecimal characters",
  "split_manifest_sha256": "64 hexadecimal characters",
  "outcomes": [
    {"question_id": "training question ID", "arm": "agent", "task_outcome": "correct"}
  ]
}
```

Allowed outcomes are `correct`, `incorrect`, `invalid`, `error`, and `unknown`.
Correct/incorrect rows require a completed response. The compiler checks the
sidecar's file bindings and training membership; the independent evaluator is
responsible for the outcome judgment. Adding outcomes creates a new immutable
pool rather than changing an existing snapshot.

## Compile without API calls

Run from the repository root, replacing paths and the independently verified
exclusion hash:

```powershell
python -m memory_pipeline --splits C:\path\prepared_v2 --exclusions C:\path\audit_v3\leakage_exclusion_manifest.json --exclusions-sha256 PINNED_SHA256 --run C:\path\multi_tool_first5_v1 --output C:\path\memory_execution_first5_v1 --pool-version 1
```

The output directory must be new. It receives `pool.json`, `compile_report.json`,
and a `.gitignore` that keeps private evidence out of Git. For a separately scored
version add `--outcomes C:\path\safe_outcomes.json`, increment `--pool-version`,
and supply `--previous-pool-sha256` from the previous report. Historical single-tool
compilation requires the explicit `--family historical_classifier` flag.

Load with `FrozenPool.load(path, expected_sha256=independently_pinned_pool_sha)`.
The payload and implementation source hashes must match. In-memory payload copies
cannot mutate a frozen pool, and saving refuses to overwrite an existing file.

## Retrieval boundary and current limits

`FrozenPool.search` accepts exactly `question_id`, `question`, `images`,
`available_tools` (name-to-version-hash mapping), and `protocol_sha256`. Visible
question/image references must exactly match the frozen input. The query's entire
available tool set and versions must match; the protocol includes prompts, model,
limits, package versions, and source hashes. Every same-case trajectory is removed
before BM25 scoring, including other questions from that case. Heldout queries
are deliberately disabled until a separate locked final-evaluation adapter exists.

The default search admits only independently marked successful trajectories.
Unknown outcomes never count as successes. `include_failures=True` additionally
admits known incorrect/invalid/error outcomes for a later failure-memory condition.
The output context excludes case/question/thread identifiers, audit references,
outcome flags, answer text, raw options, and raw reports. Returned memory IDs and
scores are audit metadata; an eventual Agent adapter must pass only `context`.

Search uses fixed BM25 over a small vocabulary of operational task features and
observed tool names. Features come from the question stem before the options.
This is a coarse lexical baseline, not medical semantic retrieval or an image
embedding. `summary_mode=True` emits a **deterministic execution-rule summary**,
explicitly marked as such. It is not an LLM summary and cannot claim causal step
credit or reconstruct missing medical reasoning.

Not yet implemented: live Agent memory injection, real-tokenizer token-matched
random controls, learned retrieval, LLM success/failure summaries, clinical step
judgments, heldout evaluation, or reported performance gains. No mock token counts
are accepted as a substitute for a future real tokenizer.

## Offline tests

```powershell
python -m unittest memory_pipeline.test_pipeline -v
```

Tests use synthetic inference only. They check label-I/O guards (`builtins.open`
and `io.open`, including `Path.open`), extra label fields, modified visible inputs,
validation/heldout rejection, same-case exclusion, exact-duplicate quarantine,
image substitution, execution/count/version proofs, family isolation,
unknown/null semantics, safe context structures, independent snapshot hashes,
immutability, and the disabled heldout boundary.
