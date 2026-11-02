"""Freeze case-disjoint unseen tuning/test inputs; keep references scorer-only.

History discovery uses actual published content, including training/retrieval
records. The legacy pool's complete boundary registry is provenance-only and is
explicitly excluded from exposure (its real memory records are still included).
No model, image hash scan, account ledger, or correctness decision is involved.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import random
import re

QID = re.compile(r"(?<![A-Za-z0-9_])(?:\d+_){1,2}\d{10,}(?![A-Za-z0-9_])")
HEX = re.compile(r"(?<![a-f0-9])[a-f0-9]{64}(?![a-f0-9])")
TEXT_SUFFIXES = {'.json', '.jsonl', '.md', '.log', '.txt'}
QID_FIELDS = {'question_id', 'source_question_id', 'qid', 'seed_question_id'}
CASE_FIELDS = {'case_id', 'case_hash', 'source_case_hash'}


def read_rows(path):
    rows = []
    for i, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f'invalid metadata JSON on line {i}') from exc
        if not isinstance(row, dict):
            raise ValueError(f'metadata line {i} is not an object')
        rows.append(row)
    return rows


def indexes(rows):
    qmap, cases, groups = {}, set(), defaultdict(list)
    for row in rows:
        case = row.get('case_id')
        qid = row.get('question_id')
        if isinstance(case, bool) or not isinstance(case, (str, int)) or not str(case).strip():
            raise ValueError('reliable explicit case_id is required')
        case = str(case).strip()
        if not isinstance(qid, str) or not qid or qid in qmap:
            raise ValueError('missing or duplicate question_id')
        if not isinstance(row.get('question'), str) or not row['question'].strip():
            raise ValueError('missing question text')
        images = row.get('images')
        if not isinstance(images, list) or any(not isinstance(p, str) for p in images):
            raise ValueError('image path list required')
        for p in images:
            rel = PurePosixPath(p)
            if rel.is_absolute() or '..' in rel.parts or '\\' in p:
                raise ValueError('unsafe image path')
        qmap[qid] = case
        full = row.get('full_question_id')
        if full and full != qid:
            if full in qmap:
                raise ValueError('duplicate full_question_id')
            qmap[full] = case
        cases.add(case)
        groups[case].append(row)
    if not groups:
        raise ValueError('empty metadata')
    hashes = {hashlib.sha256(c.encode()).hexdigest(): c for c in cases}
    return qmap, cases, hashes, groups


def _metadata_boundary(value):
    """Recognize only the known complete, content-free boundary schema."""
    boundary_fields = {'entries', 'evidence_kind', 'exclusions_sha256', 'image_audit_sha256', 'registry', 'schema_version'}
    if (not isinstance(value, dict) or not {'entries', 'registry'} <= value.keys()
            or not set(value) <= boundary_fields):
        return False
    entries = value['entries']
    registry = value['registry']
    registry_fields = {'audit_file_sha256', 'input_file_sha256', 'rows', 'source_kind', 'split_manifest_sha256'}
    entry_fields = {'case_hash', 'excluded', 'features', 'image_count',
                    'image_references_sha256', 'image_sha256', 'question_id',
                    'question_sha256', 'split'}
    return (isinstance(entries, list) and isinstance(registry, dict)
            and set(registry) <= registry_fields
            and isinstance(registry.get('rows'), list)
            and all(isinstance(x, dict) and set(x) <= entry_fields for x in entries)
            and all(isinstance(x, dict) and set(x) <= {'case_hash', 'question_id', 'split'}
                    for x in registry['rows'])
            and all(isinstance(x.get('features', []), list)
                    and all(isinstance(f, str) and len(f) < 80 for f in x.get('features', []))
                    for x in entries))


def collect_history(rows, reports):
    qmap, cases, hashes, _ = indexes(rows)
    sources, unresolved, linked_aliases, inventories = defaultdict(set), set(), set(), []
    files_n, stores = 0, []

    def scan_text(text, found):
        for token in QID.findall(text):
            if token in qmap:
                found.add(qmap[token])
        for token in HEX.findall(text):
            if token in hashes:
                found.add(hashes[token])
        for case in re.findall(r'figures[/\\]+(\d+)', text):
            if case in cases:
                found.add(case)

    def walk(value, found, source, context=frozenset(), location=''):
        if isinstance(value, dict):
            local = set(context)
            for key in QID_FIELDS:
                qid = value.get(key)
                if isinstance(qid, str) and qid:
                    if qid in qmap:
                        local.add(qmap[qid])
                        found.add(qmap[qid])
                    else:
                        unresolved.add((source, key, qid))
            for key in CASE_FIELDS:
                case = value.get(key)
                if case is None or case == '':
                    continue
                case = str(case)
                canonical = case if case in cases else hashes.get(case)
                if canonical:
                    local.add(canonical)
                    found.add(canonical)
                elif local:
                    # Some old runtimes call a question-content hash case_hash.
                    # Resolve exposure using explicit QID, never that hash/prefix.
                    linked_aliases.add((source, key, case, tuple(sorted(local))))
                else:
                    unresolved.add((source, key, case))
            for key, item in value.items():
                if key == 'boundary' and _metadata_boundary(item):
                    inventories.append({'source': source, 'json_path': location + '/boundary',
                                        'entry_count': len(item['entries']),
                                        'reason': 'complete metadata registry; no question, image bytes, prediction or reference content'})
                    continue
                scan_text(str(key), found)
                walk(item, found, source, frozenset(local), location + '/' + str(key))
        elif isinstance(value, list):
            for item in value:
                walk(item, found, source, context, location)
        elif isinstance(value, str):
            scan_text(value, found)

    root = Path(reports)
    if not root.exists():
        raise ValueError('historical artifact root does not exist: ' + str(root))
    for p in sorted(root.rglob('*')) if root.is_dir() else [root]:
        if (not p.is_file() or p.is_symlink() or p.suffix.lower() not in TEXT_SUFFIXES
                or 'api_budget' in p.name.lower() or 'ledger' in p.name.lower()):
            continue
        source = p.relative_to(root).as_posix() if root.is_dir() else p.name
        found = set()
        text = p.read_text(encoding='utf-8-sig')
        files_n += 1
        scan_text(source, found)
        file_context = frozenset(found)
        try:
            if p.name.endswith('.labels.jsonl'):
                label_rows = [json.loads(x) for x in text.splitlines() if x.strip()]
                if all(isinstance(x, dict) and set(x) <= {'question_id', 'answer'}
                       and {'question_id', 'answer'} <= set(x) for x in label_rows):
                    stores.append({'source': source, 'record_count': len(label_rows),
                                   'reason': 'isolated source reference store; actual scoring/feedback records are covered separately'})
                    continue
            if p.suffix == '.json':
                walk(json.loads(text), found, source, file_context)
            elif p.suffix == '.jsonl':
                for line in text.splitlines():
                    if line.strip():
                        walk(json.loads(line), found, source, file_context)
            else:
                scan_text(text, found)
        except json.JSONDecodeError as exc:
            raise ValueError('invalid historical JSON: ' + source) from exc
        for case in found:
            sources[case].add(source)
    return {'schema_version': 1, 'metadata_question_n': len(rows),
            'metadata_case_n': len(cases), 'files_considered': files_n,
            'excluded_case_ids': sorted(sources),
            'case_sources': {c: sorted(v) for c, v in sorted(sources.items())},
            'unresolved_references': [list(x) for x in sorted(unresolved)],
            'qid_linked_legacy_case_aliases': [list(x) for x in sorted(linked_aliases)],
            'metadata_only_inventories_not_exposure': inventories,
            'isolated_reference_stores_not_exposure': stores,
            'scope': 'all supplied actual historical content and retrieved candidate content; no account ledgers or weights',
            'exposure_definition': 'historical benchmark questions/images used in model calls, train seed/reflection, retrieved candidate or injected memory content, or published reports; source-data storage/preprocessing alone is not exposure',
            'not_established': 'does not detect model pretraining contamination or guarantee patient disjointness'}


def merge_history(parts):
    """Combine explicitly selected historical artifact roots with source provenance."""
    result = dict(parts[0][1])
    sources = defaultdict(set)
    for field in ('unresolved_references', 'qid_linked_legacy_case_aliases',
                  'metadata_only_inventories_not_exposure', 'isolated_reference_stores_not_exposure'):
        result[field] = []
    result['files_considered'] = 0
    for name, history in parts:
        result['files_considered'] += history['files_considered']
        for case, files in history['case_sources'].items():
            sources[case].update(name + '/' + f for f in files)
        for field in ('unresolved_references', 'qid_linked_legacy_case_aliases'):
            result[field].extend([[name + '/' + x[0], *x[1:]] for x in history[field]])
        for field in ('metadata_only_inventories_not_exposure', 'isolated_reference_stores_not_exposure'):
            result[field].extend([dict(x, source=name + '/' + x['source']) for x in history.get(field, [])])
    result['excluded_case_ids'] = sorted(sources)
    result['case_sources'] = {c: sorted(v) for c, v in sorted(sources.items())}
    result['historical_roots'] = [name for name, _ in parts]
    return result


def ordered_images(row):
    def details(path):
        m = re.search(r'(?i)(?:figure|fig)[_ -]*(\d+)([a-z]?)', PurePosixPath(path).stem)
        if not m:
            return path, path, (10**9, 10**9, '', path)
        suffix = m[2].lower()
        label = 'Figure ' + m[1] + suffix
        mention = re.search(r'(?i)\bfig(?:ure)?s?\.?\s*' + re.escape(m[1] + suffix) + r'\b', row['question'])
        return path, label, (mention.start() if mention else 10**9, int(m[1]), suffix, path)
    bound = sorted((details(p) for p in row['images']), key=lambda x: x[2])
    return [x[0] for x in bound], [x[1] for x in bound]


def build(rows, history, seed=20261102, tune_questions=400, test_questions=1000):
    _, cases, _, groups = indexes(rows)
    if history.get('unresolved_references'):
        raise ValueError('unresolved historical references; resolve before held-out selection')
    excluded = set(history['excluded_case_ids'])
    if not excluded <= cases:
        raise ValueError('history contains unknown case IDs')
    # Same exact source path/URL cannot cross splits, even under distinct case IDs.
    parent = {c: c for c in cases}
    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c
    owners = {}
    for row in rows:
        case = str(row['case_id']).strip()
        for kind in ('images', 'image_source_urls'):
            for value in row.get(kind, []):
                if not value:
                    continue
                key = kind, value
                if key in owners:
                    parent[find(case)] = find(owners[key])
                else:
                    owners[key] = case
    components = defaultdict(list)
    for c in sorted(cases):
        components[find(c)].append(c)
    missing_images = {str(row['case_id']).strip() for row in rows if not row['images']}
    excluded_for_selection = excluded | missing_images
    eligible, expanded = [], set(excluded_for_selection)
    for component in components.values():
        if excluded_for_selection.intersection(component):
            expanded.update(component)
        else:
            eligible.append(component)
    random.Random(seed).shuffle(eligible)
    total = sum(len(groups[c]) for comp in eligible for c in comp)
    if total < tune_questions + test_questions:
        raise ValueError(f'insufficient unseen questions: {total} available; {tune_questions + test_questions} requested')
    assignments, cursor = {}, 0
    for split, target in [('tune', tune_questions), ('test', test_questions)]:
        n = 0
        while n < target and cursor < len(eligible):
            for c in eligible[cursor]:
                assignments[c] = split
                n += len(groups[c])
            cursor += 1
        if n < target:
            raise ValueError('whole-case grouping leaves insufficient test questions')
    inputs, labels = {'tune': [], 'test': []}, {'tune': [], 'test': []}
    for comp in eligible[:cursor]:
        for c in comp:
            split = assignments[c]
            for row in sorted(groups[c], key=lambda x: x['question_id']):
                images, names = ordered_images(row)
                inputs[split].append({'question_id': row['question_id'], 'case_id': c,
                                      'question': row['question'], 'images': images,
                                      'figure_labels': names})
                if 'answer' in row:
                    labels[split].append({'question_id': row['question_id'], 'case_id': c,
                                          'answer': row['answer']})
    manifest = {'schema_version': 1, 'seed': seed, 'source_question_n': len(rows),
                'source_case_n': len(cases), 'seen_case_n': len(excluded),
                'seen_question_n': sum(len(groups[c]) for c in excluded),
                'incomplete_image_cases_excluded': sorted(missing_images),
                'exact_image_component_extra_excluded_cases': sorted(expanded - excluded_for_selection),
                'eligible_case_n': len(cases - expanded), 'eligible_question_n': total,
                'requested_questions': {'tune': tune_questions, 'test': test_questions},
                'split_question_counts': {s: len(v) for s, v in inputs.items()},
                'split_case_counts': {s: sum(x == s for x in assignments.values()) for s in inputs},
                'unused_eligible_question_n': total - sum(map(len, inputs.values())),
                'assignment': assignments, 'whole_cases_only': True,
                'inference_fields': ['question_id', 'case_id', 'question', 'images', 'figure_labels'],
                'figure_order': 'explicit full Figure label first occurrence, then natural filename order; no inferred timepoint',
                'limitations': ['case-disjoint does not establish patient-disjoint',
                                'exact source paths/URLs grouped; image bytes not scanned',
                                'references separated by files and process, not an OS access boundary']}
    return inputs, labels, manifest


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def decode_history_manifest(value):
    """Read original histories or the losslessly indexed public schema 2."""
    if not isinstance(value, dict):
        raise ValueError('history manifest must be an object')
    version = value.get('schema_version', 1)
    if version == 1:
        return value
    if version != 2:
        raise ValueError('unsupported history manifest schema')
    sources = value.get('source_files')
    by_case = value.get('case_source_indices')
    if (not isinstance(sources, list) or any(not isinstance(x, str) for x in sources)
            or not isinstance(by_case, dict)
            or set(by_case) != set(value.get('excluded_case_ids', []))):
        raise ValueError('invalid indexed history source table or case coverage')

    def source(index):
        if type(index) is not int or not 0 <= index < len(sources):
            raise ValueError('invalid history source_file_index')
        return sources[index]

    decoded = {k: v for k, v in value.items()
               if k not in {'encoding', 'source_files', 'case_source_indices'}}
    decoded['schema_version'] = 1
    decoded['source_manifest_schema_version'] = 2
    decoded['case_sources'] = {}
    for case, indices in by_case.items():
        if not isinstance(indices, list) or not indices:
            raise ValueError('excluded case requires historical source indices')
        decoded['case_sources'][case] = [source(i) for i in indices]
    decoded['qid_linked_legacy_case_aliases'] = []
    for item in value.get('qid_linked_legacy_case_aliases', []):
        if not isinstance(item, list) or len(item) != 4:
            raise ValueError('invalid indexed legacy case alias')
        decoded['qid_linked_legacy_case_aliases'].append([source(item[0]), *item[1:]])
    for field in ('metadata_only_inventories_not_exposure', 'isolated_reference_stores_not_exposure'):
        decoded[field] = []
        for item in value.get(field, []):
            if not isinstance(item, dict) or 'source_file_index' not in item:
                raise ValueError('invalid indexed historical inventory')
            decoded[field].append({**{k: v for k, v in item.items() if k != 'source_file_index'},
                                   'source': source(item['source_file_index'])})
    return decoded


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--metadata', type=Path, required=True)
    h = p.add_mutually_exclusive_group(required=True)
    h.add_argument('--reports', type=Path)
    h.add_argument('--history-manifest', type=Path)
    p.add_argument('--extra-history', type=Path, action='append', default=[],
                   help='additional actual history directory/file; repeatable; do not pass unused source-data stores')
    p.add_argument('--history-out', type=Path)
    p.add_argument('--out', type=Path)
    p.add_argument('--labels-out', type=Path)
    p.add_argument('--preview', action='store_true', help='counts only; allows label-free metadata')
    p.add_argument('--seed', type=int, default=20261102)
    p.add_argument('--tune-questions', type=int, default=400)
    p.add_argument('--test-questions', type=int, default=1000)
    a = p.parse_args(argv)
    rows = read_rows(a.metadata)
    if a.reports:
        history = merge_history([(x.name, collect_history(rows, x)) for x in [a.reports, *a.extra_history]])
    else:
        if a.extra_history:
            p.error('--extra-history requires --reports')
        history = decode_history_manifest(json.loads(a.history_manifest.read_text(encoding='utf-8')))
    if a.history_out:
        write_json(a.history_out, history)
    inputs, labels, manifest = build(rows, history, a.seed, a.tune_questions, a.test_questions)
    if not a.preview:
        if not a.out or not a.labels_out:
            p.error('--out and --labels-out required unless --preview')
        out, lab = a.out.resolve(), a.labels_out.resolve()
        if out == lab or lab.is_relative_to(out) or out.is_relative_to(lab):
            raise ValueError('labels must be outside generation input directory')
        if any(len(labels[s]) != len(inputs[s]) for s in inputs):
            raise ValueError('metadata missing references for isolated scorer')
        if out.exists() or lab.exists():
            raise ValueError('new split/label directories required; no overwrite')
        out.mkdir(parents=True); lab.mkdir(parents=True)
        for s in inputs:
            (out / f'{s}.inputs.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in inputs[s]), encoding='utf-8')
            write_json(out / f'{s}.question_ids.json', [x['question_id'] for x in inputs[s]])
            write_json(lab / f'{s}.labels.json', {'records': labels[s]})
        manifest['source_metadata_filename'] = a.metadata.name
        write_json(out / 'manifest.json', manifest)
        write_json(out / 'history_exclusions.json', history)
    print(json.dumps({k:v for k,v in manifest.items() if k != 'assignment'}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
