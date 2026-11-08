"""Zero-paid full-archive answer comparison; never edits old predictions."""
from collections import Counter
import argparse
import json
from pathlib import Path
import random

import numpy as np

from analyze_cxr_author_alignment import EXPECTED, REPORT, ROOT, predictions, read, registry, rows, terminal
from cxr_author_alignment import choice, extract, legacy_choice, m4cxr_normalize, m4cxr_recall
from score_cxr_vqa_extension import bootstrap, cluster_keys, grade


def json_diagnostics(raw):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return False, False
    old_m = (isinstance(value,dict) and set(value)=={'answer','reason'}
             and all(isinstance(v,str) for v in value.values())
             and bool(value['answer'].strip()) and len(value['answer'])<=300)
    return True, old_m


def adapt(row, prediction, source):
    """This function has no reference argument or reference-file access."""
    raw = source['raw']
    answer = extract(raw,row['question_id'],row.get('options'))
    mapped = choice(answer.answer,row['options']) if answer.answer is not None and row.get('options') else None
    json_valid, legacy_m = json_diagnostics(raw)
    return {'question_id':row['question_id'],'strict_answer':prediction.get('answer'),
            'strict_status':prediction['status'],'explicit_answer':answer.answer,
            'choice':mapped,'extraction':answer.mechanism,
            'explicit_candidates':list(answer.explicit_candidates),
            'raw_whole_json_valid':json_valid,'legacy_M_contract_compliant':legacy_m,
            'answer_absent':answer.answer is None,
            'choice_domain_invalid':bool(row.get('options') and answer.answer is not None and mapped is None),
            'archive_call':source['call_path'],'ordinal':source['ordinal'],
            'reuse_chain':source['reuse_chain'],'archive_status':source['evidence_status'],
            'technical_stop':source['technical_stop']}


def outcomes(row, adapted, reference, rng):
    """Only grading sees the reference; extraction was already completed."""
    answer = adapted['explicit_answer']
    if row.get('options'):
        correct = adapted['choice'] is not None and adapted['choice'] == reference
        no_guess, no_match = legacy_choice(answer,row['options'])
        seeded, _ = legacy_choice(answer,row['options'],rng)
        return {'aligned_correct':bool(correct),'word_recall':None,
                'legacy_no_guess_correct':no_guess==reference,
                'legacy_seeded_correct':seeded==reference,
                'legacy_no_parenthesized_choice':no_match,
                'legacy_random_draw':bool(no_match and answer is not None and answer.strip()),
                'legacy_random_correct':bool(no_match and seeded is not None and seeded==reference)}
    return {'aligned_correct':bool(answer is not None and m4cxr_normalize(answer)==m4cxr_normalize(reference)),
            'word_recall':m4cxr_recall(answer,reference) if answer is not None else 0.0,
            'legacy_no_guess_correct':None,'legacy_seeded_correct':None,
            'legacy_no_parenthesized_choice':None,'legacy_random_draw':False,
            'legacy_random_correct':False}


def summarize(spec, details, inputs):
    n = len(details)
    correct = sum(x['aligned_correct'] for x in details)
    old = sum(x['strict_correct'] for x in details)
    subsets = {}
    for name in sorted({inputs[x['question_id']].get('source',{}).get('subset','all') for x in details}):
        group = [x for x in details if inputs[x['question_id']].get('source',{}).get('subset','all')==name]
        subsets[name] = {'n':len(group),'aligned_correct':sum(x['aligned_correct'] for x in group),
                         'accuracy_pct':100*sum(x['aligned_correct'] for x in group)/len(group),
                         'strict_correct':sum(x['strict_correct'] for x in group)}
    text = spec['dataset'] != 'chexbench'
    result = dict(spec,questions=n,full_comparison=not spec['partial'],strict_correct=old,
                  aligned_correct=correct,strict_accuracy_pct=100*old/n,
                  aligned_micro_pct=100*correct/n,
                  aligned_macro_pct=float(np.mean([g['accuracy_pct'] for g in subsets.values()])),
                  subsets=subsets,answer_absent=sum(x['answer_absent'] for x in details),
                  domain_invalid=sum(x['choice_domain_invalid'] for x in details),
                  technical_stops=sum(x['technical_stop'] for x in details),
                  raw_whole_json_valid=sum(x['raw_whole_json_valid'] for x in details),
                  legacy_M_contract_compliant=sum(x['legacy_M_contract_compliant'] for x in details),
                  extraction_counts=dict(Counter(x['extraction'] for x in details)),
                  adapter_metric_only_corrections=sum(x['aligned_correct'] and not x['strict_correct'] for x in details),
                  adapter_metric_only_losses=sum(x['strict_correct'] and not x['aligned_correct'] for x in details),
                  adapter_metric_only_net=correct-old,
                  word_recall_pct=100*float(np.mean([x['word_recall'] for x in details])) if text else None,
                  legacy_no_guess_correct=None if text else sum(x['legacy_no_guess_correct'] for x in details),
                  legacy_seed0_correct=None if text else sum(x['legacy_seeded_correct'] for x in details),
                  legacy_random_draws=sum(x['legacy_random_draw'] for x in details),
                  legacy_random_correct=sum(x['legacy_random_correct'] for x in details))
    cached = read(ROOT/spec['folder']/'summary.json')
    assert cached['arms'][spec['arm']]['correct']==old, (spec['dataset'],spec['key'],'strict count differs from published cache')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=REPORT/'results',help='New empty output directory; existing results are never overwritten.')
    args=parser.parse_args()
    protocol = read(REPORT/'PROTOCOL.json')
    inventory = read(REPORT/'ARCHIVE_INVENTORY.json')
    assert inventory['comparison_arms']==45 and protocol['new_paid_requests']==0
    assert all(not arm['unresolved_archive_qids'] for arm in inventory['arms'])
    out = args.out
    assert not out.exists(), 'Existing analysis output must be retained, never overwritten.'
    inputs, adapted_arms = {}, {}
    for ds in EXPECTED:
        cohort = rows(ROOT/'reports/cxr_action_r41_20261108/results'/ds/'inputs.jsonl')
        assert len(cohort)==EXPECTED[ds]
        inputs[ds] = {x['question_id']:x for x in cohort}
    # Finish reference-free adaptation for every arm before opening references.
    for spec in registry():
        ds,key = spec['dataset'],spec['key']
        predictions_by_id = predictions(ds,key)
        ids = [qid for qid in inputs[ds] if qid in predictions_by_id]
        assert len(ids)==len(predictions_by_id)
        if not spec['partial']:
            assert set(ids)==set(inputs[ds]) and len(ids)==EXPECTED[ds]
        adapted_arms[ds,key] = [adapt(inputs[ds][qid],predictions_by_id[qid],terminal(ds,key,qid)) for qid in ids]
    references = {}
    for ds in EXPECTED:
        refs = rows(ROOT/'reports/cxr_action_r41_20261108/results'/ds/'references.jsonl')
        references[ds] = {x['question_id']:x['answer'] for x in refs}
        assert len(refs)==len(references[ds])==EXPECTED[ds] and set(references[ds])==set(inputs[ds])
    table, per_question = [], []
    for spec in registry():
        ds,key = spec['dataset'],spec['key']
        detail = adapted_arms[ds,key]
        rng = random.Random(protocol['legacy_sensitivity']['random_seed'])
        for value in detail:
            qid = value['question_id']
            old_correct,old_missing = grade(inputs[ds][qid],predictions(ds,key)[qid],references[ds][qid])
            value.update(outcomes(inputs[ds][qid],value,references[ds][qid],rng),
                         dataset=ds,method=key,reference=references[ds][qid],
                         strict_correct=old_correct,strict_missing=old_missing)
        table.append(summarize(spec,detail,inputs[ds]))
        per_question.extend(detail)
    comparisons = []
    for ds,method,baseline in [('chexbench','M43','M-C41'),('slake','M43','M-S41'),('vqarad','M42','original_M'),
                               *[(ds,'M-S41','M-C41') for ds in EXPECTED],
                               *[(ds,'M-S','original_M') for ds in EXPECTED],
                               *[(ds,'M-E','original_M') for ds in EXPECTED],
                               *[(ds,'v32_M-AS','v32_M-A') for ds in EXPECTED]]:
        left = {x['question_id']:x for x in adapted_arms[ds,method]}
        right = {x['question_id']:x for x in adapted_arms[ds,baseline]}
        assert set(left)==set(right)==set(inputs[ds])
        cohort = list(inputs[ds].values())
        delta = np.array([int(left[r['question_id']]['aligned_correct'])-int(right[r['question_id']]['aligned_correct']) for r in cohort])
        comparisons.append({'dataset':ds,'method':method,'baseline':baseline,'questions':len(delta),
                            'corrections':int(sum(delta>0)),'harms':int(sum(delta<0)),'net':int(sum(delta)),
                            'micro_delta_pp':100*float(delta.mean()),
                            'confidence':bootstrap(delta,cluster_keys(cohort),np.array([x.get('source',{}).get('subset','all') for x in cohort]))})
    rankings = {}
    for ds in EXPECTED:
        metric = 'aligned_macro_pct' if ds=='chexbench' else 'aligned_micro_pct'
        ranked = sorted((x for x in table if x['dataset']==ds and x['full_comparison']),key=lambda x:(-x[metric],x['key']))
        rankings[ds] = {'primary':metric,'whole_arm_ranking':[{'method':x['key'],'correct':x['aligned_correct'],'n':x['questions'],'micro_pct':x['aligned_micro_pct'],'macro_pct':x['aligned_macro_pct']} for x in ranked]}
    summary = {'scope':'Author metrics plus common explicit-answer adapter on fixed exposed archives; not universal official reproduction.',
               'new_paid_requests':0,'new_tool_calls':0,'new_model_predictions':0,
               'comparison_arms':len(table),'full_arms':sum(x['full_comparison'] for x in table),
               'historical_predictions_modified':False,'references_read_after_all_arms_adapted':True,
               'row_count':len(per_question),'arms':table,'rankings':rankings,'comparisons':comparisons}
    out.mkdir(parents=True)
    for name,value in [('summary.json',summary),('comparisons.json',comparisons)]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (out/'per_question.jsonl').open('x',encoding='utf-8') as stream:
        for value in per_question:
            stream.write(json.dumps(value,ensure_ascii=False)+'\n')
    print(json.dumps({'status':'zero_paid_alignment_complete','arms':len(table),'rows':len(per_question),
                      'rankings':rankings,'new_paid_requests':0},ensure_ascii=False))


if __name__=='__main__':
    main()
