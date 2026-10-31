import hashlib
import json
import math
import os
from datetime import datetime,timezone
from pathlib import Path


def now():return datetime.now(timezone.utc).isoformat()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def lines(path):
    p=Path(path)
    return [json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()] if p.exists() else []
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def write(path,value):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp')
    with t.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    t.replace(p)
def jsonl(path,records):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8',newline='\n') as f:
        for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
_TOKENIZER=None
def configure_tokenizer(path):
    global _TOKENIZER
    from tokenizers import Tokenizer
    _TOKENIZER=Tokenizer.from_file(str(path));_TOKENIZER.no_truncation();_TOKENIZER.no_padding()
def token_estimate(text):
    return len(_TOKENIZER.encode(str(text),add_special_tokens=False).ids) if _TOKENIZER is not None else math.ceil(len(str(text).encode('utf-8'))/4)
