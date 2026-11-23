"""Matched R54DS pair. Defaults to CheXBench with isolated state per arm."""
import argparse,getpass,json,os,subprocess,sys
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--suite',type=Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--dataset',choices=('chexbench','slake','vqarad'),default='chexbench');a=p.parse_args()
    cfg=json.loads(a.suite.read_text());script=Path(__file__).parent;key=None
    # Check both arms before starting any paid request.
    commands=[];outputs=[]
    for name,n in [('chexbench',618),('slake',114),('vqarad',116)]:
        if name!=a.dataset:continue
        r=cfg['datasets'][name]
        for mode in ('off','on'):
            out=str(Path(cfg['output_root'])/name/mode);outputs.append(Path(out).resolve())
            args=[sys.executable,str(script/'run_online_skill_r54ds.py'),'--skill',mode,'--dataset',name,'--expect-questions',str(n),
                '--config',cfg['config'],'--data',r['data'],'--reference-dir',r['reference_dir'],'--out',out,
                '--embedding-model',cfg['embedding_model'],'--embedding-base-url',cfg['embedding_base_url']]
            if mode=='on':args+=['--writer-config',cfg['writer_config']]
            if r.get('order_manifest'):args+=['--order-manifest',r['order_manifest']]
            commands.append((name,mode,out,args,r))
    if len(set(outputs))!=2:raise ValueError('outputs_must_be_isolated')
    for _,_,_,args,_ in commands:subprocess.run(args,check=True)
    if not a.execute:return
    key=getpass.getpass('Existing main model API key (hidden): ')
    writer=json.loads(Path(cfg['writer_config']).read_text())
    env=os.environ.copy()
    if not env.get(writer['api_key_env']):env[writer['api_key_env']]=getpass.getpass('DeepSeek writer API key (hidden): ')
    if not env.get(writer['api_key_env']):raise ValueError('missing_writer_key_environment')
    for name,mode,out,args,r in commands:
        subprocess.run(args+['--execute','--api-key-stdin'],input=key+'\n',text=True,check=True,env=env)
        cmd=[sys.executable,str(script/'report_skill_r54ds.py'),'--run',out,'--out',str(Path(out)/'analysis')]
        if r.get('historical'):cmd+=['--historical',r['historical']]
        subprocess.run(cmd,check=True)
        if mode=='on':
            parent=Path(out).parent
            subprocess.run([sys.executable,str(script/'compare_pair_r54ds.py'),'--off',str(parent/'off'),'--on',out,'--out',str(parent/'pair_summary.json')],check=True)
if __name__=='__main__':main()
