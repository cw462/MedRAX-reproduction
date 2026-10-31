#!/usr/bin/env python3
"""Retrieve conditional medical knowledge using current visible evidence only."""
import argparse
import json
from pathlib import Path
from core import load_index,normalized_query,query_text,retrieve


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index',required=True)
    p.add_argument('--query-json',required=True,help='Path to structured query JSON, or - for stdin')
    p.add_argument('--config',help='JSON override of deterministic retrieval defaults')
    p.add_argument('--top-k',type=int)
    p.add_argument('--out')
    p.add_argument('--model-cache')
    p.add_argument('--lexical-only',action='store_true',help='Explicit ablation; do not load neural encoder')
    p.add_argument('--require-dense',action='store_true',help='Fail instead of downgrade; use for registered dense experiment arms')
    args=p.parse_args()
    import sys
    q=json.load(sys.stdin) if args.query_json=='-' else json.loads(Path(args.query_json).read_text())
    cfg=json.loads(Path(args.config).read_text()) if args.config else {}
    if args.top_k:cfg['top_k']=args.top_k
    cards,meta=load_index(args.index);scores=None;mode='lexical_only';log=[]
    if args.require_dense and args.lexical_only:p.error('--require-dense and --lexical-only conflict')
    if meta.get('dense') and not args.lexical_only:
        try:
            import numpy as np
            from dense import Encoder
            d=meta['dense']
            encoder=Encoder(d['backend'],d['model'],args.model_cache,False,d.get('onnx_file','onnx/model_quint8_avx2.onnx'))
            vectors=np.load(Path(args.index)/'dense_vectors.npy',allow_pickle=False)
            query_vector=encoder.encode([query_text(normalized_query(q))])[0]
            if vectors.shape[0]!=len(cards) or vectors.shape[1]!=len(query_vector):raise ValueError('Dense dimensions/card count mismatch')
            scores=vectors@query_vector;mode='hybrid_bm25_dense_rrf'
            log.append('Neural embeddings: '+d['model']+' via '+d['backend'])
            if 'all-MiniLM-L6-v2' in d['model']:log.append('English encoder: use English question/evidence fields; bilingual document English summaries are indexed.')
        except Exception as e:
            if args.require_dense:raise
            log.append('Explicit downgrade to lexical_only: '+type(e).__name__+': '+str(e))
    elif args.require_dense:raise RuntimeError('Index has no dense vectors; build --dense-backend first')
    elif args.lexical_only:log.append('Explicit lexical_only ablation requested')
    result=retrieve(cards,q,cfg,args.index,scores,mode,log)
    payload=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.out:Path(args.out).write_text(payload,encoding='utf-8')
    else:print(payload,end='')
if __name__=='__main__':main()
