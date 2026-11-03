"""Explicit cached ONNX neural embedding adaptation; no network or TF-IDF."""
import importlib.util
import json
from pathlib import Path


class LocalEmbeddings:
    model='sentence-transformers/all-MiniLM-L6-v2 (cached ONNX)'
    def __init__(self,root,cache):
        root=Path(root);self.path=Path(cache)
        code=Path(__file__).resolve().parents[2]
        spec=importlib.util.spec_from_file_location('medrax_existing_dense',code/'reports/history/assets/knowledge_pack/retrieval/dense.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        self.encoder=mod.Encoder(cache=root/'models/medrax_embeddings',allow_download=False,threads=2)
        self.cache=json.loads(self.path.read_text()) if self.path.exists() else {}
    def vector(self,text):
        if text not in self.cache:self.cache[text]=self.encoder.encode([text])[0].tolist()
        return self.cache[text]
    def similarity(self,left,right):
        # Use the official clipping and cosine implementation.
        from medmem_agent.evolution.utils import cosine_similarity
        return cosine_similarity(self.vector(left),self.vector(right))
    def flush(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.cache));tmp.replace(self.path)
