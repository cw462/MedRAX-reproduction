"""Offline contracts for label-free V9 retrieval; the encoder is a test double."""
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

import v9_retrieval as vr


PACK = Path(__file__).resolve().parents[1] / "local_assets/MedRAX_Knowledge_Pack_v8"
if not PACK.exists():
    PACK = Path(__file__).resolve().parents[2] / "v9_assets/MedRAX_Knowledge_Pack_v8"


class RetrievalContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = {"question_id": "train_1", "question": "Where is the pulmonary nodule located?\nA. SECRET_OPTION\nB) elsewhere", "images": ["train.jpg"]}
        self.query = {"question_id": "dev_1", "question": "Where is the pulmonary nodule located?\nA) SECRET_QUERY_OPTION\nB. elsewhere", "images": ["dev.jpg"]}
        self.pool = {"payload": {"records": [{"memory_id": "B001", "source_question_id": "train_1",
                    "task_outcome": "correct", "steps": [{"tool_name": "chest_xray_expert"}]}],
                    "boundary": {"entries": [
                        {"question_id": "train_1", "case_hash": "case_train", "split": "memory_train", "excluded": False},
                        {"question_id": "dev_1", "case_hash": "case_dev", "split": "validation", "excluded": False}]}}}
        self.skill = {"skill_id": "C001", "source_trace_ids": ["train_1"],
                      "required_capabilities": ["chest_xray_vqa"], "step_credit": None,
                      "trigger": "The current question requires localization of a pulmonary nodule.",
                      "actions": [{"operation": "Ask the expert to locate the current target and state its side.", "capability": "chest_xray_vqa"}],
                      "checkpoints": ["The answer identifies the current image, object, side, and location."],
                      "required_information": ["Target location"]}
        self._write()

    def tearDown(self):
        self.temp.cleanup()

    def _write(self):
        (self.root / "pool.json").write_text(json.dumps(self.pool), encoding="utf-8")
        (self.root / "skills.json").write_text(json.dumps({"skills": [self.skill]}), encoding="utf-8")
        (self.root / "train.jsonl").write_text(json.dumps(self.source) + "\n", encoding="utf-8")

    def _retriever(self, encoder_failure=False):
        original = vr._load_module
        class Encoder:
            def __init__(self, *args):
                if encoder_failure:
                    raise FileNotFoundError("real weights unavailable")
            def encode(self, texts):
                # Explicit fixture only. Production always uses bundled real Encoder.
                return np.zeros((len(texts), 384), dtype=np.float32)
        def load(name, path):
            return types.SimpleNamespace(Encoder=Encoder) if str(path).endswith("dense.py") else original(name, path)
        with patch.object(vr, "_load_module", side_effect=load):
            return vr.V9Retriever(PACK, self.root / "pool.json", self.root / "skills.json",
                                  questions_path=self.root / "train.jsonl", max_chars=2000)

    def test_source_and_query_options_never_enter_experience_index(self):
        r = self._retriever()
        out = r.retrieve(self.query, "tool says suspicious nodule", ["chest_xray_expert"], "DKB", ["location"])
        self.assertEqual(out["e_ids"], ["B001"])
        self.assertNotIn("SECRET", str(out["e_audit"]))
        self.assertNotIn("SECRET", r.b_documents[0])
        self.assertNotIn("SECRET", r.c_documents[0])
        self.assertEqual(out["query"]["visible_evidence"][0]["status"], "hypothesis")
        self.assertTrue(out["e_token_estimate"] > 0)

    def test_same_case_is_excluded_even_when_stem_is_identical(self):
        self.pool["payload"]["boundary"]["entries"][1]["case_hash"] = "case_train"
        self._write()
        out = self._retriever().retrieve(self.query, "", ["chest_xray_expert"], "DKB")
        self.assertEqual(out["e_ids"], [])
        self.assertIn("same_case", out["e_audit"]["rejected"][0]["reasons"])

    def test_missing_skill_tool_causes_zero_injection(self):
        out = self._retriever().retrieve(self.query, "", ["chest_xray_classifier"], "DKC")
        self.assertEqual(out["e_block"], "")
        self.assertIn("unavailable_required_tool", out["e_audit"]["rejected"][0]["reasons"])

    def test_skill_disease_template_requires_current_trigger_relevance(self):
        self.skill["trigger"] = "There is a pleural effusion that needs localization."
        self._write()
        out = self._retriever().retrieve(self.query, "", ["chest_xray_expert"], "DKC")
        self.assertEqual(out["e_ids"], [])
        self.assertIn("trigger_finding_not_supported_by_current_task_or_reports", out["e_audit"]["rejected"][0]["reasons"])

    def test_source_specific_side_is_not_transferred(self):
        self.skill["trigger"] = "A pulmonary nodule in the right lung needs localization."
        self._write()
        out = self._retriever().retrieve(self.query, "", ["chest_xray_expert"], "DKC")
        self.assertEqual(out["e_ids"], [])
        self.assertIn("source_bound_trigger_side_not_established", out["e_audit"]["rejected"][0]["reasons"])

    def test_C_keeps_conditional_action_and_checkpoint(self):
        out = self._retriever().retrieve(self.query, "", ["chest_xray_expert"], "DKC")
        self.assertEqual(out["e_ids"], ["C001"])
        self.assertIn("Action:", out["e_block"])
        self.assertIn("Check:", out["e_block"])
        self.assertIn("applicability is a hypothesis", out["e_block"])
        self.assertLessEqual(len(out["e_block"]), 2000)

    def test_missing_real_dense_fails_instead_of_lexical_downgrade(self):
        with self.assertRaisesRegex(FileNotFoundError, "real weights"):
            self._retriever(encoder_failure=True)

    def test_control_group_has_no_retrieval_context(self):
        out = self._retriever().retrieve(self.query, "", ["chest_xray_expert"], "D")
        self.assertEqual((out["k_block"], out["e_block"]), ("", ""))
        self.assertEqual(out["k_token_estimate"] + out["e_token_estimate"], 0)

    def test_heldout_query_is_not_enabled_by_this_adapter(self):
        self.pool["payload"]["boundary"]["entries"][1]["split"] = "heldout_test"
        self._write()
        with self.assertRaisesRegex(ValueError, "validation cases only"):
            self._retriever().retrieve(self.query, "", ["chest_xray_expert"], "D")

    def test_source_question_file_rejects_label_fields(self):
        self.source["answer"] = "A"
        self._write()
        with self.assertRaisesRegex(ValueError, "inference-only"):
            self._retriever()

    def test_missing_source_stem_fails_before_paid_work(self):
        self.source["question_id"] = "different_train"
        self._write()
        with self.assertRaisesRegex(ValueError, "missing source stems"):
            self._retriever()

    def test_observed_absent_requires_direct_image_reference(self):
        uncertain = vr._observation_projection([{"text": "No effusion", "status": "observed_absent", "source": "report_tool"}])
        self.assertEqual(uncertain[0]["status"], "hypothesis")
        observed = vr._observation_projection([{"text": "No effusion", "status": "observed_absent", "evidence_type": "direct_image_observation", "evidence_ref": "image:1"}])
        self.assertEqual(observed[0]["status"], "absent")

    def test_runner_raw_evidence_result_is_preserved_as_hypothesis(self):
        shared = [{"result": {"report": "Right upper lung nodule is described."},
                   "tool_name": "chest_xray_report_generator", "evidence_ref": "p0:tool:1",
                   "status": "hypothesis", "source": "raw_tool_report_not_verified_patient_fact"}]
        out = self._retriever().retrieve(self.query, shared, ["chest_xray_expert"], "DKB", ["location"])
        observation = out["query"]["visible_evidence"][0]
        self.assertIn("Right upper lung nodule", observation["text"])
        self.assertEqual(observation["status"], "hypothesis")
        self.assertEqual(observation["evidence_ref"], "p0:tool:1")


if __name__ == "__main__":
    unittest.main()
