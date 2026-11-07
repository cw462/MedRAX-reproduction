"""Apply explicit source-only reviews to generated candidates, without any target labels."""
import argparse
from pathlib import Path
from cxr_action_skill_r41 import read,write,sha,load

def main():
    p=argparse.ArgumentParser()
    for k in ('candidates','reviews','runtime','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();bank=read(a.candidates);review=read(a.reviews)
    if bank.get('schema')!='cxr_action_skill_r41_candidates' or bank.get('source_only') is not True:raise ValueError('not_source_candidates')
    if review.get('candidate_sha256')!=sha(a.candidates) or review.get('source_only_review') is not True or not review.get('reviewer'):raise ValueError('source_review_required')
    decisions=review['decisions'];cards=[]
    if set(decisions)!={x['id'] for x in bank['items']}:raise ValueError('review_every_candidate')
    for c in bank['items']:
        d=decisions[c['id']]
        if not d.get('reason') or d['decision'] not in ('accept','reject'):raise ValueError('explicit_review_decision')
        if d['decision']=='accept':cards.append(c)
    if not any(c.get('kind')=='task' for c in cards):raise ValueError('no_accepted_task_card')
    obj=dict(bank,schema='cxr_action_skill_r41',frozen=True,items=cards,candidate_sha256=sha(a.candidates),review_sha256=sha(a.reviews))
    # Validate in temporary file before publishing frozen bank.
    import tempfile
    tools=read(a.runtime)['arms']['M']['tools']
    with tempfile.TemporaryDirectory() as td:
        f=Path(td)/'bank.json';write(f,obj);load(f,tools)
    write(a.out,obj);print({'cards':len(cards),'task_cards':sum(c['kind']=='task' for c in cards),'bank':str(a.out)})
if __name__=='__main__':main()
