"""Full-cohort R54 Skill-off scores after the explicitly requested scope change."""
import argparse
import json
from pathlib import Path

from online_memory_r49 import save_once
from r54_off_only_completion import ARM, COUNTS, require_generation_zero, read
from report_skill_r54 import report


def score(run):
    run = Path(run); scope = require_generation_zero(run); ds = scope['dataset']
    manifest = read(run / 'manifest.json'); complete = read(run / 'complete.json')
    if (manifest['arm'] != ARM or manifest['dataset'] != ds or manifest['skill_enabled'] is not False
            or complete['arm'] != ARM or complete['status'] != 'generation_complete'
            or len(manifest['inputs']) != COUNTS[ds] or complete['questions'] != COUNTS[ds]):
        raise ValueError('full_R54_off_only_cohort_required')
    if any((run / 'services/calls/R49-META').glob('*/*/started.json')) or any((run / 'services/embeddings').glob('*/started.json')):
        raise ValueError('R54_off_only_requires_zero_META_and_embedding_requests')
    # Unchanged current raw adapter/outcomes. report() adapts the entire current
    # raw cohort before reading feedback/GT or learned window records.
    summary, details = report(run)
    if (summary['candidate_hit_questions'] or summary['activated_questions']
            or summary['meta_calls'] or summary['resources']['embedding']['requests']):
        raise ValueError('R54_off_only_learning_or_activation_must_be_disabled')
    summary.update(scope='user_selected_R54_without_Skill_only',
        protocol_scope_change=scope['schema'], cancelled_Skill_on_formal_requests=0,
        raw_adaptation_before_any_scoring_labels=True,
        paired_comparison_available=False,
        limitations='User cancelled the unstarted R54 Skill-on arm. This is the full R54 no-Skill arm with online same-image GT feedback, not an A/B Skill-effect estimate. Original eight-tool/model/EOS protocols unchanged.')
    return summary, details


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True); parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(); summary, details = score(args.run)
    save_once(args.out / 'summary.json', summary); save_once(args.out / 'per_question.json', details)
    print(json.dumps({'dataset': summary['dataset'], 'n': summary['questions'], 'correct': summary['correct'],
        'accuracy_pct': summary['accuracy_pct'], 'scope': summary['scope']}, ensure_ascii=False))
