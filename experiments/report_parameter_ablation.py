"""Development-only 2x2 report decoding diagnosis; no API and no answer labels.

The upstream source is unchanged. Each variant changes only the GenerationConfig
construction in an explicit subclass. Nonempty output is not clinical accuracy.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack, redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

import report_smoke as audit
import classifier_smoke
from single_tool_agent_smoke import load_inputs, image_paths

VARIANTS = (("upstream", False, False), ("beams_only", True, False),
            ("eos_only", False, True), ("beams_and_eos", True, True))


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','input','images-root','cache-dir','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--device',default='cuda:0')
    p.add_argument('--max-cases',type=int,default=5)
    a=p.parse_args(argv)
    if not 1<=a.max_cases<=10:p.error('Use 1..10 development images')
    repo,root,cache,out=(x.resolve() for x in (a.repo,a.images_root,a.cache_dir,a.output))
    selected=[(r,image_paths(r,root)) for r in load_inputs(a.input,a.max_cases)]
    if any(len(paths)!=1 for r,paths in selected):p.error('Requires complete single-image questions')
    out.mkdir(parents=True,exist_ok=False)
    (out/'.gitignore').write_text('*\n')
    summary={'kind':'development_report_decoding_2x2','status':'running',
             'started_utc':datetime.now(timezone.utc).isoformat(),
             'source':audit.source_provenance(repo),
             'runner_sha256':audit.sha256_file(Path(__file__)),
             'input_sha256':audit.sha256_file(a.input),
             'clinical_accuracy_evaluated':False,'reference_answers_used':False,
             'variants':[v[0] for v in VARIANTS],'results':[],'assets':[]}
    try:
        snapshots={}
        for role,spec in audit.MODEL_SPECS.items():
            path,manifest=audit.inspect_snapshot(cache,spec)
            snapshots[spec['repo_id']]=(role,path);summary['assets'].append(manifest)
        with patch.dict(os.environ,{'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1'}):
            with open(os.devnull,'w') as sink,redirect_stdout(sink),redirect_stderr(sink):
                import torch
                from transformers import GenerationConfig
                name='_report_parameter_upstream'
                spec=importlib.util.spec_from_file_location(name,repo/audit.TOOL_RELATIVE)
                module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
                class ControlledReport(module.ChestXRayReportGeneratorTool):
                    variant_name:str='upstream'
                    change_beams:bool=False
                    change_eos:bool=False
                    records:list=[]
                    def _generate_report_section(self,pixels,model,tokenizer):
                        params={**self.generation_args,'bos_token_id':model.config.bos_token_id,
                                'eos_token_id':model.config.eos_token_id,'pad_token_id':model.config.pad_token_id,
                                'decoder_start_token_id':tokenizer.cls_token_id}
                        if self.change_beams:
                            params.pop('beam_width',None);params['num_beams']=2
                        if self.change_eos:
                            eos=model.config.decoder.eos_token_id
                            if not isinstance(eos,int) or eos!=tokenizer.sep_token_id:
                                raise ValueError('Decoder EOS and tokenizer separator must agree')
                            params['eos_token_id']=eos
                        config=GenerationConfig(**params)
                        ids=model.generate(pixels,generation_config=config)
                        row=ids[0].tolist()
                        self.records.append({'length':len(row),'num_beams':config.num_beams,
                            'eos_token_id':config.eos_token_id,'pad_token_id':config.pad_token_id,
                            'contains_configured_eos':None if config.eos_token_id is None else config.eos_token_id in row,
                            'reached_max_length':len(row)>=config.max_length})
                        return tokenizer.batch_decode(ids,skip_special_tokens=True)[0]
                observed=[]
                with ExitStack() as stack:
                    for cls,kind in ((module.VisionEncoderDecoderModel,'model'),(module.BertTokenizer,'tokenizer'),(module.ViTImageProcessor,'processor')):
                        stack.enter_context(patch.object(cls,'from_pretrained',side_effect=audit.local_loader(cls.from_pretrained,kind,snapshots,observed)))
                    tool=ControlledReport(cache_dir=str(cache),device=a.device)
                if len(observed)!=6:raise ValueError('Missing verified asset loads')
                baseline_hashes={}
                for ordinal,(row,paths) in enumerate(selected,1):
                    for variant,beams,eos in VARIANTS:
                        tool.variant_name=variant;tool.change_beams=beams;tool.change_eos=eos;tool.records=[]
                        if a.device.startswith('cuda'):torch.cuda.synchronize()
                        start=time.monotonic();result=tool.invoke({'image_path':str(paths[0])})
                        if a.device.startswith('cuda'):torch.cuda.synchronize()
                        elapsed=time.monotonic()-start
                        checks=audit.validate_report(result)
                        digest=checks['report_sha256']
                        if variant=='upstream':baseline_hashes[ordinal]=digest
                        entry={'ordinal':ordinal,'question_id':str(row['question_id']),
                               'image_sha256':audit.sha256_file(paths[0]),'variant':variant,
                               'elapsed_seconds':elapsed,'generation':tool.records,
                               'same_text_as_upstream':digest==baseline_hashes[ordinal],
                               'report_sha256':digest,'report_chars':checks['report_chars']}
                        (out/f'{ordinal:02d}_{variant}.txt').write_text(result[0],encoding='utf-8')
                        summary['results'].append(entry)
                summary['status']='completed'
    except Exception as exc:
        summary.update(status='failed',error_type=type(exc).__name__)
    finally:
        summary['loaded_module_versions']=classifier_smoke.loaded_module_versions()
        summary['finished_utc']=datetime.now(timezone.utc).isoformat()
        (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({'status':summary['status'],'completed_combinations':len(summary['results'])}))
    return 0 if summary['status']=='completed' else 1

if __name__=='__main__':raise SystemExit(main())
