"""Repair only inherited original-image URL bases in the public VQA comparator."""
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/cxr_online_skill_r49_20261108'
EVIDENCE = REPORT / 'evidence/vqarad'
RECEIPT = REPORT / 'deployment_source/VQARAD_IMAGE_LINK_REPAIR.json'

if RECEIPT.exists():
    raise RuntimeError('portable_link_repair_already_completed')
source = EVIDENCE / 'comparison_sources.json'
inputs = {r['question_id']: r for r in (json.loads(line) for line in (EVIDENCE / 'inputs.jsonl').read_text(encoding='utf-8').splitlines() if line.strip())}
value = json.loads(source.read_text(encoding='utf-8'))
pattern = re.compile(r'(?:\.\./)+data/vqarad_cxr/assets/([A-Za-z0-9_.-]+\.(?:jpg|jpeg|png|webp))')
changes = []
for arm, cases in value.items():
    for qid, case in cases.items():
        names = {Path(p).name for p in inputs[qid]['images']}
        def portable(item):
            if isinstance(item, dict):
                return {k: portable(v) for k, v in item.items()}
            if isinstance(item, list):
                return [portable(v) for v in item]
            if not isinstance(item, str):
                return item
            def replace(match):
                name = match.group(1)
                if name not in names or not (EVIDENCE / 'assets' / name).is_file():
                    raise ValueError('original_image_filename_not_bound_to_current_question:' + qid)
                new = 'assets/' + name
                changes.append({'arm': arm, 'question_id': qid, 'old': match.group(0), 'portable': new})
                return new
            return pattern.sub(replace, item)
        cases[qid] = portable(case)
if not changes:
    raise RuntimeError('no_observed_legacy_image_base_to_repair')
backup = REPORT / 'deployment_source/vqarad_comparison_sources.before_image_link_repair.json'
if backup.exists():
    raise RuntimeError('original_public_bundle_backup_already_exists')
shutil.copyfile(source, backup)
source.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
RECEIPT.write_text(json.dumps({'scope': 'Portable image URL-base repair only, using exact question_id/current-original filename membership and already exported image existence.', 'original_public_bundle': backup.relative_to(REPORT).as_posix(), 'changes': changes, 'original_private_predictions_and_scores_modified': False, 'new_inference_or_scoring_calls': 0, 'hash_or_pixel_checks': False}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
shutil.copyfile(__file__, REPORT / 'deployment_source/repair_r49_vqarad_public_image_links.py')
print(json.dumps({'portable_image_references_repaired': len(changes), 'new_inference_or_scoring_calls': 0}))
