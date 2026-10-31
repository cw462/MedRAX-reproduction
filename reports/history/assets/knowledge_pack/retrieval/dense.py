"""Real optional neural encoders: CPU ONNX MiniLM or sentence-transformers.

Model weights live in an external user cache, not in the knowledge bundle.
"""
from pathlib import Path
import os
import urllib.request

DEFAULT_MODEL='sentence-transformers/all-MiniLM-L6-v2'
DEFAULT_ONNX='onnx/model_quint8_avx2.onnx'


def download_file(url,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.partial')
    try:
        with urllib.request.urlopen(url,timeout=90) as response, open(tmp,'wb') as output:
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                output.write(chunk)
        tmp.replace(path)
    finally:
        if tmp.exists():tmp.unlink()


class Encoder:
    def __init__(self,backend='onnx',model=DEFAULT_MODEL,cache=None,allow_download=False,
                 onnx_file=DEFAULT_ONNX,threads=2):
        self.backend=backend;self.model=model;self.onnx_file=onnx_file
        self.cache=Path(cache or os.environ.get('MEDRAX_EMBED_CACHE',Path.home()/'.cache'/'medrax_embeddings'))
        if backend=='sentence_transformers':
            from sentence_transformers import SentenceTransformer
            self.encoder=SentenceTransformer(model,cache_folder=str(self.cache),device='cpu',local_files_only=not allow_download)
        elif backend=='onnx':
            import onnxruntime as ort
            from tokenizers import Tokenizer
            folder=self.cache/model.replace('/','--')
            files={onnx_file:folder/'model.onnx','tokenizer.json':folder/'tokenizer.json'}
            for remote,path in files.items():
                if not path.exists():
                    if not allow_download:raise FileNotFoundError(f'Missing model file {path}; run build_index with --allow-model-download or supply --model-cache.')
                    download_file(f'https://huggingface.co/{model}/resolve/main/{remote}',path)
            opts=ort.SessionOptions();opts.intra_op_num_threads=threads;opts.inter_op_num_threads=1
            self.encoder=ort.InferenceSession(str(files[onnx_file]),sess_options=opts,providers=['CPUExecutionProvider'])
            self.tokenizer=Tokenizer.from_file(str(files['tokenizer.json']))
            self.tokenizer.enable_truncation(max_length=256)
            self.tokenizer.enable_padding(pad_id=0,pad_token='[PAD]')
        else:raise ValueError('Unknown dense backend '+backend)

    def encode(self,texts,batch_size=32):
        import numpy as np
        if not texts:return np.empty((0,0),dtype=np.float32)
        if self.backend=='sentence_transformers':
            return self.encoder.encode(texts,batch_size=batch_size,normalize_embeddings=True,show_progress_bar=False).astype('float32')
        result=[]
        names={x.name for x in self.encoder.get_inputs()}
        for start in range(0,len(texts),batch_size):
            enc=self.tokenizer.encode_batch(texts[start:start+batch_size])
            data={'input_ids':np.asarray([x.ids for x in enc],dtype=np.int64),
                  'attention_mask':np.asarray([x.attention_mask for x in enc],dtype=np.int64),
                  'token_type_ids':np.asarray([x.type_ids for x in enc],dtype=np.int64)}
            out=self.encoder.run(None,{k:v for k,v in data.items() if k in names})[0]
            if out.ndim==3:
                mask=data['attention_mask'][...,None].astype(np.float32)
                out=(out*mask).sum(1)/np.maximum(mask.sum(1),1)
            result.append(out/np.maximum(np.linalg.norm(out,axis=1,keepdims=True),1e-12))
        return np.concatenate(result).astype('float32')
