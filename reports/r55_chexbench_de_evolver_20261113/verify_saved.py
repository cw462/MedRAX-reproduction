"""Reproduce the published CheXBench comparison from saved evidence, offline."""

import argparse
from collections import Counter
import csv
from datetime import datetime
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import urlsplit


ARMS = {'D': 'M43-IM-GT-T55-D', 'E': 'R55-E-EvolveR'}
COUNTS = {'rad_restruct': 115, 'slake': 123, 'openi': 380}
QUESTION_ID = re.compile(r'chexbench_(rad_restruct|slake|openi)_\d+')
ASSET_ID = re.compile(r'img-[a-f0-9]{64}')
ASSET_TOKEN = re.compile(r'asset:(img-[a-f0-9]{64})')
REQUEST_IMAGE_TOKEN = re.compile(r'request-image-sha256:([a-f0-9]{64})')
CSV_FIELDS = (
    'dataset', 'ordinal', 'question_id', 'question', 'reference',
    'D_answer', 'E_answer', 'D_correct', 'E_correct', 'D_tool_calls',
    'E_tool_calls', 'same_image_ids_equal',
)


def require(condition, description):
    if not condition:
        raise ValueError(description)


def terminal_text(attempt):
    response = attempt['response.json']
    message = response['choices'][0]['message']
    content = message.get('content')
    if isinstance(content, list):
        content = '\n'.join(block.get('text', '') for block in content
                            if isinstance(block, dict) and block.get('type') == 'text')
    if isinstance(content, str) and not (message.get('tool_calls') or message.get('function_call')):
        return content
    return None


class Evidence:
    def __init__(self, root):
        self.root = root.resolve(strict=True)
        self.documents = {}
        self.tool_records = set()
        self.snapshots = set()
        self.snapshot_windows = {}
        index = self.read('asset_references.json', check_assets=False)
        self.assets = index['assets']
        self.request_images = self.read('request_image_references.json', check_assets=False)
        commit = index['verified_origin_commit']
        require(re.fullmatch(r'[a-f0-9]{40}', commit), 'invalid asset index commit')
        for asset_id, record in self.assets.items():
            require(ASSET_ID.fullmatch(asset_id) and record['asset_id'] == asset_id,
                    f'invalid asset index entry {asset_id}')
            link = record.get('published_asset_url')
            require(bool(link) != bool(record.get('exclusion_reason')),
                    f'asset has no unambiguous publication disposition {asset_id}')
            if link:
                url = urlsplit(link)
                require(url.scheme == 'https' and url.netloc == 'github.com'
                        and f'/blob/{commit}/' in url.path, f'asset lacks a commit-bound link {asset_id}')

    def path(self, name):
        relative = PurePosixPath(name)
        require(not relative.is_absolute() and '..' not in relative.parts and '\\' not in name,
                f'invalid report path {name}')
        path = (self.root / relative).resolve(strict=True)
        require(path.is_relative_to(self.root) and path.is_file(), f'invalid report file {name}')
        return path

    def read(self, name, *, check_assets=True, retain=True):
        if name in self.documents:
            return self.documents[name]
        value = json.loads(self.path(name).read_text(encoding='utf-8-sig'))
        if check_assets:
            self.check_assets(value, name)
        if retain:
            self.documents[name] = value
        return value

    def check_tool_record(self, name):
        if name not in self.tool_records:
            saved = self.read(name, retain=False)
            require({'request.json', 'result.json'} <= saved.keys(), f'{name}: incomplete saved tool')
            self.tool_records.add(name)

    def check_snapshot(self, arm, window, name):
        key = (arm, window)
        if key not in self.snapshot_windows:
            saved_window = self.read(f'experience/{arm}/windows/{window:04d}/read_snapshot.json', retain=False)
            snapshot = self.read(name, retain=False)
            require(snapshot == saved_window, f'{arm}: bank snapshot differs from window {window}')
            self.snapshots.add(name)
            self.snapshot_windows[key] = name
        require(self.snapshot_windows[key] == name, f'{arm}: multiple bank snapshots in window {window}')

    def check_assets(self, value, name):
        if isinstance(value, dict):
            if 'asset_ref' in value:
                asset = value['asset_ref']
                require(asset in self.assets, f'{name}: unbound asset {asset}')
            for key in ('asset_refs', 'canonical_asset_ids', 'derived_asset_ids'):
                if key in value:
                    for asset in value[key]:
                        require(asset in self.assets, f'{name}: unbound asset {asset}')
            for child in value.values():
                self.check_assets(child, name)
        elif isinstance(value, list):
            for child in value:
                self.check_assets(child, name)
        elif isinstance(value, str):
            for asset in ASSET_TOKEN.findall(value):
                require(asset in self.assets, f'{name}: unbound asset {asset}')
            for digest in REQUEST_IMAGE_TOKEN.findall(value):
                require(digest in self.request_images, f'{name}: unbound request image {digest}')


def verify_arm(evidence, arm, row, record, seen, totals, extract, choice, failure_reason):
    qid = row['question_id']
    label = f'{arm}/{qid}'
    ordinal = row['ordinal']
    reference = row['reference']
    score, prediction = record['saved_score'], record['prediction']
    context, feedback, steps = record['context'], record['feedback'], record['steps']
    for kind, bound in (('score', score), ('prediction', prediction),
                        ('context', context), ('feedback', feedback)):
        require((bound['ordinal'], bound['question_id']) == (ordinal, qid),
                f'{label}: wrong {kind} binding')
    require(prediction['arm'] == ARMS[arm], f'{label}: wrong prediction arm')
    require(feedback['timing'] == 'after_immutable_prediction'
            and datetime.fromisoformat(feedback['released_at'])
            >= datetime.fromisoformat(prediction['prediction_saved_at']),
            f'{label}: reference feedback order')
    require(feedback['reference_annotation']['answer'] == score['reference'] == reference,
            f'{label}: reference mismatch')
    require((score['question'], score['options']) == (row['question'], row['options']),
            f'{label}: scored question/options mismatch')
    require(score['same_image_ids'] == prediction['same_image_ids'] == context['same_image_ids']
            and set(score['same_image_ids']) <= seen, f'{label}: same-image context mismatch')

    main = record['model_calls']['R49-AGENT'][qid]['attempts']
    require(len(main) == prediction['main_calls'] == score['main_calls'] and bool(main),
            f'{label}: main call count mismatch')
    raw = terminal_text(main[max(main, key=int)])
    require(raw == prediction['terminal_raw'], f'{label}: terminal response mismatch')
    answer = extract(raw, qid, row['options']).answer
    option = choice(answer, row['options']) if answer is not None else None
    correct = option == reference
    require((answer, option, correct) == (score['answer'], score['choice'], score['correct'])
            and (answer, correct) == (row[f'{arm}_answer'], row[f'{arm}_correct']),
            f'{label}: reproduced answer or score mismatch')

    tools, observations = record['tool_calls'], prediction['observations']
    require(len(tools) == len(observations) == score['tool_calls']
            == prediction['tool_calls'] == row[f'{arm}_tool_calls'], f'{label}: tool call count mismatch')
    for step, (tool, observation) in enumerate(zip(tools, observations, strict=True), 1):
        require(tool['ordinal'] == step and tool['delivered'] == observation,
                f'{label}: tool observation mismatch at {step}')
        selection = tool['selection']
        failure = tool['failure']
        if failure is None:
            require(selection == observation, f'{label}: tool selection mismatch at {step}')
        else:
            require(failure['raw_selection'] == selection and failure['delivered_observation'] == observation,
                    f'{label}: failed tool binding mismatch at {step}')
        key = selection['cache_key']
        require(re.fullmatch(r'[a-f0-9]{64}', key)
                and tool['saved_tool_record'] == f'tool-records/{arm}/{key}.json',
                f'{label}: tool cache reference mismatch at {step}')
        evidence.check_tool_record(tool['saved_tool_record'])
    failures = sum(bool(failure_reason(observation)) for observation in observations)
    require(failures == score['failed_tool_calls'], f'{label}: failed tool count mismatch')
    totals['counts'].update(correct=int(correct), questions=1, main_calls=len(main),
                            tool_calls=len(tools), failed_tool_calls=failures)
    totals['tools'].update(obs['tool'] for obs in observations)

    snapshot = context['skill_snapshot_file']
    require(re.fullmatch(r'experience/snapshots/[a-f0-9]{64}\.json', snapshot),
            f'{label}: invalid bank snapshot path')
    window = context['window']
    require(isinstance(window, int) and window >= 0, f'{label}: invalid bank window')
    evidence.check_snapshot(arm, window, snapshot)
    totals['windows'][window] += 1
    searches = record['experience_search_receipts']
    if arm == 'D':
        require(not searches and not context['selected_skills'], f'{label}: unexpected experience')
        return
    before = searches['pre_answer.json']
    require(steps and before == score['pre_answer_search'] == steps[0]['pre_answer_experience_search'],
            f'{label}: saved pre-answer experience mismatch')
    require(before['trigger'] == 'required_pre_answer' and before['status'] in ('empty_bank', 'retrieved')
            and bool(before['active_card_count']) == bool(before['results']) == (before['status'] == 'retrieved'),
            f'{label}: invalid required experience check')
    for card in before['results']:
        require(card['source_question_ids'] and set(card['source_question_ids']) <= seen,
                f'{label}: experience source question occurs at or after use')
    followups = [step[key] for step in steps for key in ('pre_answer_experience_search', 'experience_search')
                 if key in step and step[key]['trigger'] == 'model_followup']
    require(followups == score['followup_searches'], f'{label}: experience follow-up mismatch')
    totals['counts'].update(required_pre_answer_checks=1, experience_delivered_questions=bool(before['results']))


def verify(root):
    evidence = Evidence(root)
    sys.path.insert(0, str(evidence.path('source/cxr_author_alignment.py').parent))
    evidence.path('source/cxr_image_memory_r44.py')
    from cxr_author_alignment import choice, extract
    from cxr_image_memory_r44 import tool_failure_reason

    scope = evidence.read('outgoing_scope.json')
    saved = evidence.read('summary.json')
    rows, index = evidence.read('per_question.json'), evidence.read('case_index.json')
    require(len(rows) == len(index) == scope['cases'] == sum(COUNTS.values()), 'wrong cohort size')
    require(set(scope['arms']) == set(ARMS) and scope['new_model_calls'] == 0, 'wrong outgoing scope')
    with evidence.path('per_question.csv').open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        require(tuple(reader.fieldnames or ()) == CSV_FIELDS, 'unexpected CSV columns')
        require(list(reader) == [{key: '' if row[key] is None else str(row[key]) for key in CSV_FIELDS}
                                 for row in rows], 'CSV does not match paired JSON')
    protocol = evidence.read('protocol.json')
    require(set(protocol) == set(ARMS), 'wrong protocol arm membership')
    source_totals = {source: Counter() for source in COUNTS}
    arms = {arm: {'counts': Counter(), 'tools': Counter(), 'windows': Counter()} for arm in ARMS}
    shared_context_count = 0
    seen = set()
    case_paths = set()
    for ordinal, (row, item) in enumerate(zip(rows, index, strict=True), 1):
        qid = row['question_id']
        match = QUESTION_ID.fullmatch(qid)
        require(match is not None and qid not in seen, f'invalid or duplicated question {qid}')
        source = match[1]
        path = f'cases/{source}/{qid}.json'
        case_paths.add(path)
        require(row['ordinal'] == ordinal and row['dataset'] == 'chexbench', f'{qid}: invalid pair binding')
        d, e = row['D_correct'], row['E_correct']
        require(item == {'ordinal': ordinal, 'question_id': qid, 'source': source, 'path': path,
                         'D_correct': d, 'E_correct': e}, f'{qid}: case index mismatch')
        case = evidence.read(path, retain=False)
        require(case['pair'] == row and set(case['arms']) == set(ARMS), f'{qid}: pair evidence mismatch')
        options = case['input']['options']
        require(all(case['input'][key] == row[key] for key in ('question_id', 'question'))
                and row.get('options', options) == options and row['reference'] in options,
                f'{qid}: input evidence mismatch')
        require(bool(case['canonical_asset_ids']), f'{qid}: missing canonical asset')
        for arm, record in case['arms'].items():
            verify_arm(evidence, arm, dict(row, options=options), record, seen, arms[arm],
                       extract, choice, tool_failure_reason)
        actual_same = (case['arms']['D']['prediction']['same_image_ids']
                       == case['arms']['E']['prediction']['same_image_ids'])
        require(actual_same == row['same_image_ids_equal'], f'{qid}: paired same-image context mismatch')
        shared_context_count += actual_same
        source_totals[source].update(questions=1, D_correct=int(d), E_correct=int(e),
                                     corrected=int(not d and e), regressed=int(d and not e))
        seen.add(qid)

    require({p.relative_to(evidence.root).as_posix() for p in (evidence.root / 'cases').rglob('*.json')}
            == case_paths, 'case directory membership mismatch')
    require({source: total['questions'] for source, total in source_totals.items()} == COUNTS
            and source_totals == saved['sources'], 'source-group scores do not reproduce')
    total = sum(source_totals.values(), Counter())
    n = total['questions']
    require([total[key] for key in ('questions', 'D_correct', 'E_correct', 'corrected', 'regressed')]
            == [618, 445, 458, 69, 56], 'unexpected R55 saved cohort result')
    pair = saved['pair']
    net = total['corrected'] - total['regressed']
    require(pair['dataset'] == 'chexbench' and pair['n'] == n
            and all(total[key] == pair[key] for key in ('D_correct', 'E_correct', 'corrected', 'regressed'))
            and (pair['net'], pair['same_image_ids_equal'], pair['accuracy_difference_pp'])
            == (net, shared_context_count, 100 * net / n), 'paired summary does not reproduce')
    for arm, values in arms.items():
        final_repo = evidence.read(f'experience/{arm}/final_repo.json', retain=False)
        completion = evidence.read(f'completion/{arm}.json', retain=False)
        native = evidence.read(f'completion/{arm}_native.json')
        require(all(native[key] == 0 for key in ('runner_exit', 'generation_exit', 'score_exit')),
                f'{arm}: native dataset phases did not all exit zero')
        require((completion['status'], completion['arm'], completion['questions'], completion['final_repo'])
                == ('generation_complete', ARMS[arm], n, final_repo), f'{arm}: completion binding mismatch')
        windows = {window['window']: window['episodes'] for window in completion['windows']}
        require(windows == values['windows'] and sum(windows.values()) == n, f'{arm}: incomplete windows')
        previous_repo = None
        for number in sorted(windows):
            window_path = f'experience/{arm}/windows/{number:04d}'
            start = evidence.read(f'{window_path}/read_snapshot.json', retain=False)
            require(previous_repo is None or previous_repo == start, f'{arm}: bank lineage at window {number}')
            previous_repo = evidence.read(f'{window_path}/repo.json', retain=False)
        require(previous_repo == final_repo, f'{arm}: final saved bank does not match last window')
        official = saved['arms'][arm]
        require(official['dataset'] == 'chexbench' and official['arm'] == ARMS[arm]
                and all(official[key] == value for key, value in values['counts'].items())
                and official['tools_by_name'] == dict(values['tools']), f'{arm}: arm summary does not reproduce')
        accuracy = 100 * total[f'{arm}_correct'] / n
        require(official['accuracy_pct'] == accuracy
                and pair['arms'][arm]['accuracy_pct'] == accuracy
                and pair['arms'][arm]['questions'] == n
                and pair['arms'][arm]['correct'] == total[f'{arm}_correct']
                and pair[f'{arm}_tool_calls'] == values['counts']['tool_calls'],
                f'{arm}: paired arm totals do not reproduce')
    evidence.read('experience/E/embedding_receipts.json')
    for path in (evidence.root / 'experience').glob('*/windows/*/*.json'):
        if path.name not in ('read_snapshot.json', 'repo.json'):
            evidence.read(path.relative_to(evidence.root).as_posix(), retain=False)
    tool_records = evidence.tool_records
    snapshots = evidence.snapshots
    for folder, names, key in (('tool-records', tool_records, 'tool_records'),
                               ('experience/snapshots', snapshots, 'saved_snapshots')):
        files = {p.relative_to(evidence.root).as_posix() for p in (evidence.root / folder).rglob('*.json')}
        require(files == names and len(names) == scope[key], f'{folder}: referenced file membership mismatch')
    return {
        'questions': n, 'reextracted_terminal_responses': n * len(ARMS), 'sources': source_totals,
        'arms': {arm: dict(values['counts'], tools_by_name=values['tools']) for arm, values in arms.items()},
        'corrected': total['corrected'], 'regressed': total['regressed'], 'net': net,
        'accuracy_difference_pp': pair['accuracy_difference_pp'], 'tool_records': len(tool_records),
        'bank_snapshots': len(snapshots), 'asset_index_entries': len(evidence.assets), 'new_model_calls': 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.report), ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
