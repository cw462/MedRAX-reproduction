#!/usr/bin/env python3
"""SERVER-ONLY integration test: real official Run.round/propose/critic, scripted LLM,
synthetic runtime. No paid API and no medical dataset. Not executed in the authoring
container because GitHub clone was unavailable. Do not report it as passed until run.
"""
from pathlib import Path
import argparse
import contextlib
import importlib
import io
import json
import shutil
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from m5rrsi.io import command, git, read_json, write_json, file_hash
from m5rrsi.search import OfficialSearch
from m5rrsi.data import prepare, References
from m5rrsi.engine import StreamEngine
from test_local import ToyRuntime, ToyScorer


def main():
    p=argparse.ArgumentParser(); p.add_argument("--repo",required=True); p.add_argument("--lock",required=True); p.add_argument("--report",required=True)
    a=p.parse_args(); out=Path(a.report).resolve(); out.parent.mkdir(parents=True,exist_ok=True)
    log=io.StringIO()
    with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(log):
        root=Path(d); repo=root/"rrsi"
        command(["git","clone","--no-hardlinks",str(Path(a.repo).resolve()),str(repo)])
        lock=read_json(a.lock); git(repo,"checkout","--detach",lock["commit"])
        template=Path(__file__).resolve().parents[1]/"domain_template"
        h=repo/"domains/med_m5/harness"; shutil.copytree(template,repo/"domains/med_m5")
        write_json(h/"toy.json",{"better":False})
        git(repo,"add","domains/med_m5"); git(repo,"commit","-m","synthetic integration H0")
        h0=git(repo,"rev-parse","HEAD")
        img=root/"toy.png"; img.write_bytes(b"synthetic-only")
        public=[]
        for i in range(3): public.append({"id":f"test{i}","dataset":"synthetic","question":"synthetic question",
            "options":[{"label":"A","text":"one"},{"label":"B","text":"two"}],"images":[str(img)]})
        src=root/"public.jsonl"; src.write_text("\n".join(json.dumps(x) for x in public))
        manifest=prepare(src,root/"stream.json")
        refs=root/"refs.jsonl"; refs.write_text("\n".join(json.dumps({"id":x["id"],"reference":"B"}) for x in public))
        cfg=read_json(Path(__file__).resolve().parents[1]/"configs/ttl_official.json")
        cfg.update(upstream_repo=str(repo),upstream_lock=str(Path(a.lock).resolve()),initial_commit=h0,
                   run_dir=str(root/"run"),expected_questions=3)
        cfg["search"].update(max_rounds=2,candidates=1,replay_window_cases=2,repair_rounds=0)
        rt=ToyRuntime(); scorer=ToyScorer(); search=OfficialSearch(cfg,rt,scorer)
        analyst=importlib.import_module("rrsi.analyst"); critic=importlib.import_module("rrsi.critic"); proposer=importlib.import_module("rrsi.propose")
        # Only the model RESPONSES are scripted; official action parser, edits, review,
        # git worktrees, evaluations, selection, histories and Run.round still execute.
        analyst.generate=lambda *x,**kw: json.dumps({"action":"report","failure_modes":[{"mode":"toy","n_tasks":1}],"capability_gaps":[],"success_habits":[]})
        critic.generate=lambda *x,**kw: json.dumps({"verdict":"accept","reasons":[],"risk_notes":["SYNTHETIC TEST"]})
        def done(): return {"action":"done","summary":"synthetic mechanism test","edits":[{
            "id":"C1","component":"config","hypothesis":"Synthetic fixture behavior change",
            "targets_mode":"toy","predicted_affected":["q000001"],
            "retroactive_check":"Synthetic only; no medical performance claim"}]}
        actions=iter([
            {"action":"edit_file","path":"toy.json","old":"false","new":"true"},done(),
            {"action":"write_file","path":"test_note.py","content":"# Synthetic second candidate; should not improve the score.\n"},done()])
        proposer.generate=lambda *x,**kw: json.dumps(next(actions))
        engine=StreamEngine(cfg,manifest,References(refs,[x["id"] for x in public]),rt,scorer,search)
        result=engine.run()
        assert result["correct"]=={"fixed_m5":0,"rrsi_acc":2}, result
        q2=read_json(root/"run/primary/q000002/completed.json")
        assert q2["commits"]["rrsi_acc"]!=h0
        checkpoint=read_json(root/"run/search/checkpoints/after_000002/done.json")
        assert checkpoint["accepted"] is False  # equal accuracy must not promote
        assert search.run.frontier()["incumbent"]["extra"]["panel_id"]==search.domain.panel_id
        details={"result":result,"h0":h0,"selected":checkpoint["commit"],"upstream_commit":lock["commit"],
                 "real_loop_module":str(Path(search.loop.__file__).relative_to(repo)),
                 "official_loop_hash":file_hash(repo/"rrsi/loop.py"),"synthetic_only":True}
    logpath=out.with_suffix(".log"); logpath.write_text(log.getvalue(),encoding="utf-8")
    detailpath=out.with_name(out.stem+"_details.json"); write_json(detailpath,details)
    write_json(out,{"status":"passed","passed_checks":["real_Run_round","official_proposal_path","accuracy_patch","version_inheritance"],
                    "evidence_files":[str(logpath),str(detailpath)],"scope":"real upstream integration with scripted LLM and toy runtime; no Qwen/medical run"})
    print(f"PASSED; evidence: {out}")

if __name__=="__main__": main()
