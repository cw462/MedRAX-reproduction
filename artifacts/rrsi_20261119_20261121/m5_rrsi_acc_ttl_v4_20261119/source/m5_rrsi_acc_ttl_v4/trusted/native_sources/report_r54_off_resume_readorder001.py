"""One full-cohort R54 Off score using its new actual native continuation mapping."""
import argparse
import json
from pathlib import Path
import report_skill_r54 as original
from online_memory_r49 import save_once
from r54_resume_readorder_guard001 import require_native_full
from r54_off_resume_evidence import (SCHEMA, ARM, QID, KEY, ORDINAL, require_generation_zero,
                                     approved_recovery, read)


def score(out):
    out = Path(out); require_native_full(out)
    adapted = original.adapt_run(out)  # All current raw first, before feedback or recovery bodies.
    scope = require_generation_zero(out)  # Deep complete/learned bodies only after raw adaptation.
    recovered = approved_recovery(out) if scope['dataset'] == 'chexbench' else None
    if recovered:
        receipt = read(out / 'resume002_tool_deliveries' / QID / (str(ORDINAL) + '.json'))
        selection = read(out / 'services/tool_selections/R49-AGENT' / QID / (str(ORDINAL) + '.json'))
        prediction = read(out / 'predictions' / ARM / (QID + '.json'))
        if (receipt.get('selection') != selection or receipt.get('adoption') != recovered['adoption']
                or selection.get('technical_user_stop_recovery') != recovered['adoption']
                or selection not in prediction.get('observations', [])):
            raise ValueError('R54_recovered_observation_not_bound_to_prediction')
    summary, details = original.report(out, adapted=adapted)
    if (summary['candidate_hit_questions'] or summary['activated_questions'] or summary['meta_calls']
            or summary['resources']['embedding']['requests'] or summary['pipeline'].get('analysis', 0)):
        raise ValueError('R54_resume002_Skill_off_must_remain_disabled')
    summary.update(scope='complete_online_R54_Off_resumed_after_R56', protocol_resume=SCHEMA,
                   paired_comparison_available=False, cancelled_Skill_on_formal_requests=0,
                   raw_adaptation_before_any_scoring_labels=True)
    summary['resources']['interrupted_local_tool_attempt'] = (
        {'cache_key': KEY, 'original_generation_state': 'unknown_after_known_user_stop',
         'result_or_native_exit_available': False} if recovered else None)
    summary['resources']['one_new_local_recovery'] = (
        {'result': recovered['result'], 'adoption': recovered['adoption'], 'attempts': 1} if recovered else None)
    summary['resources'].update(provider_Credits=None, provider_invoice=None, GPU_cost=None)
    summary['limitations'] = ('Full R54 no-Skill arm with online same-image feedback, stopped after308 and '
        'resumed after full R56. Original local q309 generation state unknown; one separate original-tool '
        'recovery. Earlier native -15/241/143 and cancelled On preserved. Temporal/resource confounds, '
        'overlapping elapsed sums and unknown invoice/GPU cost; no paired Skill-effect or clinical claim.')
    return summary, details


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); summary, details = score(args.run)
    save_once(args.out / 'summary.json', summary); save_once(args.out / 'per_question.json', details)
    print(json.dumps({k: summary[k] for k in ('dataset', 'questions', 'correct', 'accuracy_pct', 'scope')}))
