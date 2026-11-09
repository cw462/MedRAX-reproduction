"""Record the observed terminated prepare; no publication gate override."""
import json
from datetime import datetime,timezone
from pathlib import Path

root=Path(__file__).resolve().parents[1]
report=root/'reports/cxr_online_skill_r49_20261108'
receipt=report/'deployment_source/PUBLICATION_PATH_CACHE_CONTINUATION.json'
value=json.loads(receipt.read_text(encoding='utf-8'))
assert not (root/'local_assets/r49_publication/prepared.json').exists()
assert not (report/'PUBLICATION_MANIFEST.json').exists()
assert 'original_prepare_later_native_result' not in value
value['original_prepare_later_native_result']={'session':93625,'process_id':5396,'native_exit':1,
 'utc':datetime.now(timezone.utc).isoformat(),'operator_stop_after_confirmed_exact_command':True,
 'reason':'read-only path-normalization gate consumed over18 minutes without manifest/allowlist; same gate resumed using cached identical substitutions',
 'internal_gate_position_not_observed':True,'manifest_or_allowlist_written':False,
 'inference_scoring_export_operations':0,'successful_prepare_claim':False}
value['technical_continuation_authorized_scope']='one optimized prepare; no ready checks bypassed; original native failure retained'
receipt.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
with (report/'CLAIMS_FROM_RESULTS.md').open('a',encoding='utf-8') as f:f.write('\nThe original final-follow-up prepare native session93625 was deliberately stopped after over18 minutes in its read-only gate (actual exit1, no manifest/allowlist). A technical continuation runs the same gates with the path cache optimization; its exact internal old gate position is unknown. This does not repeat any inference/private scoring/export/model review.\n')
print(json.dumps({'original_prepare_native_exit':1,'no_manifest_written':True,'continuation_not_yet_started':True}))
