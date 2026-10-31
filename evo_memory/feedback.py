from pathlib import Path
from .io import read,write,lines,now


class PredictionJournal:
    def __init__(self,root):self.root=Path(root)
    def path(self,qid,arm):return self.root/qid/arm/'prediction.json'
    def get(self,qid,arm):
        p=self.path(qid,arm);return read(p) if p.exists() else None
    def commit(self,prediction):
        if prediction['status'] not in {'completed','invalid_answer','request_failed'}:raise ValueError('not_a_submitted_terminal_prediction')
        p=self.path(prediction['question_id'],prediction['arm'])
        if p.exists():
            if read(p)!=prediction:raise ValueError('submitted_prediction_is_immutable')
        else:write(p,prediction)


class FeedbackBroker:
    """Only this interface holds eval references; release requires disk commits."""
    def __init__(self,label_source,rows,case_map,journal,output,arms=('E','ES')):
        import hashlib,json
        raw=Path(label_source).read_bytes();identity={'sha256':hashlib.sha256(raw).hexdigest(),'filename':Path(label_source).name}
        identity_path=Path(output).parent/'feedback_source_identity.json'
        if identity_path.exists() and read(identity_path)!=identity:raise ValueError('feedback_source_changed_on_resume')
        if not identity_path.exists():write(identity_path,identity)
        self._labels={x['question_id']:x for x in map(json.loads,raw.decode('utf-8-sig').splitlines()) if x}
        self.rows={r['question_id']:r for r in rows};self.case_map=case_map;self.journal=journal;self.output=Path(output);self.arms=arms
        self.cases={}
        for step,row in enumerate(rows,1):self.cases.setdefault(case_map[row['question_id']],[]).append((step,row['question_id']))
        if any(q not in self._labels for q in self.rows):raise ValueError('broker_reference_coverage_missing')
    def ready(self,case_id):
        return all(self.journal.get(q,a) is not None for _,q in self.cases[case_id] for a in self.arms)
    def release(self,case_id,step):
        if not self.ready(case_id) or step<max(i for i,_ in self.cases[case_id]):raise ValueError('feedback_before_all_case_predictions_committed')
        p=self.output/(case_id+'.json')
        if p.exists():return read(p)
        from experiments.v12_evidence import question_parts
        values={}
        for _,qid in self.cases[case_id]:
            label=self._labels[qid];answer=str(label['answer']).strip().upper();options=question_parts(self.rows[qid]['question'])[1]
            if answer not in options:raise ValueError('invalid_broker_reference')
            values[qid]={'answer':answer,'correct_choice_text':options[answer],
                         'explanation':label.get('explanation') or None}
        value={'case_id':case_id,'released_after_step':step,'released_utc':now(),'references':values,
               'committed_predictions':{q:{a:str(self.journal.path(q,a)) for a in self.arms} for _,q in self.cases[case_id]}}
        write(p,value);return value
    def released_cases(self):return {p.stem for p in self.output.glob('*.json')} if self.output.exists() else set()
