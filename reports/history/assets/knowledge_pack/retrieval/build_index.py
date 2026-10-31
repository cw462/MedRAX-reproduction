#!/usr/bin/env python3
"""Build a portable card index; never crawls benchmark/dev documents."""
import argparse
import datetime
import json
import shutil
from pathlib import Path
from core import canonical_card,EXCLUDED_TYPES,dense_card_text


def build(args):
    cards=[];seen=set();excluded=[]
    for file in args.cards:
        with open(file,encoding='utf-8') as f:
            for line_number,line in enumerate(f,1):
                if not line.strip():continue
                c=canonical_card(json.loads(line))
                if c['kind'] in EXCLUDED_TYPES:
                    excluded.append({'file':str(file),'line':line_number,'knowledge_id':c['knowledge_id'],'reason':'nonmedical_knowledge_kind'});continue
                if c.get('split') in {'test','validation','dev'} or c.get('contains_reference_answer'):
                    excluded.append({'file':str(file),'line':line_number,'knowledge_id':c['knowledge_id'],'reason':'benchmark_or_development_material'});continue
                if c['knowledge_id'] in seen:raise ValueError('Duplicate knowledge_id '+c['knowledge_id'])
                seen.add(c['knowledge_id']);cards.append(c)
    if not cards:raise ValueError('No eligible static medical knowledge cards')
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    metadata={'schema_version':1,'built_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'card_count':len(cards),'source_count':len(set(c['source_id'] for c in cards)),
              'mode':'lexical_only','dense':None,'excluded':excluded,
              'lexical_engine':'BM25_k1_1.5_b_0.75','policy':'Only explicit curated static medical cards; no methods/dev/answers.'}
    if args.dense_backend!='none':
        try:
            import numpy as np
            from dense import Encoder
            encoder=Encoder(args.dense_backend,args.dense_model,args.model_cache,args.allow_model_download,args.onnx_file)
            vectors=encoder.encode([dense_card_text(c) for c in cards])
            np.save(out/'dense_vectors.npy',vectors)
            metadata['mode']='hybrid_bm25_dense_rrf'
            metadata['dense']={'backend':args.dense_backend,'model':args.dense_model,'onnx_file':args.onnx_file,
                               'dimension':int(vectors.shape[1]),'normalized':True,'weights_in_bundle':False}
        except Exception as e:
            if not args.allow_lexical_fallback:raise
            metadata['dense_error']=type(e).__name__+': '+str(e)
    if metadata['dense'] is None and (out/'dense_vectors.npy').exists():(out/'dense_vectors.npy').unlink()
    (out/'cards.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in cards),encoding='utf-8')
    (out/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if args.source_pages:
        destination=out/'source_pages.jsonl'
        if Path(args.source_pages).resolve()!=destination.resolve():shutil.copyfile(args.source_pages,destination)
    print(json.dumps(metadata,ensure_ascii=False,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cards',nargs='+',required=True,help='Curated static medical JSONL only')
    p.add_argument('--out',required=True)
    p.add_argument('--source-pages',help='Optional JSONL: source_id, page (1-based), text, source_file; used only for cited parent expansion')
    p.add_argument('--dense-backend',choices=['none','onnx','sentence_transformers'],default='none')
    p.add_argument('--dense-model',default='sentence-transformers/all-MiniLM-L6-v2')
    p.add_argument('--onnx-file',default='onnx/model_quint8_avx2.onnx')
    p.add_argument('--model-cache')
    p.add_argument('--allow-model-download',action='store_true')
    p.add_argument('--allow-lexical-fallback',action='store_true',help='Report downgrade explicitly if encoder is unavailable')
    build(p.parse_args())
if __name__=='__main__':main()
