"""Offline tests only. All fake-native predictions are synthetic and temporary."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openi60.common import ExperimentError, read_json, write_once
from openi60.cohort import laterality_signature, build_cohort, validate_inputs
from openi60.hook import BEGIN, END, patched_messages, make_services
from openi60.setup import prepare, verify_frozen, map_paths, NATIVE_FILES, CODE_FILES, TOOLS
from openi60.analysis import compare_cases


def row(n, left="left pleural effusion", right="right pleural effusion", study=None):
    study = study if study is not None else n
    return {"question_id": f"chexbench_openi_{n:04d}", "question": "Which finding?",
            "options": {"A": left, "B": right},
            "images": [f"images/CXR{study}_IM-001-{n:04d}.png"],
            "image_id": f"image{n}", "source": {"subset": "OpenI"}}


def minimal_manifest(rows):
    seen = {}; order = []
    for r in rows:
        key = r["image_id"]
        prev = seen.setdefault(key, [])
        order.append({"question_id": r["question_id"], "image_key": key, "previous_ids": list(prev)})
        prev.append(r["question_id"])
    return {"inputs": rows, "order": order}

class CohortTests(unittest.TestCase):
    def test_left_right(self): self.assertEqual(laterality_signature(row(1)), "<SIDE> pleural effusion")
    def test_labels_not_fixed(self):
        r = row(1); r["options"] = {"B": "right nodule", "A": "left nodule"}
        self.assertEqual(laterality_signature(r), "<SIDE> nodule")
    def test_mismatched_findings_rejected(self): self.assertIsNone(laterality_signature(row(1, "left mass", "right effusion")))
    def test_upper_lower_rejected(self): self.assertIsNone(laterality_signature(row(1, "upper lobe", "lower lobe")))
    def test_bilateral_rejected(self): self.assertIsNone(laterality_signature(row(1, "bilateral effusion", "right effusion")))
    def test_other_subset_rejected(self):
        r = row(1); r["question_id"] = "vqarad_1"; r["source"]["subset"] = "VQA-RAD"
        self.assertIsNone(laterality_signature(r))
    def test_source_label_guard(self):
        r = row(1); r["source"]["answer"] = "B"
        with self.assertRaises(ExperimentError): validate_inputs([r])
    def test_result_log_guard(self):
        r = row(1); r["correct"] = True
        with self.assertRaises(ExperimentError): validate_inputs([r])
    def test_deterministic_and_original_order(self):
        m = minimal_manifest([row(i) for i in range(1, 21)])
        a = build_cohort(m, 7, 42, 20); b = build_cohort(m, 7, 42, 20)
        self.assertEqual(a, b)
        self.assertEqual(a[2]["selected_ids"], sorted(a[2]["selected_ids"]))
        self.assertEqual(len(a[0]), 7)
    def test_pool_guard(self):
        with self.assertRaises(ExperimentError): build_cohort(minimal_manifest([row(1)]), 1, 0, 293)
    def test_duplicate_id_guard(self):
        with self.assertRaises(ExperimentError): validate_inputs([row(1), row(1)])
    def test_no_external_previous_ids(self):
        rows = [row(i) for i in range(1, 8)]
        for r in rows:
            r["image_id"] = "shared"; r["images"] = ["images/CXR1_IM-same.png"]
        sample, order, _ = build_cohort(minimal_manifest(rows), 3, 2, 7)
        for i, item in enumerate(order): self.assertEqual(item["previous_ids"], [r["question_id"] for r in sample[:i]])
    def test_same_study_excluded_from_confirmation(self):
        rows = [row(i, study=1 if i <= 3 else i) for i in range(1, 10)]
        m = minimal_manifest(rows)
        _, _, c = build_cohort(m, 5, 1, 9)
        selected = set(c["selected_ids"])
        if selected & {r["question_id"] for r in rows[:3]}:
            self.assertFalse(set(c["remaining_case_disjoint_candidate_ids"]) & {r["question_id"] for r in rows[:3]})
    def test_input_not_mutated(self):
        m = minimal_manifest([row(i) for i in range(6)]); saved = copy.deepcopy(m)
        build_cohort(m, 2, 0, 6); self.assertEqual(m, saved)
    def test_path_traversal_guard(self):
        r = row(1); r["images"] = ["../answers.json"]
        with self.assertRaises(ExperimentError): validate_inputs([r])

class HookTests(unittest.TestCase):
    def setUp(self): self.messages = [{"role": "system", "content": "native"}, {"role": "user", "content": "question"}]
    def test_baseline_same_object(self):
        outgoing, b, a = patched_messages(self.messages, "")
        self.assertIs(outgoing, self.messages); self.assertEqual(a, b)
    def test_only_system_suffix(self):
        saved = copy.deepcopy(self.messages)
        outgoing, before, after = patched_messages(self.messages, "policy")
        self.assertEqual(self.messages, saved); self.assertEqual(outgoing[1], saved[1]); self.assertTrue(after.startswith(before))
        self.assertEqual(after.count(BEGIN), 1)
    def test_duplicate_guard(self):
        messages, _, _ = patched_messages(self.messages, "policy")
        with self.assertRaises(ExperimentError): patched_messages(messages, "policy")
    def test_missing_system(self):
        with self.assertRaises(ExperimentError): patched_messages(self.messages[1:], "policy")
    def test_nonmain_unchanged(self):
        class Base:
            def __init__(self, out): self.out = out
            def call(self, row, arm, ordinal, messages): return messages
        with tempfile.TemporaryDirectory() as tmp:
            cls = make_services(Base, "policy", "L1", {"q1"})
            obj = cls(Path(tmp) / "services")
            self.assertIs(obj.call({"question_id": "tool-q"}, "R55-TOOL", 1, self.messages), self.messages)
            outgoing = obj.call({"question_id": "q1"}, "R49-AGENT", 1, self.messages)
            self.assertIn(BEGIN, outgoing[0]["content"])
            self.assertTrue((Path(tmp) / "prompt_audit/q1/1.json").exists())
    def test_wrong_arm_patch_guard(self):
        class Base:
            def call(self, row, arm, ordinal, messages): pass
        with self.assertRaises(ExperimentError): make_services(Base, "policy", "B0", {"q"})

class PairTests(unittest.TestCase):
    def test_pair_arithmetic(self):
        base = [{"question_id": str(i), "correct": c, "reference": "A", "question": "Q", "options": {"A": "a"}}
                for i, c in enumerate([0, 1, 1, 0])]
        cand = copy.deepcopy(base)
        for r, c in zip(cand, [1, 0, 1, 1]): r["correct"] = c
        _, s = compare_cases(base, cand, [str(i) for i in range(4)])
        self.assertEqual((s["gains_G"], s["harms_H"], s["net_G_minus_H"], s["delta_pp"]), (2, 1, 1, 25.0))
    def test_partial_not_ranked(self):
        with self.assertRaises(ExperimentError): compare_cases([], [], ["q"])
    def test_string_bool_not_accepted(self):
        rec = [{"question_id": "q", "correct": "False"}]
        with self.assertRaises(ExperimentError): compare_cases(rec, rec, ["q"])
    def test_reference_mismatch(self):
        with self.assertRaises(ExperimentError): compare_cases(
            [{"question_id": "q", "correct": True, "reference": "A"}],
            [{"question_id": "q", "correct": False, "reference": "B"}], ["q"])
    def test_path_map_only_selected_prefix(self):
        data = {"/old/images/a.png": {"path": "/old/x", "model": "/models/keep"}, "other": "/older/keep"}
        new = map_paths(data, Path("/old"), Path("/new"))
        self.assertEqual(new["/new/images/a.png"], {"path": "/new/x", "model": "/models/keep"})
        self.assertEqual(new["other"], "/older/keep")

# These fixtures deliberately DO NOT implement a medical model or the real scorer.
# They exercise wrapper plumbing and safety checks without credentials/network/GPU.
FAKE_SERVICE = '''
import json
from pathlib import Path
class Services:
    def __init__(self, out): self.out=out
    def call(self, row, arm, ordinal, messages):
        folder=self.out/'calls'/arm/row['question_id']/str(ordinal)
        folder.mkdir(parents=True, exist_ok=True)
        (folder/'request.json').write_text(json.dumps({'messages':messages}))
        return 'B' if '[OPENI60_L1_SOLVER_POLICY_BEGIN]' in messages[0]['content'] else 'A'
'''
FAKE_RUNNER = '''
import json,sys
from pathlib import Path
from types import SimpleNamespace
from run_r55_full848_dataset import ARMS,COUNTS
import r55_memevolve_driver003 as bridge

def save(p,v):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v))
class CheckpointMemory:
    def __init__(self,runtime,out,key,inputs,fixture=None):
        self.prefix=set()
        self.provider=SimpleNamespace(nodes={i:SimpleNamespace(content='seed'+str(i),id=str(i)) for i in range(7)},enable_tool_memory=False)
        self.model=SimpleNamespace(use_token_plan=False,calls=0)

def run_dataset(code,out,data,references,runtime):
    from skill_services_r55 import Services
    assert sys.stdin.readline().strip() and sys.stdin.readline().strip()
    m=json.loads((out/'manifest.json').read_text()); assert COUNTS['chexbench']==len(m['inputs'])
    mem=CheckpointMemory(runtime,out/'external_memory','fake',m['inputs']);service=Services(out/'services')
    for i,row in enumerate(m['inputs'],1):
        q=row['question_id']; answer=service.call(row,'R49-AGENT',1,[{'role':'system','content':'synthetic-test-system'},{'role':'user','content':row['question']}])
        stamp='2026-01-01T00:00:00+00:00'
        pred={'question_id':q,'answer':answer,'prediction_saved_at':stamp,'main_calls':1,'tool_calls':0,'observations':[],'ordinal':i,'same_image_ids':[]}
        save(out/'predictions'/m['arm']/(q+'.json'),pred)
        ref=json.loads((references/(q+'.json')).read_text())
        save(out/'feedback'/(q+'.json'),{'saved_prediction':pred,'timing':'after_immutable_prediction','released_at':stamp,'reference_annotation':{'answer':ref['answer']}})
        save(out/'external_memory/episodes'/q/'retrieval.json',{'synthetic_only':True})
        save(out/'external_memory/episodes'/q/'ingest.json',{'prediction_saved_at':stamp,'feedback_released_at':stamp})
    save(out/'complete.json',{'status':'generation_complete','questions':len(m['inputs']),'arm':m['arm']})
    result={'memory_model_calls':0,'questions':len(m['inputs']),'synthetic_only':True}
    save(out/'memory.completed.json',result);return result
'''
FAKE_SCORE = '''
import json
from run_r55_full848_dataset import COUNTS

def score_dataset(code,run):
    m=json.loads((run/'manifest.json').read_text()); assert len(m['inputs'])==COUNTS['chexbench']
    cases=[]
    for r in m['inputs']:
        q=r['question_id'];pred=json.loads((run/'predictions'/m['arm']/(q+'.json')).read_text());fb=json.loads((run/'feedback'/(q+'.json')).read_text())
        cases.append({'question_id':q,'question':r['question'],'options':r['options'],'answer':pred['answer'],'reference':fb['reference_annotation']['answer'],'correct':pred['answer']==fb['reference_annotation']['answer'],'main_calls':1,'tool_calls':0,'failed_tool_calls':0})
    out=run/'analysis';out.mkdir();s={'questions':len(cases),'correct':sum(r['correct'] for r in cases),'model_usage_by_role':{},'synthetic_only':True}
    (out/'per_question.json').write_text(json.dumps(cases));(out/'summary.json').write_text(json.dumps(s));return s
'''

def fixture(base: Path):
    native = base / "native"; code = native / "code/M5"; ex = code / "experiments"
    ex.mkdir(parents=True)
    for name in NATIVE_FILES: (native / name).write_text("# synthetic offline fixture\n")
    for name in CODE_FILES: (ex / name).write_text("# synthetic offline fixture\n")
    (native / "run_r55_11tools_m5.py").write_text(FAKE_RUNNER)
    (native / "run_r55_full848_dataset.py").write_text("COUNTS={'chexbench':618}\nARMS={'M5':'R55-M5-11tools-CheXagent8B'}\n")
    (native / "score_r55_full848_dataset.py").write_text(FAKE_SCORE)
    (native / "r55_memevolve_driver003.py").write_text("def plain(v): return str(v)\n")
    (ex / "skill_services_r55.py").write_text(FAKE_SERVICE)
    runtime = base / "runtime"
    for name in ("EvolveLab", "models", "deps"): (runtime / name).mkdir(parents=True)
    data = base / "original_data"; refs = base / "refs"; refs.mkdir()
    rows = [row(i) for i in range(1, 7)]
    views = {}
    for r in rows:
        p = data / r["images"][0]; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b"synthetic-not-a-real-image")
        views[str(p)] = {"modality": "CXR", "view": "frontal"}
        (refs / (r["question_id"] + ".json")).write_text(json.dumps({"question_id": r["question_id"], "answer": "B"}))
    m = minimal_manifest(rows)
    m.update(dataset="chexbench",arm="R55-M5-11tools-CheXagent8B",skill_enabled=False,cerebra_generated_tools=False,
             memory_provider="cerebra_fusion_memory",memory_source="078e18cb6153fdc5b888308349cb6771eb7bde8f",
             runtime={"arms":{"M":{"tools":sorted(TOOLS)}},"tools":{k:{} for k in TOOLS},
                      "backend_config":{"r54_image_views_by_path":views}},
             protocol={"model":"qwen3.7-plus","experiment_id":"synthetic"},config={},
             reference_files={r["question_id"]:{"file":r["question_id"]+".json"} for r in rows},
             embedding_model="synthetic",embedding_base_url="synthetic")
    manifest = native / "manifests/M5/chexbench.json"; manifest.parent.mkdir(parents=True); manifest.write_text(json.dumps(m))
    cfg = {"schema":"openi60_config_v1","native_root":str(native),"code_root":str(code),
           "template_manifest":str(manifest),"data_root":str(data),"references_root":str(refs),
           "memory_runtime":str(runtime),"work_dir":str(base / "work"),"prompt_file":str(ROOT / "prompts/L1_zh.txt"),
           "n":3,"seed":42,"expected_pool":6,"expected_main_model":"qwen3.7-plus","gpu":"0",
           "main_key_env":"OPENI60_MAIN_API_KEY","memory_key_env":"OPENI60_MEMORY_API_KEY","execution_order":["B0","L1"]}
    return cfg

class IntegrationTests(unittest.TestCase):
    def test_prepare_frozen_and_original_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = fixture(Path(d)); orig = Path(cfg["template_manifest"]).read_bytes()
            prepare(cfg); f = verify_frozen(Path(cfg["work_dir"]))
            self.assertEqual(f["cohort"]["n"], 3)
            self.assertEqual(Path(cfg["template_manifest"]).read_bytes(), orig)
            for name in f["image_sha256"]:
                p=Path(cfg["work_dir"])/'data'/name;self.assertFalse(p.is_symlink())
            b=read_json(Path(cfg['work_dir'])/'B0/manifest.json');l=read_json(Path(cfg['work_dir'])/'L1/manifest.json')
            self.assertEqual(b['inputs'],l['inputs']);self.assertEqual(b['order'],l['order'])
    def test_source_tamper_guard(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=fixture(Path(d));prepare(cfg)
            (Path(cfg['native_root'])/'run_r55_11tools_m5.py').write_text('# changed')
            with self.assertRaises(ExperimentError): verify_frozen(Path(cfg['work_dir']))
    def test_work_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=fixture(Path(d));prepare(cfg)
            with self.assertRaises(ExperimentError): prepare(cfg)
    def test_full_fake_native_subprocess_flow(self):
        with tempfile.TemporaryDirectory() as d:
            cfg=fixture(Path(d));prepare(cfg);work=Path(cfg['work_dir'])
            env=dict(os.environ,OPENI60_MAIN_API_KEY='SYNTHETIC_NOT_A_REAL_KEY',OPENI60_MEMORY_API_KEY='SYNTHETIC_NOT_A_REAL_KEY')
            cmd=[sys.executable,str(ROOT/'openi60_cli.py'),'run','--work',str(work)]
            no=subprocess.run(cmd,env=env,text=True,capture_output=True)
            self.assertNotEqual(no.returncode,0);self.assertFalse((work/'B0/complete.json').exists())
            result=subprocess.run(cmd+['--execute'],env=env,text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr+'\n'+result.stdout)
            summary=read_json(work/'paired_analysis/summary.json')
            self.assertEqual((summary['n'],summary['gains_G'],summary['harms_H']),(3,3,0))
            for arm in ('B0','L1'): self.assertTrue(summary['prompt_and_feedback_audit'][arm]['passed'])
            rerun=subprocess.run(cmd+['--execute'],env=env,text=True,capture_output=True)
            self.assertEqual(rerun.returncode,0,rerun.stderr)
            self.assertIn('already_scored_no_new_inference',rerun.stdout)

if __name__ == '__main__': unittest.main(verbosity=2)
