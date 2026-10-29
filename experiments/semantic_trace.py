"""Task 1: capture *semantic* tool observations during a real run (V4 plan §5).

Why this exists
---------------
The existing traces keep only execution facts: tool name, a hash of the arguments,
output lengths and a hash of the content. That is enough to prove a tool ran, but
it cannot be summarised into a reusable skill, because the actual findings,
measurements and locations are gone.

This module derives, per tool call, the compact semantic content a summariser can
actually use, and writes it to a private JSONL next to the run. It never guesses:
if a tool returned something it cannot parse, the record says so instead of
inventing a finding, and every clinical claim keeps `evidence_status` separate
from the task outcome.

Nothing here re-derives medical correctness. A tool's statement is recorded as a
tool statement.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

MAX_TEXT = 1200


def _text(value, limit=MAX_TEXT):
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] if len(text) > limit else text


def _unwrap(result):
    """Split an official tool return into (payload, metadata)."""
    if isinstance(result, tuple) and len(result) == 2:
        payload, meta = result
        return payload, (meta if isinstance(meta, dict) else {})
    return result, {}


def _number(value):
    """Accept Python numbers and numpy scalars alike (torchxrayvision returns float32)."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _classifier_facts(payload):
    """Top findings with their scores, plus the operating-point caveat.

    The official classifier returns a bare mapping of pathology -> score (numpy
    float32 values), not a wrapper with a "scores" key, so the mapping itself is
    the score table.
    """
    scores = None
    if isinstance(payload, dict):
        for key in ("scores", "predictions", "probabilities", "pathologies"):
            if isinstance(payload.get(key), dict):
                scores = payload[key]
                break
        if scores is None:
            numeric = {k: _number(v) for k, v in payload.items()}
            if numeric and all(v is not None for v in numeric.values()):
                scores = numeric
    if not isinstance(scores, dict) or not scores:
        return {"note": "classifier output not parseable into named scores"}
    ranked = sorted(((_number(v), str(k)) for k, v in scores.items()
                     if _number(v) is not None), reverse=True)
    return {
        "top_findings": [{"finding": k, "score": round(v, 4)} for v, k in ranked[:5]],
        "score_semantics": "operating_point_normalised_scores_not_calibrated_probabilities",
    }


def _report_facts(payload):
    if isinstance(payload, dict):
        findings = payload.get("findings")
        impression = payload.get("impression")
        if findings or impression:
            return {"findings": _text(findings), "impression": _text(impression)}
    if isinstance(payload, str) and payload.strip():
        return {"report_text": _text(payload)}
    return {"note": "report output not parseable"}


def _vqa_facts(payload):
    if isinstance(payload, dict):
        for key in ("response", "answer", "text", "output"):
            if isinstance(payload.get(key), str) and payload[key].strip():
                return {"answer_text": _text(payload[key])}
    if isinstance(payload, str) and payload.strip():
        return {"answer_text": _text(payload)}
    return {"note": "vqa output not parseable"}


def _grounding_facts(payload):
    """Grounded phrases with their image-space boxes."""
    boxes = []
    if isinstance(payload, dict):
        for item in payload.get("predictions") or []:
            phrase = item.get("phrase") if isinstance(item, dict) else None
            container = (item.get("bounding_boxes") or {}) if isinstance(item, dict) else {}
            coords = container.get("image_coordinates") or []
            for box in coords:
                try:
                    boxes.append({"phrase": _text(phrase, 200),
                                  "box_xyxy_normalised": [round(float(x), 4) for x in box]})
                except (TypeError, ValueError):
                    continue
    if not boxes:
        return {"grounded_regions": [], "note": "no grounded region returned (legitimate negative)"}
    return {"grounded_regions": boxes[:6],
            "note": "boxes are model output; not a diagnosis and not independently verified"}


def _segmentation_facts(payload, meta):
    regions = []
    if isinstance(payload, dict):
        for key in ("regions", "masks", "metrics"):
            value = payload.get(key)
            if isinstance(value, (list, dict)) and value:
                regions = value if isinstance(value, list) else [value]
                break
    return {"region_summary": _text(regions, 600) if regions else None,
            "artifact": "mask file under the run's private temp dir" if meta.get("artifact_dir") else None}


def semantic_observation(kind, result):
    """Compact, summariser-usable content of one tool return."""
    payload, meta = _unwrap(result)
    failed = bool(payload.get("error")) if isinstance(payload, dict) else False
    if kind == "classification":
        facts = _classifier_facts(payload)
    elif kind == "report":
        facts = _report_facts(payload)
    elif kind in ("vqa", "llava"):
        facts = _vqa_facts(payload)
    elif kind == "grounding":
        facts = _grounding_facts(payload)
    elif kind == "segmentation":
        facts = _segmentation_facts(payload, meta)
    else:
        facts = {"note": "utility tool: no clinical content"}

    execution = "failed" if failed else (meta.get("analysis_status") or "unknown")
    return {
        "tool_kind": kind,
        "execution_status": execution,
        "failed_return": failed,
        "facts": facts,
        # keep the plan's separation explicit rather than implied
        "evidence_status": "tool_statement_unverified",
        "clinical_evidence": "unknown",
        "step_credit": None,
    }


class SemanticTraceWriter:
    """Append-only JSONL of semantic observations for one run."""

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")
        self.written = 0

    def record(self, *, question_id, tool_name, tool_version, arguments, kind, result,
               elapsed_ms=None, phase=None):
        observation = semantic_observation(kind, result)
        row = {"question_id": str(question_id), "tool_name": tool_name,
               "tool_version": tool_version, "phase": phase,
               "arguments": {k: _text(v, 300) for k, v in (arguments or {}).items()
                             if k in ("image_path", "phrase", "question", "prompt", "max_new_tokens")},
               "elapsed_ms": elapsed_ms,
               "observation": observation}
        self._handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        self._handle.flush()
        self.written += 1
        return row

    def close(self):
        try:
            self._handle.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
