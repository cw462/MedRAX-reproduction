"""Merge explicitly reviewed source-derived task cards with existing specific cards."""
import argparse
from pathlib import Path
from cxr_action_skill_r41 import *
import cxr_skill_r41_base as old

def main():
    p=argparse.ArgumentParser()
    for k in ('source-bank','reviewed-task-cards','runtime','out'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();rt=read(a.runtime);tools=rt['arms']['M']['tools'];cards=load(a.source_bank,tools)
    review=read(a.reviewed_task_cards)
    if review.get('source_only_review') is not True or not review.get('reviewer'):raise ValueError('explicit_source_review_required')
    allowed={s for c in cards for s in c['source_ids']}
    for item in review['items']:
        c=dict(item)
        if c.pop('kind',None)!='task':raise ValueError('task_kind_required')
        old.validate_card(c,tools)
        if not set(c['source_ids'])<=allowed:raise ValueError('unsupported_source_id')
        cards.append(dict(c,kind='task'))
    obj={'schema':'cxr_action_skill_r41','source_only':True,'frozen':True,'source_bank_sha256':sha(a.source_bank),'review_sha256':sha(a.reviewed_task_cards),'items':cards}
    if len({c['id'] for c in cards})!=len(cards):raise ValueError('duplicate_card_id')
    write(a.out,obj);load(a.out,tools)
    print({'cards':len(cards),'sha256':sha(a.out)})
if __name__=='__main__':main()
