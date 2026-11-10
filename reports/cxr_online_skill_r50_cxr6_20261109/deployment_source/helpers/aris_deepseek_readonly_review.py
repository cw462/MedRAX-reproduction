"""Fresh/continued user-selected DeepSeek Claude Code review, isolated settings."""
import argparse,json,os,subprocess,uuid
from pathlib import Path
from datetime import datetime
from urllib.parse import urlsplit
from deepseek_review_credential import user_supplied_key
ROOT=Path(__file__).resolve().parents[1]


def put(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    p=argparse.ArgumentParser();p.add_argument('--trace',type=Path,required=True);p.add_argument('--prompt',type=Path,required=True)
    p.add_argument('--resume');a=p.parse_args();trace=a.trace.resolve();trace.mkdir(parents=True,exist_ok=True)
    assert not (trace/'started.json').exists(),'review_already_dispatched_do_not_retry_unknown'
    route=subprocess.run(['python','-X','utf8','C:/Users/cheng/aris_repo/tools/reviewer_route.py','--project',str(ROOT),
          '--host','codex','--tier','deep','--reviewer','claude-code','--model','deepseek-v4-pro'],capture_output=True,text=True,encoding='utf-8',check=True)
    (trace/'route.json').write_text(route.stdout,encoding='utf-8')
    cfg=json.loads(Path('C:/Users/cheng/.claude/settings.json').read_text(encoding='utf-8-sig'));env=os.environ.copy()
    for key in list(env):
        if key.startswith('ANTHROPIC_'):env.pop(key)
    env['ANTHROPIC_BASE_URL']=cfg['env']['ANTHROPIC_BASE_URL'];env['ANTHROPIC_AUTH_TOKEN']=user_supplied_key()
    for name in ['ANTHROPIC_MODEL','ANTHROPIC_DEFAULT_OPUS_MODEL','ANTHROPIC_DEFAULT_SONNET_MODEL','ANTHROPIC_DEFAULT_HAIKU_MODEL']:
        env[name]='deepseek-v4-pro'
    cli=Path(os.environ['APPDATA'])/'npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe';assert cli.is_file()
    session=a.resume or str(uuid.uuid4());prompt=a.prompt.read_text(encoding='utf-8')
    (trace/'request.md').write_text(prompt,encoding='utf-8')
    args=[str(cli),'-p','--safe-mode','--setting-sources','','--model','deepseek-v4-pro',
       '--tools','Read,Grep,Glob','--allowedTools','Read,Grep,Glob','--permission-mode','dontAsk','--no-chrome','--output-format','json']
    args+=['--resume',session] if a.resume else ['--session-id',session]
    put(trace/'started.json',{'utc':datetime.now().astimezone().isoformat(),'session_id':session,'fresh':not bool(a.resume),
        'backend':'claude-code','transport':'native CLI; raw modelUsage and native turn-count metadata required; MCP adapter omits those fields','requested_model':'deepseek-v4-pro',
        'provider_host':urlsplit(env['ANTHROPIC_BASE_URL']).hostname,'settings_sources':'none; user-supplied key only in process env','tools':['Read','Grep','Glob']})
    with (trace/'stdout.json').open('w',encoding='utf-8') as out,(trace/'stderr.log').open('w',encoding='utf-8') as err:
        proc=subprocess.Popen(args,cwd=ROOT,env=env,stdin=subprocess.PIPE,stdout=out,stderr=err,text=True,encoding='utf-8')
        put(trace/'process.json',{'pid':proc.pid,'session_id':session});proc.communicate(prompt)
    put(trace/'exit.json',{'exit_code':proc.returncode,'utc':datetime.now().astimezone().isoformat()})
    if proc.returncode!=0:
        print(json.dumps({'status':'failed','exit_code':proc.returncode,'trace':str(trace)}));return
    raw=json.loads((trace/'stdout.json').read_text(encoding='utf-8'))
    if raw.get('is_error') or not raw.get('result'):
        print(json.dumps({'status':'error_or_empty','trace':str(trace)}));return
    (trace/'response.md').write_text(raw['result']+'\n',encoding='utf-8')
    put(trace/'metadata.json',{'status':'completed','session_id':raw.get('session_id',session),'modelUsage':raw.get('modelUsage'),
        'usage':raw.get('usage'),'CLI_estimated_USD':raw.get('total_cost_usd'),'duration_ms':raw.get('duration_ms'),
        'turns':raw.get('num_turns'),'permission_denials':raw.get('permission_denials'),'provider_invoice':False,
        'identity_limit':'CLI reported service alias; no independent model-weight attestation'})
    print(json.dumps({'status':'completed','models':list((raw.get('modelUsage') or {}).keys()),'session_id':raw.get('session_id',session),'trace':str(trace)}))


if __name__=='__main__':main()
