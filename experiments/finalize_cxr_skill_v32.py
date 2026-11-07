"""Build a new reviewed bank from saved source replies without another API call.

Identity canonicalization requires exact source-case membership. Explicitly
reviewed procedural edits may be supplied in a separate manifest. Originals stay intact.
"""
import argparse
import hashlib
import json
from pathlib import Path

from cxr_skill_v2 import validate_card


def candidates(source, source_out, tools):
    accepted, rejected, bindings = [], [], []
    for case in source['cases']:
        cid=str(case['case_id'])
        response=source_out/'calls/M-S'/cid/'1/response.json'
        if not response.exists():raise ValueError('Missing saved source response: '+cid)
        try:
            raw=json.loads(response.read_text())['choices'][0]['message']['content']
            card=json.loads(raw)
            if isinstance(card,dict) and set(card)=={'skip'}:
                rejected.append({'source_id':cid,'reason':'model_skip','detail':card['skip']});continue
            validate_card(card,tools)
            legal={cid,*[str(t['source_id']) for t in case['source_trajectories']]}
            if card['id'] not in legal or not set(card['source_ids'])<=legal:
                raise ValueError('Returned identifiers are not members of the supplied source case')
            bindings.append({'case_id':cid,'returned_id':card['id'],'returned_source_ids':card['source_ids'],
                             'response_sha256':hashlib.sha256(response.read_bytes()).hexdigest(),
                             'change':'Canonicalize known source-question/case identifiers to the enclosing case; clinical text unchanged.'})
            card={**card,'id':cid,'source_ids':[cid]}
            accepted.append(validate_card(card,tools))
        except (ValueError,TypeError,KeyError) as exc:
            rejected.append({'source_id':cid,'reason':'invalid_source_card','detail':str(exc)[:300]})
    return accepted,rejected,bindings


def main():
    p=argparse.ArgumentParser()
    for name in ('source','source-out','config','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--review',type=Path)
    a=p.parse_args();raw=a.source.read_bytes();source=json.loads(raw)
    cfg=json.loads(a.config.read_text());rt=json.loads(Path(cfg['runtime']).read_text())
    cards,rejected,bindings=candidates(source,a.source_out,rt['arms']['M-S']['tools'])
    if a.review:
        review=json.loads(a.review.read_text())
        if review['status']!='passed':raise ValueError('Review is not complete')
        if review['source_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('Reviewed source changed')
        excluded=review['excluded_case_ids'];kept=review['retained_case_ids']
        if set(excluded)&set(kept) or set(excluded)|set(kept)!={c['id'] for c in cards}:
            raise ValueError('Review must account for every structurally valid source card')
        cards=[c for c in cards if c['id'] in kept]
        for card in cards:
            revision=review.get('revisions',{}).get(card['id'])
            if revision:
                before=hashlib.sha256(json.dumps(card,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                if before!=revision['candidate_sha256']:raise ValueError('Reviewed candidate changed')
                if set(revision['fields'])&{'id','source_ids'}:raise ValueError('Cannot edit source identity')
                card.update(revision['fields']);validate_card(card,rt['arms']['M-S']['tools'])
        rejected.extend({'source_id':cid,'reason':'source_content_review','detail':reason} for cid,reason in excluded.items())
    if not cards:raise ValueError('No usable source cards')
    image_manifest=json.loads((a.source_out/'source_v2_manifest.json').read_text())['images']
    bank={'schema':'cxr_skill_v2','source_only':True,'frozen':bool(a.review),
          'source_sha256':hashlib.sha256(raw).hexdigest(),'items':cards,'rejected':rejected,
          'source_image_manifest':image_manifest,'source_identity_normalization':bindings}
    if a.review:bank['content_review']=review
    text=json.dumps(bank,ensure_ascii=False,indent=2)
    if a.out.exists():
        if a.out.read_text()!=text:raise ValueError('Refuse to overwrite bank')
    else:a.out.write_text(text)
    print(json.dumps({'cards':len(cards),'rejected':len(rejected),'frozen':bank['frozen'],'bank_sha256':hashlib.sha256(a.out.read_bytes()).hexdigest(),'new_paid_calls':0}))


if __name__=='__main__':main()
