"""Offline protocol/stage-accounting invariants; no API or model loading."""
from contextlib import redirect_stdout
from copy import deepcopy
from decimal import Decimal, localcontext
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import validation_protocol as validation
from money_guard import MoneyGuard, BudgetIntegrityError
from chunked_budget import ChunkedBudgetGuard
from data_tools import audit_figures as files
from data_tools import freeze_validation
from data_tools.test_audit_figures import run_audit


def ledger_origin(guard, limit="10"):
    return {"schema_version": 1, "ledger_id": guard._state["ledger_id"],
            "monetary_policy": guard.policy_snapshot(), "starting_committed_cny": str(Decimal("100")-guard.remaining),
            "stage_limit_cny": limit, "starting_ledger_generation": guard._state["generation"]}


class ValidationProtocolTest(unittest.TestCase):
    def test_360_balanced_reproducible_schedule_cases_not_repeats(self):
        ids = [f"q{i:02}" for i in range(30)]
        schedule = validation.schedule(ids)
        self.assertEqual(schedule, validation.schedule(ids))
        self.assertEqual(len(schedule), 360)
        self.assertEqual(len({(x["slice_id"], x["question_id"], x["arm"]) for x in schedule}), 360)
        self.assertEqual([x["schedule_index"] for x in schedule], list(range(1, 361)))
        for offset in range(0, 360, 4):
            block = schedule[offset:offset+4]
            self.assertEqual({(x["cap"], x["arm"]) for x in block}, {(512,"direct"),(512,"agent"),(1024,"direct"),(1024,"agent")})
            self.assertEqual({x["question_id"] for x in block}, {ids[(offset//4)%30]})
        self.assertNotEqual(schedule, validation.schedule(ids, seed=7))

    def test_strict_stage_boundary_and_hard_limit(self):
        origin = {"starting_committed_cny": "13.85858", "stage_limit_cny": "10"}
        self.assertTrue(validation.stage_decision(origin, "18.65666", 1024, "81.34334")["allowed"])
        self.assertFalse(validation.stage_decision(origin, "18.65667", 1024, "81.34333")["allowed"])
        self.assertEqual(validation.stage_decision(origin, "13.85858", 1024, "5")["stop_reason"], "budget")
        with self.assertRaises(BudgetIntegrityError): validation.stage_decision(origin, "13", 512, "87")
        with localcontext() as context:
            context.prec = 2
            decision = validation.stage_decision(origin, "18.65666", 1024, "81.34334")
        self.assertEqual(decision["required_reservation_cny"], "5.20192")

    def test_512_guard_counts_real_shared_charges_and_blocks_before_reserve(self):
        with TemporaryDirectory() as temp, MoneyGuard(Path(temp)/"ledger.json") as shared:
            origin = ledger_origin(shared, "3")
            guard = validation.StageBudgetGuard(shared, origin, cap=512)
            block = guard.reserve(request_id="synthetic-one")
            guard.settle(block, None, response_received=False, error_type="synthetic_failure")
            before = shared.path.read_bytes()
            with self.assertRaises(validation.StageBudgetExceeded): guard.reserve(request_id="must-not-reserve")
            self.assertEqual(shared.path.read_bytes(), before)
            self.assertEqual(len(shared._state["reservations"]), 1)

    def test_1024_insufficient_stage_never_reserves_even_first_block(self):
        with TemporaryDirectory() as temp, MoneyGuard(Path(temp)/"ledger.json") as shared:
            guard = validation.StageBudgetGuard(ChunkedBudgetGuard(shared), ledger_origin(shared, "5"), cap=1024)
            before = shared.path.read_bytes()
            with self.assertRaises(validation.StageBudgetExceeded): guard.reserve(request_id="no-api")
            self.assertEqual(shared.path.read_bytes(), before)
            self.assertEqual(shared._state["reservations"], [])

    def test_guard_boundary_is_independent_of_callers_decimal_precision(self):
        with TemporaryDirectory() as temp, MoneyGuard(Path(temp)/"ledger.json") as shared:
            guard = validation.StageBudgetGuard(ChunkedBudgetGuard(shared), ledger_origin(shared, "5.20192"), cap=1024)
            with localcontext() as context:
                context.prec = 2
                decision = guard.preflight()
            self.assertTrue(decision["allowed"])
            self.assertEqual(Decimal(decision["stage_spent_cny"]), Decimal(0))

    def test_1024_adapter_and_identity_are_not_interchangeable(self):
        with TemporaryDirectory() as temp:
            with MoneyGuard(Path(temp)/"one.json") as first, MoneyGuard(Path(temp)/"two.json") as second:
                origin = ledger_origin(first)
                with self.assertRaises(ValueError): validation.StageBudgetGuard(first, origin, cap=1024)
                with self.assertRaises(ValueError): validation.StageBudgetGuard(ChunkedBudgetGuard(first), origin, cap=512)
                with self.assertRaises(BudgetIntegrityError): validation.StageBudgetGuard(second, origin, cap=512)

    def test_read_only_snapshot_has_no_constructor_side_effect_and_rejects_pending(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)/"ledger.json"
            with MoneyGuard(path) as shared:
                policy, identity = shared.policy_snapshot(), shared._state["ledger_id"]
                before = path.read_bytes()
                snapshot = validation.read_ledger(path, identity, policy)
                self.assertFalse(snapshot["locked_snapshot"])
                self.assertEqual(path.read_bytes(), before)
                block = shared.reserve(request_id="in-flight")
                pending = path.read_bytes()
                with self.assertRaisesRegex(BudgetIntegrityError, "unsettled"):
                    validation.read_ledger(path, identity, policy)
                self.assertEqual(path.read_bytes(), pending)
                shared.settle(block, None)
            with self.assertRaises(ValueError): validation.read_ledger(Path(temp)/"absent.json", identity, policy)
            self.assertFalse((Path(temp)/"absent.json").exists())
            with self.assertRaises(BudgetIntegrityError): validation.read_ledger(path, "0"*32, policy)

    def test_stage_origin_reused_across_plans_without_reset(self):
        with TemporaryDirectory() as temp, MoneyGuard(Path(temp)/"ledger.json") as shared:
            snap = validation.read_ledger(shared.path, shared._state["ledger_id"], shared.policy_snapshot())
            path = Path(temp)/"stage.json"
            origin, create = validation.stage_origin(path, snap, "10")
            self.assertTrue(create); self.assertFalse(path.exists())
            files.write_json(path, origin); frozen = path.read_bytes()
            block = shared.reserve(request_id="stage-spend"); shared.settle(block, None)
            after = validation.read_ledger(shared.path, shared._state["ledger_id"], shared.policy_snapshot())
            reused, create = validation.stage_origin(path, after, "10")
            self.assertFalse(create); self.assertEqual(origin, reused); self.assertEqual(path.read_bytes(), frozen)
            self.assertNotEqual(after["committed_cny"], reused["starting_committed_cny"])
            with self.assertRaises(BudgetIntegrityError): validation.stage_origin(path, after, "20")
            changed = deepcopy(after); changed["ledger_id"] = "1"*32
            with self.assertRaises(BudgetIntegrityError): validation.stage_origin(path, changed, "10")

    def test_validation_loader_reads_no_labels_and_checks_all_images(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); split, archive, _, image_audit, _ = run_audit(root)
            target = root/"validation"
            freeze_validation.freeze(archive, split, image_audit, target, count=3)
            original = Path.open
            def guarded(path, mode="r", *args, **kwargs):
                if "r" in mode and ".labels." in path.name: self.fail("Label read forbidden")
                return original(path, mode, *args, **kwargs)
            with patch.object(Path, "open", guarded):
                rows, provenance = validation.load_validation(target, split, expected_count=3)
            self.assertEqual(len(rows), 3)
            self.assertEqual(len(set(provenance["case_hashes_audit_only"].values())), 3)
            image = target/"images"/rows[-1]["images"][-1]
            image.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "frozen original"):
                validation.load_validation(target, split, expected_count=3)

    def test_plan_denominators_are_new_validation_not_old_fifty_manifest(self):
        rows = [{"question_id": f"q{i:02}", "question": "synthetic", "images": ["synthetic.png"]} for i in range(30)]
        registry = {kind: {"kind": kind, "mode": "original", "source": {"commit": "source", "tool_lf_sha256": kind}}
                    for kind in ("classification", "report")}
        args = SimpleNamespace(validation_dir=Path("validation"), repo=Path("repo"), ledger=Path("ledger"), schedule_seed=validation.SEED)
        origin = {"starting_committed_cny": "10", "stage_limit_cny": "20"}
        snapshot = {"monetary_policy": {"budget_cny": "100"}}
        base = {"source_sha256": {}, "question_ids": [r["question_id"] for r in rows], "records": [],
                "max_model_calls": 4, "max_tool_calls": 2, "prompts": {"synthetic": True}}
        def source(repo, kind): return {"commit": "source", "tool_lf_sha256": kind, "tool_sha256": kind}
        with patch.object(validation.diag, "build_plan", return_value=base), patch.object(validation.multi.variants, "_source", side_effect=source):
            plan = validation.build_plan(rows, {"split": "validation"}, args, origin, snapshot, "prompt", registry, "source-hash")
        self.assertEqual(plan["planned_arm_results"], 360)
        self.assertEqual(plan["planned_case_count"], 30)
        self.assertFalse(plan["runtime_implemented"])
        self.assertIsNone(plan["runtime_entrypoint"])
        self.assertEqual(len(plan["condition_plans"]), 6)
        for item in plan["condition_plans"].values():
            self.assertEqual(len(item["schedule"]), 60)
            self.assertEqual(item["planned_question_count"], 30)
            self.assertEqual(item["request_accounting"]["reservation_blocks_per_request"], item["cap"]//512)
        self.assertTrue(plan["scoring_contract"]["repeats_are_not_independent_cases"])

    def test_help_explicitly_has_no_execution_option(self):
        stream = io.StringIO()
        with redirect_stdout(stream), self.assertRaises(SystemExit) as caught:
            validation.main(["--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("NEVER executes models", stream.getvalue())
        self.assertNotIn("--execute", stream.getvalue())
        self.assertNotIn("--resume", stream.getvalue())

    def test_prepare_writes_only_pending_plans_and_never_changes_shared_ledger(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            split, archive, _, audit_dir, _ = run_audit(root)
            validation_dir = root/"validation"
            freeze_validation.freeze(archive, split, audit_dir, validation_dir, count=3)
            real_load = validation.load_validation
            ledger = root/"ledger.json"
            with MoneyGuard(ledger) as shared:
                policy, identity = shared.policy_snapshot(), shared._state["ledger_id"]
            registry = {kind: {"kind": kind, "mode": "original", "source": {"commit": "source", "tool_lf_sha256": kind}}
                        for kind in ("classification", "report")}
            tool_plan = {"monetary_policy": policy, "tool_registry": registry}
            tool_manifest = root/"tool_manifest.json"
            files.write_json(tool_manifest, {"plan_sha256": validation.diag.hash_value(tool_plan), "plan": tool_plan})
            args = SimpleNamespace(output=root/"plan", validation_dir=validation_dir, split_directory=split,
                                   tool_manifest=tool_manifest, ledger=ledger, expected_ledger_id=identity,
                                   stage_state=root/"stage.json", stage_soft_limit_cny="10", repo=root/"upstream",
                                   schedule_seed=validation.SEED)
            baseline_bytes = ledger.read_bytes()
            source = lambda repo, kind: {"commit": "source", "tool_lf_sha256": kind, "tool_sha256": kind}
            utils = SimpleNamespace(load_prompts_from_file=lambda _: {"MEDICAL_ASSISTANT": "synthetic prompt"})
            base = {"source_sha256": {}, "max_model_calls": 4, "max_tool_calls": 2}
            with patch.object(validation, "load_validation", side_effect=lambda a,b: real_load(a,b,expected_count=3)), \
                    patch.object(validation.diag.smoke, "module_from_file", return_value=utils), \
                    patch.object(validation.diag, "build_plan", return_value=base), \
                    patch.object(validation.multi.variants, "_source", side_effect=source), \
                    patch.object(validation.multi, "run_arm", side_effect=AssertionError("Plan must not run any arm")):
                manifest = validation.prepare(args)
            summary = files.read_json(args.output/"summary.json")
            self.assertEqual(manifest["plan"]["status"], "prepared_not_executed")
            self.assertEqual(summary["terminal_count"], 0)
            self.assertEqual(len(summary["question_results"]), 36)
            self.assertTrue(all(x["status"] == "pending_not_executed" for x in summary["question_results"]))
            self.assertFalse((args.output/"results.jsonl").exists())
            self.assertFalse((args.output/"finalization.json").exists())
            self.assertEqual(ledger.read_bytes(), baseline_bytes)
            self.assertEqual(len(list(args.output.glob("cap*/plan.json"))), 6)


if __name__ == "__main__": unittest.main()
