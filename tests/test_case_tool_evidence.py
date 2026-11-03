"""E3 synthetic cache contracts; no benchmark data, GPU, model or provider API."""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

from experiments import build_case_tool_evidence as builder
from experiments.tool_variants import CLASSIFIER_LABELS
from experiments.worker_bridge import decode_value


class Schema:
    @staticmethod
    def model_json_schema():
        return {"properties": {"image_path": {"type": "string"}}, "required": ["image_path"]}


class FakeTool:
    args_schema = Schema

    def __init__(self, name, calls, failure=None):
        self.name, self.calls, self.failure = name, calls, failure

    def invoke(self, arguments):
        self.calls.append((self.name, arguments))
        if self.failure:
            raise self.failure
        metadata = {"analysis_status": "completed", "image_path": arguments["image_path"]}
        if self.name == builder.TOOLS[0]:
            return {label: 0.25 for label in CLASSIFIER_LABELS}, metadata
        metadata["sections_generated"] = ["findings", "impression"]
        return ("CHEST X-RAY REPORT\n\nFINDINGS:\nSynthetic fixture only."
                "\n\nIMPRESSION:\nNo clinical inference performed.", metadata)


class FakePool:
    def __init__(self, failure=None):
        self.calls = []
        self.tools = {name: FakeTool(name, self.calls, failure) for name in builder.TOOLS}

    def get(self, name):
        return self.tools[name], {"tool": name, "source": "synthetic_fixture", "mode": "original"}


class NeverPool:
    def get(self, name):
        raise AssertionError("Cached or ineligible input must not initialize a model")


def fixture(root, *, small=False):
    images = root / "images"
    images.mkdir()
    names = ["a.png"] if small else ["a.png", "b.png", "ct.png", "mri.png", "unknown.png", "c.png"]
    for number, name in enumerate(names):
        Image.new("RGB", (32, 32), (number * 30, 20, 40)).save(images / name)
    rows = [{"question_id": "q1", "case_id": "case1", "question": "Question secret? A) X B) Y",
             "images": ["a.png"], "figure_labels": ["Figure 1A"]}]
    if not small:
        rows += [{"question_id": "q2", "case_id": "case1", "question": "Second secret? A) X B) Y",
                  "images": ["b.png", "a.png", "ct.png"], "figure_labels": ["Figure 1B", "Figure 1A", "Figure 2"]},
                 {"question_id": "q3", "case_id": "case2", "question": "Third? A) X B) Y",
                  "images": ["mri.png", "unknown.png"]},
                 {"question_id": "q4", "case_id": "case3", "question": "Fourth? A) X B) Y", "images": ["c.png"]}]
    inputs, manifest = root / "inputs.jsonl", root / "modality.json"
    inputs.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    modalities = {"a.png": "CXR", "b.png": "CXR", "ct.png": "CT", "mri.png": "MRI", "c.png": "CXR"}
    builder.write(manifest, {"schema_version": 1, "images": [
        {"source_filename": name, "modality": modalities[name],
         "provenance": {"kind": "human_review", "source": "synthetic_fixture", "quote": modalities[name]}}
        for name in names if name in modalities]})
    return inputs, images, manifest


class CaseToolEvidenceTests(unittest.TestCase):
    def plan(self, paths, *, small=False):
        return builder.prepare_plan(*paths, expected_cases=1 if small else 3,
                                    expected_questions=1 if small else 4)

    def test_union_deduplication_modality_gate_and_reuse(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = self.plan(fixture(root))
            self.assertEqual(plan["planned_tool_invocations"], 6)
            self.assertEqual(plan["case_image_count"], 6)
            self.assertEqual(len(plan["cases"][0]["images"]), 3)
            out, pool = root / "cache", FakePool()
            index = builder.generate_cases(plan, out, pool)
            self.assertEqual(len(pool.calls), 6)
            self.assertEqual(len({(name, args["image_path"]) for name, args in pool.calls}), 6)
            self.assertTrue(all(set(args) == {"image_path"} for _, args in pool.calls))
            self.assertFalse(any(Path(args["image_path"]).name in {"ct.png", "mri.png", "unknown.png"}
                                 for _, args in pool.calls))
            self.assertEqual(index["question_to_case"], {"q1": "case1", "q2": "case1", "q3": "case2", "q4": "case3"})
            self.assertEqual(index["no_evidence_case_count"], 1)
            empty = builder.read(out / "cases/case2.json")
            self.assertEqual(empty["evidence_for_model"]["status"], "NO_EVIDENCE")
            self.assertEqual(empty["tool_results"], [])
            case = builder.read(out / "cases/case1.json")
            self.assertEqual(case["unique_original_count"], 3)
            self.assertIsInstance(decode_value(case["tool_results"][0]["typed_result"]), tuple)
            self.assertNotIn("Question secret", json.dumps(case))
            before = (out / "cases/case1.json").read_bytes()
            self.assertEqual(index, builder.generate_cases(plan, out, NeverPool()))
            self.assertEqual(before, (out / "cases/case1.json").read_bytes())

    def test_interrupted_invocation_is_never_reissued(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = self.plan(fixture(root, small=True), small=True)
            out, pool = root / "cache", FakePool()
            pool.tools[builder.TOOLS[0]].failure = KeyboardInterrupt()
            with self.assertRaises(KeyboardInterrupt):
                builder.generate_cases(plan, out, pool)
            self.assertFalse((out / "index.json").exists())
            resumed = FakePool()
            index = builder.generate_cases(plan, out, resumed)
            self.assertEqual([name for name, _ in resumed.calls], [builder.TOOLS[1]])
            self.assertEqual(index["interrupted_unknown_count"], 1)
            self.assertEqual(index["tool_invocation_count"], 1)
            case = builder.read(out / "cases/case1.json")
            self.assertEqual(case["tool_results"][0]["status"], "interrupted_unknown")
            self.assertEqual(case["tool_results"][0]["error_type"], "InterruptedUnknown")

    def test_execution_failures_are_saved_and_not_patient_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = self.plan(fixture(root, small=True), small=True)
            out, pool = root / "cache", FakePool(RuntimeError("synthetic_failure"))
            index = builder.generate_cases(plan, out, pool)
            self.assertEqual(index["tool_invocation_count"], 2)
            case = builder.read(out / "cases/case1.json")
            self.assertEqual(case["evidence_status"], "NO_EVIDENCE")
            self.assertEqual(case["evidence_for_model"]["images"], [])
            self.assertTrue(all(r["error_message"] == "synthetic_failure" for r in case["tool_results"]))
            builder.generate_cases(plan, out, NeverPool())

    def test_extra_label_fields_and_conflicting_modalities_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = fixture(root, small=True)
            original = paths[0].read_text(encoding="utf-8")
            for forbidden in ("answer", "correct_answer", "categories", "reasoning", "prediction"):
                row = json.loads(original)
                row[forbidden] = "hidden_label"
                paths[0].write_text(json.dumps(row), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "label_free"):
                    self.plan(paths, small=True)
            paths[0].write_text(original, encoding="utf-8")
            manifest = builder.read(paths[2])
            manifest["images"].append(dict(manifest["images"][0], modality="CT"))
            builder.write(paths[2], manifest)
            with self.assertRaisesRegex(ValueError, "conflicting_modality"):
                self.plan(paths, small=True)

    def test_changed_selection_cannot_reuse_a_frozen_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            paths = fixture(root, small=True)
            plan = self.plan(paths, small=True)
            out = root / "cache"
            builder.generate_cases(plan, out, FakePool())
            row = json.loads(paths[0].read_text(encoding="utf-8"))
            row["question"] += " Changed."
            paths[0].write_text(json.dumps(row), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "frozen_artifact_conflict"):
                builder.generate_cases(self.plan(paths, small=True), out, NeverPool())

    def test_prepare_cli_loads_no_ml_and_does_not_create_completion_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            inputs, images, manifest = fixture(root, small=True)
            out = root / "prepared"
            args = ["--inputs", str(inputs), "--image-root", str(images),
                    "--modality-manifest", str(manifest), "--repo", str(root / "nonexistent_repo"),
                    "--out", str(out), "--expected-cases", "1", "--expected-questions", "1"]
            code = ("import sys; from experiments.build_case_tool_evidence import main; "
                    "main(sys.argv[1:]); assert not any(x in sys.modules for x in "
                    "('torch', 'torchxrayvision', 'transformers', 'tool_registry_ext'))")
            run = subprocess.run([sys.executable, "-B", "-c", code, *args],
                                 cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)["status"], "prepared_no_inference")
            self.assertTrue((out / "plan.json").exists())
            self.assertFalse((out / "index.json").exists())
            self.assertFalse((out / "cases").exists())


if __name__ == "__main__":
    unittest.main()
