"""Run two separately marked native H0 integration cases before formal freezing."""
import argparse
import copy
import json
from pathlib import Path
import sys
import time
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    package = root/'source/m5_rrsi_acc_ttl_v4'
    sys.path.insert(0, str(package))
    from m5rrsi.io import read_json, write_json, write_once
    from m5rrsi.data import public_case
    from m5rrsi.process_runtime import ProcessRuntime
    from m5rrsi.runtime import NativeScorer
    from m5rrsi.steps import transition
    from integration.native_gateway import control_request

    cfg = read_json(root/'configs/run.json')
    runtime_cfg = copy.deepcopy(cfg['runtime'])
    runtime_cfg['case_metadata'] = str(root/'integration_inputs/trusted/native_cases.json')
    manifest = read_json(root/'integration_inputs/stream.json')
    if manifest['n'] != 2:
        raise RuntimeError('The native integration probe requires exactly two separately marked cases')
    metadata = read_json(runtime_cfg['case_metadata'])
    out = root/'evidence/native_h0_probe'
    out.mkdir(parents=True, exist_ok=True)
    harness = root/'upstream/rrsi-official-v4/domains/med_m5/harness'
    if not harness.is_dir():
        harness = package/'native_harness'
    runtime = ProcessRuntime(runtime_cfg, out/'runtime_audit')
    runtime.preflight()
    scorer = NativeScorer(cfg['scorer_command'], cfg['metric_id'])

    def phase(before, folder, operation, **kwargs):
        folder = Path(folder)
        attempted = folder/'probe_attempted.json'
        if attempted.is_file() and not (folder/'locked.json').is_file():
            raise RuntimeError('Incomplete prior native probe phase retained for recovery: '+str(folder))
        if not attempted.is_file():
            write_once(attempted, {'operation':operation,'time':time.time(),'scope':'nonformal_native_integration'})
        return transition(runtime,harness,before,folder,operation,seed=cfg['seed'],**kwargs)

    first = phase(None,out/'initial/first','initialize')
    second = phase(None,out/'initial/second','initialize')

    def canonical(state):
        values = {}
        for path in sorted(Path(state).rglob('*')):
            if path.is_file():
                relative = path.relative_to(state).as_posix()
                if relative == 'cerebra_fusion_memory/cf_database.json':
                    value = read_json(path)
                    value.get('metadata',{}).pop('last_updated',None)
                    values[relative] = json.dumps(value,sort_keys=True,ensure_ascii=False).encode()
                else:
                    values[relative] = path.read_bytes()
        return values

    if canonical(first['state']) != canonical(second['state']):
        raise RuntimeError('The two canonical empty H0 memory trees differ')
    initial_graph = read_json(Path(first['state'])/'cerebra_fusion_memory/cf_database.json')
    if initial_graph['nodes'] or initial_graph['edges']:
        raise RuntimeError('The integration H0 memory is not empty')
    write_once(out/'initial_parity.json',{'equal':True,'normalization':['metadata.last_updated'],
               'files':sorted(canonical(first['state'])),'seed_nodes':0})

    state = first['state']
    completed = []
    for index,row in enumerate(manifest['cases']):
        case = public_case(row)
        qdir = out/f'q{index+1:06d}'
        prediction = phase(state,qdir/'predict','predict',case=case)
        if not (qdir/'predict/locked.json').is_file():
            raise RuntimeError('No feedback is permitted before the current prediction lock')
        feedback_path = qdir/'feedback.json'
        if feedback_path.is_file():
            feedback = read_json(feedback_path)
        else:
            references = [json.loads(line) for line in (root/'integration_inputs/private/references.jsonl').read_text().splitlines() if line.strip()]
            reference = next(item['reference'] for item in references if item['id']==case['id'])
            feedback = {'correct':scorer.score(case,prediction['result'],reference),'reference':reference}
            write_once(feedback_path,feedback)
        after = phase(prediction['state'],qdir/'observe','observe',case=case,
                      prediction=prediction['result'],feedback=feedback)
        state = after['state']
        graph = read_json(Path(state)/'cerebra_fusion_memory/cf_database.json')
        record = {'id':case['id'],'dataset':case['dataset'],'scope':'nonformal_native_integration',
                  'prediction_lock':str(qdir/'predict/locked.json'),'feedback':str(feedback_path),
                  'correct':feedback['correct'],'main_usage':prediction['result']['usage'],
                  'writer_usage':after['result']['usage'],'node_count':len(graph['nodes']),
                  'edge_count':len(graph['edges']),'state':state,
                  'native_ingest':after['result'].get('memory_ingest'),
                  'harness_sha256':prediction['result']['harness_sha256']}
        write_once(qdir/'completed.json',record)
        completed.append(record)
        write_json(out/'progress.json',{'completed':len(completed),'planned':2,
                   'formal_predictions':0,'latest':record})

    standalone = out/'standalone_chest_xray_expert.json'
    observed_tool_calls = sum(item['main_usage']['tool_calls'] for item in completed)
    if observed_tool_calls == 0 and not standalone.is_file():
        case = public_case(manifest['cases'][0])
        meta = metadata[case['id']]
        standalone_state = out/'standalone_state'
        standalone_state.mkdir(exist_ok=True)
        attempted = out/'standalone_attempted.json'
        if attempted.is_file():
            raise RuntimeError('The prior standalone tool attempt needs receipt inspection before retry')
        write_once(attempted,{'time':time.time(),'scope':'standalone_probe_not_actor_selection'})
        session = control_request(runtime_cfg['control_socket'], {
            'action':'register','operation':'predict','seed':cfg['seed'],'limits':runtime_cfg['limits'],
            'state_dir':str(standalone_state),'case':case,'native_row':meta['native_row'],
            'order_item':meta['order_item'],'ordinal':meta['ordinal'],
            'image_annotations':meta['image_annotations']})
        receipt = None
        try:
            payload = {'row':meta['native_row'],'action':{'tool':'chest_xray_expert',
                       'args':{'question':case['question']}},'ordinal':1}
            request = Request(session['gateway_url']+'/tool',data=json.dumps(payload).encode(),
                              headers={'Content-Type':'application/json'},method='POST')
            with urlopen(request,timeout=900) as response:
                observation = json.load(response)
            if observation.get('ok') is not True:
                raise RuntimeError('The standalone native tool request failed')
            write_once(standalone,{'scope':'standalone_probe_not_actor_selection',
                       'case_id':case['id'],'result':observation['result']})
        finally:
            receipt = control_request(runtime_cfg['control_socket'],{'action':'close','session':session['session']})
            write_json(out/'standalone_gateway_receipt.json',receipt)

    result = {'status':'native_probe_completed','scope':'nonformal_native_integration',
              'completed':completed,'formal_predictions':0,
              'canonical_initial_parity':str(out/'initial_parity.json'),
              'standalone_tool_probe':str(standalone) if standalone.is_file() else None,
              'real_same_image_pair':False,
              'same_image_timing_evidence':'separate software tests; no real same-image pair is claimed',
              'runtime_isolation':'chroot_uid_shared_network_user_authorized'}
    write_once(out/'completed.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
