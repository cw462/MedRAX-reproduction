"""V9 retrieval: static hybrid K and independently re-indexed B/C action memory.

The B and C indexes contain source *question stems* only. Neither source options,
labels, old retrieval hits, nor source report prose are indexed. Clinical knowledge
uses the supplied V8 BM25 + actual neural dense + RRF implementation and its scope
filters. Missing neural dependencies fail before a paid run; there is no downgrade.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import re

from skill_policy import _topic_tags
from skill_render import CAPABILITY_TOOLS


GROUPS = {"D", "DK", "DKB", "DKC"}
OPTION_START = re.compile(r"(?m)^\s*(?:[A-F][.)：:]|\([A-F]\))\s*")
GENERIC_TERMS = {"diagnosis", "likely", "probable", "most", "following", "best", "correct",
                 "abnormal", "abnormality", "abnormalities", "observed", "shown", "show",
                 "seen", "present", "finding", "findings", "feature", "features", "describe",
                 "radiographic", "radiological", "provided", "given", "based", "appears", "appearance",
                 "condition", "conditions", "represents", "indicates", "indicate", "primary", "main"}
SPATIAL_TOOLS = {"chest_xray_expert", "llava_med_qa", "xray_phrase_grounding", "image_visualizer"}


def stem_of(question):
    return OPTION_START.split(str(question), maxsplit=1)[0].strip()


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _strings(value):
    if value is None:
        return []
    return [value] if isinstance(value, str) else [str(x) for x in value]


def task_types(question):
    """Question-only task projection; no answer or result-informed routing."""
    stem = stem_of(question).lower()
    patterns = {
        "localization": r"\b(where|location|located|locali[sz]|lobe|zone|intercostal|rib)\w*\b",
        "comparison": r"\b(compar|chang|prior|previous|follow.up|resolv|resolut|larger|smaller)\w*\b",
        "relation": r"\b(relation|relative|adjacent|contact|versus|between|mediastinal shift)\w*\b",
        "diagnosis": r"\b(diagnos|differential|disease|etiology|cause)\w*\b",
        "classification": r"\b(classif|type|categor|pattern)\w*\b",
        "description": r"\b(characteri[sz]|describ|morpholog|feature|appear)\w*\b",
        "detection": r"\b(detect|finding|abnormal|present|absent|evidence|sign)\w*\b",
    }
    return sorted(name for name, pattern in patterns.items() if re.search(pattern, stem)) or ["detection"]


def modality_of(question):
    stem = stem_of(question).lower()
    if re.search(r"\b(ct|ctpa|hrct|computed tomography)\b", stem):
        return "ct"
    # This adapter is registered for the ChestAgentBench chest-radiograph inputs.
    return "radiograph"


def _observation_projection(value):
    """Tool diagnostic text remains a reported hypothesis, never an image fact."""
    if not value:
        return []
    if isinstance(value, str):
        return [{"text": value, "status": "hypothesis", "source": "tool_report_unverified"}]
    if isinstance(value, dict):
        value = [value]
    out = []
    for item in value:
        if isinstance(item, str):
            out.append({"text": item, "status": "hypothesis", "source": "tool_report_unverified"})
            continue
        projected = {k: item[k] for k in ("text", "entity", "attribute", "value", "status",
                     "source", "evidence_ref", "laterality", "time", "image_id", "object_id") if k in item}
        if not projected.get("text") and "result" in item:
            projected["text"] = json.dumps(item["result"], ensure_ascii=False, default=str)
            projected["tool_name"] = item.get("tool_name")
        # Affirmed tool-generated diagnoses do not become observed facts by relabeling.
        grounded = item.get("evidence_type") == "direct_image_observation" and item.get("evidence_ref")
        if not grounded:
            projected["status"] = "hypothesis"
            projected["source"] = item.get("source", "tool_report_unverified")
        else:
            projected["status"] = {"observed_present": "present", "observed_absent": "absent"}.get(
                item.get("status"), item.get("status", "unresolved"))
        out.append(projected)
    return out


def _token_estimate(block):
    return math.ceil(len(block.encode("utf-8")) / 4) if block else 0


def _bounded_skill(record, budget):
    """Keep an actionable C skill inside the shared context budget, by field."""
    def compact(value, limit):
        text = re.sub(r"\s+", " ", str(value)).strip()
        return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " ..."
    lines = [f"[C SKILL {record['skill_id']}; applicability is a hypothesis]",
             "If current evidence establishes this trigger: " + compact(record.get("trigger", ""), 290)]
    lines += ["Action: " + compact(action.get("operation", ""), 220) + " -> " +
              CAPABILITY_TOOLS.get(action.get("capability"), "UNAVAILABLE")
              for action in record.get("actions", [])[:2]]
    lines += ["Check: " + compact(check, 170) for check in record.get("checkpoints", [])[:2]]
    lines += ["Need: " + compact(need, 100) for need in record.get("required_information", [])[:2]]
    lines += ["Fallback if " + compact(f.get("when", ""), 90) + ": " + compact(f.get("operation", ""), 150)
              for f in record.get("fallbacks", [])[:1] if isinstance(f, dict)]
    lines += ["Avoid: " + compact(x, 150) for x in record.get("avoid", [])[:1]]
    selected = []
    for line in lines:
        if len("\n".join(selected + [line])) + 1 <= budget:
            selected.append(line)
    # A conditional wrapper without an action AND an observable check is not memory use.
    if not any(x.startswith("Action:") for x in selected) or not any(x.startswith("Check:") for x in selected):
        return ""
    return "\n".join(selected) + "\n"


class V9Retriever:
    def __init__(self, knowledge_pack, pool_path, skills_path, dense_model_path=None,
                 questions_path=None, max_chars=3000, top_k=3):
        self.pack = Path(knowledge_pack)
        self.max_chars, self.top_k = int(max_chars), min(3, int(top_k))
        if self.max_chars < 500 or self.top_k < 1:
            raise ValueError("retrieval requires max_chars >= 500 and 1 <= top_k <= 3")
        self.core = _load_module("_v9_knowledge_core", self.pack / "retrieval/core.py")
        self.index_dir = self.pack / "retrieval/index_hybrid"
        self.meta = _read_json(self.index_dir / "metadata.json")
        self.cards = [self.core.canonical_card(json.loads(line)) for line in
                      (self.index_dir / "cards.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        if not self.meta.get("dense"):
            raise RuntimeError("V9 registered K arms require a real dense index")
        import numpy as np
        self.vectors = np.load(self.index_dir / "dense_vectors.npy", allow_pickle=False)
        dense = _load_module("_v9_knowledge_dense", self.pack / "retrieval/dense.py")
        config = self.meta["dense"]
        self.encoder = dense.Encoder(config["backend"], config["model"], dense_model_path,
                                     False, config.get("onnx_file", "onnx/model_quint8_avx2.onnx"))
        if self.vectors.shape != (len(self.cards), config["dimension"]):
            raise ValueError("dense index/card dimensions disagree")
        self.dense_cache = str(dense_model_path) if dense_model_path else None

        envelope = _read_json(pool_path)
        self.pool = envelope["payload"]
        self.records = self.pool["records"]
        self.skills = _read_json(skills_path)["skills"]
        self.boundary = {str(x["question_id"]): x for x in self.pool["boundary"]["entries"]}
        if questions_path is None:
            raise ValueError("training inference questions are required to re-index B/C by stem")
        self.questions = {}
        paths = questions_path if isinstance(questions_path, (list, tuple)) else [questions_path]
        for path in paths:
            for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                if set(row) != {"question_id", "question", "images"}:
                    raise ValueError("source index accepts inference-only rows, never labels")
                self.questions[str(row["question_id"])] = row
        missing_b = [r["source_question_id"] for r in self.records if str(r["source_question_id"]) not in self.questions]
        missing_c = [qid for s in self.skills for qid in s.get("source_trace_ids", []) if str(qid) not in self.questions]
        if missing_b or missing_c:
            raise ValueError(f"missing source stems for B/C: {sorted(set(missing_b + missing_c))[:8]}")
        self.b_documents = [stem_of(self.questions[str(r["source_question_id"])]["question"]) for r in self.records]
        self.c_documents = ["\n".join(stem_of(self.questions[str(qid)]["question"])
                                     for qid in s.get("source_trace_ids", [])) for s in self.skills]
        self.b_index = self.core.BM25(self.b_documents)
        self.c_index = self.core.BM25(self.c_documents)

    def describe(self):
        return {"knowledge_mode": "hybrid_bm25_dense_rrf", "knowledge_cards": len(self.cards),
                "dense": self.meta["dense"], "dense_cache": self.dense_cache,
                "b_records": len(self.records), "c_skills": len(self.skills),
                "experience_index": "source_question_stem_only", "max_chars_per_layer": self.max_chars,
                "top_k": self.top_k, "current_case_fact_inference": False}

    def _boundary_check(self, row):
        qid = str(row["question_id"])
        entry = self.boundary.get(qid)
        if entry is None:
            raise ValueError("query missing from declared split/case boundary")
        if entry.get("split") != "validation" or entry.get("excluded"):
            raise ValueError("V9 diagnostic adapter accepts nonexcluded validation cases only")
        return entry

    def _knowledge(self, query):
        vector = self.encoder.encode([self.core.query_text(self.core.normalized_query(query))])[0]
        if len(vector) != self.vectors.shape[1]:
            raise ValueError("query encoder dimension differs from saved real dense index")
        scores = self.vectors @ vector
        result = self.core.retrieve(self.cards, query, {"top_k": self.top_k}, self.index_dir,
                                    scores, "hybrid_bm25_dense_rrf", ["V9 require_dense; no lexical downgrade"])
        header = ("[K: CONDITIONAL CLINICAL KNOWLEDGE]\nThese are evidence requirements, not patient facts. "
                  "A diagnosis mentioned here remains a hypothesis until current images support it.\n")
        parts, ids = [], []
        for hit in result["hits"]:
            card = hit["knowledge_card"]
            text = (f"[{hit['knowledge_id']}; source {hit['source_id']} pages {','.join(hit['source_pages'])}]\n"
                    f"Rule: {card['summary_en'] or card['summary_zh']}\n"
                    f"Required current evidence: {'; '.join(card['required_patient_evidence'])}\n"
                    f"Limitations: {'; '.join(card['limitations'])}\n")
            if len(header) + sum(len(p) for p in parts) + len(text) > self.max_chars:
                result["rejected"].append({"knowledge_id": hit["knowledge_id"], "reasons": ["render_budget"]})
                continue
            parts.append(text)
            ids.append(hit["knowledge_id"])
        result["rendered_ids"] = ids
        # Raw cards/source passages stay in the replay/audit result, not the prompt.
        return header + "\n".join(parts) if parts else "", ids, result

    def _scope_experience(self, row, source_ids, document, required_tools, query, evidence_needs):
        entry = self._boundary_check(row)
        reasons = []
        for source_id in source_ids:
            source_entry = self.boundary.get(str(source_id))
            if not source_entry or source_entry.get("split") != "memory_train" or source_entry.get("excluded"):
                reasons.append("source_not_admitted_training_case")
            elif source_entry["case_hash"] == entry["case_hash"]:
                reasons.append("same_case")
        if not required_tools:
            reasons.append("no_action_capability")
        elif not required_tools <= query["tools"]:
            reasons.append("unavailable_required_tool")
        if modality_of(document) != query["modality"]:
            reasons.append("modality_mismatch")
        if not set(task_types(document)).intersection(query["task"]):
            reasons.append("task_mismatch")
        # A generic 'most likely diagnosis' overlap alone does not establish relevance.
        overlap = set(self.core.tokens(document)).intersection(self.core.tokens(query["stem"])) - GENERIC_TERMS
        if not overlap:
            reasons.append("no_specific_stem_overlap")
        current_topics, source_topics = _topic_tags(query["stem"]), _topic_tags(document)
        if current_topics and source_topics and not current_topics.intersection(source_topics):
            reasons.append("finding_scope_mismatch")
        needs = " ".join(evidence_needs).lower()
        if re.search(r"\b(left|right|laterality|locali[sz]|location|relation|position|rib|intercostal|compar|prior|previous)", needs):
            if not required_tools.intersection(SPATIAL_TOOLS):
                reasons.append("action_cannot_supply_spatial_or_comparison_evidence")
        return sorted(set(reasons))

    def _experience(self, row, tools, group, evidence_needs, observations=None):
        is_b = group == "DKB"
        records = self.records if is_b else self.skills
        documents = self.b_documents if is_b else self.c_documents
        index = self.b_index if is_b else self.c_index
        stem = stem_of(row["question"])
        query = {"stem": stem, "tools": set(tools), "modality": modality_of(stem), "task": task_types(stem)}
        projected_observations = _observation_projection(observations)
        # Reports may make a trigger worth verifying; this is never proof the trigger is true.
        scope_text = stem + " " + " ".join(evidence_needs) + " " + " ".join(
            str(o.get("text", "")) for o in projected_observations)
        scores = index.scores(stem)
        audit = {"representation": "B_structured_actions" if is_b else "C_conditional_skill",
                 "index_text": "source_question_stem_only", "query_text": stem,
                 "rejected": [], "ranked": [], "rendered_ids": []}
        selected, ids = [], []
        header = ("[E: TRAINING ACTION EXPERIENCE; NO CURRENT PATIENT FACTS]\n"
                  "Use only to choose actions/checkpoints for the current unresolved attributes. "
                  "Historical findings, side, position, time, diagnoses and output values cannot be transferred.\n")
        order = sorted(range(len(records)), key=lambda i: (-scores[i], str(records[i].get("memory_id", records[i].get("skill_id", "")))))
        for i in order:
            record = records[i]
            mid = record["memory_id"] if is_b else record["skill_id"]
            source_ids = [str(record["source_question_id"])] if is_b else [str(x) for x in record.get("source_trace_ids", [])]
            if is_b:
                required_tools = {step["tool_name"] for step in record.get("steps", [])}
            else:
                caps = set(record.get("required_capabilities", [])) | {a.get("capability") for a in record.get("actions", [])}
                required_tools = {CAPABILITY_TOOLS.get(c, "unknown:" + str(c)) for c in caps}
            reasons = self._scope_experience(row, source_ids, documents[i], required_tools, query, evidence_needs)
            if scores[i] <= 0:
                reasons.append("zero_stem_bm25")
            if is_b and record.get("task_outcome") != "correct":
                reasons.append("B_source_not_successful_training_trajectory")
            if not is_b:
                if not source_ids:
                    reasons.append("missing_source_trace")
                if record.get("step_credit") is not None:
                    reasons.append("unsupported_step_credit")
                if not record.get("checkpoints") or not record.get("actions"):
                    reasons.append("not_conditional_action_skill")
                declared_tasks = set(self.core.tasks(record.get("task_types", [])))
                if declared_tasks and not declared_tasks.intersection(query["task"]):
                    reasons.append("skill_task_scope_mismatch")
                trigger_topics = _topic_tags(record.get("trigger", ""))
                if trigger_topics and not trigger_topics.intersection(_topic_tags(scope_text)):
                    reasons.append("trigger_finding_not_supported_by_current_task_or_reports")
                trigger_sides = set(re.findall(r"\b(left|right)\b", record.get("trigger", "").lower()))
                current_sides = set(re.findall(r"\b(left|right)\b", scope_text.lower()))
                if trigger_sides and not trigger_sides <= current_sides:
                    reasons.append("source_bound_trigger_side_not_established")
                if re.search(r"\b(patient has|diagnosis is|answer is|correct option)\b", " ".join(
                        str(a.get("operation", "")) for a in record.get("actions", [])), re.I):
                    reasons.append("source_diagnosis_assertion")
            if reasons:
                audit["rejected"].append({"id": mid, "reasons": sorted(set(reasons)), "score": scores[i]})
                continue
            audit["ranked"].append({"id": mid, "score": scores[i], "source_ids": source_ids,
                                     "required_tools": sorted(required_tools)})
            if len(selected) >= self.top_k:
                continue
            if is_b:
                sequence = []
                for step in record["steps"]:
                    if not sequence or sequence[-1] != step["tool_name"]:
                        sequence.append(step["tool_name"])
                text = (f"[B {mid}]\nIf the current task has an unresolved attribute matching the selected source-task scope, "
                        f"the historical action sequence was: {' -> '.join(sequence)}.\n"
                        "Choose only the step capable of observing that attribute; bind its parameters to current images, "
                        "object, side and time. Check its actual returned content for the requested attribute. "
                        "If missing, generic or conflicting, keep the attribute unresolved and stop or choose another available action. "
                        "Historical execution success does not verify a diagnosis or a step's contribution.\n")
            else:
                text = _bounded_skill(record, self.max_chars - len(header) - sum(len(p) for p in selected) - 2)
                if not text:
                    audit["rejected"].append({"id": mid, "reasons": ["insufficient_budget_for_action_and_checkpoint"], "score": scores[i]})
                    continue
            if len(header) + sum(len(p) for p in selected) + len(text) > self.max_chars:
                audit["rejected"].append({"id": mid, "reasons": ["render_budget"], "score": scores[i]})
                continue
            selected.append(text)
            ids.append(mid)
        audit["rendered_ids"] = ids
        audit["abstained"] = not ids
        return header + "\n".join(selected) if selected else "", ids, audit

    def retrieve(self, row, observation_text, tools, group, evidence_needs=None):
        if group not in GROUPS:
            raise ValueError("unknown V9 diagnostic group")
        self._boundary_check(row)
        needs = _strings(evidence_needs)
        query = {"question_stem": stem_of(row["question"]), "visible_evidence": _observation_projection(observation_text),
                 "candidate_hypotheses": [], "missing_attributes": needs, "modality": modality_of(row["question"]),
                 "task": task_types(row["question"]), "population": "unknown"}
        result = {"group": group, "k_block": "", "e_block": "", "k_ids": [], "e_ids": [],
                  "k_audit": {"disabled": True}, "e_audit": {"disabled": True}, "query": query,
                  "token_count_method": "utf8_bytes_div4_estimate_not_provider_usage"}
        if group != "D":
            result["k_block"], result["k_ids"], result["k_audit"] = self._knowledge(query)
        if group in {"DKB", "DKC"}:
            result["e_block"], result["e_ids"], result["e_audit"] = self._experience(row, tools, group, needs, observation_text)
        result["k_token_estimate"] = _token_estimate(result["k_block"])
        result["e_token_estimate"] = _token_estimate(result["e_block"])
        return result
