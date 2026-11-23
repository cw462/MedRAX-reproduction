#!/usr/bin/env python3
"""Run ON THE SERVER with GitHub access. Resolve once; record full commit+hashes.
No upstream snapshot is bundled or falsely claimed to have been downloaded locally.
"""
from pathlib import Path
import argparse
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from m5rrsi.io import command, git, write_json, file_hash, ProtocolError
from m5rrsi.upstream import source_contract

p = argparse.ArgumentParser()
p.add_argument("--dest", required=True)
p.add_argument("--ref", default="main", help="prefer a reviewed full commit; main resolves once to full SHA")
a = p.parse_args(); target = Path(a.dest).resolve()
if target.exists(): raise SystemExit("Destination already exists; do not overwrite any existing experiment")
url = "https://github.com/google-research/rrsi.git"
command(["git", "clone", url, str(target)], timeout=600)
git(target, "checkout", "--detach", a.ref)
source_contract(target)
commit = git(target, "rev-parse", "HEAD")
lock = {"repository": url, "requested_ref": a.ref, "commit": commit,
        "core_sha256": {str(f.relative_to(target)): file_hash(f) for f in sorted((target/"rrsi").rglob("*.py"))}}
lock_path = target.parent / (target.name + ".upstream.lock.json")
write_json(lock_path, lock)
template = Path(__file__).resolve().parents[1] / "domain_template"
shutil.copytree(template, target / "domains" / "med_m5")
print(f"Downloaded official commit: {commit}\nLock: {lock_path}\n"
      "Now transplant real M5 into domains/med_m5/harness and commit H0. Do NOT run the scaffold as M5.")
