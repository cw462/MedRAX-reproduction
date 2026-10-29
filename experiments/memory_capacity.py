"""R7: capacity/diversity control over what a memory block is allowed to contain.

What the data says
------------------
Only 18 of the 60 frozen pool records are ever retrieved by the 29 validation
questions, and rank 1 uses just 7 distinct memories. So a hard capacity cap would
remove almost nothing. The real redundancy is *content*: many records share the
same feature tags and the same tool sequence, so a top-3 block can spend two of
its three slots on near-identical memories.

So R7 here is a diversity filter, not a size cap: before rendering, collapse hits
whose memory signatures are near-duplicates and keep the highest-scoring
representative of each cluster. The block keeps its size budget but carries more
distinct evidence.

Faithfulness notes
------------------
* Similarity is computed only from what the pool already exposes (feature tags,
  tool names, execution outcomes). No labels, no question text.
* Filtering happens after retrieval, so the frozen ranking is untouched; this can
  only ever *remove* near-duplicates from a block.
* A dropped duplicate is recorded, never silently discarded.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


def memory_signature(record):
    """The coarse structural fingerprint the pool exposes for one trajectory."""
    tokens = set(record.get("features") or [])
    for step in record.get("steps") or []:
        tokens.add("tool:" + str(step.get("tool_name")))
        shape = step.get("observation_shape") or {}
        for key in shape:
            tokens.add("shape:" + str(key))
    tokens.add("outcome:" + str(record.get("task_outcome")))
    return frozenset(tokens)


def jaccard(a, b):
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def cluster_memories(records, threshold=0.85):
    """Greedy single-pass clustering over memory signatures."""
    clusters = []          # list of (representative_record, member_records)
    for record in records:
        signature = memory_signature(record)
        placed = False
        for representative, members in clusters:
            if jaccard(signature, memory_signature(representative)) >= threshold:
                members.append(record)
                placed = True
                break
        if not placed:
            clusters.append((record, [record]))
    return clusters


def select_diverse(hits, records_by_id, *, threshold=0.85, max_items=None):
    """Drop later hits that near-duplicate an already-kept memory.

    Returns (kept_hits, dropped_ids). Kept hits are already in score order.
    """
    kept, dropped, signatures = [], [], []
    for hit in hits:
        record = records_by_id.get(hit["memory_id"])
        if record is None:
            kept.append(hit)
            continue
        signature = memory_signature(record)
        if any(jaccard(signature, seen) >= threshold for seen in signatures):
            dropped.append(hit["memory_id"])
            continue
        kept.append(hit)
        signatures.append(signature)
        if max_items and len(kept) >= max_items:
            break
    return kept, dropped


class DiversePool:
    """Pool wrapper applying the R7 diversity filter after retrieval."""

    def __init__(self, inner, records, threshold=0.85):
        self._inner = inner
        self._by_id = {record["memory_id"]: record for record in records}
        self.threshold = threshold
        self.last_dropped = []

    def payload(self):
        return self._inner.payload()

    def search(self, query, **kwargs):
        hits = self._inner.search(query, **kwargs)
        kept, dropped = select_diverse(hits, self._by_id, threshold=self.threshold)
        self.last_dropped = dropped
        return kept


def _load_bundle(root):
    root = Path(root)
    payload = json.loads((root / "runs/memory_pool_v3/pool.json").read_text(encoding="utf-8"))["payload"]
    questions = [json.loads(line) for line in
                 (root / "data/memory_v1/inputs/validation_subset_v2.jsonl")
                 .read_text(encoding="utf-8").splitlines() if line.strip()][:29]
    return payload, questions


def main(root):
    payload, questions = _load_bundle(root)
    records = payload["records"]
    by_id = {r["memory_id"]: r for r in records}

    clusters = cluster_memories(records)
    sizes = Counter(len(members) for _rep, members in clusters)
    print(f"pool records: {len(records)}")
    print(f"signature clusters at threshold 0.85: {len(clusters)}")
    print(f"cluster size histogram: {dict(sorted(sizes.items()))}")
    print(f"largest cluster: {max(len(m) for _r, m in clusters)} memories")

    # how redundant are the blocks that were actually used in R3?
    retrieval = [json.loads(line) for line in
                 (Path(root) / "runs/val29_full_r3/retrieval.jsonl")
                 .read_text(encoding="utf-8").splitlines() if line.strip()]
    collapsed = 0
    per_question = []
    for row in retrieval:
        ids = row.get("memory_ids") or []
        kept, dropped = select_diverse([{"memory_id": i} for i in ids], by_id)
        collapsed += len(dropped)
        per_question.append((len(ids), len(kept), dropped))
    print(f"\nR3 blocks: {sum(q[0] for q in per_question)} memory slots over "
          f"{len(per_question)} questions")
    print(f"slots removed as near-duplicates: {collapsed}")
    questions_with_drop = sum(1 for q in per_question if q[2])
    print(f"questions whose block shrinks: {questions_with_drop}/{len(per_question)}")
    for qid, (before, after, dropped) in zip([r["question_id"] for r in retrieval], per_question):
        if dropped:
            print(f"  {qid:26s} {before} -> {after} dropped={len(dropped)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
