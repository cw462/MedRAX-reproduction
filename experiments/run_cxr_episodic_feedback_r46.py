"""Two-stage source feedback then frozen-memory development; no dev-label access."""
import argparse
import json
from pathlib import Path
import sys
import time

from cxr_episodic_feedback_r46 import *


def main():
    p=argparse.ArgumentParser()
    for key in ['data','out']:p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--phase',choices=['source','development'],required=True)
    p.add_argument('--config',type=Path);p.add_argument('--execute',action='store_true');p.add_argument('--api-key-stdin',action='store_true')
    a=p.parse_args()
    from run_cxr_vqa_toolsets import PaidCalls,exclusive_lock,freeze_protocol,now,save
    source=rows(a.data/'source_inputs.jsonl');development=rows(a.data/'inputs.jsonl')
    spec=make_protocol(source,development,a.data);a.out.mkdir(parents=True,exist_ok=True)
    with exclusive_lock(a.out/'.generation.lock'):
        freeze_protocol(a.out,spec)
        if not a.execute:
            print(json.dumps({'status':'zero_paid_prepared','source_calls':24,'development_calls':54,'tools':0}));return
        assert a.config and a.api_key_stdin
        arms=['SOURCE','SOURCE_REFLECT'] if a.phase=='source' else list(ARMS)
        assert not any(list((a.out/'calls'/arm).glob('*/*/started.json')) for arm in arms),'existing_send_no_automatic_restart'
        assert not any((a.out/'predictions'/arm).exists() for arm in arms),'phase_already_started'
        key=sys.stdin.readline().strip();assert key
        paid=PaidCalls(read(a.config),spec,a.out,key)
        tick=time.monotonic();started=now()
        def call(row,arm,payload):
            paid.call(row,arm,1,payload)
            folder=a.out/'calls'/arm/row['question_id']/'1';receipt=read(folder/'result.json')
            assert receipt.get('response_received') is True and not receipt.get('error'),'unhealthy_request_receipt'
            return read(folder/'response.json')
        if a.phase=='source':
            episodes=[]
            for index,row in enumerate(source):
                q=row['question_id'];info=image_info(row,a.data)
                ctx=retrieve(row,info,episodes);assert set(ctx['included_ids'])<=set(spec['source_question_ids'][:index])
                save(a.out/'contexts/SOURCE'/(q+'.json'),ctx)
                raw=call(row,'SOURCE',messages(row,info,SOURCE_SYSTEM,ctx));value=terminal(raw,q)
                # The source prediction is committed BEFORE current truth is read.
                predicted_at=now();prediction={'question_id':q,'answer':value['answer'],'reason':value['reason'],
                    'case_description':value['phi'],'extraction':value['extraction'],'saved_before_current_reference':True,
                    'current_reference_read':False,'utc':predicted_at,'main_calls':1,'tool_calls':0}
                prediction_path=a.out/'predictions/SOURCE'/(q+'.json');save(prediction_path,prediction)
                annotation=read(a.data/'source_labels'/(q+'.json'));assert annotation['question_id']==q and annotation['image_id']==row['image_id']
                assert prediction_path.is_file()
                feedback={'question_id':q,'source_annotation':annotation['answer'],'model_answer':value['answer'],
                    'model_reason':value['reason'],'case_description_before_feedback':value['phi'],'actual_tool_trajectory':[]}
                save(a.out/'feedback'/(q+'.json'),{'prediction_saved_at':predicted_at,'reference_revealed_at':now(),
                    'prediction_path':str(prediction_path),'y':annotation['answer'],'source_split':'train'})
                reflection=call(row,'SOURCE_REFLECT',messages(row,info,REFLECTION_SYSTEM,feedback=feedback))
                reflected=terminal(reflection,q)['aux'];sigma=reflected.get('sigma');gamma=reflected.get('gamma')
                valid=all(isinstance(x,str) and x.strip() for x in [sigma,gamma])
                episode={'question_id':q,'question':row['question'],'phi':value['phi'] or row['question'],'tau':[],
                    'y_hat':value['answer'],'y':annotation['answer'],'sigma':sigma,'gamma':gamma,
                    'image_pixel_sha256':info['pixel_sha256'],'image_vector':info['image_vector'],
                    'source_split':'train','source_index':index,'accepted_structural_fields':valid,
                    'not_clinically_adjudicated':True,'utc':now()}
                save(a.out/'episodes_raw'/(q+'.json'),episode)
                if valid:episodes.append(episode)
                save(a.out/'source_progress.json',{'processed':index+1,'accepted':len(episodes),'last':q,'utc':now()})
                print(json.dumps({'source_saved':q,'current_feedback_after_prediction':True,'accepted':valid}),flush=True)
            for arm in ['SOURCE','SOURCE_REFLECT']:
                for filename in ['started.json','request.json','response.json','result.json']:
                    assert {p.parent.parent.name for p in (a.out/'calls'/arm).glob('*/1/'+filename)}==set(spec['source_question_ids'])
            save(a.out/'frozen_E.json',{'episodes':episodes,'source_question_ids':spec['source_question_ids'],
                 'source_only':True,'development_labels_read':False,'frozen_at':now()})
            save(a.out/'source.complete.json',{'source_cases':12,'main_calls':24,'tools':0,'accepted_episodes':len(episodes),
                 'started_at':started,'completed_at':now(),'elapsed_s':time.monotonic()-tick,'frozen_E_sha256':sha(a.out/'frozen_E.json')})
        else:
            assert read(a.out/'source.complete.json')['main_calls']==24
            ready=read(a.out/'MEMORY_REVIEW_READY.json')
            assert ready['source_only'] is True and ready['review_completed'] is True
            library=a.out/'approved_E.json';assert ready['approved_library_sha256']==sha(library)
            approved=read(library);episodes=approved['episodes'];assert episodes and approved['source_only'] is True
            assert {e['question_id'] for e in episodes}<=set(spec['source_question_ids'])
            frozen_hash=sha(library)
            for index,row in enumerate(development):
                q=row['question_id'];info=image_info(row,a.data)
                for arm in ARMS if index%2==0 else ARMS[::-1]:
                    assert sha(library)==frozen_hash,'development_library_changed'
                    ctx=retrieve(row,info,episodes) if arm=='P1' else {'included_ids':[],'examples':[],'query_uses_reference':False}
                    save(a.out/'contexts'/arm/(q+'.json'),ctx)
                    result=terminal(call(row,arm,messages(row,info,BASE,ctx)),q)
                    save(a.out/'predictions'/arm/(q+'.json'),{'question_id':q,'arm':arm,'answer':result['answer'],
                        'status':'explicit_answer' if result['answer'] is not None else 'missing_explicit_answer',
                        'extraction':result['extraction'],'main_calls':1,'tool_calls':0,'source_memory_ids':ctx['included_ids'],
                        'development_reference_read':False,'utc':now()})
                    print(json.dumps({'development_saved':q,'arm':arm}),flush=True)
            expected={x['question_id'] for x in development}
            for arm in ARMS:
                assert {x.stem for x in (a.out/'predictions'/arm).glob('*.json')}==expected
                assert len(list((a.out/'calls'/arm).glob('*/1/response.json')))==27
                save(a.out/('complete_'+arm+'.json'),{'questions':27,'main_calls':27,'tools':0,'utc':now()})
            save(a.out/'development.complete.json',{'pairs':27,'main_calls':54,'tools':0,'started_at':started,
                'completed_at':now(),'elapsed_s':time.monotonic()-tick,'approved_E_sha256':frozen_hash,
                'development_feedback':False})


if __name__=='__main__':main()
