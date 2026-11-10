"""Bounded read-only diagnostics for the observed tokenizer load exception."""
import contextlib,io,json
from datetime import datetime,timezone
from deploy_cxr6_r50 import connect,remote_python,script,PREP,RUN

DEST=PREP/'failures/001_chex_104'
SOURCE=r'''
from pathlib import Path
import json
r=Path(RUN);runtime=json.loads((r/'configs/runtime.json').read_text())
model=Path(runtime['backend_config']['medvlm_model'])
v={'model_path':str(model),'resolved_model_path':str(model.resolve()),'files':{},'new_model_or_tokenizer_loads':0}
for name in ('config.json','tokenizer.json','tokenizer_config.json','preprocessor_config.json','processor_config.json'):
 p=model/name
 if p.exists():
  st=p.stat();v['files'][name]={'bytes':st.st_size,'mtime':st.st_mtime,'resolved':str(p.resolve())}
tok=json.loads((model/'tokenizer.json').read_text())
part=tok['model'];vocab=part['vocab'];merges=part.get('merges',[])
v['tokenizer_metadata']={'model_type':part.get('type'),'vocab_entries':len(vocab),'merges':len(merges),
 'diagnostic_token_in_vocab':'ViewChild' in vocab,'diagnostic_token_id':vocab.get('ViewChild'),
 'related_vocab_keys':[(k,value) for k,value in vocab.items() if 'ViewChild' in k][:8],
 'related_merges':[x for x in merges if 'ViewChild' in (x if isinstance(x,str) else ' '.join(x))][:12],
 'added_token_contains_diagnostic':any(x.get('content')=='ViewChild' for x in tok.get('added_tokens',[]))}
config=json.loads((model/'tokenizer_config.json').read_text());v['tokenizer_configuration']={k:config.get(k) for k in ('tokenizer_class','model_max_length','added_tokens_decoder') if k!='added_tokens_decoder'}
site=Path(runtime['tools']['medvlm_r1']['python']).parent.parent/'lib/python3.12/site-packages'
v['existing_package_metadata']=[{'name':p.name,'mtime':p.stat().st_mtime} for pattern in ('transformers-*.dist-info','tokenizers-*.dist-info','protobuf-*.dist-info') for p in site.glob(pattern)]
print(json.dumps(v,ensure_ascii=False))
'''

def main():
    marker=DEST/'asset_diagnostic.started.json'
    with marker.open('x',encoding='utf-8') as f:json.dump({'utc':datetime.now(timezone.utc).isoformat(),'read_only_no_model_load_or_hash_or_changes':True},f)
    output=io.StringIO()
    with connect() as client,contextlib.redirect_stdout(output):remote_python(client,script(SOURCE,RUN=RUN),timeout=30)
    result=json.loads(output.getvalue())
    with (DEST/'asset_diagnostic.completed.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
