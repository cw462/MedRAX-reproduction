"""Boundary and action-card contracts without model requests."""
import copy
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
import v9_retrieval as v9
from v10_retrieval import V10Retriever, action_card, plan_projection


PACK = Path(__file__).resolve().parents[1] / "local_assets/MedRAX_Knowledge_Pack_v8"
if not PACK.exists():
    PACK = Path(__file__).resolve().parents[2] / "v9_assets/MedRAX_Knowledge_Pack_v8"


class V10RetrievalContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.query = {"question_id": "dev", "question": "Where is the pulmonary nodule located?\nA. QUERY_OPTION", "images": ["dev.png"]}
        self.plan = {"task": ["localization"], "anatomy": "lung nodule",
            "option_differences": [{"attribute": "location", "question": "Which lobe contains the nodule?", "option_labels": ["A", "B"]}],
            "missing_attributes": ["location"], "recommended_view": "crop"}
        self.sources = [{"question_id": f"train{i}", "question": "Where is the pulmonary nodule located?\nA. SOURCE_OPTION", "images": [f"train{i}.png"]} for i in range(3)]
        records = [{"memory_id": f"M{i}", "source_question_id": f"train{i}", "task_outcome": outcome,
            "steps": [{"tool_name": "chest_xray_expert", "execution": "returned_valid", "observation_shape": {"response_chars": 30}, "step_credit": None}]}
            for i, outcome in enumerate(["correct", "incorrect", "error"])]
        self.pool = {"payload": {"records": records, "boundary": {"entries": [
            {"question_id": "dev", "case_hash": "dev_case", "split": "validation", "excluded": False}] + [
            {"question_id": f"train{i}", "case_hash": f"train{i}_case", "split": "memory_train", "excluded": False} for i in range(3)]}}}

    def tearDown(self):
        self.temp.cleanup()

    def retriever(self):
        (self.root/"pool.json").write_text(json.dumps(self.pool))
        (self.root/"skills.json").write_text(json.dumps({"skills": []}))
        (self.root/"train.jsonl").write_text("\n".join(json.dumps(x) for x in self.sources))
        original = v9._load_module
        class Encoder:
            def __init__(self, *args): pass
            def encode(self, texts): return np.zeros((len(texts), 384), dtype=np.float32)
        def load(name, path):
            return types.SimpleNamespace(Encoder=Encoder) if str(path).endswith("dense.py") else original(name, path)
        with patch.object(v9, "_load_module", side_effect=load):
            return V10Retriever(PACK, self.root/"pool.json", self.root/"skills.json", questions_path=self.root/"train.jsonl")

    def test_selects_one_success_and_one_failure_without_source_options(self):
        retriever = self.retriever()
        out = retriever.retrieve(self.query, [], ["chest_xray_expert"], "VKE", plan=self.plan)
        self.assertEqual(out["e_audit"]["selected_polarities"], ["failure", "success"])
        self.assertEqual(len(out["action_cards"]), 2)
        self.assertNotIn("SOURCE_OPTION", str(retriever.action_documents))
        self.assertNotIn("QUERY_OPTION", str(out["query"]))
        self.assertIn("Which lobe contains the nodule?", out["e_block"])
        self.assertIn("causally verified", out["e_block"])
        self.assertTrue(all(x["step_credit"] is None for x in out["action_cards"]))

    def test_same_case_and_nontraining_sources_never_injected(self):
        self.pool["payload"]["boundary"]["entries"][1]["case_hash"] = "dev_case"
        self.pool["payload"]["boundary"]["entries"][2]["split"] = "heldout_test"
        out = self.retriever().retrieve(self.query, [], ["chest_xray_expert"], "VKE", plan=self.plan)
        self.assertEqual(out["e_ids"], ["B10_M2"])
        reasons = {code for r in out["e_audit"]["rejected"] for code in r["reasons"]}
        self.assertTrue({"same_case", "source_not_admitted_training_case"} <= reasons)

    def test_base_arm_retrieves_nothing_and_vk_has_no_experience(self):
        r = self.retriever()
        out = r.retrieve(self.query, [], ["chest_xray_expert"], "V", plan=self.plan)
        self.assertEqual((out["k_block"], out["e_block"]), ("", ""))
        out = r.retrieve(self.query, [], ["chest_xray_expert"], "VK", plan=self.plan)
        self.assertEqual(out["e_ids"], [])
        self.assertLessEqual(len(out["k_ids"]), 2)

    def test_planning_is_never_promoted_to_observed_patient_evidence(self):
        r = self.retriever()
        out = r.retrieve(self.query, [{"text": "SECRET_P0_ASSERTION", "status": "present"}], ["chest_xray_expert"], "VK", plan=self.plan)
        self.assertEqual(out["query"]["visible_evidence"], [])
        self.assertFalse(out["shared_plan_projection"]["is_patient_observation"])
        self.assertNotIn("SECRET_P0_ASSERTION", str(out))
        self.assertNotIn("option_labels", str(out["shared_plan_projection"]))

    def test_recorded_failures_are_distinguished_from_unverified_causes(self):
        record = copy.deepcopy(self.pool["payload"]["records"][1])
        record["steps"][0]["execution"] = "exception"
        card = action_card(record, self.sources[1]["question"])
        self.assertEqual(card["failed_tools"], ["chest_xray_expert"])
        self.assertIn("whole_answer_incorrect_cause_unknown", card["failure_cues"])
        self.assertEqual(card["causal_attribution"], "unknown")

    def test_changed_option_question_changes_query_without_source_answers(self):
        a = plan_projection(self.query, self.plan)
        plan = copy.deepcopy(self.plan)
        plan["option_differences"][0] = {"attribute": "morphology", "question": "Is the nodule margin smooth or irregular?"}
        b = plan_projection(self.query, plan)
        self.assertNotEqual(a["target_text"], b["target_text"])
        self.assertIn("morphology", b["attribute_tags"])

    def test_free_form_task_is_canonical_for_scope_but_kept_in_query(self):
        plan = copy.deepcopy(self.plan)
        plan["task"] = "localization diagnosis characterization"
        out = self.retriever().retrieve(self.query, [], ["chest_xray_expert"], "VKE", plan=plan)
        self.assertEqual(out["query"]["task"], ["description", "diagnosis", "localization"])
        self.assertIn("localization diagnosis characterization", out["query"]["question_stem"])
        self.assertEqual(out["e_audit"]["selected_polarities"], ["failure", "success"])
        self.assertFalse(any("task_mismatch" in x["reasons"] for x in out["e_audit"]["rejected"]))
        row = dict(self.query, official_group="classification,characterization,diagnosis,reasoning")
        projection = plan_projection(row, dict(plan, task="choose the best option"))
        self.assertEqual(projection["task"], ["classification", "description", "diagnosis"])
        self.assertEqual(projection["task_scope_source"], "official_group")


if __name__ == "__main__": unittest.main()
