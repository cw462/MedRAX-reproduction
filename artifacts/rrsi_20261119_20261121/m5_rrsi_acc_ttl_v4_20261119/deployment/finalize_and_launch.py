"""Freeze the verified native M5 TTL configuration and launch its single arm."""
import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--controller',action='store_true')
    args=parser.parse_args()
    root=args.root.resolve();package=root/'source/m5_rrsi_acc_ttl_v4'
    sys.path.insert(0,str(package))
    from m5rrsi.io import read_json,write_json,write_once,tree_hash,file_hash,git
    from m5rrsi.validation import validate_config,budget,freeze,verify_frozen,runtime_fingerprint
    from m5rrsi.upstream import verify_lock
    from integration.native_gateway import read_key
    cfgpath=root/'configs/run.json';cfg=read_json(cfgpath)
    gateway=read_json(root/'trusted/gateway.json')
    env=dict(os.environ)
    env[cfg['search_llm']['api_key_env']]=read_key(gateway['key_files']['main'])
    env[cfg['search_llm']['base_url_env']]=gateway['main_base_url']
    env['PYTHONPATH']=str(package)
    env['PYTHONDONTWRITEBYTECODE']='1'
    os.environ.update({name:env[name] for name in (cfg['search_llm']['api_key_env'],cfg['search_llm']['base_url_env'])})
    control=root/'deployment';control.mkdir(exist_ok=True)
    marker=control/'formal_controller.started.json'
    run=Path(cfg['run_dir'])

    if args.controller:
        state={'pid':os.getpid(),'status':'running','time':time.time(),'config':str(cfgpath)}
        write_json(control/'formal_controller.status.json',state)
        try:
            warm=control/'first_five.completed.json'
            phases=[] if warm.is_file() else [('first_five',['--stop-after','5'])]
            phases.append(('full_resume',[]))
            for name,extra in phases:
                if (run/'STOP').exists():
                    write_json(control/'formal_controller.status.json',{**state,'status':'stopped_by_STOP','phase':name})
                    return
                command=[sys.executable,'-B','-m','m5rrsi.cli','run','--config',str(cfgpath),*extra]
                if (run/'run_identity.json').is_file():command.append('--resume')
                log=control/(name+'.log')
                with log.open('ab') as output:
                    process=subprocess.run(command,cwd=package,env=env,stdout=output,stderr=subprocess.STDOUT)
                write_json(control/(name+'.exit.json'),{'exit':process.returncode,'time':time.time(),'log':str(log)})
                if process.returncode:
                    raise RuntimeError('Formal phase failed: '+name+'; see '+str(log))
                progress=read_json(run/'progress.json')
                if name=='first_five':
                    if progress['completed']<5:
                        raise RuntimeError('First segment returned before five questions completed')
                    write_once(warm,{'completed':5,'search_checkpoint_finished_before_resume':True})
            progress=read_json(run/'progress.json')
            if progress['completed']!=848:raise RuntimeError('Full formal stream is incomplete')
            from m5rrsi.report import report
            summary=report(run)
            write_json(control/'formal_controller.status.json',{**state,'status':'complete','completed':848,'summary':summary})
            write_json(control/'formal_controller.exit.json',{'exit':0,'time':time.time()})
        except Exception as error:
            write_json(control/'formal_controller.status.json',{**state,'status':'failed','error':str(error),'time':time.time()})
            write_json(control/'formal_controller.exit.json',{'exit':1,'time':time.time()})
            raise
        return

    if marker.is_file():
        prior=read_json(marker);proc=Path('/proc',str(prior['pid']),'cmdline')
        if proc.is_file() and b'--controller' in proc.read_bytes().split(b'\0'):
            print(json.dumps({'status':'already_running',**prior}));return
    if not (run/'frozen.json').is_file():
        probe=root/'evidence/native_h0_probe'
        done=read_json(probe/'completed.json')
        records=done['completed']
        if len(records)!=2 or done['formal_predictions']!=0:
            raise RuntimeError('Two nonformal native integration cases must finish first')
        initial=read_json(probe/'initial_parity.json')
        if initial.get('equal') is not True or initial['seed_nodes']!=0:
            raise RuntimeError('Canonical empty H0 parity did not pass')
        harness=Path(cfg['upstream_repo'])/'domains/med_m5/harness'
        hhash=tree_hash(harness)
        evidence=[probe/'completed.json',probe/'initial_parity.json']
        predictions=[];feedbacks=[];observations=[];node_counts=[]
        for i,record in enumerate(records,1):
            q=probe/f'q{i:06d}';locked=read_json(q/'predict/locked.json');observed=read_json(q/'observe/locked.json');feedback=read_json(q/'feedback.json')
            if locked['result']['harness_sha256']!=hhash or locked['result']['model']!='qwen3.7-plus':
                raise RuntimeError('Native H0 source or actor identity changed')
            if observed['result']['usage']['authoritative'] is not True or locked['result']['usage']['authoritative'] is not True:
                raise RuntimeError('Native gateway usage is not authoritative')
            if not observed['result']['memory_ingest']['accepted']:
                raise RuntimeError('Native memory ingest did not accept the actual locked prediction')
            graph=read_json(Path(observed['state'])/'cerebra_fusion_memory/cf_database.json')
            node_counts.append(len(graph['nodes']))
            predictions.append(locked);feedbacks.append(feedback)
            observations.extend(locked['result']['trace']['prediction'].get('observations',[]))
            evidence.extend([q/'predict/locked.json',q/'feedback.json',q/'observe/locked.json',q/'completed.json'])
        standalone=probe/'standalone_chest_xray_expert.json'
        if standalone.is_file():
            observations.append(read_json(standalone)['result']['observation']);evidence.append(standalone)
        gpu_tools={'chest_xray_expert','maira2_grounded_report','xray_phrase_grounding','llava_med_qa','llava_rad','medgemma','medvlm_r1'}
        gpu_observations=[value for value in observations if value.get('status')=='completed'
                          and value.get('tool',value.get('backend')) in gpu_tools
                          and any(event.get('status')=='completed' for event in
                                  value.get('actual_model_events', value.get('observation',{}).get('actual_model_events',[]) if isinstance(value.get('observation'),dict) else []))]
        if not gpu_observations or not max(node_counts):
            raise RuntimeError('A real completed GPU tool trace and a successful native graph write are required')
        ids={row['id'] for row in records};model_receipts=[];models=set();closed=[]
        for path in (root/'gateway_audit').glob('*/registered.json'):
            registration=read_json(path);meta=registration['metadata'];row=meta.get('native_row') or {}
            if row.get('question_id') not in ids or not path.with_name('closed.json').is_file():continue
            receipt=read_json(path.with_name('closed.json'))
            if receipt.get('authoritative') is not True or receipt.get('usage_unknown'):raise RuntimeError('Native provider usage unresolved')
            closed.append(path.with_name('closed.json'))
            for receipt_path in path.parent.glob('model_receipts/*.json'):
                value=read_json(receipt_path);models.add(value['model_returned']);model_receipts.append(receipt_path)
        if not any(name.startswith('qwen3.7-plus') for name in models) or 'deepseek-flash' not in models:
            raise RuntimeError('Real Qwen and official DeepSeek model-return receipts are missing')
        evidence.extend(closed+model_receipts)
        binding=read_json(root/'trusted/gateway.provenance.json')['native_binding']
        native_provider=Path(binding['memory_runtime'])/'EvolveLab/providers/cerebra_fusion_memory_provider.py'
        transplanted_provider=harness/'EvolveLab/providers/cerebra_fusion_memory_provider.py'
        if native_provider.read_text()!=transplanted_provider.read_text():
            raise RuntimeError('The transplanted native provider source differs')

        def write_report(key,checks,files,**details):
            paths=[str(Path(p).resolve()) for p in files]
            if not all(Path(p).is_file() for p in paths):raise RuntimeError('A required native evidence file is missing')
            write_json(cfg['evidence'][key],{'status':'passed','passed_checks':checks,'evidence_files':paths,**details})
        write_report('h0_parity_report',['original_images','native_tool_trace','native_memory_writer','source_tree_execution'],evidence,
                     scope='Actual nonformal medical H0 integration; locked predictions precede reference feedback',
                     model_returned=sorted(models),canonical_initial_normalization=['metadata.last_updated'],
                     graph_nodes_after_observe=node_counts,real_same_image_pair=False,
                     native_provider_sources=[str(native_provider),str(transplanted_provider)],
                     native_provider_file_hashes={str(native_provider):file_hash(native_provider),
                                                  str(transplanted_provider):file_hash(transplanted_provider)},
                     same_image_note='No real same-image pair is claimed; software timing checks are separate')

        native_source=Path(binding['experiment_sources'])
        parser_path=native_source/'cxr_author_alignment.py'
        spec=importlib.util.spec_from_file_location('_native_probe_parser',parser_path)
        original=importlib.util.module_from_spec(spec);sys.modules[spec.name]=original;spec.loader.exec_module(original)
        original_grader=native_source/'r54_author_metrics.py'
        text=original_grader.read_text();tree=ast.parse(text)
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='outcomes')
        namespace=dict(vars(original));exec(ast.get_source_segment(text,function),namespace)
        adapter_spec=importlib.util.spec_from_file_location('_protected_native_score',package/'integration/native_score.py')
        adapter=importlib.util.module_from_spec(adapter_spec);adapter_spec.loader.exec_module(adapter)
        manifest=read_json(root/'integration_inputs/stream.json');parity=[]
        for row,locked,feedback in zip(manifest['cases'],predictions,feedbacks):
            options={x['label']:x['text'] for x in row['options']};native_row={'question_id':row['id'],'options':options}
            reference=feedback['reference'];reference=reference['answer'] if isinstance(reference,dict) else reference
            for raw in (locked['result']['terminal_raw'],'{}','invalid output','{"answer":"","reason":""}'):
                explicit=original.extract(raw,row['id'],options).answer
                adapted={'explicit_answer':explicit,'choice':original.choice(explicit,options) if explicit is not None and options else None}
                expected=int(namespace['outcomes'](native_row,adapted,reference,random.Random(0))['aligned_correct'])
                actual=adapter.score({'id':row['id'],'dataset':row['dataset'],'options':row['options'],
                         'answer':locked['result']['answer'],'terminal_raw':raw,'reference':reference})['correct']
                if actual!=expected:raise RuntimeError('Protected scorer differs from the native scorer')
                parity.append({'case_id':row['id'],'original_locked_response':raw==locked['result']['terminal_raw'],
                               'native_correct':expected,'protected_correct':actual})
        if cfg['expected_questions']!=848 or read_json(cfg['manifest'])['n']!=848:raise RuntimeError('Formal denominator changed')
        parity_path=root/'evidence/scorer_native_comparison.json'
        write_json(parity_path,{'comparisons':parity,'integration_denominator':2,'formal_denominator':848})
        write_report('native_scorer_report',['same_parser','same_denominator','invalid_answer_policy'],
                     [parity_path,parser_path,original_grader,package/'integration/native_score.py',*evidence[:10]],
                     metric_id=cfg['metric_id'],formal_denominator=848)

        isolation_path=root/'evidence/process_isolation.json';worker_path=root/'evidence/process_native_worker.json'
        isolation=read_json(isolation_path);worker=read_json(worker_path)
        witness=json.loads(isolation['stdout'])
        if isolation['status']!='passed' or isolation['exit']!=0:raise RuntimeError('Actual process isolation did not pass')
        if not all(witness.get(name) is True for name in ('host_root_hidden','host_shm_hidden','harness_readonly','native_cache_readonly','memory_writable')):
            raise RuntimeError('Required process file boundaries are absent')
        if witness['uid']!=cfg['runtime']['worker_uid'] or witness['caps_effective']!=0:raise RuntimeError('Candidate privilege boundary changed')
        if worker['check']['status']!='passed' or worker['initialize']['status']!='passed':raise RuntimeError('Native process worker is not verified')
        if gateway['limits']!={'model_calls':None,'tool_calls':None,'output_tokens':2048}:raise RuntimeError('Native resource limits changed')
        if gateway['protocol']['model']!='qwen3.7-plus' or 'token-plan.' not in gateway['main_base_url']:raise RuntimeError('Qwen Token Plan binding changed')
        if gateway['runtime']['tools']['chest_xray_expert']['revision']!='4934e91451945c8218c267aae9c34929a7677829':raise RuntimeError('Original CheXagent revision changed')
        write_report('sandbox_gateway_report',['no_future_files','no_other_arm_state','model_pinned','tool_versions_pinned','gateway_enforces_limits','authoritative_usage'],
                     [isolation_path,worker_path,root/'trusted/gateway.json',root/'trusted/gateway.provenance.json',*model_receipts,*closed],
                     isolation='chroot_uid_shared_network',network_difference='Shared host network, explicitly authorized by the user',
                     limits=gateway['limits'],authoritative_usage=True)
        upstream_report=Path(cfg['evidence']['upstream_contract_report']);up=read_json(upstream_report)
        rebased=[]
        for name in up['evidence_files']:
            path=Path(name)
            if not path.is_file():path=upstream_report.parent/path.name
            if not path.is_file():raise RuntimeError('Actual official-core evidence is missing: '+str(path))
            rebased.append(str(path.resolve()))
        up['evidence_files']=rebased;write_json(upstream_report,up)
        verify_lock(cfg['upstream_repo'],cfg['upstream_lock'])
        git(cfg['upstream_repo'],'add','--','domains/med_m5')
        changed=subprocess.run(['git','diff','--cached','--quiet'],cwd=cfg['upstream_repo']).returncode
        if changed:git(cfg['upstream_repo'],'commit','-m','Bind native M5 harness for accuracy-first TTL')
        cfg['initial_commit']=git(cfg['upstream_repo'],'rev-parse','HEAD')
        cfg['runtime']['rootfs']=str(root/'cpu-rootfs002')
        write_json(cfgpath,cfg)
        if cfg.get('primary_arms')!=['rrsi_acc']:raise RuntimeError('Only the new RRSI arm is authorized')
        estimate=budget(cfg)
        if estimate['primary_question_predictions']!=848 or estimate['max_sequential_replay_predictions_without_failures_or_retries']!=100500:
            raise RuntimeError('The declared formal budget changed')
        write_json(root/'evidence/final_budget.json',estimate)
        validate_config(cfg);runtime_fingerprint(cfg);freeze(cfg)
    else:
        verify_frozen(cfg)

    log=control/'formal_controller.log'
    with log.open('ab') as output:
        process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--root',str(root),'--controller'],
                    cwd=package,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
    result={'pid':process.pid,'config':str(cfgpath),'run_dir':str(run),'initial_commit':cfg['initial_commit'],
            'log':str(log),'time':time.time(),'first_segment_questions':5,'automatic_resume':True}
    write_json(marker,result)
    print(json.dumps({'status':'launched',**result},indent=2))


if __name__=='__main__':
    main()
