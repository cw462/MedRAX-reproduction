"""New tiny cache-construction witness, not an old result/metric test."""
import ast,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'local_assets'))
import publish_cxr_online_skill_r49 as publication

ast.parse((ROOT/'local_assets/publish_cxr_online_skill_r49.py').read_text(encoding='utf-8'))
original=publication.read;reads=[]
def observed(path):reads.append(str(path));return original(path)
publication.read=observed
evidence=publication.REPORT/'evidence/chexbench'
first=original(evidence/'image_assets.json')[0]
for doc in (evidence/'manifest.json',evidence/'new_cache_witness/q/request.json'):
    path=os.path.relpath((evidence/first['path']).resolve(),doc.parent).replace('\\','/')
    assert publication.public_asset_semantics({'path':path,'nonpath':'data:image/png;base64,'+'a'*10000},doc)=={'path':'PUBLIC_ASSET:0','nonpath':'data:image/png;base64,'+'a'*10000}
assert len(reads)==1 and len(publication._PUBLIC_TARGETS)==1
print(json.dumps({'new_parent_cache_construction_cases':2,'asset_map_reads_for_two_distinct_parents':len(reads),
  'passed':True,'new_inference_scoring_export_or_image_hash_checks':0}))
