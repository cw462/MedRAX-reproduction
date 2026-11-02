import json
from pathlib import Path
import tempfile
import unittest

from experiments.score_votes import (choose_k, correctness_auroc, error_overlap,
                                    exact_mcnemar, load_complete_run, paired,
                                    paired_bootstrap, resources, score, vote,
                                    vote_diagnostics)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def run_fixture(root, name, answers, model=None, complete=True):
    path = root / name
    samples = len(answers[0])
    put(path / "protocol.json", {"model": model or name, "samples": samples, "temperature": .2 if samples == 1 else .7})
    put(path / "selection.json", {"rows": [{"question_id": f"q{i + 1}", "case_id": f"c{i + 1}"}
                                          for i in range(len(answers))]})
    put(path / "status.json", {"status": "generation_complete" if complete else "running"})
    records = [{"question_id": f"q{qi + 1}", "case_id": f"c{qi + 1}", "sample_index": i + 1,
                "status": "completed" if answer else "request_failed", "answer": answer,
                "attempts": [{"ordinal": 1, "usage": {"input_tokens": 2, "output_tokens": 1},
                              "settlement": {"charged_cny": "0.001"}}]}
               for qi, row in enumerate(answers) for i, answer in enumerate(row)]
    (path / "predictions.jsonl").write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")
    return path


class VoteMathTests(unittest.TestCase):
    def test_missing_is_not_a_vote_or_fallback(self):
        self.assertIsNone(vote([None, None], "A"))
        self.assertEqual(vote([None, "B", "B"], "A"), "B")

    def test_tie_does_not_choose_unvoted_direct(self):
        self.assertEqual(vote(["B", "C"], "C"), "C")
        self.assertEqual(vote(["B", "C"], "A"), "B")
        self.assertEqual(vote(["A", "B", "C"], "C", [.6, .3, .3]), "A")

    def test_invalid_weights_rejected(self):
        with self.assertRaises(ValueError):
            vote(["A"], weights=[float("nan")])
        with self.assertRaises(ValueError):
            vote(["A"], weights=[-1])

    def test_exact_mcnemar(self):
        self.assertEqual(exact_mcnemar(0, 0), 1)
        self.assertAlmostEqual(exact_mcnemar(5, 0), .0625)
        self.assertAlmostEqual(exact_mcnemar(1, 1), 1)
        self.assertGreaterEqual(exact_mcnemar(1000, 1100), 0)

    def test_missing_recovery_reported_separately(self):
        qids = ["1", "2", "3", "4"]
        labels = dict.fromkeys(qids, "A")
        old = dict(zip(qids, [None, "B", "A", "A"]))
        new = dict(zip(qids, ["A", "A", None, "B"]))
        result = paired(old, new, labels, qids, dict(zip(qids, ["x", "x", "y", "y"])), 50)
        self.assertEqual(result["missing_to_correct"], 1)
        self.assertEqual(result["correct_to_missing"], 1)
        self.assertEqual(result["legal_wrong_to_correct"], 1)
        self.assertEqual(result["correct_to_legal_wrong"], 1)
        self.assertEqual(result["net"], 0)
        self.assertEqual(result["bootstrap"]["case_n"], 2)

    def test_bootstrap_clusters_cases_not_questions(self):
        qids = ["1", "2", "3"]
        labels = dict.fromkeys(qids, "A")
        old = dict.fromkeys(qids, "B")
        new = dict.fromkeys(qids, "A")
        result = paired_bootstrap(old, new, labels, qids, {"1": "c1", "2": "c1", "3": "c2"}, 20)
        self.assertEqual(result["delta_ci95"], [1, 1])
        self.assertEqual(result["case_n"], 2)

    def test_k_plateau_is_not_best_of_curve_search(self):
        curve = [{"k": k, "mean_accuracy": value} for k, value in [(1, .70), (3, .73), (5, .732), (7, .76), (9, .77)]]
        self.assertEqual(choose_k(curve), 3)

    def test_kappa_degenerate_is_explicit_null(self):
        self.assertIsNone(error_overlap({"q": "A"}, {"q": "A"}, {"q": "A"}, ["q"])["correctness_cohen_kappa"])

    def test_openai_usage_tokens_are_counted(self):
        value = resources([{"status": "completed", "attempts": [{"usage": {"prompt_tokens": 15, "completion_tokens": 9}}]}])
        self.assertEqual(value["input_tokens"], 15)
        self.assertEqual(value["output_tokens"], 9)

    def test_margin_auroc_handles_ties_and_degenerate_classes(self):
        result = correctness_auroc([.1, .5, .5, .9], [False, False, True, True])
        self.assertEqual(result["auroc"], .875)
        self.assertEqual(result["correct_n"], 2)
        for labels in ([], [True, True], [False, False]):
            value = correctness_auroc([.5] * len(labels), labels)
            self.assertIsNone(value["auroc"])
            self.assertIn("undefined_reason", value)


class CompletePhaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        put(self.root / "labels.json", {"labels": {"q1": "A", "q2": "B"}})

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self, arms, **kwargs):
        result = {"phase": 1, "split": "tune", "baseline": "D", "arms": arms,
                  "bootstrap_repeats": 20, "subsample_repeats": 20, **kwargs}
        put(self.root / "phase.json", result)
        return self.root / "phase.json"

    def test_incomplete_phase_blocks_before_reference_access(self):
        run_fixture(self.root, "d", [["A"], ["B"]], complete=False)
        manifest = self.manifest([{"id": "D", "run": "d"}])
        with self.assertRaisesRegex(ValueError, "generation_not_complete"):
            score(manifest, self.root / "nonexistent_labels.json", self.root / "report")

    def test_generation_gate_blocks_completed_baseline_before_labels(self):
        run_fixture(self.root, "d", [["A"], ["B"]])
        protocol = json.loads((self.root / "d" / "protocol.json").read_text())
        protocol["extra_body"] = {"enable_thinking": True, "reasoning_effort": "max"}
        put(self.root / "d" / "protocol.json", protocol)
        put(self.root / "phase0" / "status.json", {"status": "running"})
        manifest = self.manifest([{"id": "D", "run": "d"}], generation_gate="phase0/status.json")
        with self.assertRaisesRegex(ValueError, "generation_gate_not_complete"):
            score(manifest, self.root / "nonexistent_labels.json", self.root / "report")
        put(self.root / "phase0" / "status.json", {"status": "generation_complete"})
        result = score(manifest, self.root / "labels.json", self.root / "report")
        self.assertTrue(result["direct_anchor_configurations"]["D"]["enable_thinking"])
        self.assertEqual(result["direct_anchor_configurations"]["D"]["reasoning_effort"], "max")

    def test_duplicate_terminal_rejected_even_with_complete_status(self):
        path = run_fixture(self.root, "d", [["A"], ["B"]])
        p = path / "predictions.jsonl"
        p.write_text(p.read_text() + "\n" + p.read_text().splitlines()[0])
        manifest = self.manifest([{"id": "D", "run": "d"}])
        with self.assertRaisesRegex(ValueError, "unique_terminal"):
            score(manifest, self.root / "nonexistent_labels.json", self.root / "report")

    def test_phase1_gate_and_full_denominator(self):
        run_fixture(self.root, "d", [["A"], [None]])
        run_fixture(self.root, "cot", [["A"], ["B"]])
        manifest = self.manifest([{"id": "D", "run": "d"}, {"id": "COT", "run": "cot"}],
                                 selection={"candidates": ["D", "COT"]})
        result = score(manifest, self.root / "labels.json", self.root / "report")
        self.assertEqual(result["totals"]["D"]["planned_n"], 2)
        self.assertEqual(result["totals"]["D"]["accuracy"], .5)
        self.assertEqual(result["tuning_decisions"]["phase1"]["selected"], "COT")
        self.assertEqual(result["comparisons"]["D_to_COT"]["missing_to_correct"], 1)

    def test_guard_recovery_difference_preserved_in_report(self):
        path = run_fixture(self.root, "d", [["A"], ["B"]])
        put(path / "ledger_final_summary.json", {"run_increment_cny": "0.050", "price_basis": "fixture"})
        manifest = self.manifest([{"id": "D", "run": "d"}])
        result = score(manifest, self.root / "labels.json", self.root / "report")
        self.assertEqual(result["resources"]["D"]["saved_settlement_cny"], "0.002")
        self.assertEqual(result["resources"]["D"]["guard_minus_saved_settlements_cny"], "0.048")
        self.assertTrue((self.root / "report" / "cost_summary.json").exists())

    def test_sample_votes_preserve_originals_and_firstK(self):
        run_fixture(self.root, "d", [["B"], ["B"]])
        path = run_fixture(self.root, "sc", [["B", "A", "A"], [None, "B", "B"]])
        original = (path / "predictions.jsonl").read_bytes()
        manifest = self.manifest([{"id": "D", "run": "d"}, {"id": "SC", "run": "sc", "direct_arm": "D"}], phase=2)
        result = score(manifest, self.root / "labels.json", self.root / "report")
        self.assertEqual(result["totals"]["SC/K1"]["correct"], 0)
        self.assertEqual(result["totals"]["SC/K3"]["correct"], 2)
        self.assertEqual(original, (path / "predictions.jsonl").read_bytes())
        self.assertEqual(result["sampling_curves"]["SC"][0]["resamples"], 20)
        self.assertNotIn("agent_v2_voting", result)
        self.assertFalse((self.root / "report" / "vote_diagnostics.json").exists())

    def test_v2_matched_single_and_same_temperature_comparisons_keep_D_ties(self):
        run_fixture(self.root, "d", [["B"], ["B"]], model="qwen")
        run_fixture(self.root, "hires", [["A"], ["A"]], model="qwen")
        path = run_fixture(self.root, "sc", [["B"] + ["A"] * 8, ["A"] + ["B"] * 8], model="qwen")
        original = (path / "predictions.jsonl").read_bytes()
        manifest = self.manifest([
            {"id": "D", "run": "d"}, {"id": "SelectedSingle", "run": "hires"},
            {"id": "S0", "run": "sc", "direct_arm": "D"}], phase=2,
            primary_voting_arm="S0", selected_single_arm="SelectedSingle", fixed_primary_k=9,
            ks=list(range(1, 10)))
        result = score(manifest, self.root / "labels.json", self.root / "report")
        self.assertEqual(result["comparisons"]["D_to_S0/K9"]["net"], 1)
        self.assertEqual(result["comparisons"]["SelectedSingle_to_S0/K9"]["net"], 1)
        self.assertEqual(result["comparisons"]["S0/K1_to_S0/K9"]["net"], 2)
        rows = json.loads((self.root / "report" / "per_question.json").read_text())["records"]
        self.assertEqual(rows[0]["answers"]["S0/K2"], "B")  # D wins the tie, not HiRes A.
        self.assertEqual(result["agent_v2_voting"]["primary_view"], "S0/K9")
        self.assertFalse(result["agent_v2_voting"]["primary_K_selected_from_labels"])
        self.assertEqual(original, (path / "predictions.jsonl").read_bytes())
        diagnostics = json.loads((self.root / "report" / "vote_diagnostics.json").read_text())
        self.assertFalse(diagnostics["labels_used"])
        self.assertEqual(diagnostics["records"][0]["sample_answers"], ["B"] + ["A"] * 8)
        self.assertNotIn('"reference"', json.dumps(diagnostics))
        self.assertNotIn('"correct"', json.dumps(diagnostics))

    def test_v2_primary_is_nine_even_when_sampling_curve_plateaus_at_one(self):
        run_fixture(self.root, "d", [["A"], ["B"]])
        run_fixture(self.root, "sc", [["A"] * 9, ["B"] * 9])
        manifest = self.manifest([{"id": "D", "run": "d"},
                                  {"id": "S0", "run": "sc", "direct_arm": "D"}],
                                 primary_voting_arm="S0", selected_single_arm="D", fixed_primary_k=9)
        result = score(manifest, self.root / "labels.json", self.root / "report")
        self.assertEqual(choose_k(result["sampling_curves"]["S0"]), 1)
        self.assertEqual(result["tuning_decisions"]["S0_selected_K"], 9)
        agreement = result["agent_v2_voting"]
        self.assertIsNone(agreement["agreement_bins"]["technical_incomplete"]["vote_totals"])
        self.assertIsNone(agreement["correctness_auroc"]["complete_nine_only"]["margin_planned"]["auroc"])

    def test_v2_diagnostics_do_not_treat_missing_as_unanimous_or_genuine_split(self):
        answers = [["A"] * 9, ["A"] * 8 + ["B"], ["A"] * 7 + ["B"] * 2,
                   ["A"] * 6 + ["B"] * 3, ["A"] * 5 + ["B"] * 4,
                   ["A"] * 8 + [None], [None] * 9, ["A"] * 4 + ["B"] * 4 + [None]]
        path = run_fixture(self.root, "sc", answers)
        run = load_complete_run(path)
        qids = run["qids"]
        rows = vote_diagnostics(run, dict.fromkeys(qids, "B"), qids,
                                {q: "c" + q[1:] for q in qids})
        self.assertEqual(rows[0]["agreement_bin"], "unanimous_9_of_9")
        self.assertEqual(rows[1]["agreement_bin"], "high_agreement_7_or_8_of_9")
        self.assertEqual(rows[2]["agreement_bin"], "high_agreement_7_or_8_of_9")
        self.assertEqual(rows[3]["agreement_bin"], "split_at_most_6_of_9")
        self.assertFalse(rows[3]["complete_split_by_top_votes"]["5"])
        self.assertTrue(rows[3]["complete_split_by_top_votes"]["6"])
        self.assertTrue(rows[2]["complete_split_by_top_votes"]["7"])
        self.assertEqual(rows[5]["agreement_bin"], "technical_incomplete")
        self.assertEqual(rows[5]["agreement_planned"], 8 / 9)
        self.assertEqual(rows[5]["margin_planned"], 8 / 9)
        self.assertEqual(rows[5]["missing_samples"], 1)
        self.assertIsNone(rows[6]["vote_answer"])
        self.assertTrue(rows[6]["split_by_top_votes"]["6"])
        self.assertFalse(rows[6]["complete_split_by_top_votes"]["6"])
        self.assertEqual(rows[7]["vote_answer"], "B")
        self.assertEqual(rows[7]["margin_planned"], 0)
        # The same label-free metadata feeds scored strata, with every question retained.
        run_fixture(self.root, "d", [["A"] for _ in answers])
        put(self.root / "labels.json", {q: "A" for q in qids})
        manifest = self.manifest([{"id": "D", "run": "d"},
                                  {"id": "S0", "run": "sc", "direct_arm": "D"}],
                                 primary_voting_arm="S0", selected_single_arm="D", fixed_primary_k=9)
        result = score(manifest, self.root / "labels.json", self.root / "report")
        groups = result["agent_v2_voting"]["agreement_bins"]
        self.assertEqual([v["planned_n"] for v in groups.values()], [1, 2, 2, 3])
        thresholds = result["agent_v2_voting"]["split_thresholds"]
        self.assertEqual(thresholds["6"]["complete_split"]["planned_n"], 2)
        self.assertEqual(thresholds["6"]["incomplete_meeting_raw_rule_n"], 2)
        self.assertEqual(thresholds["6"]["complete_split_fraction_of_all_questions"], 2 / 8)
        self.assertEqual(thresholds["5"]["complete_split"]["planned_n"], 1)
        self.assertEqual(thresholds["7"]["complete_split"]["planned_n"], 3)

    def test_v2_invalid_primary_configuration_rejected_before_label_access(self):
        run_fixture(self.root, "d", [["A"], ["B"]])
        run_fixture(self.root, "sc", [["A"] * 9, ["B"] * 9])
        manifest = self.manifest([{"id": "D", "run": "d"},
                                  {"id": "S0", "run": "sc", "direct_arm": "D"}],
                                 primary_voting_arm="S0", selected_single_arm="D", fixed_primary_k=7)
        with self.assertRaisesRegex(ValueError, "fixed_nine"):
            score(manifest, self.root / "nonexistent_labels.json", self.root / "report")

    def test_test_split_never_selects_prompt_or_K(self):
        run_fixture(self.root, "d", [["B"], ["B"]])
        run_fixture(self.root, "sc", [["B", "A", "A"], [None, "B", "B"]])
        manifest = self.manifest([{"id": "D", "run": "d"}, {"id": "SC", "run": "sc", "direct_arm": "D"}],
                                 split="test", selection={"candidates": ["D"]})
        result = score(manifest, self.root / "labels.json", self.root / "report")
        self.assertFalse(result["tuning_decisions"])
        self.assertFalse(result["sampling_curves"])

    def test_phase3a_direct_anchors_need_no_ensemble_samples(self):
        arms = []
        for arm, answers in [("D", [["A"], ["B"]]), ("MAX", [["A"], ["A"]]), ("GPT4O", [["B"], ["B"]])]:
            run_fixture(self.root, arm, answers, model='gpt-4o' if arm=='GPT4O' else arm)
            arms.append({"id": arm, "run": arm})
        manifest = self.manifest(arms, phase="3a")
        result = score(manifest, self.root / "labels.json", self.root / "report")
        self.assertIsNone(result["ensemble"])
        self.assertEqual(set(result["totals"]), {"D", "MAX", "GPT4O"})
        self.assertEqual(len(result["pairwise_direct_error_overlap"]), 3)
        self.assertEqual(set(result['gpt4o_provider_alias_arms']), {'GPT4O'})
        self.assertFalse(result['gpt4o_provider_alias_arms']['GPT4O']['paper_snapshot_match_established'])
        self.assertFalse(result['paper_GPT4o_attribution_arms_executed'])

    def test_ensemble_excludes_strongest_from_B3_anchor(self):
        arms = []
        for i in range(3):
            did = "D" if i == 0 else "D" + str(i)
            run_fixture(self.root, f"d{i}", [["A" if i == 0 else "C"], ["B"]], model=f"m{i}")
            sample_n = 9 if i == 0 else 3
            run_fixture(self.root, f"s{i}", [["A" if i == 0 else "C"] * sample_n, ["B"] * sample_n], model=f"m{i}")
            arms.extend([{"id": did, "run": f"d{i}"}, {"id": f"S{i}", "run": f"s{i}", "direct_arm": did}])
        manifest = self.manifest(arms, phase=3, ensemble={"members": ["S0", "S1", "S2"],
                                                       "weights": {"S0": .8, "S1": .7, "S2": .7}, "strongest_member": "S0"})
        result = score(manifest, self.root / "labels.json", self.root / "report")
        self.assertEqual(result["totals"]["B1_best_member_K9"]["correct"], 2)
        self.assertEqual(result["totals"]["B2_three_models_3x3"]["correct"], 1)
        self.assertEqual(result["totals"]["B3_without_strongest"]["correct"], 1)
        value = json.loads((self.root / "phase.json").read_text())
        value["split"] = "test"
        put(self.root / "phase.json", value)
        with self.assertRaisesRegex(ValueError, "frozen_tuning"):
            score(manifest, self.root / "labels.json", self.root / "report2")
        value["frozen_before_test"] = True
        value["ensemble"]["weights_source"] = "phase3a B0 tuning metrics"
        put(self.root / "phase.json", value)
        frozen = score(manifest, self.root / "labels.json", self.root / "report2")
        self.assertEqual(frozen["totals"]["B2_three_models_3x3"]["correct"], 1)
        self.assertNotIn("S1/K5", frozen["totals"])

    def test_primary_ensemble_uses_weighted_model_majorities(self):
        arms = []
        for i in range(3):
            did = "D" if i == 0 else "D" + str(i)
            run_fixture(self.root, f"d{i}", [["A"], ["B"]], model=f"m{i}")
            first = ["A", "A", "A"] if i == 0 else ["C", "C", "A"]
            run_fixture(self.root, f"s{i}", [first + ["A"] * 6, ["B"] * 9], model=f"m{i}")
            arms.extend([{"id": did, "run": f"d{i}"}, {"id": f"S{i}", "run": f"s{i}", "direct_arm": did}])
        manifest = self.manifest(arms, phase=3, ensemble={"members": ["S0", "S1", "S2"],
                                                       "weights": {"S0": .8, "S1": .7, "S2": .7}, "strongest_member": "S0"})
        result = score(manifest, self.root / "labels.json", self.root / "report")
        self.assertEqual(result["totals"]["B2_three_models_3x3"]["correct"], 1)
        self.assertEqual(result["totals"]["B2_pooled_nine_samples_secondary"]["correct"], 2)
        self.assertEqual(result["comparisons"]["B1_to_B2"]["net"], -1)


if __name__ == "__main__":
    unittest.main()
