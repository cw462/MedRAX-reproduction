"""Reproduce the R55 SLAKE and VQA-RAD outgoing results from bundle files only."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import random
import re
import struct
import sys
from urllib.parse import urlsplit


COUNTS = {'slake': 114, 'vqarad': 116}
ARMS = {'D': 'M43-IM-GT-T55-D', 'E': 'R55-E-EvolveR'}
CSV_FIELDS = ('dataset', 'ordinal', 'question_id', 'question', 'reference', 'D_answer',
              'E_answer', 'D_correct', 'E_correct', 'D_tool_calls', 'E_tool_calls',
              'same_image_ids_equal')
ASSET = r'img-[a-f0-9]{64}'
ASSET_TOKEN = re.compile(r'asset:(' + ASSET + ')')
REQUEST_IMAGE = re.compile(r'request-image-sha256:([a-f0-9]{64})')
JPEG_SOF = {0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf}
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff', '.svg', '.avif'}
SLAKE_ATTRIBUTION = {
    'dataset': 'SLAKE',
    'credit': 'Bo Liu, Li-Ming Zhan, Li Xu and Xiao-Ming Wu',
    'official_project': 'https://www.med-vqa.com/slake/',
    'distribution': 'https://huggingface.co/datasets/BoKelvin/SLAKE',
    'license': 'CC BY 4.0',
    'license_url': 'https://creativecommons.org/licenses/by/4.0/',
}
SLAKE_TOOL_ARTIFACTS = {
    'maira2_grounded_report': {'grounded_report.png'},
    'roi_crop': {'original.png', 'roi_context.png', 'roi_zoom.png'},
}
PHRASE_OVERLAY = re.compile(r'maira_runtime/overlays/grounding_[a-f0-9]{8}\.png')


def require(condition, context):
    if not condition:
        raise ValueError(context)


def utc(value):
    timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(timestamp.tzinfo is not None, 'timestamp has no timezone')
    return timestamp


class Bundle:
    def __init__(self, root):
        self.root = root.resolve(strict=True)

    def path(self, name):
        member = PurePosixPath(name)
        require(not member.is_absolute() and '..' not in member.parts and '\\' not in name,
                f'unsafe bundle member {name}')
        path = (self.root / member).resolve(strict=True)
        require(path.is_relative_to(self.root) and path.is_file(), f'outside bundle or missing {name}')
        return path

    def read(self, name):
        return json.loads(self.path(name).read_text(encoding='utf-8-sig'))

    def members(self, folder):
        return {path.relative_to(self.root).as_posix() for path in (self.root / folder).rglob('*.json')}


def terminal_text(attempt):
    message = attempt['response.json']['choices'][0]['message']
    content = message.get('content')
    if isinstance(content, list):
        content = '\n'.join(item.get('text', '') for item in content
                            if isinstance(item, dict) and item.get('type') == 'text')
    if isinstance(content, str) and not (message.get('tool_calls') or message.get('function_call')):
        return content
    return None


def closed(attempt, label, *, writer=False):
    require({'request.json', 'started.json', 'result.json'} <= attempt.keys(), f'{label}: incomplete receipt')
    started, result = attempt['started.json'], attempt['result.json']
    received = 'response.json' in attempt
    require(result['response_received'] is received, f'{label}: response presence differs from receipt')
    if writer:
        require(started['response_received'] is False and 'request_id' not in started and 'request_id' not in result,
                f'{label}: writer receipt binding')
        utc(started['utc'])
    else:
        require(result['request_id'] == started['request_id'] and utc(started['utc']) <= utc(result['utc']),
                f'{label}: request/response receipt binding')
    require(received or bool(result.get('error')), f'{label}: missing response with no failure receipt')
    return result


def adapt_raw(bundle, adapter):
    """Use only input and raw model fields until all 460 adaptations finish."""
    collected = {}
    for dataset, count in COUNTS.items():
        members = sorted(bundle.members(f'{dataset}/cases'))
        require(len(members) == count, f'{dataset}: case count differs')
        adapted_cases = []
        for name in members:
            case = bundle.read(name)
            row = case['input']
            qid = row['question_id']
            require(re.fullmatch(rf'{dataset}_\d+', qid) and name == f'{dataset}/cases/{qid}.json'
                    and row['options'] == {} and set(case['arms']) == set(ARMS), f'{name}: input binding')
            adapted_arms = {}
            for arm, record in case['arms'].items():
                label = f'{name}/{arm}'
                prediction = record['prediction']
                require((prediction['question_id'], prediction['arm']) == (qid, ARMS[arm]), label)
                main = record['model_calls']['R49-AGENT'][qid]['attempts']
                require(len(main) == prediction['main_calls'] > 0
                        and set(main) == {str(i) for i in range(1, len(main)+1)}, f'{label}: main call ordinals')
                for ordinal, attempt in main.items():
                    result = closed(attempt, f'{label}/{ordinal}')
                    require(result['response_received'] and not result.get('error'), f'{label}/{ordinal}: logical call failed')
                ordinal = str(len(main))
                raw = terminal_text(main[ordinal])
                require(raw == prediction['terminal_raw'], f'{label}: raw and saved terminal differ')
                adapted_arms[arm] = adapter(row, prediction, {'raw': raw, 'call_path': name,
                    'ordinal': ordinal, 'reuse_chain': [], 'technical_stop': False,
                    'evidence_status': 'received_terminal_text' if raw else 'nonfinal_or_unavailable'})
            adapted_cases.append((case, adapted_arms))
        collected[dataset] = sorted(adapted_cases, key=lambda value: value[0]['arms']['D']['prediction']['ordinal'])
    return collected


def check_recovery(record, qid):
    recovery = record['main_call_recovery']
    plan, outcome = recovery['plan'], recovery['outcome']
    first = recovery['first_attempt']
    replacement = record['model_calls']['R49-AGENT'][qid]['attempts']['2']
    first_result = closed(first, f'{qid}/original attempt')
    second_result = closed(replacement, f'{qid}/replacement')
    require(recovery['logical_ordinal'] == plan['logical_ordinal'] == outcome['logical_ordinal'] == 2
            and recovery['replacement_record'] == ['model_calls', 'R49-AGENT', qid, 'attempts', '2']
            and plan['question_id'] == outcome['question_id'] == qid and plan['max_attempts'] == 2
            and plan['revision'] == outcome['schema'] == 'slake_main_retry001'
            and re.fullmatch(r'[a-f0-9]{64}', plan['request_sha256'])
            and outcome['request_sha256'] == plan['request_sha256'], f'{qid}: retry lineage')
    require(recovery['archived_requests_byte_equal'] is True and first['request.json'] == replacement['request.json']
            and not first_result['response_received'] and second_result['response_received']
            and not second_result.get('error') and outcome['disposition'] == 'usable_replacement'
            and second_result['request_id'] == first_result['request_id']+':retry2'
            and all(token in first_result['error'] for token in ('Error code: 500', 'StatusCode=503', 'QpsLimitExceeded')),
            f'{qid}: first failure or successful replacement changed')


def asset_tokens(value):
    if isinstance(value, dict):
        if 'asset_ref' in value:
            yield value['asset_ref']
        for key in ('asset_refs', 'canonical_asset_ids', 'derived_asset_ids'):
            yield from value.get(key, ())
        for child in value.values():
            yield from asset_tokens(child)
    elif isinstance(value, list):
        for child in value:
            yield from asset_tokens(child)
    elif isinstance(value, str):
        yield from ASSET_TOKEN.findall(value)
        for digest in REQUEST_IMAGE.findall(value):
            yield 'img-'+digest


def check_assets(value, assets, label):
    require(all(token in assets for token in asset_tokens(value)), f'{label}: unbound asset reference')


def image_header(raw, label):
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        require(len(raw) >= 33 and raw[8:16] == b'\x00\x00\x00\rIHDR', f'{label}: PNG header')
        return ('PNG', *struct.unpack_from('>II', raw, 16))
    require(raw.startswith(b'\xff\xd8') and raw.endswith(b'\xff\xd9'), f'{label}: JPEG boundaries')
    offset = 2
    while offset < len(raw):
        require(raw[offset] == 0xff, f'{label}: JPEG marker')
        while offset < len(raw) and raw[offset] == 0xff:
            offset += 1
        require(offset + 3 <= len(raw), f'{label}: JPEG segment header')
        marker = raw[offset]
        length = struct.unpack_from('>H', raw, offset + 1)[0]
        require(marker not in (0xda, 0xd9) and 2 <= length <= len(raw) - offset - 1,
                f'{label}: JPEG segment before frame')
        if marker in JPEG_SOF:
            require(length >= 8, f'{label}: JPEG frame length')
            height, width = struct.unpack_from('>HH', raw, offset + 4)
            return ('JPEG', width, height)
        offset += 1 + length
    raise ValueError(f'{label}: JPEG frame missing')


def allowed_slake_tool_artifact(tool, artifact):
    return isinstance(artifact, str) and (
        artifact in SLAKE_TOOL_ARTIFACTS.get(tool, ())
        or (tool == 'xray_phrase_grounding' and PHRASE_OVERLAY.fullmatch(artifact) is not None)
    )


def check_local_tool_occurrences(attribution, identifier, sources, cases, tool_assets):
    declared = attribution.get('saved_tool_occurrences')
    if 'saved_tool_occurrences' not in attribution:
        arm, tool = attribution['experiment_arm'], attribution['tool']
        require(arm in ARMS and tool == 'maira2_grounded_report', f'{identifier}: legacy tool attribution')
        expected = {(arm, tool, 'grounded_report.png'): set(sources)}
    else:
        require(isinstance(declared, list) and declared and not {'experiment_arm', 'tool'} & attribution.keys(),
                f'{identifier}: saved tool occurrence format')
        expected = {}
        for row in declared:
            require(set(row) == {'experiment_arm', 'tool', 'artifact', 'question_ids'},
                    f'{identifier}: saved tool occurrence fields')
            arm, tool, artifact, qids = (row[key] for key in ('experiment_arm', 'tool', 'artifact', 'question_ids'))
            key = (arm, tool, artifact)
            require(arm in ARMS and allowed_slake_tool_artifact(tool, artifact) and key not in expected
                    and isinstance(qids, list) and qids and len(set(qids)) == len(qids) and set(qids) <= sources.keys(),
                    f'{identifier}: saved tool occurrence membership')
            expected[key] = set(qids)
        require(set.union(*expected.values()) == sources.keys(), f'{identifier}: saved tool questions differ')

    actual = defaultdict(set)
    for qid, case in cases.items():
        for arm, record in case['arms'].items():
            for tool in record['tool_calls']:
                role = tool['selection']['tool']
                saved_role, files = tool_assets[f"slake/{tool['saved_tool_record']}"]
                for member, asset_id in files.items():
                    artifact = member.removeprefix('artifacts/')
                    if (asset_id == identifier and member != artifact
                            and allowed_slake_tool_artifact(role, artifact)):
                        require(saved_role == role, f'{identifier}/{qid}: saved tool role differs')
                        actual[(arm, role, artifact)].add(qid)
    if declared is None:
        require(all(qids <= actual[key] for key, qids in expected.items()), f'{identifier}: legacy tool link differs')
    else:
        require(actual == expected, f'{identifier}: saved tool links differ')


def check_local_attribution(asset, assets, cases, source_pages, tool_assets):
    identifier = asset['asset_id']
    attribution = asset['image_attribution']
    sources = asset['sources_by_question_id']
    require(sources and all(attribution.get(key) == value for key, value in SLAKE_ATTRIBUTION.items())
            and source_pages['slake'] == attribution['official_project']
            and re.fullmatch(r'[a-f0-9]{40}', attribution['revision']) and attribution['split'] == 'test'
            and re.fullmatch(r'xmlab\d+/source\.jpg', attribution['original_image'])
            and isinstance(attribution['changes'], str) and attribution['changes'].strip(),
            f'{identifier}: SLAKE attribution')
    visual = asset['image_visual_evidence']
    require(visual['source'] in ('r54_exact_byte_native_visual_review', 'r55_native_visual_review')
            and isinstance(visual['decision'], str) and visual['decision'].strip(), f'{identifier}: visual evidence')
    if visual['source'] == 'r54_exact_byte_native_visual_review':
        require(type(visual['index']) is int and visual['index'] > 0, f'{identifier}: R54 visual index')

    derived = 'tool_derived' in asset['kinds']
    if derived:
        parent = attribution['canonical_asset_id']
        require(parent != identifier and parent in assets and 'canonical' in assets[parent]['kinds']
                and 'canonical' not in asset['kinds'],
                f'{identifier}: tool derivative parent')
    else:
        parent = identifier
        tool_fields = {'canonical_asset_id', 'experiment_arm', 'tool', 'saved_tool_occurrences'}
        require('canonical' in asset['kinds'] and not tool_fields & attribution.keys(),
                f'{identifier}: canonical image attribution')
    for qid, source in sources.items():
        require(qid in cases and source == cases[qid]['input']['source']
                and all(source[key] == attribution[key] for key in ('dataset', 'revision', 'split', 'original_image'))
                and f"slake_{source['original_qid']}" == qid
                and parent in cases[qid]['canonical_asset_ids']
                and assets[parent]['sources_by_question_id'].get(qid) == source, f'{identifier}/{qid}: source or parent')
    if derived:
        check_local_tool_occurrences(attribution, identifier, sources, cases, tool_assets)


def check_local_images(bundle, packed, assets, raw, source_pages, tool_assets):
    cases = {case['input']['question_id']: case for case, _ in raw['slake']}
    members, formats, kinds = set(), Counter(), Counter()
    bytes_verified = 0
    for identifier, asset in packed.items():
        digest = identifier.removeprefix('img-')
        member = asset['published_asset_path']
        require(re.fullmatch(rf'images/slake/{digest}\.(?:jpg|png)', member) and member not in members,
                f'{identifier}: unsafe or duplicate local image path')
        path = bundle.path(member)
        require(path == bundle.root / member, f'{identifier}: redirected local image')
        payload = path.read_bytes()
        require(hashlib.sha256(payload).hexdigest() == asset['projected_sha256'] == digest
                and type(asset['projected_bytes']) is int and len(payload) == asset['projected_bytes'] == asset['bytes'],
                f'{identifier}: local image bytes or SHA-256 differ')
        image_format, width, height = image_header(payload, identifier)
        require((image_format, width, height) == (asset['format'], asset['width'], asset['height'])
                and width > 0 and height > 0 and (image_format == 'PNG') == member.endswith('.png'),
                f'{identifier}: local image header differs')
        check_local_attribution(asset, assets, cases, source_pages, tool_assets)
        members.add(member)
        formats[image_format] += 1
        kinds['tool_derived' if 'tool_derived' in asset['kinds'] else 'canonical'] += 1
        bytes_verified += len(payload)
    actual = {path.relative_to(bundle.root).as_posix() for path in bundle.root.rglob('*')
              if (path.is_file() or path.is_symlink()) and (
                  path.is_relative_to(bundle.root / 'images') or path.suffix.lower() in IMAGE_SUFFIXES)}
    require(actual == members, 'local image files differ from indexed paths')
    return {'files': len(members), 'bytes': bytes_verified, 'formats': dict(formats), 'kinds': dict(kinds)}


def check_arm(bundle, dataset, arm, row, pair, record, adapted, seen, totals, support,
              outcomes, failure_reason, assets, rng):
    qid = row['question_id']
    label = f'{dataset}/{arm}/{qid}'
    score, prediction, context, feedback = (record[key] for key in ('saved_score', 'prediction', 'context', 'feedback'))
    ordinal = pair['ordinal']
    require(all((value['question_id'], value['ordinal']) == (qid, ordinal)
                for value in (score, prediction, context, feedback)), f'{label}: question and ordinal binding')
    require(feedback['timing'] == 'after_immutable_prediction'
            and utc(feedback['released_at']) >= utc(prediction['prediction_saved_at']), f'{label}: feedback order')
    reference = feedback['reference_annotation']['answer']
    require(reference == score['reference'] == pair['reference'] and score['question'] == row['question']
            and score['options'] == {}, f'{label}: reference or question differs')
    require(score['same_image_ids'] == prediction['same_image_ids'] == context['same_image_ids']
            and set(score['same_image_ids']) <= seen, f'{label}: same-image chronology')
    correct = outcomes(row, adapted, reference, rng)['aligned_correct']
    answer = adapted['explicit_answer']
    require((answer, adapted['choice'], correct) == (score['answer'], score['choice'], score['correct'])
            and (answer, correct) == (pair[f'{arm}_answer'], pair[f'{arm}_correct']), f'{label}: score differs')

    tools, observations = record['tool_calls'], prediction['observations']
    require(len(tools) == len(observations) == score['tool_calls'] == prediction['tool_calls']
            == pair[f'{arm}_tool_calls'] and prediction['main_calls'] == score['main_calls'], f'{label}: call totals')
    for step, (tool, observation) in enumerate(zip(tools, observations, strict=True), 1):
        require(tool['ordinal'] == step and tool['delivered'] == observation, f'{label}: tool observation {step}')
        selection, failure = tool['selection'], tool['failure']
        require((selection == observation if failure is None else failure['raw_selection'] == selection
                 and failure['delivered_observation'] == observation), f'{label}: tool selection {step}')
        cache = selection['cache_key']
        path = f'{dataset}/tool-records/{arm}/{cache}.json'
        require(re.fullmatch(r'[a-f0-9]{64}', cache) and path == f"{dataset}/{tool['saved_tool_record']}", label)
        if path not in support['tools']:
            detail = bundle.read(path)
            require({'request.json', 'result.json'} <= detail.keys(), f'{path}: incomplete tool record')
            require(all(asset in assets for asset in detail['derived_assets'].values()), f'{path}: derived assets')
            check_assets(detail, assets, path)
            support['tools'][path] = (detail['request.json'].get('tool'), detail['derived_assets'])
    failures = sum(bool(failure_reason(observation)) for observation in observations)
    require(failures == score['failed_tool_calls'], f'{label}: failed tool count')
    totals['counts'].update(questions=1, correct=correct, main_calls=score['main_calls'],
                            tool_calls=len(tools), failed_tool_calls=failures)
    totals['tool_names'].update(observation['tool'] for observation in observations)

    snapshot = context['skill_snapshot_file']
    require(re.fullmatch(r'experience/snapshots/[a-f0-9]{64}\.json', snapshot), f'{label}: bank snapshot path')
    window = context['window']
    key = (arm, window)
    if key not in support['windows']:
        require(bundle.read(f'{dataset}/{snapshot}') == bundle.read(
            f'{dataset}/experience/{arm}/windows/{window:04d}/read_snapshot.json'), f'{label}: bank snapshot')
        support['snapshots'].add(f'{dataset}/{snapshot}')
        support['windows'][key] = snapshot
    require(support['windows'][key] == snapshot, f'{label}: inconsistent window snapshot')
    totals['windows'][window] += 1
    searches = record['experience_search_receipts']
    if arm == 'D':
        require(not searches and not context['selected_skills'], f'{label}: unexpected experience lookup')
    else:
        before = searches['pre_answer.json']
        steps = record['steps']
        require(before == score['pre_answer_search'] == steps[0]['pre_answer_experience_search']
                and before['trigger'] == 'required_pre_answer' and before['status'] in ('empty_bank', 'retrieved')
                and bool(before['active_card_count']) == bool(before['results']) == (before['status'] == 'retrieved'),
                f'{label}: required pre-answer search')
        require(all(card['source_question_ids'] and set(card['source_question_ids']) <= seen
                    for card in before['results']), f'{label}: experience source chronology')
        followups = [step[key] for step in steps for key in ('pre_answer_experience_search', 'experience_search')
                     if key in step and step[key]['trigger'] == 'model_followup']
        require(followups == score['followup_searches'], f'{label}: follow-up search')
        totals['counts'].update(required_pre_answer_checks=1, experience_delivered_questions=bool(before['results']))

    for role, events in record['model_calls'].items():
        for event, calls in events.items():
            for step, attempt in calls['attempts'].items():
                receipt = closed(attempt, f'{label}/{role}/{event}/{step}', writer=role == 'R54DS-WRITER')
                totals['roles'][role].update(requests=1, received=receipt['response_received'], failed=bool(receipt.get('error')))
    if 'main_call_recovery' in record:
        require((dataset, arm, qid) == ('slake', 'E', 'slake_12393'), f'{label}: unexpected main recovery')
        check_recovery(record, qid)
        totals['roles']['R49-AGENT'].update(requests=1, failed=1)
        totals['retries'] += 1
    return correct


def check_dataset(bundle, dataset, cases, scope, assets, outcomes, failure_reason, tool_assets):
    count = COUNTS[dataset]
    require(scope == bundle.read(f'{dataset}/outgoing_scope.json') and scope['cases'] == count
            and set(scope['arms']) == set(ARMS) and scope['new_model_calls'] == 0, f'{dataset}: scope')
    pairs, index = (bundle.read(f'{dataset}/{name}.json') for name in ('per_question', 'case_index'))
    with bundle.path(f'{dataset}/per_question.csv').open(encoding='utf-8-sig', newline='') as handle:
        csv_rows = csv.DictReader(handle)
        require(tuple(csv_rows.fieldnames or ()) == CSV_FIELDS and list(csv_rows) == [
            {key: '' if row[key] is None else str(row[key]) for key in CSV_FIELDS} for row in pairs], f'{dataset}: CSV differs')
    require(len(cases) == len(pairs) == len(index) == count, f'{dataset}: paired membership')
    summary = bundle.read(f'{dataset}/summary.json')
    protocols = bundle.read(f'{dataset}/protocol.json')
    totals = {arm: {'counts': Counter(), 'windows': Counter(), 'tool_names': Counter(),
                    'roles': defaultdict(Counter), 'retries': 0} for arm in ARMS}
    support = {'tools': {}, 'snapshots': set(), 'windows': {}}
    seen, paired = set(), Counter()
    rng = {arm: random.Random(0) for arm in ARMS}
    for ordinal, ((case, adapted), pair, item) in enumerate(zip(cases, pairs, index, strict=True), 1):
        row, arms = case['input'], case['arms']
        qid = row['question_id']
        require(qid not in seen and case['pair'] == pair and (pair['dataset'], pair['ordinal'], pair['question_id'],
                pair['question'], pair['options']) == (dataset, ordinal, qid, row['question'], {}), f'{dataset}/{qid}: pair binding')
        require(item == {'ordinal': ordinal, 'question_id': qid, 'path': f'cases/{qid}.json',
                         'D_correct': pair['D_correct'], 'E_correct': pair['E_correct']}, f'{qid}: case index')
        canonical = [image['asset_ref'] for image in row['images']]
        require(canonical and canonical == case['canonical_asset_ids']
                and all(assets[asset]['sources_by_question_id'][qid] == row['source'] for asset in canonical), f'{qid}: attribution')
        check_assets(case, assets, qid)
        d, e = (check_arm(bundle, dataset, arm, row, pair, arms[arm], adapted[arm], seen,
                          totals[arm], support, outcomes, failure_reason, assets, rng[arm]) for arm in ARMS)
        same = arms['D']['prediction']['same_image_ids'] == arms['E']['prediction']['same_image_ids']
        require(same == pair['same_image_ids_equal'], f'{qid}: paired same-image context')
        paired.update(n=1, D_correct=d, E_correct=e, D_tool_calls=pair['D_tool_calls'], E_tool_calls=pair['E_tool_calls'],
                      corrected=not d and e, regressed=d and not e, same_image_ids_equal=same)
        seen.add(qid)
    paired['net'] = paired['corrected']-paired['regressed']
    pair_summary = summary['pair']
    require(all(pair_summary[key] == value for key, value in paired.items())
            and pair_summary['accuracy_difference_pp'] == 100*paired['net']/count, f'{dataset}: paired summary')
    for arm, total in totals.items():
        official, completion = summary['arms'][arm], bundle.read(f'{dataset}/completion/{arm}.json')
        protocol, native = protocols[arm], bundle.read(f'{dataset}/completion/{arm}_native.json')
        final = bundle.read(f'{dataset}/experience/{arm}/final_repo.json')
        require((completion['status'], completion['arm'], completion['questions'], completion['final_repo'])
                == ('generation_complete', ARMS[arm], count, final) and protocol['arm'] == ARMS[arm]
                and protocol['dataset'] == dataset and len(set(protocol['tool_names'])) == 11
                and all(native[key] == 0 for key in ('runner_exit', 'generation_exit', 'score_exit')),
                f'{dataset}/{arm}: native and protocol completion')
        windows = {window['window']: window['episodes'] for window in completion['windows']}
        require(windows == total['windows'] and sum(windows.values()) == count, f'{dataset}/{arm}: window membership')
        previous = None
        for window in sorted(windows):
            prefix = f'{dataset}/experience/{arm}/windows/{window:04d}'
            start = bundle.read(f'{prefix}/read_snapshot.json')
            require(previous is None or start == previous, f'{prefix}: bank lineage')
            previous = bundle.read(f'{prefix}/repo.json')
        require(previous == final, f'{dataset}/{arm}: final bank differs')
        accuracy = 100*total['counts']['correct']/count
        require(official['dataset'] == dataset and official['arm'] == ARMS[arm]
                and official['accuracy_pct'] == accuracy == pair_summary['arms'][arm]['accuracy_pct']
                and pair_summary['arms'][arm]['questions'] == count
                and pair_summary['arms'][arm]['correct'] == total['counts']['correct']
                and all(official[key] == value for key, value in total['counts'].items())
                and official['tools_by_name'] == dict(total['tool_names']), f'{dataset}/{arm}: score and tool summary')
        usage = official['model_usage_by_role']
        require(set(usage) == set(total['roles']) and all(usage[role][key] == value
                for role, counts in total['roles'].items() for key, value in counts.items()), f'{dataset}/{arm}: model receipt counts')
    require(totals['E']['retries'] == int(dataset == 'slake') and totals['D']['retries'] == 0,
            f'{dataset}: missing original SLAKE failure')
    for folder, expected, key in (('tool-records', set(support['tools']), 'tool_records'),
                                  ('experience/snapshots', support['snapshots'], 'saved_snapshots')):
        members = bundle.members(f'{dataset}/{folder}')
        require(members == expected and len(members) == scope[key], f'{dataset}/{folder}: support membership')
    request_images = bundle.read(f'{dataset}/request_image_references.json')
    require(all('img-'+digest in assets and type(n) is int and n > 0 for digest, n in request_images.items())
            and sum(request_images.values()) == scope['redactions']['inline_images'], f'{dataset}: request image index')
    tool_assets.update(support['tools'])
    return {'pair': dict(paired), 'arms': {arm: dict(total['counts'], roles=dict(total['roles']))
            for arm, total in totals.items()}, 'tool_records': len(support['tools']),
            'snapshots': len(support['snapshots']), 'preserved_original_failed_main_calls': totals['E']['retries']}


def verify(root):
    bundle = Bundle(root)
    source_names = ('cxr_author_alignment.py', 'cxr_image_memory_r44.py', 'r54_author_metrics.py')
    source = bundle.path(f'source/{source_names[0]}').parent
    for name in source_names:
        require(bundle.path(f'source/{name}').parent == source, f'{name}: scorer source path')
    sys.path.insert(0, str(source))
    try:
        from cxr_image_memory_r44 import tool_failure_reason
        from r54_author_metrics import adapt, outcomes
        require(all(Path(sys.modules[name.removesuffix('.py')].__file__).parent == source
                    for name in source_names), 'scorer modules must be loaded from the bundle')
    finally:
        sys.path.pop(0)
    raw = adapt_raw(bundle, adapt)
    scope = bundle.read('outgoing_scope.json')
    image_index = bundle.read('asset_references.json')
    assets, commit = image_index['assets'], image_index['verified_origin_commit']
    require(set(scope['datasets']) == set(COUNTS) and scope['cases'] == sum(COUNTS.values())
            and scope['new_model_calls'] == 0
            and scope['image_binaries'] == image_index['image_binaries']
            and scope['assets'] == len(assets), 'bundle scope differs')
    dispositions = Counter()
    packed = {}
    for identifier, record in assets.items():
        link, withheld = record.get('published_asset_url'), record.get('withheld_reason')
        local = record.get('published_asset_path')
        require(re.fullmatch(ASSET, identifier) and identifier == record['asset_id']
                and sum(map(bool, (link, withheld, local))) == 1, f'{identifier}: asset disposition')
        if link:
            dispositions['linked'] += 1
            url = urlsplit(link)
            require(commit and re.fullmatch(r'[a-f0-9]{40}', commit) and url.scheme == 'https'
                    and url.netloc == 'github.com' and f'/blob/{commit}/' in url.path, f'{identifier}: exact link')
        elif local:
            dispositions['packed'] += 1
            packed[identifier] = record
        else:
            dispositions['withheld'] += 1
    require(type(scope['image_binaries']) is int and scope['image_binaries'] == len(packed)
            and dispositions == scope['image_links'], 'asset disposition counts differ')
    tool_assets = {}
    datasets = {dataset: check_dataset(bundle, dataset, raw[dataset], scope['datasets'][dataset], assets, outcomes,
                                      tool_failure_reason, tool_assets) for dataset in COUNTS}
    local = check_local_images(bundle, packed, assets, raw, image_index['source_pages'], tool_assets)
    return {'schema': 'r55_open_text_outgoing_reproduction_v1', 'datasets': datasets,
            'reextracted_terminal_responses': sum(COUNTS.values())*len(ARMS), 'new_model_calls': 0,
            'raw_answers_adapted_before_label_use': True, 'asset_dispositions': dict(dispositions),
            'local_images_verified': local,
            'limits': ['Case JSON stores raw replies and feedback together. Extraction uses only input, prediction and model records.',
                       'Local image bytes, headers, and recorded attribution are checked offline. This run neither reviews pixels for identity nor verifies source rights.',
                       'Remote links are checked syntactically without fetching images.',
                       'Retry request objects match in the bundle. Original byte equality is retained as a projection receipt.'],
            'utc': datetime.now(timezone.utc).isoformat()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    require(not args.receipt.resolve().is_relative_to(args.bundle.resolve()) and not args.receipt.exists(),
            'receipt must be new and outside the bundle')
    sys.dont_write_bytecode = True
    result = verify(args.bundle)
    with args.receipt.open('x', encoding='utf-8') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
