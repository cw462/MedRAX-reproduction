"""Unmodified common explicit-answer adaptation and outcome functions.
Copied from score_cxr_author_alignment; no historical scorer imports or execution.
"""
import json
from cxr_author_alignment import choice,extract,legacy_choice,m4cxr_normalize,m4cxr_recall

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
