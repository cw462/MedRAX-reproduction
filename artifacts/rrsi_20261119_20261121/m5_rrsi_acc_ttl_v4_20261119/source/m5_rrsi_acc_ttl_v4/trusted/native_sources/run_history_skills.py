"""Plus H1/S1/HS or isolated training reflections using original paid worker."""
import argparse
import json
import os
from pathlib import Path

import run_sampled_vlm as worker
from run_direct_vlm import read,read_lines,write,now
from history_skills import ID,VERSION,REFLECTION_SYSTEM,history_block,skills_block,parse_reflection,retrieve


class Adapter:
    def prepare(self,cfg,out):
        self.cfg=cfg;self.out=out;self.base=Path(cfg['root'])/'runs'/ID
        self.rows=read_lines(Path(cfg['root'])/cfg['input'])
        self.categories=read(self.base/'inputs/categories.json')
        self.folds=read(self.base/'inputs/folds.json')
        arm=cfg['arm']
        if arm=='Reflection':
            self.training=read(self.base/'training/source_examples.json')
            ids=set(read(self.base/'training/reflection_ids.json'));self.rows=[r for r in self.rows if r['question_id'] in ids]
        else:
            self.histories=read(self.base/'inputs/histories.json') if arm in ('H1','HS') else None
            if arm in ('S1','HS'):self.stores=read(self.base/'skills/crossfit_stores.json')['stores']
        if len(self.rows)!=cfg['question_count']:raise ValueError('frozen_arm_denominator')
        worker.frozen_write(out/'selection.json',{'rows':self.rows})
        worker.frozen_write(out/'question_selection.json',{'rows':self.rows})
        worker.frozen_write(out/'protocol.json',dict(cfg,implementation_commit=os.environ.get('MEDRAX_CODE_COMMIT','unrecorded'),labels_loaded_by_generation=arm=='Reflection',reflection_training_exception=arm=='Reflection'))
        return self.rows

    def legal(self,row):
        if self.cfg['arm']=='Reflection':return self.categories[row['question_id']]
        return worker.question_parts(row['question'])[1]

    def parse(self,text,legal):
        return parse_reflection(text,legal) if self.cfg['arm']=='Reflection' else worker.parse_answer(text,legal)

    def request(self,row,cfg,out):
        messages,images=worker.request_for(row,cfg)
        q=row['question_id'];arm=cfg['arm']
        if arm=='Reflection':
            messages[0]['content']=REFLECTION_SYSTEM
            block='SOURCE FOLD TRAINING EXAMPLE\n'+json.dumps(self.training[q],ensure_ascii=False)+'\nOfficial categories: '+','.join(self.categories[q])+'\n'
            messages[1]['content'].insert(0,{'type':'text','text':block})
        else:
            block=''
            if self.histories is not None:block+=history_block(self.histories[row['case_id']])
            if arm in ('S1','HS'):
                selected=retrieve(row,self.categories[q],self.folds[row['case_id']],self.stores)
                worker.frozen_write(out/'retrieval'/ (q+'.json'),{'question_id':q,'target_fold':self.folds[row['case_id']],'skill_ids':[s['skill_id'] for s in selected],'source_case_ids':[s['source_case_id'] for s in selected],'source_folds':[s['source_fold'] for s in selected]})
                block+=skills_block(selected)
            messages[1]['content'].insert(0,{'type':'text','text':block})
        return messages,images


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--approval',type=Path);p.add_argument('--api-key-stdin',action='store_true');p.add_argument('--prepare-only',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--acknowledge-stop')
    a=p.parse_args();cfg=read(a.config)
    if cfg['experiment_id']!=ID or cfg['plan_version']!=VERSION or cfg['model']!='qwen3.7-plus' or cfg['arm'] not in ('H1','S1','HS','Reflection'):raise ValueError('plus_only_scope')
    if not a.api_key_stdin:a.prepare_only=True
    if not a.prepare_only:
        approval=read(a.approval) if a.approval else {}
        if approval.get('experiment_id')!=ID or approval.get('status')!='approved' or approval.get('models')!=['qwen3.7-plus'] or approval.get('plan_version')!=VERSION:raise ValueError('explicit_plus_user_approval_required')
    out=a.out.resolve();expected=(Path(cfg['root'])/'runs'/ID/'arms'/cfg['arm']).resolve()
    if out!=expected:raise ValueError('new_namespace_required')
    out.mkdir(parents=True,exist_ok=True)
    with worker.exclusive_lock(out/'.generation.lock'):
        try:return worker.run(a,cfg,out,adapter=Adapter())
        except Exception as exc:
            write(out/'fatal_error.json',{'utc':now(),'error_type':type(exc).__name__,'message':worker.safe_error(exc)})
            state=read(out/'status.json') if (out/'status.json').exists() else {}
            write(out/'status.json',dict(state,status='stopped',updated_utc=now(),error_type=type(exc).__name__))
            raise


if __name__=='__main__':raise SystemExit(main())
