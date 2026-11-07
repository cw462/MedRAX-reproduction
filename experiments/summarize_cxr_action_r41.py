"""Classify completed R4.1 outcomes without rescoring or altering predictions."""
from collections import Counter
import json
from pathlib import Path

from run_cxr_action_r41 import parse
from run_cxr_vqa_toolsets import validate_actions

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/cxr_action_r41_20261108'
DATASETS = ('chexbench', 'slake', 'vqarad')
ARMS = ('M-S41', 'M-C41')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]


def main():
    totals = {a: Counter() for a in ARMS}
    classifications, missing, changes, datasets = [], [], [], {}
    cards = Counter()
    for dataset in DATASETS:
        folder = REPORT / 'results' / dataset
        gate = read(folder / 'completion_gate.json')
        assert gate['effective_job_exit'] == 0
        summary, analysis = read(folder / 'summary.json'), read(folder / 'analysis.json')
        details = {(x['arm'], x['question_id']): x for x in rows(folder / 'per_question.jsonl')}
        inputs = {x['question_id']: x for x in rows(folder / 'inputs.jsonl')}
        runtime = read(folder / 'frozen_run.json')['runtime']
        cards.update(analysis['card_frequency'])
        ds_counts = {a: Counter() for a in ARMS}
        for arm in ARMS:
            predictions = rows(folder / ('predictions_' + arm + '.jsonl'))
            assert {x['question_id'] for x in predictions} == set(inputs)
            for prediction in predictions:
                qid = prediction['question_id']
                grade = details[arm, qid]
                reused = prediction['reused_historical_M']
                category, diagnostic = 'correct', {}
                if grade['missing']:
                    if reused:
                        category = 'historical_reuse_missing'
                    elif prediction.get('technical_failure'):
                        category = 'technical_tool_missing'
                    else:
                        calls_path = folder / 'calls' / arm / (qid + '.json')
                        calls = read(calls_path)
                        last = calls[-1]
                        text = last['response']['choices'][0]['message']['content']
                        diagnostic = {'call_ordinal': last['ordinal'],
                                      'call_evidence': calls_path.relative_to(REPORT).as_posix()}
                        try:
                            obj = parse(text)
                        except (ValueError, IndexError) as exc:
                            category = 'json_format_missing'
                            diagnostic['strict_parse_error'] = type(exc).__name__ + ': ' + str(exc)
                        else:
                            try:
                                validate_actions(obj, runtime, arm, 4 - prediction['tool_calls'],
                                                 len(inputs[qid]['images']))
                            except (ValueError, TypeError, KeyError) as exc:
                                category = 'invalid_action_plan_missing'
                                diagnostic['validation_error'] = str(exc)
                            else:
                                category = 'no_explicit_answer_missing'
                elif not grade['correct']:
                    category = 'valid_answer_incorrect'
                row = {'dataset': dataset, 'arm': arm, 'question_id': qid,
                       'selected': not reused, 'category': category,
                       'saved_status': prediction['status'], 'correct': grade['correct'],
                       'missing': grade['missing'], **diagnostic}
                classifications.append(row)
                ds_counts[arm][category] += 1
                totals[arm][category] += 1
                if grade['missing']:
                    missing.append(row)
        primary = summary['comparisons']['M-S41 vs M-C41']
        ds_changes = []
        for item in analysis['paired_changes']:
            if not item['delta']:
                continue
            category = ('control_missing_to_skill_correct' if item['delta'] > 0 and item['control']['missing']
                        else 'valid_wrong_to_correct' if item['delta'] > 0
                        else 'control_correct_to_skill_missing' if item['skill']['missing']
                        else 'control_correct_to_valid_wrong')
            change = {'dataset': dataset, 'question_id': item['question_id'],
                      'delta': item['delta'], 'category': category}
            changes.append(change)
            ds_changes.append(change)
        datasets[dataset] = {'denominator': summary['questions'],
                             'categories': ds_counts, 'primary': primary,
                             'selected': analysis['groups']['selected'],
                             'card_frequency': analysis['card_frequency'],
                             'behavior': {a: {k: v for k, v in analysis['behavior'][a].items()
                                              if k in ('main_limit_hits', 'tool_limit_hits',
                                                       'generation_wall_seconds_including_recovery_pause',
                                                       'resources')} for a in ARMS}}
    source = read(REPORT / 'results/source_learning/resources.json')
    dev = read(REPORT / 'results/development/resources.json')
    target_cost = sum(d['behavior'][a]['resources']['proxy_cny'] for d in datasets.values() for a in ARMS)
    output = {'scope': 'Completed R4.1 outcomes; saved strict grades reused, no new inference or rescoring.',
              'categories': totals, 'datasets': datasets, 'card_frequency': cards,
              'paired_change_categories': Counter(x['category'] for x in changes),
              'missing_outcomes': missing, 'correctness_changes': changes,
              'cost_cny_tokenproxy': {'targets': round(target_cost, 6),
                                      'source': source['proxy_cny'],
                                      'development': round(sum(x['proxy_cny'] for x in dev.values()), 6),
                                      'total': round(target_cost + source['proxy_cny'] +
                                                     sum(x['proxy_cny'] for x in dev.values()), 6)},
              'limitations': ['Dataset totals can overlap cases; do not interpret pooled counts as independent patients.',
                              'Single sequential sample per arm, reused historical M on unselected cases.',
                              'Exposed benchmarks and source cases are development evidence, not unseen tests.',
                              'No answer was inferred from prose or reason; JSON parsing is diagnostic only.']}
    (REPORT / 'error_taxonomy.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (REPORT / 'outcome_categories.jsonl').write_text('\n'.join(json.dumps(x, ensure_ascii=False) for x in classifications) + '\n', encoding='utf-8')
    print(json.dumps({'categories': totals, 'paired_changes': output['paired_change_categories'],
                      'cost': output['cost_cny_tokenproxy'], 'card_frequency': cards}, ensure_ascii=False))


if __name__ == '__main__':
    main()
