"""Continue only the diagnosed two-case immutable-progress metadata failure.

Never calls the original runner again, rewrites a prediction, or repeats a
closed source request. Inference/reflection/retrieval remain the frozen core.
"""
import argparse,hashlib,json,re,sys,time
from datetime import datetime
from pathlib import Path
from cxr_episodic_feedback_r46 import *


def restore(value,out):
    if isinstance(value,dict):
        digest=value.get('cxr_request_image_base64_sha256')
        if digest is not None:
            assert re.fullmatch('[0-9a-f]{64}',digest)
            encoded=(out/'request_image_base64'/digest).read_text(encoding='ascii')
            assert hashlib.sha256(encoded.encode('ascii')).hexdigest()==digest
            return 'data:'+value['media_type']+';base64,'+encoded
        return {k:restore(v,out) for k,v in value.items()}
    if isinstance(value,list):return [restore(x,out) for x in value]
    return value


def payload(spec,body):
    return {'model':spec['model'],'messages':body,'temperature':spec['temperature'],'top_p':spec['top_p'],
            'max_tokens':spec['max_output_tokens'],'extra_body':{'enable_thinking':False},'stream':False}


def validate_prefix(out,data):
    source=rows(data/'source_inputs.jsonl');dev=rows(data/'inputs.jsonl');spec=make_protocol(source,dev,data)
    assert read(out/'protocol.json')==spec
    assert (out.parent/'jobs/source.exitcode').read_text().strip()=='1'
    log=(out.parent/'jobs/source.log').read_text(errors='replace')
    assert 'FileExistsError:' in log and "source_progress.json" in log,'not_the_diagnosed_progress_failure'
    assert not (out/'source.complete.json').exists() and not (out/'frozen_E.json').exists()
    assert not (out/'source.effective.exitcode').exists()
    expected={x['question_id'] for x in source[:2]}
    for arm in ['SOURCE','SOURCE_REFLECT']:
        for name in ['request.json','started.json','response.json','result.json']:
            assert {p.parent.parent.name for p in (out/'calls'/arm).glob('*/1/'+name)}==expected,'unknown_or_extended_sent_prefix'
        assert len(list((out/'calls'/arm).glob('*/*/started.json')))==2,'unexpected_source_ordinal'
    for folder in ['predictions/SOURCE','feedback','episodes_raw','contexts/SOURCE']:
        assert {p.stem for p in (out/folder).glob('*.json')}==expected
    assert not list((out/'calls/P0').glob('*/*/started.json')) and not list((out/'calls/P1').glob('*/*/started.json'))
    progress=read(out/'source_progress.json');assert progress['processed']==1 and progress['last']==source[0]['question_id']
    episodes=[]
    for index,row in enumerate(source[:2]):
        q=row['question_id'];info=image_info(row,data);ctx=retrieve(row,info,episodes)
        assert read(out/'contexts/SOURCE'/(q+'.json'))==ctx
        for arm in ['SOURCE','SOURCE_REFLECT']:
            receipt=read(out/'calls'/arm/q/'1/result.json')
            assert receipt.get('response_received') is True and not receipt.get('error'),'unknown_sent_or_unhealthy_receipt'
        raw=read(out/'calls/SOURCE'/q/'1/response.json');value=terminal(raw,q);pred=read(out/'predictions/SOURCE'/(q+'.json'))
        assert all(pred.get(k)==v for k,v in [('answer',value['answer']),('reason',value['reason']),('case_description',value['phi'])])
        assert pred['current_reference_read'] is False and pred['saved_before_current_reference'] is True
        assert restore(read(out/'calls/SOURCE'/q/'1/request.json'),out)==payload(spec,messages(row,info,SOURCE_SYSTEM,ctx))
        annotation=read(data/'source_labels'/(q+'.json'));note=read(out/'feedback'/(q+'.json'))
        assert annotation['question_id']==q and annotation['image_id']==row['image_id'] and note['y']==annotation['answer']
        assert datetime.fromisoformat(note['reference_revealed_at'])>=datetime.fromisoformat(pred['utc'])
        feedback={'question_id':q,'source_annotation':annotation['answer'],'model_answer':value['answer'],
            'model_reason':value['reason'],'case_description_before_feedback':value['phi'],'actual_tool_trajectory':[]}
        assert restore(read(out/'calls/SOURCE_REFLECT'/q/'1/request.json'),out)==payload(spec,messages(row,info,REFLECTION_SYSTEM,feedback=feedback))
        reflected=terminal(read(out/'calls/SOURCE_REFLECT'/q/'1/response.json'),q)['aux'];episode=read(out/'episodes_raw'/(q+'.json'))
        assert all(episode.get(k)==v for k,v in [('source_index',index),('phi',value['phi'] or row['question']),('tau',[]),
             ('y_hat',value['answer']),('y',annotation['answer']),('sigma',reflected.get('sigma')),('gamma',reflected.get('gamma')),
             ('image_pixel_sha256',info['pixel_sha256']),('image_vector',info['image_vector'])])
        valid=all(isinstance(episode.get(k),str) and episode[k].strip() for k in ['sigma','gamma'])
        assert episode['accepted_structural_fields']==bool(valid)
        if valid:episodes.append(episode)
    return source,dev,spec,episodes


def main():
    p=argparse.ArgumentParser()
    for key in ['data','out']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--config',type=Path);p.add_argument('--execute',action='store_true');p.add_argument('--api-key-stdin',action='store_true')
    a=p.parse_args()
    from run_cxr_vqa_toolsets import PaidCalls,exclusive_lock,now,save
    with exclusive_lock(a.out/'.generation.lock'):
        source,dev,spec,episodes=validate_prefix(a.out,a.data)
        if not a.execute:
            print(json.dumps({'validated_closed_prefix_cases':2,'closed_main_requests':4,'remaining_main':20,'no_api':True}));return
        gate=read(a.out.parent/'RECOVERY_REVIEW_READY.json');assert gate['review_completed'] is True and gate['verdict']=='ready'
        assert a.config and a.api_key_stdin
        key=sys.stdin.readline().strip();assert key;paid=PaidCalls(read(a.config),spec,a.out,key);tick=time.monotonic()
        save(a.out/'recovery/source_recovery_started.json',{'known_failure':'immutable source_progress metadata overwrite',
            'closed_prefix_cases':2,'prefix_requests':4,'prefix_retried':False,'frozen_core_changed':False,'utc':now()})
        for index,row in enumerate(source[2:],start=2):
            q=row['question_id'];info=image_info(row,a.data);ctx=retrieve(row,info,episodes)
            assert set(ctx['included_ids'])<=set(spec['source_question_ids'][:index])
            save(a.out/'contexts/SOURCE'/(q+'.json'),ctx)
            def call(arm,body):
                paid.call(row,arm,1,body);folder=a.out/'calls'/arm/q/'1';receipt=read(folder/'result.json')
                assert receipt.get('response_received') is True and not receipt.get('error')
                return read(folder/'response.json')
            value=terminal(call('SOURCE',messages(row,info,SOURCE_SYSTEM,ctx)),q);stamp=now()
            predpath=a.out/'predictions/SOURCE'/(q+'.json')
            save(predpath,{'question_id':q,'answer':value['answer'],'reason':value['reason'],'case_description':value['phi'],
                'extraction':value['extraction'],'saved_before_current_reference':True,'current_reference_read':False,
                'utc':stamp,'main_calls':1,'tool_calls':0})
            annotation=read(a.data/'source_labels'/(q+'.json'));assert annotation['question_id']==q and annotation['image_id']==row['image_id']
            assert predpath.is_file()
            feedback={'question_id':q,'source_annotation':annotation['answer'],'model_answer':value['answer'],
                'model_reason':value['reason'],'case_description_before_feedback':value['phi'],'actual_tool_trajectory':[]}
            save(a.out/'feedback'/(q+'.json'),{'prediction_saved_at':stamp,'reference_revealed_at':now(),
                'prediction_path':str(predpath),'y':annotation['answer'],'source_split':'train'})
            reflected=terminal(call('SOURCE_REFLECT',messages(row,info,REFLECTION_SYSTEM,feedback=feedback)),q)['aux']
            sigma=reflected.get('sigma');gamma=reflected.get('gamma');valid=all(isinstance(x,str) and x.strip() for x in [sigma,gamma])
            episode={'question_id':q,'question':row['question'],'phi':value['phi'] or row['question'],'tau':[],
                'y_hat':value['answer'],'y':annotation['answer'],'sigma':sigma,'gamma':gamma,'image_pixel_sha256':info['pixel_sha256'],
                'image_vector':info['image_vector'],'source_split':'train','source_index':index,'accepted_structural_fields':bool(valid),
                'not_clinically_adjudicated':True,'utc':now()}
            save(a.out/'episodes_raw'/(q+'.json'),episode)
            if valid:episodes.append(episode)
            # A different immutable progress event for each completed case.
            save(a.out/'source_progress_events'/(f'{index+1:04d}.json'),{'processed':index+1,'accepted':len(episodes),'last':q,'utc':now()})
            print(json.dumps({'source_saved':q,'known_recovery':True,'accepted':bool(valid)}),flush=True)
        expected=set(spec['source_question_ids'])
        for arm in ['SOURCE','SOURCE_REFLECT']:
            for name in ['request.json','started.json','response.json','result.json']:
                assert {p.parent.parent.name for p in (a.out/'calls'/arm).glob('*/1/'+name)}==expected
            assert len(list((a.out/'calls'/arm).glob('*/*/started.json')))==12
            for q in expected:
                receipt=read(a.out/'calls'/arm/q/'1/result.json');assert receipt.get('response_received') is True and not receipt.get('error')
        save(a.out/'frozen_E.json',{'episodes':episodes,'source_question_ids':spec['source_question_ids'],'source_only':True,
             'development_labels_read':False,'frozen_at':now()})
        starts=[read(p)['utc'] for p in (a.out/'calls').glob('*/*/1/started.json')];started=min(starts);completed=now()
        save(a.out/'source.complete.json',{'source_cases':12,'main_calls':24,'tools':0,'accepted_episodes':len(episodes),
             'started_at':started,'completed_at':completed,'recovery_elapsed_s':time.monotonic()-tick,
             'wall_seconds_including_interruption':(datetime.fromisoformat(completed)-datetime.fromisoformat(started)).total_seconds(),
             'frozen_E_sha256':sha(a.out/'frozen_E.json'),'completion_mode':'known_progress_metadata_failure_recovery',
             'original_source_exit':1,'closed_prefix_cases_reused_without_api':2,'prefix_main_requests_not_retried':4})
        with (a.out/'source.effective.exitcode').open('x',encoding='utf-8') as f:f.write('0\n')
        print('SOURCE_KNOWN_METADATA_RECOVERY_COMPLETE',flush=True)


if __name__=='__main__':main()
