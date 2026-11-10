"""User-requested descriptive Skill analysis of the already-scored 420-case prefix.

No inference, new grading, label-file reads, producer changes, or final-score receipts.
Read only five immutable archived card/context/window documents for this new scope.
"""
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from deploy_cxr6_r50 import LOCAL, RUN, connect

PREFIX = LOCAL / 'local_assets/r50_cxr6_preparation/user_requested_interim_accuracy_20261110'
DEST = PREFIX / 'skill_effect_analysis'
SID = 's_39391f294d360026'
FILES = (
    'windows/0010/repo.json',
    'windows/0011/events.json',
    'windows/0012/events.json',
    'contexts/chexbench_openi_0092.json',
    'prescreen_events/chexbench_openi_0092.json',
)


def now():
    return datetime.now(timezone.utc).isoformat()


def once(name, value):
    path = DEST / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def metric(rows):
    count = sum(row['correct'] for row in rows)
    return {'n': len(rows), 'correct': count,
            'accuracy_pct': 100 * count / len(rows) if rows else None}


def main():
    DEST.mkdir()
    once('started.json', {'utc': now(), 'user_request': '分析一下这个注入skill有没有效',
        'scope': 'Analyze existing frozen 420-case outcomes and five archived card/context/window files.',
        'new_model_calls': 0, 'new_scoring': False, 'producer_modified': False})
    copied = []
    try:
        snapshot = json.loads((PREFIX / 'raw_prefix_snapshot.json').read_text(encoding='utf-8'))
        graded = json.loads((PREFIX / 'per_question.json').read_text(encoding='utf-8'))
        assert snapshot['committed_prefix_n'] == len(graded) == 420
        assert [item['ordinal'] for item in graded] == list(range(1, 421))
        cases = {item['row']['question_id']: item for item in snapshot['cases']}
        assert set(cases) == {item['question_id'] for item in graded}
        with connect() as client, client.open_sftp() as sftp:
            for relative in FILES:
                remote = RUN + '/generation/chexbench/' + relative
                size = sftp.stat(remote).st_size
                assert 0 < size <= 2_000_000, (relative, size)
                with sftp.open(remote, 'rb') as handle:
                    raw = handle.read()
                assert len(raw) == size
                parsed = json.loads(raw)
                target = DEST / 'archived_evidence' / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as handle:
                    handle.write(raw)
                copied.append({'remote': remote, 'local': str(target), 'bytes': len(raw)})
                assert isinstance(parsed, dict)
        once('archived_evidence.completed.json', {'utc': now(), 'count': len(copied),
            'files': copied, 'scope': 'Fixed historical windows 11-13 and first injected context only; not a live inventory rerun.'})
        rows = []
        for grade in graded:
            case = cases[grade['question_id']]
            pred = case['prediction']
            assert bool(pred['selected_skill_ids']) == grade['skill_injected']
            names = [item.get('tool', item.get('backend', 'unknown')) for item in pred['observations']]
            rows.append({'question_id': grade['question_id'], 'ordinal': grade['ordinal'],
                'subset': grade['subset'], 'task': case['row']['source']['task'],
                'correct': bool(grade['score']['aligned_correct']),
                'injected': grade['skill_injected'], 'skill_ids': grade['selected_skill_ids'],
                'same_image_hit': bool(pred['same_image_ids']),
                'main_calls': pred['main_calls'], 'tool_calls': pred['tool_calls'],
                'grounding_calls': names.count('xray_phrase_grounding'), 'tools': names,
                'options': case['row'].get('options'), 'choice': grade['adapted']['choice'],
                'reference': grade['reference'], 'reason': pred['reason'],
                'image_key': case['prediction_event']['image_key']})
        injected = [row for row in rows if row['injected']]
        before = [row for row in rows if not row['injected']]
        assert len(injected) == 90 and all(row['subset'] == 'OpenI' for row in injected)
        assert all(row['skill_ids'] == [SID] for row in injected)
        assert [row['ordinal'] for row in injected] == list(range(331, 421))
        comparisons = {}
        for name, group in [('all_uninjected', before), ('all_injected', injected),
                ('OpenI_before', [row for row in before if row['subset'] == 'OpenI']),
                ('OpenI_injected', injected)]:
            comparisons[name] = dict(metric(group),
                same_image_hits=sum(row['same_image_hit'] for row in group),
                unique_image_groups=len({row['image_key'] for row in group}),
                grounding_used_questions=sum(row['grounding_calls'] > 0 for row in group),
                exactly_two_grounding_questions=sum(row['grounding_calls'] == 2 for row in group),
                grounding_only_questions=sum(set(row['tools']) == {'xray_phrase_grounding'} for row in group),
                mean_main_calls=statistics.mean(row['main_calls'] for row in group),
                mean_tool_calls=statistics.mean(row['tool_calls'] for row in group))
        card = json.loads((DEST / 'archived_evidence/windows/0010/repo.json').read_text(encoding='utf-8'))['skills'][SID]
        first_context = json.loads((DEST / 'archived_evidence/contexts/chexbench_openi_0092.json').read_text(encoding='utf-8'))
        assert first_context['ordinal'] == 331
        assert len(first_context['selected_skills']) == 1
        assert first_context['selected_skills'][0]['id'] == SID
        assert first_context['selected_skills'][0]['c'] == card['c']
        credits = []
        by_id = {row['question_id']: row for row in injected}
        for window in ('0011', '0012'):
            events = json.loads((DEST / 'archived_evidence/windows' / window / 'events.json').read_text(encoding='utf-8'))
            for event in events['credit']:
                assert event['skill'] == SID and event['trajectory'] in by_id
                row = by_id[event['trajectory']]
                credits.append(dict(event, correct=row['correct'], ordinal=row['ordinal'], completed_window=int(window) + 1))
        assert len(credits) == 60 and len({item['trajectory'] for item in credits}) == 60
        credit_cross = {}
        for status in sorted({item['status'] for item in credits}):
            selected = [item for item in credits if item['status'] == status]
            credit_cross[status] = dict(metric(selected),
                wrong=len(selected) - sum(item['correct'] for item in selected),
                positive_numeric_credit=sum(item['credit'] > 0 for item in selected),
                negative_numeric_credit=sum(item['credit'] < 0 for item in selected))
        windows = [dict(ordinal_start=lo, ordinal_end=lo+29,
            **metric([row for row in rows if lo <= row['ordinal'] <= lo+29]))
            for lo in (241, 271, 301, 331, 361, 391)]
        paired_status = 'No same-question same-model same-state Skill-on/off counterfactual exists in this prefix.'
        summary = {'utc': now(), 'frozen_prefix_n': 420, 'scope': 'Descriptive secondary analysis of already-saved outcomes, not new grading.',
            'comparisons': comparisons, 'windows': windows,
            'crude_injected_minus_uninjected_pp': comparisons['all_injected']['accuracy_pct'] - comparisons['all_uninjected']['accuracy_pct'],
            'OpenI_injected_minus_before_pp': comparisons['OpenI_injected']['accuracy_pct'] - comparisons['OpenI_before']['accuracy_pct'],
            'OpenI_relative_accuracy_change_pct': 100 * (comparisons['OpenI_injected']['accuracy_pct'] / comparisons['OpenI_before']['accuracy_pct'] - 1),
            'card_id': SID, 'card': {key: card[key] for key in ('c', 'source_ids', 'status', 'usage') if key in card},
            'credit_cross_tab': credit_cross, 'credit_coverage_n': len(credits),
            'credit_coverage_ordinals': [331, 390], 'unreviewed_last_window_in_this_archive_n': 30,
            'all_90_received_same_card': True, 'same_period_uninjected_control_n': 0,
            'counterfactual': paired_status,
            'causal_effect_identified': False,
            'limitations': ['Ordered nonrandomized tasks; source stratification does not remove difficulty, time, online memory, tool stochasticity or protocol differences.',
                'Same-model adoption statuses are process attributions; signed numeric credit also uses actual reward and a category baseline, not a paired counterfactual.',
                'Card source_count is one and the final 30 cases lack completed-window adoption records in the captured historical windows.',
                'No new ablation or intervention was authorized or run.'],
            'new_model_or_tool_calls': 0, 'new_grade_or_reference_body_reads': 0,
            'running_protocol_or_predictions_modified': False, 'final_score_receipts_consumed': False}
        once('per_case_analysis.json', rows)
        once('credit_case_bindings.json', credits)
        once('summary.json', summary)
        once('completed.json', {'utc': now(), 'status': 'completed', 'files_captured': len(copied),
            'frozen_prefix_n': 420, 'new_inference_or_grading': False, 'final_score_consumed': False})
        print(json.dumps(summary, ensure_ascii=False))
    except Exception as error:
        once('failure.json', {'utc': now(), 'error': repr(error), 'files_copied': copied,
            'partial_originals_preserved': True, 'automatic_retry': False})
        raise


if __name__ == '__main__':
    main()
