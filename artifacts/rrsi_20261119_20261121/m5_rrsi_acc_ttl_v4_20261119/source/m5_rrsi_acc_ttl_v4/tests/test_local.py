"""Offline software tests. Synthetic fixtures are NOT medical experiment results."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

from m5rrsi.io import ProtocolError, write_json, read_json, digest, tree_hash, copy_tree, file_hash, write_once, git, code_export
from m5rrsi.data import prepare, References
from m5rrsi.steps import transition
from m5rrsi.engine import StreamEngine
from m5rrsi.domain import MedM5Domain
from m5rrsi.selection import check_pair
from m5rrsi.validation import budget, validate_config
from m5rrsi.upstream import safe_path
from m5rrsi.runtime import require_prediction
from m5rrsi.report import report


class ToyRuntime:
    """Explicit synthetic state machine, only in tests/; never used by production CLI."""
    def __init__(self): self.calls = []; self.fail_observe_once = False
    def call(self, harness, state, op, *, case=None, prediction=None, feedback=None, seed=0):
        state = Path(state); cfg = read_json(Path(harness) / "toy.json")
        memfile = state / "memory.json"
        mem = read_json(memfile) if memfile.exists() else []
        self.calls.append({"op": op, "id": case["id"] if case else None,
                           "memory": list(mem), "feedback": feedback, "harness": str(harness)})
        result = {"usage": {"total_tokens": 1, "model_calls": 1, "tool_calls": 0},
                  "harness_sha256": tree_hash(harness), "model": "toy"}
        if op == "initialize": write_json(memfile, [])
        elif op == "predict":
            if feedback is not None: raise AssertionError("feedback before prediction")
            result.update(answer=("B" if cfg.get("better") else "A"), trace=[{"remembered": list(mem)}])
        elif op == "observe":
            if self.fail_observe_once:
                self.fail_observe_once = False
                raise RuntimeError("synthetic crash")
            if cfg.get("writer", True): mem.append(case["id"])
            write_json(memfile, mem)
        return result


class ToyScorer:
    metric_id = "toy_exact"
    def score(self, case, prediction, reference): return int(prediction["answer"] == reference)


class NoSearch:
    def __init__(self): self.events = []
    def advance(self, rows, state, commit):
        self.events.append(len(rows))
        return {"commit": commit, "state": state}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.p = Path(self.tmp.name)
        self.h = self.p / "h"; self.h.mkdir(); write_json(self.h / "toy.json", {})
        self.img = self.p / "image.png"; self.img.write_bytes(b"synthetic image bytes, not medical")
        self.case = {"id": "x1", "dataset": "synthetic", "question": "toy question", "options": [{"label":"A","text":"one"},{"label":"B","text":"two"}],
                     "images": [{"path": str(self.img), "sha256": file_hash(self.img)}]}
        self.runtime = ToyRuntime(); self.scorer = ToyScorer()
    def tearDown(self): self.tmp.cleanup()
    def initialize(self): return transition(self.runtime, self.h, None, self.p/"init", "initialize")["state"]
    def stream(self, n=3):
        pub = self.p / "public.jsonl"
        rows = [{**self.case, "id":f"x{i}", "images":[str(self.img)], "group_keys":["same_image"]} for i in range(n)]
        pub.write_text("\n".join(json.dumps(r) for r in rows))
        m = prepare(pub, self.p/"manifest.json")
        refs = self.p/"refs.jsonl"; refs.write_text("\n".join(json.dumps({"id":r["id"],"reference":"B"}) for r in rows))
        r = References(refs, [x["id"] for x in rows])
        cfg = {"run_dir":str(self.p/"run"),"upstream_repo":str(self.p),"initial_commit":"H0","seed":42,"expected_questions":n}
        search = NoSearch()
        e = StreamEngine(cfg,m,r,self.runtime,self.scorer,search,export=lambda *a:self.h)
        return e,search


class TestIO(Fixture):
    def test_atomic_roundtrip(self):
        write_json(self.p/"x.json", {"x":"中文"}); self.assertEqual(read_json(self.p/"x.json"),{"x":"中文"})
    def test_immutable_record(self):
        write_once(self.p/"x.json", {"x":1})
        with self.assertRaises(ProtocolError): write_once(self.p/"x.json", {"x":2})
    def test_tree_hash_changes(self):
        h=tree_hash(self.h); write_json(self.h/"toy.json", {"v":1}); self.assertNotEqual(h,tree_hash(self.h))
    def test_symlink_denied(self):
        (self.h/"leak").symlink_to(self.img)
        with self.assertRaises(ProtocolError): tree_hash(self.h)
    def test_copy_is_independent(self):
        copy_tree(self.h,self.p/"copy"); write_json(self.p/"copy"/"toy.json",{"other":1}); self.assertEqual(read_json(self.h/"toy.json"),{})
    def test_safe_path_rejects_escape(self):
        with self.assertRaises(ValueError): safe_path(self.h,"../refs.jsonl")
    def test_safe_path_rejects_prefix_sibling(self):
        with self.assertRaises(ValueError): safe_path(self.h,"../h_secret/key")
    def test_safe_path_accepts_local(self): self.assertEqual(safe_path(self.h,"toy.json"), self.h/"toy.json")
    def test_git_export_committed_code(self):
        repo=self.p/"repo"; repo.mkdir(); git(repo,"init"); h=repo/"domains/med_m5/harness"; h.mkdir(parents=True)
        write_json(h/"toy.json",{"old":1}); git(repo,"add","."); git(repo,"commit","-m","H0"); commit=git(repo,"rev-parse","HEAD")
        write_json(h/"toy.json",{"uncommitted":1})
        export=code_export(repo,commit,self.p/"export")
        self.assertEqual(read_json(export/"toy.json"),{"old":1})


class TestData(Fixture):
    def test_input_order_and_related_questions_preserved(self):
        e,_=self.stream(); self.assertEqual([r["id"] for r in e.manifest["cases"]],["x0","x1","x2"])
        self.assertTrue(all(r["group_keys"]==["same_image"] for r in e.manifest["cases"]))
    def test_public_label_rejected(self):
        x={**self.case,"images":[str(self.img)],"reference":"A"}; f=self.p/"bad.jsonl"; f.write_text(json.dumps(x))
        with self.assertRaises(ProtocolError): prepare(f,self.p/"out")
    def test_duplicate_ids_rejected(self):
        x={**self.case,"images":[str(self.img)]}; f=self.p/"bad.jsonl"; f.write_text(json.dumps(x)+"\n"+json.dumps(x))
        with self.assertRaises(ProtocolError): prepare(f,self.p/"out")
    def test_missing_image_rejected(self):
        x={**self.case,"images":["missing.png"]}; f=self.p/"bad.jsonl"; f.write_text(json.dumps(x))
        with self.assertRaises(ProtocolError): prepare(f,self.p/"out")
    def test_labels_require_both_locks(self):
        e,_=self.stream()
        with self.assertRaises(ProtocolError): e.references.after_lock("x0",[self.p/"a",self.p/"b"])
    def test_mismatched_reference_ids_rejected(self):
        f=self.p/"ref.jsonl"; f.write_text('{"id":"wrong","reference":"A"}')
        with self.assertRaises(ProtocolError): References(f,["x1"])


class TestSteps(Fixture):
    def test_prediction_locked_before_feedback(self):
        state=self.initialize(); pred=transition(self.runtime,self.h,state,self.p/"pred","predict",case=self.case)
        self.assertTrue((self.p/"pred/locked.json").exists()); self.assertIsNone(self.runtime.calls[-1]["feedback"])
    def test_resume_does_not_predict_twice(self):
        state=self.initialize(); transition(self.runtime,self.h,state,self.p/"pred","predict",case=self.case)
        n=len(self.runtime.calls); transition(self.runtime,self.h,state,self.p/"pred","predict",case=self.case)
        self.assertEqual(n,len(self.runtime.calls))
    def test_locked_memory_mutation_detected(self):
        state=self.initialize(); p=transition(self.runtime,self.h,state,self.p/"pred","predict",case=self.case)
        write_json(Path(p["state"])/"memory.json",["tamper"])
        with self.assertRaises(ProtocolError): transition(self.runtime,self.h,state,self.p/"pred","predict",case=self.case)
    def test_source_state_is_immutable(self):
        state=self.initialize(); before=tree_hash(state); pred=transition(self.runtime,self.h,state,self.p/"pred","predict",case=self.case)
        transition(self.runtime,self.h,pred["state"],self.p/"obs","observe",case=self.case,prediction=pred["result"],feedback={"correct":0,"reference":"B"})
        self.assertEqual(before,tree_hash(state))
    def test_observe_crash_resume(self):
        state=self.initialize(); p=transition(self.runtime,self.h,state,self.p/"pred","predict",case=self.case)
        self.runtime.fail_observe_once=True
        with self.assertRaises(RuntimeError): transition(self.runtime,self.h,p["state"],self.p/"obs","observe",case=self.case,prediction=p["result"],feedback={"correct":0,"reference":"B"})
        a=transition(self.runtime,self.h,p["state"],self.p/"obs","observe",case=self.case,prediction=p["result"],feedback={"correct":0,"reference":"B"})
        self.assertEqual(read_json(Path(a["state"])/"memory.json"),["x1"])
    def test_usage_missing_is_not_free(self):
        with self.assertRaises(ProtocolError): require_prediction({"answer":"A","trace":[]})


def evaluation(rewards, panel="p", cost=10):
    # rewards: task x repeat
    k=len(rewards[0]); tasks={str(i):NS(rewards=r) for i,r in enumerate(rewards)}
    return NS(k=k,per_task=tasks,S=sum(map(sum,rewards))/(len(rewards)*k),C=cost,
        n_expected=len(rewards)*k,missing=0,
        extra={"panel_id":panel,"replay_start_hash":"s","feedback_mode":"full_label","metric_id":"m"})


class TestSelection(unittest.TestCase):
    def test_strict_gain_accepted(self): self.assertTrue(check_pair(evaluation([[0,0],[1,1]]),evaluation([[1,1],[1,1]]))[0])
    def test_tie_not_accepted(self): self.assertFalse(check_pair(evaluation([[1,1]]),evaluation([[1,1]],cost=1))[0])
    def test_cheaper_loss_rejected(self): self.assertFalse(check_pair(evaluation([[1,1]]),evaluation([[0,0]],cost=1))[0])
    def test_expensive_gain_allowed(self): self.assertTrue(check_pair(evaluation([[0,0]],cost=1),evaluation([[1,1]],cost=1000))[0])
    def test_mixed_repeat_regression_rejected(self): self.assertFalse(check_pair(evaluation([[1,0],[0,0]]),evaluation([[0,1],[0,1]]))[0])
    def test_different_panels_rejected(self): self.assertFalse(check_pair(evaluation([[0,0]]),evaluation([[1,1]],panel="future"))[0])
    def test_different_memory_rejected(self):
        a=evaluation([[0,0]]); b=evaluation([[1,1]]); b.extra["replay_start_hash"]="future"; self.assertFalse(check_pair(a,b)[0])
    def test_missing_trial_rejected(self):
        a=evaluation([[0,0]]); b=evaluation([[1,1]]); b.missing=1; self.assertFalse(check_pair(a,b)[0])
    def test_nonbinary_reward_rejected(self):
        a=evaluation([[0,0]]); b=evaluation([[1,0.5]]); self.assertFalse(check_pair(a,b)[0])
    def test_positive_floor_enforced(self): self.assertFalse(check_pair(evaluation([[0,1]]),evaluation([[1,1]]),min_gain=0.6)[0])


class TestStream(Fixture):
    def test_stream_first_pass_counts(self):
        e,s=self.stream(); result=e.run(); self.assertEqual(result["completed"],3); self.assertEqual(result["correct"],{"fixed_m5":0,"rrsi_acc":0})
    def test_both_predictions_before_any_feedback(self):
        e,_=self.stream(); e.run()
        ops=[r["op"] for r in self.runtime.calls if r["id"]=="x0"]
        self.assertEqual(ops,["predict","predict","observe","observe"])
    def test_related_next_question_sees_previous_memory(self):
        e,_=self.stream(); e.run()
        preds=[r for r in self.runtime.calls if r["id"]=="x1" and r["op"]=="predict"]
        self.assertTrue(all(r["memory"]==["x0"] for r in preds))
    def test_search_each_feedback_not_every_ten(self):
        e,s=self.stream(5); e.run(); self.assertEqual(s.events,[1,2,3,4])
    def test_no_search_after_last_question(self):
        e,s=self.stream(); e.run(); self.assertNotIn(3,s.events)
    def test_stop_and_resume_keeps_primary_locks(self):
        e,s=self.stream(5); e.run(2); n=sum(r["op"]=="predict" for r in self.runtime.calls); e.run()
        self.assertEqual(n,4); self.assertEqual(sum(r["op"]=="predict" for r in self.runtime.calls),10)
    def test_arms_do_not_share_state(self):
        e,_=self.stream(); e.run(); r=read_json(e.out/"primary/q000001/completed.json")
        self.assertNotEqual(r["states_after_observe"]["fixed_m5"],r["states_after_observe"]["rrsi_acc"])
    def test_primary_report_has_no_replay(self):
        e,_=self.stream(); e.run(); r=report(e.out); self.assertEqual(r["scores"]["overall"]["fixed_m5"]["n"],3)
    def test_historical_start_excludes_current_feedback(self):
        e,_=self.stream(); e.run(); row=read_json(e.out/"primary/q000002/completed.json")
        self.assertEqual(read_json(Path(row["before_evolving"])/"memory.json"),["x0"])


class TestReplay(Fixture):
    def test_sequential_replay_writer_updates_next_question(self):
        e,_=self.stream(); e.run(); completed=[read_json(p) for p in sorted((e.out/"primary").glob("*/completed.json"))]
        repo=self.p/"r"; h=repo/"domains/med_m5/harness"; copy_tree(self.h,h)
        d=MedM5Domain(repo,self.runtime,self.scorer); d.bind(completed,completed[-1]["states_after_observe"]["rrsi_acc"],2)
        before=len(self.runtime.calls); d.run(repo,self.p/"search","j",d.evolve_ids(),2)
        calls=self.runtime.calls[before:]; preds=[r for r in calls if r["op"]=="predict"]
        self.assertEqual(preds[0]["memory"],["x0"]); self.assertEqual(preds[1]["memory"],["x0","x1"])
        self.assertEqual(preds[2]["memory"],["x0"])
    def test_panel_change_changes_identity(self):
        e,_=self.stream(); e.run(); rows=[read_json(p) for p in sorted((e.out/"primary").glob("*/completed.json"))]
        d=MedM5Domain(self.p,self.runtime,self.scorer); d.bind(rows[:2],rows[1]["states_after_observe"]["rrsi_acc"],2); a=d.panel_id
        d.bind(rows,rows[2]["states_after_observe"]["rrsi_acc"],2); self.assertNotEqual(a,d.panel_id)


class TestConfig(unittest.TestCase):
    def config(self): return read_json(Path(__file__).parents[1]/"configs/ttl_official.json")
    def test_template_cannot_run(self):
        with self.assertRaises(ProtocolError): validate_config(self.config())
    def test_budget_is_explicit(self):
        b=budget(self.config()); self.assertEqual(b["primary_question_predictions"],848)
        self.assertEqual(b["max_sequential_replay_predictions_without_failures_or_retries"],100500)
    def test_invalid_candidate_count(self):
        c=self.config(); c["search"]["candidates"]=9
        with self.assertRaises(ProtocolError): validate_config(c,template_ok=True)
    def test_negative_accuracy_threshold(self):
        c=self.config(); c["search"]["min_gain"]=-0.1
        with self.assertRaises(ProtocolError): validate_config(c,template_ok=True)
    def test_outcome_only_not_silently_supported(self):
        c=self.config(); c["feedback_mode"]="outcome_only"
        with self.assertRaises(ProtocolError): validate_config(c,template_ok=True)

if __name__=="__main__": unittest.main()
