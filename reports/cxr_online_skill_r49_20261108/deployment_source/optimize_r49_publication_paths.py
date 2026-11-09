"""Cache unchanged public path substitutions for remaining publication phases."""
import ast,json,os
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/cxr_online_skill_r49_20261108'
SOURCE=ROOT/'local_assets/publish_cxr_online_skill_r49.py'
BACKUP=REPORT/'deployment_source/publish_cxr_online_skill_r49.before_path_normalization_cache.py'

NEW='''_PUBLIC_MAPPINGS = {}


def public_asset_semantics(value, document):
    """Apply the same ordered substitutions, caching by evidence/document parent."""
    import os
    evidence = REPORT/'evidence/chexbench'
    for dataset in DATASETS:
        candidate = REPORT/'evidence'/dataset
        if document.resolve().is_relative_to(candidate.resolve()):
            evidence = candidate
            break
    cache_key = (evidence, document.parent)
    if cache_key not in _PUBLIC_MAPPINGS:
        assets = read(evidence/'image_assets.json')
        mappings = sorted([(os.path.relpath((evidence/item['path']).resolve(), document.parent).replace('\\\\', '/'),
                            'PUBLIC_ASSET:'+str(index)) for index, item in enumerate(assets)],
                          key=lambda pair: -len(pair[0]))
        # A substitution cannot occur if every old path requires this absent
        # literal substring. This avoids scanning inline base64 once per asset.
        anchor = '/assets/' if mappings and all('/assets/' in old for old, _ in mappings) else None
        _PUBLIC_MAPPINGS[cache_key] = mappings, anchor
    mappings, anchor = _PUBLIC_MAPPINGS[cache_key]
    def normalize(item):
        if isinstance(item, dict):
            return {key: normalize(child) for key, child in item.items()}
        if isinstance(item, list):
            return [normalize(child) for child in item]
        if isinstance(item, str):
            if anchor and anchor not in item:
                return item
            for old, new in mappings:
                item = item.replace(old, new)
        return item
    return normalize(value)


'''


def function(source):
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='public_asset_semantics')
    ns={'REPORT':REPORT,'DATASETS':['chexbench','slake','vqarad'],'_PUBLIC_MAPPINGS':{},
        'read':lambda p:json.loads(p.read_text(encoding='utf-8-sig'))}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'<semantic-function-only>','exec'),ns)
    return ns['public_asset_semantics']


def main():
    assert not BACKUP.exists(),'path_cache_patch_already_prepared'
    old=SOURCE.read_text(encoding='utf-8-sig')
    start=old.index('def public_asset_semantics(');end=old.index('def embedding_http_recovery(',start)
    updated=old[:start]+NEW+old[end:];ast.parse(updated)
    before,after=function(old),function(updated)
    assets=json.loads((REPORT/'evidence/chexbench/image_assets.json').read_text())
    for doc in (REPORT/'evidence/chexbench/predictions/a/example.json',REPORT/'evidence/chexbench/example.json',REPORT/'evidence/chexbench/assets/example.json'):
        relative=os.path.relpath((REPORT/'evidence/chexbench'/assets[0]['path']).resolve(),doc.parent).replace('\\','/')
        sample={'path':relative,'nested':[{'text':'before '+relative+' after'},'data:image/jpeg;base64,'+'a'*10000,'unchanged']}
        assert before(sample,doc)==after(sample,doc)
    with BACKUP.open('x',encoding='utf-8') as f:f.write(old)
    SOURCE.write_text(updated,encoding='utf-8')
    (REPORT/'deployment_source/publish_cxr_online_skill_r49.py').write_text(updated,encoding='utf-8')
    (REPORT/'deployment_source/optimize_r49_publication_paths.py').write_text(Path(__file__).read_text(encoding='utf-8'),encoding='utf-8')
    receipt={'utc':datetime.now(timezone.utc).isoformat(),'change':'same path substitutions/order; cache mappings/sort once and skip provably absent literal anchor',
      'new_synthetic_nested_path_identity_cases':3,'passed':True,'inference_scoring_export_calls':0,'original_prepare_native_session':93625,
      'original_prepare_remains_running_original_loaded_source':True,'original_source_preserved':BACKUP.name,
      'new_model_review':False,'post_review_reporting_only_delta':True}
    (REPORT/'deployment_source/PUBLICATION_PATH_CACHE_CONTINUATION.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    meta=REPORT/'RESULT_CLAIM_METADATA.json';value=json.loads(meta.read_text(encoding='utf-8-sig'))
    value['additional_post_review_reporting_delta']=receipt;meta.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (REPORT/'CLAIMS_FROM_RESULTS.md').open('a',encoding='utf-8') as f:f.write('\nPost-review publication-only performance delta: identical ordered public image URL replacements now cache mappings and skip a literal anchor proven absent. Three new nested synthetic path-equivalence cases passed; original source and receipt retained. No model review, metric, prediction, export or inference was repeated.\n')
    print(json.dumps({'status':'path_cache_prepared','new_tiny_semantic_cases_passed':3,'original_prepare_93625_not_restarted':True}))


if __name__=='__main__':main()
