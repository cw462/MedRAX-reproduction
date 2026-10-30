"""V10 pre-action retrieval from static K and weakly supervised training actions.

The shared option-difference plan is input, never a current-case observation.
Only training stems, task/attribute tags and recorded tool execution structure
are indexed for B. No source answer, options or clinical tool prose is copied.
"""
from __future__ import annotations

from collections import Counter
import re

from v9_retrieval import (V9Retriever, GENERIC_TERMS, _strings, _token_estimate,
                          modality_of, stem_of, task_types)


GROUPS = {"V", "VK", "VKE"}
ATTRIBUTE_PATTERNS = {
    "laterality": r"\b(left|right|bilateral|unilateral|laterality|side)\b",
    "location": r"\b(location|located|lobe|zone|apical|apex|basal|base|hilar|hilum|retrocardiac|upper|lower|middle|intercostal)\b",
    "size": r"\b(size|small|large|enlarg|diameter|width|height|volume)\w*\b",
    "number": r"\b(number|multiple|single|solitary|count|two|three)\b",
    "morphology": r"\b(morpholog|shape|margin|border|wall|round|linear|reticul|cavit|calcif|opacity|opacities|pattern|appearance)\w*\b",
    "relation": r"\b(relation|adjacent|displac|shift|contact|overlap|pleural origin|silhouette)\w*\b",
    "comparison": r"\b(compar|prior|previous|change|interval|progress|resolv|stability|stable|view|projection)\w*\b",
    "presence": r"\b(presen|absen|detect|evidence|visible|finding|abnormal)\w*\b",
}
ANATOMY_PATTERNS = {
    "lung": r"\b(lung|pulmonary|lobe|lobar|parenchym|pneumonia|atelectasis|nodule)\w*\b",
    "pleura": r"\b(pleur|pneumothorax|effusion|costophrenic)\w*\b",
    "mediastinum": r"\b(mediastin|trache|hilar|hilum)\w*\b",
    "heart": r"\b(heart|cardiac|cardiomegal|cardiomediastinal)\w*\b",
    "diaphragm": r"\b(diaphragm|hemidiaphragm|subdiaphragm)\w*\b",
    "chest_wall": r"\b(chest wall|rib|stern|clavic|scapul|bone|skelet|pectus)\w*\b",
    "device": r"\b(tube|catheter|line|device|pacemaker|drain)\w*\b",
}
VISUAL_TOOLS = {"chest_xray_expert", "llava_med_qa", "xray_phrase_grounding", "image_visualizer"}
TOOL_CAPABILITIES = {
    "chest_xray_expert": "targeted visual question location morphology comparison",
    "llava_med_qa": "targeted visual question location morphology comparison",
    "xray_phrase_grounding": "localize target region box location",
    "image_visualizer": "view image crop region detail morphology",
    "chest_xray_classifier": "classification score presence hypothesis",
    "chest_xray_report_generator": "whole image description report hypothesis",
    "chest_xray_segmentation": "anatomic segmentation lung heart region size",
    "dicom_processor": "image orientation metadata view",
}
TASK_PATTERNS = {
    "localization": r"\b(locali[sz](?:ation|e|ed|ing)?|locat(?:e|ed|ion|ing)|where)\b|定位",
    "comparison": r"\b(compar(?:e|ed|ing|ison|ative)?|interval change|temporal change|follow[ -]up)\b|比较|對比|对比",
    "relation": r"\b(relation(?:ship)?s?|spatial relationship|spatial reasoning)\b|关系|關係",
    "diagnosis": r"\b(diagnos(?:is|es|tic|e|ing)|differential|etiology|aetiology)\b|诊断|診斷",
    "classification": r"\b(classif(?:y|ication|ied|ying)|categor(?:y|ization|isation|ize|ise))\b|分类|分類",
    "description": r"\b(descri(?:be|ption|ptive|bing)|characteri[sz](?:ation|e|ing)|morpholog(?:y|ical)|feature description)\b|描述|表征|特征",
    "detection": r"\b(detect(?:ion|ing|ed)?|presence|absence|recognition|identify|identification)\b|检测|檢測|识别|識別",
}


def tags(text, patterns):
    return sorted(key for key, pattern in patterns.items() if re.search(pattern, str(text), re.I))


def compact(value, limit=320):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " ..."


def canonical_tasks(value):
    """Normalize free-form model task prose, not only exact enum strings."""
    text = " ".join(_strings(value)).replace("_", " ")
    return tags(text, TASK_PATTERNS)


def plan_projection(row, plan=None, evidence_needs=None):
    """Allowlist a shared task plan; option labels/predicted choices are omitted."""
    plan = plan if isinstance(plan, dict) else {}
    differences = []
    for item in plan.get("option_differences", plan.get("discriminators", []))[:2]:
        if isinstance(item, dict):
            differences.append({"attribute": compact(item.get("attribute", ""), 90),
                                "question": compact(item.get("question", ""), 360)})
        else:
            differences.append({"attribute": "", "question": compact(item, 360)})
    stem = stem_of(row["question"])
    needs = _strings(plan.get("missing_attributes")) + _strings(evidence_needs)
    needs += [d["attribute"] for d in differences if d["attribute"]]
    task_description = " ".join(_strings(plan.get("task")))
    task = canonical_tasks(plan.get("task"))
    task_scope_source = "shared_plan"
    if not task:
        task = canonical_tasks(row.get("official_group"))
        task_scope_source = "official_group"
    if not task:
        task = task_types(stem)
        task_scope_source = "question_stem_fallback"
    anatomy = _strings(plan.get("anatomy")) or tags(stem, ANATOMY_PATTERNS)
    distinction_text = " ".join(d["attribute"] + " " + d["question"] for d in differences)
    target = " ".join([task_description, " ".join(task), " ".join(anatomy), distinction_text, " ".join(needs)])
    return {"task": task, "anatomy": anatomy, "option_differences": differences,
            "task_description": task_description, "task_scope_source": task_scope_source,
            "missing_attributes": list(dict.fromkeys(compact(x, 160) for x in needs if x)),
            "attribute_tags": tags(target or stem, ATTRIBUTE_PATTERNS),
            "anatomy_tags": tags(target + " " + stem, ANATOMY_PATTERNS),
            "target_text": target.strip() or stem,
            "recommended_view": plan.get("recommended_view", "full"),
            "is_patient_observation": False}


def action_card(record, question):
    """A per-trajectory card with observed execution and explicit causal limits."""
    stem = stem_of(question)
    steps = record.get("steps", [])
    sequence = [s["tool_name"] for s in steps]
    counts = Counter(sequence)
    outcome = record.get("task_outcome", "unknown")
    polarity = "success" if outcome == "correct" else "failure" if outcome in {"incorrect", "invalid", "error"} else "unknown"
    failed = [s["tool_name"] for s in steps if s.get("execution") in {"exception", "returned_invalid", "failed", "timed_out"}]
    cues = []
    if any(n > 1 for n in counts.values()): cues.append("repeated_tool_names_recorded_arguments_not_compared")
    if failed: cues.append("tool_failure_or_invalid_return_recorded")
    if outcome == "error": cues.append("whole_trajectory_error")
    if outcome == "incorrect": cues.append("whole_answer_incorrect_cause_unknown")
    return {"action_card_id": "B10_" + record["memory_id"], "memory_id": record["memory_id"],
            "source_question_id": str(record["source_question_id"]), "polarity": polarity,
            "task_outcome": outcome, "task": task_types(stem), "anatomy": tags(stem, ANATOMY_PATTERNS),
            "attributes": tags(stem, ATTRIBUTE_PATTERNS), "source_task": stem,
            "historical_tool_sequence": sequence, "failed_tools": sorted(set(failed)),
            "execution_observations": [{"tool": s["tool_name"], "execution": s.get("execution", "unknown"),
                "observation_shape": s.get("observation_shape", {}), "source_event_line": s.get("source_event_line")}
                for s in steps], "failure_cues": cues,
            "supervision": "whole_question_outcome_only", "clinical_observation_content": "unavailable_in_structured_pool",
            "step_credit": None, "causal_attribution": "unknown"}


class V10Retriever(V9Retriever):
    def __init__(self, knowledge_pack, pool_path, skills_path, dense_model_path=None,
                 questions_path=None, max_chars=2400, top_k=2):
        super().__init__(knowledge_pack, pool_path, skills_path, dense_model_path,
                         questions_path, max_chars, min(2, top_k))
        self.action_cards = [action_card(r, self.questions[str(r["source_question_id"])]["question"])
                             for r in self.records]
        self.action_documents = [" ".join([c["source_task"], " ".join(c["task"]),
            " ".join(c["anatomy"]), " ".join(c["attributes"]),
            " ".join(TOOL_CAPABILITIES.get(t, t) for t in c["historical_tool_sequence"])]) for c in self.action_cards]
        self.action_index = self.core.BM25(self.action_documents)

    def describe(self):
        result = super().describe()
        result.update(experience_index="training_task_anatomy_attributes_actual_tool_capabilities",
                      action_card_polarities=dict(Counter(c["polarity"] for c in self.action_cards)),
                      max_success_cards=1, max_failure_cards=1, step_credit=None,
                      retrieval_timing="after_shared_option_plan_before_roi_and_tools")
        return result

    def _knowledge_actions(self, query, target):
        vector = self.encoder.encode([self.core.query_text(self.core.normalized_query(query))])[0]
        if len(vector) != self.vectors.shape[1]:
            raise ValueError("query encoder dimension differs from saved real dense index")
        result = self.core.retrieve(self.cards, query, {"top_k": self.top_k}, self.index_dir,
            self.vectors @ vector, "hybrid_bm25_dense_rrf", ["V10 original dense encoder; discriminative task query"])
        header = ("[K: OBSERVATION RULES BEFORE ACTION SELECTION]\n"
                  "Use only relevant rules to choose where/what to inspect. These are not current patient facts.\n")
        blocks, ids = [], []
        for hit in result["hits"]:
            card = hit["knowledge_card"]
            # Planning/follow-up advice without an image observation is not a V10 rule.
            if set(card["task_scope"]) <= {"planning"}:
                result["rejected"].append({"knowledge_id": hit["knowledge_id"], "reasons": ["no_current_observation_rule"]})
                continue
            rule = card["summary_en"] or card["summary_zh"]
            evidence = "; ".join(card["required_patient_evidence"])
            if "comparison" in card["task_scope"]:
                action = "Compare the corresponding structure on the available full images/views; do not infer change if no comparable view exists."
            elif set(card["task_scope"]) & {"localization", "relation"}:
                action = "Locate the named structure on the full image, then inspect its boundary/neighbor relation on a crop with the full image retained."
            else:
                action = "Inspect the named feature at the target region with full-image context; ask a focused visual question about the competing attributes."
            text = (f"[{hit['knowledge_id']}; {hit['source_id']} pages {','.join(hit['source_pages'])}]\n"
                    f"Observe: {compact(evidence or rule, 240)}\n"
                    f"Distinguish: {compact(rule, 360)}\n"
                    f"Next action: {action}\n"
                    f"Limit: {compact('; '.join(card['limitations']), 200)}\n")
            if len(header) + sum(map(len, blocks)) + len(text) > self.max_chars:
                result["rejected"].append({"knowledge_id": hit["knowledge_id"], "reasons": ["render_budget"]})
                continue
            blocks.append(text); ids.append(hit["knowledge_id"])
        result.update(rendered_ids=ids, abstained=not ids,
                      action_target=target, query_is_observation=False)
        if not ids: result["abstention_reasons"] = ["no_renderable_relevant_observation_rule"]
        return header + "\n".join(blocks) if blocks else "", ids, result

    def _action_experience(self, row, tools, target):
        entry = self._boundary_check(row)
        tools = set(tools)
        query = target["target_text"]
        scores = self.action_index.scores(query)
        audit = {"representation": "B_positive_negative_action_cards", "index_text": "training_task_anatomy_attributes_actual_tool_capabilities",
                 "query_text": query, "rejected": [], "ranked": [], "rendered_ids": [],
                 "supervision": "whole_question_outcome_only", "step_credit": None}
        order = sorted(range(len(self.action_cards)), key=lambda i: (-scores[i], self.action_cards[i]["action_card_id"]))
        selected, selected_cards, ids, polarities = [], [], [], set()
        header = ("[E: TRAINING ACTION CARDS; USE BEFORE ROI/TOOL CHOICE]\n"
                  "Whole-question outcomes are weak supervision, not evidence of step causality. "
                  "Never copy source findings, side or answer. Use a relevant card to change one current action and state which change.\n")
        for i in order:
            card = self.action_cards[i]
            source = self.boundary.get(card["source_question_id"])
            available = set(card["historical_tool_sequence"]) & tools
            reasons = []
            if not source or source.get("split") != "memory_train" or source.get("excluded"):
                reasons.append("source_not_admitted_training_case")
            elif source["case_hash"] == entry["case_hash"]: reasons.append("same_case")
            if card["polarity"] == "unknown": reasons.append("unknown_training_outcome")
            if modality_of(card["source_task"]) != modality_of(row["question"]): reasons.append("modality_mismatch")
            if not available: reasons.append("no_available_recorded_action")
            if not set(card["task"]) & set(self.core.tasks(target["task"])): reasons.append("task_mismatch")
            if card["anatomy"] and target["anatomy_tags"] and not set(card["anatomy"]) & set(target["anatomy_tags"]):
                reasons.append("anatomy_mismatch")
            attribute_overlap = set(card["attributes"]) & set(target["attribute_tags"])
            specific_overlap = (set(self.core.tokens(card["source_task"])) & set(self.core.tokens(query))) - GENERIC_TERMS
            if not attribute_overlap and not specific_overlap: reasons.append("no_specific_ambiguity_overlap")
            if scores[i] <= 0: reasons.append("zero_action_bm25")
            if reasons:
                audit["rejected"].append({"id": card["action_card_id"], "score": scores[i], "reasons": sorted(set(reasons))})
                continue
            audit["ranked"].append({"id": card["action_card_id"], "score": scores[i], "source_ids": [card["source_question_id"]],
                "polarity": card["polarity"], "required_tools": sorted(available), "attribute_overlap": sorted(attribute_overlap)})
            if card["polarity"] in polarities: continue
            visual = sorted(available & VISUAL_TOOLS)
            action_tool = visual[0] if visual else sorted(available)[0]
            sequence = " -> ".join(dict.fromkeys(card["historical_tool_sequence"]))
            target_question = compact("; ".join(d["question"] for d in target["option_differences"]) or
                                      "; ".join(target["missing_attributes"]) or "the unresolved option-defining attribute", 240)
            if card["polarity"] == "success":
                action = (f"Consider the recorded compatible tool {action_tool}, asking specifically: {target_question}. "
                          "Bind its input to the current target region/view; compare every changed attribute, not only the most salient one.")
                observation = "Recorded execution: " + ", ".join(f"{x['tool']}={x['execution']}" for x in card["execution_observations"][:3])
            else:
                if card["failed_tools"]:
                    action = ("If the same execution failure occurs, switch to a compatible focused visual check instead of spending the remaining budget repeating it. ")
                elif "repeated_tool_names_recorded_arguments_not_compared" in card["failure_cues"]:
                    action = ("Before another call to the same tool, choose a different target question or view and check whether the prior return already addresses it. ")
                else:
                    action = ("Treat a generic report/class score as a hypothesis; seek an independent focused image observation before combining option attributes. ")
                action += f"Current alternative question: {target_question}. This is a proposed alternative, not a causally verified remedy."
                observation = "Recorded failure cues: " + ", ".join(card["failure_cues"] or ["whole_trajectory_failure_cause_unknown"])
            text = (f"[{card['action_card_id']}; {card['polarity']}; whole-question outcome={card['task_outcome']}]\n"
                    f"Applicable ambiguity: task={','.join(card['task'])}; anatomy={','.join(card['anatomy']) or 'unspecified'}; attributes={','.join(card['attributes']) or 'unspecified'}.\n"
                    f"Historical actions: {compact(sequence, 250)}\n{compact(observation, 260)}\n"
                    f"Current action: {action}\n"
                    "Expected check: obtain a referenced image observation of the requested attribute; historical clinical observation text is unavailable and step credit is unknown.\n")
            if len(header) + sum(map(len, selected)) + len(text) > self.max_chars:
                audit["rejected"].append({"id": card["action_card_id"], "score": scores[i], "reasons": ["render_budget"]})
                continue
            selected.append(text); selected_cards.append(card); ids.append(card["action_card_id"]); polarities.add(card["polarity"])
        audit.update(rendered_ids=ids, abstained=not ids, selected_polarities=sorted(polarities))
        return header + "\n".join(selected) if selected else "", ids, audit, selected_cards

    def retrieve(self, row, observation_text, tools, group, evidence_needs=None, plan=None):
        if group not in GROUPS: raise ValueError("unknown V10 group")
        self._boundary_check(row)
        target = plan_projection(row, plan, evidence_needs)
        query = {"question_stem": target["target_text"], "visible_evidence": [], "candidate_hypotheses": [],
                 "missing_attributes": target["missing_attributes"], "modality": modality_of(row["question"]),
                 "task": target["task"], "population": "unknown"}
        result = {"group": group, "k_block": "", "e_block": "", "k_ids": [], "e_ids": [], "action_cards": [],
                  "k_audit": {"disabled": True}, "e_audit": {"disabled": True}, "query": query,
                  "shared_plan_projection": target, "token_count_method": "utf8_bytes_div4_estimate_not_provider_usage",
                  "retrieval_timing": "before_roi_and_tool_selection"}
        if group in {"VK", "VKE"}:
            result["k_block"], result["k_ids"], result["k_audit"] = self._knowledge_actions(query, target)
        if group == "VKE":
            result["e_block"], result["e_ids"], result["e_audit"], result["action_cards"] = self._action_experience(row, tools, target)
        result["k_token_estimate"] = _token_estimate(result["k_block"])
        result["e_token_estimate"] = _token_estimate(result["e_block"])
        return result
