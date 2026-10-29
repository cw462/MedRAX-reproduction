"""R5: a question-specific retriever, entirely inside experiments/.

Why this exists
---------------
The frozen `FrozenPool.search` tokenizes only the boundary entry's coarse
`features` tags (["finding","laterality","multi_image","vqa"]). Few tag
combinations exist, so many questions collapse onto the same ranking: on the 29
frozen validation questions it produced only 7 distinct injected blocks, with 12
questions sharing one identical block. A memory block that is identical for 12
different questions cannot be transferring per-question information.

What this does
--------------
The pool deliberately stores hashes instead of question text, but every record
carries `source_question_id`, and the frozen training *inputs* file holds those
question texts. Joining record -> training question text recovers real lexical
signal without touching the pool, any hashed module, or any label.

Measured offline on the frozen validation set: 7 -> 29 distinct top-3 blocks,
largest identical group 12 -> 1, 17 distinct rank-1 memories.

Guards kept from the frozen path
--------------------------------
The same-case exclusion, the outcome filter, the `excluded` leakage flag and the
question/image digest checks are all still applied. Only the ranking signal
changes. This is a declared method arm, not a repair of the frozen retriever.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from memory_core.schema import digest
from memory_pipeline.core import Boundary, _context, canonical_bytes

STOPWORDS = set("""a an the of in on at to for with and or is are was were be been being this that these those
which what how does do did can could would should may might will shall about into from as by it its
patient case image show shows shown seen following best answer choice option select""".split())


def tokenize_text(text):
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


def bm25_rank(query_tokens, docs, k1=1.5, b=0.75):
    """docs: list of (record, token_list). Returns [(score, record)] descending."""
    n = len(docs)
    if not n:
        return []
    avg = sum(len(t) for _, t in docs) / n
    df = Counter()
    for _, tokens in docs:
        for word in set(tokens):
            df[word] += 1
    out = []
    for record, tokens in docs:
        counts = Counter(tokens)
        score = 0.0
        for word in set(query_tokens):
            count = counts[word]
            if not count:
                continue
            idf = math.log(1 + (n - df[word] + 0.5) / (df[word] + 0.5))
            score += idf * count * (k1 + 1) / (count + k1 * (1 - b + b * len(tokens) / avg))
        if score > 0:
            out.append((score, record))
    out.sort(key=lambda pair: (-pair[0], pair[1]["memory_id"]))
    return out


class TextRetrievalPool:
    """Drop-in for FrozenPool: same payload()/search() surface, better ranking."""

    def __init__(self, payload, training_inputs):
        self._payload = payload
        self._boundary = Boundary(canonical_bytes(payload["boundary"]))
        self._records = payload["records"]
        rows = {}
        for line in Path(training_inputs).read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["question_id"]] = row
        self._training_rows = rows
        self._docs = {}
        for record in self._records:
            row = rows.get(record["source_question_id"])
            if row is not None:
                self._docs[record["memory_id"]] = tokenize_text(row["question"])

    def payload(self):
        return self._payload

    def coverage(self):
        return {"records": len(self._records),
                "records_with_training_text": len(self._docs),
                "training_rows": len(self._training_rows)}

    def search(self, query, *, top_k=3, min_score=0.0, include_failures=False,
               summary_mode=False):
        if not isinstance(query, dict) or not {"question_id", "question", "images",
                                               "available_tools"} <= set(query):
            raise ValueError("Retrieval query needs question_id, question, images and available_tools")
        if top_k not in (1, 3, 5):
            raise ValueError("Use declared validation retrieval settings")
        source = self._boundary.lookup(query["question_id"])
        if source["excluded"]:
            raise ValueError("Query question is excluded by the leakage manifest")
        if (digest(query["question"]) != source["question_sha256"]
                or digest(query["images"]) != source["image_references_sha256"]):
            raise ValueError("Query must exactly match isolated visible input, without appended labels")

        keep = {"correct"} if not include_failures else {"correct", "incorrect", "invalid", "error"}
        docs = []
        for record in self._records:
            if record["source_case_hash"] == source["case_hash"]:
                continue
            if record["task_outcome"] not in keep:
                continue
            tokens = self._docs.get(record["memory_id"])
            if tokens:
                docs.append((record, tokens))

        ranked = bm25_rank(tokenize_text(query["question"]), docs)
        hits = []
        for score, record in ranked:
            if score < min_score:
                continue
            hits.append({"memory_id": record["memory_id"], "score": score,
                         "context": _context(record, summary_mode,
                                             include_outcome=include_failures)})
            if len(hits) >= top_k:
                break
        return hits
