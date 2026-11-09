"""Preserve the second prepare stop and the precise remaining cost correction."""
import json
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[1];report=root/'reports/cxr_online_skill_r49_20261108'
p=report/'deployment_source/PUBLICATION_PATH_CACHE_CONTINUATION.json';v=json.loads(p.read_text())
assert 'second_prepare_later_native_result' not in v
assert not (root/'local_assets/r49_publication/prepared.json').exists()
assert not (report/'PUBLICATION_MANIFEST.json').exists()
v['second_prepare_later_native_result']={'session':82168,'process_id':64084,'native_exit':1,
 'utc':datetime.now(timezone.utc).isoformat(),'operator_stop_after_confirmed_exact_command':True,
 'reason':'first optimization still resolved all asset targets per new document parent; cache already-resolved target set once per dataset as in successful public verifier',
 'internal_gate_position_not_observed':True,'manifest_or_allowlist_written':False,
 'inference_scoring_export_operations':0,'successful_prepare_claim':False}
v['second_performance_delta']={'resolved_asset_targets_cached_once_per_dataset':True,
 'same_ordered_relative_path_substitutions':True,'literal_absent_anchor_extended_to_root_assets_prefix':True,
 'new_distinct_parent_construction_witnesses':2,'asset_map_reads_for_two_distinct_parents':1,'passed':True,
 'new_model_review':False,'new_file_image_hash_gate':False,'per_gate_progress_output_added':True}
p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
meta=report/'RESULT_CLAIM_METADATA.json';m=json.loads(meta.read_text(encoding='utf-8-sig'))
m['additional_post_review_reporting_delta']=v
meta.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
with (report/'TESTS.md').open('a',encoding='utf-8') as f:f.write('\nLater actual continuation: native82168 was also deliberately stopped with exit1 and no manifest/allowlist. Its mapping cache still resolved every asset once per new document parent. The next source caches resolved asset targets once per dataset, preserving substitutions; two new distinct-parent construction witnesses passed, with one asset-map read. Gate progress output was added. No inference/private metrics/export/model review was repeated.\n')
with (report/'CLAIMS_FROM_RESULTS.md').open('a',encoding='utf-8') as f:f.write('\nA second publication-only performance correction caches resolved asset targets once per dataset. The prior optimized prepare82168 was stopped with native1 and no outputs; its exact internal gate position remains unknown. Two distinct-parent construction witnesses passed, with one asset-map read; original sources and all stops are retained. The final follow-up reuses the actual completed prepare gate for sequential content/index/base-guard phases and stages changed/new report files plus fixed source/index entries, preserving the original full allowlist. These reporting deltas were not separately model-reviewed.\n')
print(json.dumps({'preserved_prepare_native_exits':[1,1],'resolved_target_cache_witness_passed':True,'next_prepare_not_yet_started':True}))
