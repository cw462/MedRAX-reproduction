# Training execution memory

This module converts completed tool-call journals into structured training experiences
and retrieves them for the Agent. It does not call a model API or read reference labels.
The Qwen prototype has used a real training pool; aggregate results are recorded in
`reports/qwen-memory-initial-2026-10-28.md` and subsequent comparison reports.

## Hashes are records

Source, model, protocol, input and pool digests are recorded for tracing a run.
They are not locks: editing code or changing those digests does not invalidate memory,
discard a trajectory, require rebuilding the pool or block loading and retrieval.
Historical expected hashes may be supplied as optional audit information.

```python
pool = FrozenPool.load("/private/pool.json")
audit = pool.hash_audit()  # Actual digest and observed changes; no rejection.
```

`expected_sha256=...` remains an optional compatibility argument. It never requires
equality with the current pool. Pool and implementation updates can be loaded together.
An explicit pool version and previous-pool digest can describe an update without being
requirements to edit its content. Saving uses a new filename to preserve existing files.

## Data and execution boundaries

- Training membership, case IDs, excluded-case lists and strict field schemas remain
  checked. Validation and heldout trajectories cannot become training experiences.
- Completed runs must contain the declared questions, matched starts/terminals and
  thread identities, supported tool kinds and actual invocation counts. Zero actual
  tool calls create no experience. Updated source/tool/image hashes are audit notes.
- Outcome sidecars contain question ID, arm and a coarse outcome plus file metadata.
  Reference letters, predictions, explanations and report prose are not accepted.
- Execution validity, whole-task correctness, clinical evidence and step credit remain
  distinct. Clinical evidence is unknown and step credit is null in this module.
- Output lengths and tool sequences do not reconstruct missing reasoning or reports.

## Compile and retrieve

```bash
python -m memory_pipeline --splits /private/prepared_v2 --exclusions /private/exclusions.json --run /private/completed-training-run --output /private/new-pool --pool-version 1 --outcomes /private/scorer-outcomes.json
```

`--exclusions-sha256` is optional. Compilation records actual file digests and observed
differences. The older `allow_image_integrity_skip` argument remains compatible; a hash
difference no longer causes skipping or rejection.

Retrieval accepts the current question ID, visible question/images, available tools
and protocol metadata. It excludes every experience from the current case and checks
that the tools actually used in a trajectory are available. It does not require exact
version hashes or equality of the entire registered tool set. Protocol digests may
differ. Default retrieval uses known successful training outcomes; include_failures
also admits known failures. Unknown outcomes are never treated as success. Heldout
queries require a separate evaluation adapter and remain disabled here.

Summary mode produces deterministic execution summaries, not an LLM medical summary.
`injection.build_memory_block` renders only permitted context fields, without source
case/question identifiers, answer text or raw report prose. The Agent entry is
`experiments/memory_agent_eval.py`: memory arms require --pool, with no required hash.
Resuming after code/hash updates records the new plan in `plan_history.jsonl`, while
keeping the original manifest and completed question outcomes.

## Offline checks

```bash
python -m unittest memory_pipeline.test_pipeline memory_core.test_memory_core -v
python -m unittest discover -s experiments -p 'test_recorded_run_journal.py' -v
```

Tests cover older hashes/implementations, updated tool versions, continued retrieval,
source/label boundaries, case exclusion, actual execution accounting and resumption
without repeating completed API work. Synthetic tests are software checks only.
