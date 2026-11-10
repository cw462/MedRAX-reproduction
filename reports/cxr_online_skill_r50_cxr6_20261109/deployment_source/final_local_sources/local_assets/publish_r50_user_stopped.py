"""Explicit user-stopped partial publication. No benchmark inference or automatic resume.

Each phase has a single started/completed/failure receipt; final 848 gates are
intentionally not used to misrepresent an authorized incomplete publication.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments'))
PREP = ROOT / 'local_assets/r50_user_stop_publication_20261110'
OLD_PREP = ROOT / 'local_assets/r50_cxr6_preparation'
MIRROR = Path('D:/MedRAX_Experiment_Artifacts/online_skill_r50_user_stopped_20261110')
GEN = MIRROR / 'generation/chexbench'
REPORT = ROOT / 'reports/cxr_online_skill_r50_cxr6_20261109'
EVIDENCE = REPORT / 'evidence/chexbench'
BASE = '3ab0a927526e0910328b8db2503ac0fdc0e10036'
ARM = 'M43-IM-GT-S50-CXR6'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        handle.write(value.rstrip() + '\n')


def phase(name, operation):
    started = PREP / (name + '.started.json')
    assert not started.exists() and not (PREP / (name + '.completed.json')).exists(), 'single_use_phase_' + name
    put(started, {'utc': datetime.now(timezone.utc).isoformat(), 'phase': name, 'user_stopped': True, 'automatic_retry': False})
    try:
        result = operation()
    except Exception as error:
        put(PREP / (name + '.failure.json'), {'error': repr(error), 'partial_originals_preserved': True, 'automatic_retry': False})
        raise
    put(PREP / (name + '.completed.json'), dict(result, status='completed', utc=datetime.now(timezone.utc).isoformat()))
    return result


def gate():
    stop = read(PREP / 'stop.completed.json')
    collection = read(PREP / 'collection.completed.json')
    assert stop['status'] == 'USER_STOPPED_INCOMPLETE' and collection['status'] == 'completed'
    assert stop['counts']['predictions'] == stop['counts']['prediction_events'] == stop['counts']['feedback'] == 435
    assert (MIRROR / 'jobs/controller_amendment003.exitcode').read_text().strip() == '241'
    assert (MIRROR / 'jobs/chexbench_amendment003.exitcode').read_text().strip() == '-15'
    assert (GEN / 'generation.amendment003.exitcode').read_text().strip() == '-15'
    manifest = read(GEN / 'manifest.json')
    assert manifest['arm'] == ARM and len(manifest['inputs']) == 618
    assert len(list((GEN / 'predictions' / ARM).glob('*.json'))) == 435
    assert len(list((GEN / 'contexts').glob('*.json'))) == 436
    assert not (GEN / 'complete.json').exists()
    return stop, collection, manifest


def semantic_strings(value):
    """Inspect JSON string contents, not escaped serialization syntax as paths."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from semantic_strings(item)
    elif isinstance(value, list):
        for item in value:yield from semantic_strings(item)
    elif isinstance(value, str):
        if value.lstrip().startswith(('{','[')):
            try:parsed=json.loads(value)
            except ValueError:pass
            else:
                yield from semantic_strings(parsed)
                return
        yield value


def score():
    import score_r50_stopped_prefix as scoring
    stop, collection, manifest = gate()
    inputs = manifest['inputs'][:435]
    answers = scoring.raw_adapt(GEN, inputs)
    put(PREP / 'reference_free_adaptation.json', {'n': 435, 'references_read': False, 'answers': answers})
    identity = read(ROOT / 'local_assets/r49_dataset_score_receipts/chexbench.json')['identity']
    refs = [json.loads(line) for line in Path(identity['references']).read_text(encoding='utf-8').splitlines() if line.strip()]
    summary, details = scoring.grade_saved(GEN, inputs, answers, refs)
    old = read(OLD_PREP / 'user_requested_interim_accuracy_20261110/per_question.json')
    assert all(a['question_id'] == b['question_id'] and a['adapted'] == b['adapted']
        and a['aligned_correct'] == bool(b['score']['aligned_correct']) for a, b in zip(details[:420], old))
    out = REPORT / 'results/user_stopped'
    put(out / 'summary.json', summary)
    put(out / 'per_question.json', details)
    put(PREP / 'reference_subset.json', [item for item in refs if item['question_id'] in {row['question_id'] for row in inputs}])
    return {'questions': 435, 'correct': summary['correct'], 'accuracy_pct': summary['accuracy_pct'],
        'source': str(out), 'all435_adapted_before_labels': True, 'original420_unchanged': True,
        'full_cohort_score_receipts_consumed': False}


def export(resume=False):
    from export_cxr_vqa_extension import RequestEvidencePublisher, restore_images
    from export_cxr_image_memory_gt_r47 import derived_assets
    from export_online_skill_r49 import copy_records
    from export_online_skill_r50 import finish_images, export_health
    stop, collection, manifest = gate()
    assert read(PREP / 'score.completed.json')['status'] == 'completed'
    assert EVIDENCE.exists() if resume else not EVIDENCE.exists()
    if resume:
        assert (PREP/'export002.failure.json').is_file() and (PREP/'export002_diagnosis.json').is_file()
        assert not (EVIDENCE/'publication_manifest.json').exists()
    identity = read(ROOT / 'local_assets/r49_dataset_score_receipts/chexbench.json')['identity']
    data = Path(identity['data'])
    from export_vote_phase import DATA_URI, SECRET, PRIVATE_PATH
    class StoppedEvidencePublisher(RequestEvidencePublisher):
        def emit(self,path,value,jsonl=False):
            if resume and path.exists():
                self.files.add(path)
                return
            path.parent.mkdir(parents=True,exist_ok=True)
            cleaned=self.clean(value,path)
            if any(pattern.search(item) for item in semantic_strings(cleaned) for pattern in (DATA_URI,SECRET,PRIVATE_PATH)):
                raise ValueError('outgoing_semantic_string_contains_private_content:'+str(path.relative_to(self.out)))
            body=('\n'.join(json.dumps(item,ensure_ascii=False) for item in cleaned) if jsonl else json.dumps(cleaned,ensure_ascii=False,indent=2))+'\n'
            with path.open('x',encoding='utf-8') as handle:handle.write(body)
            self.files.add(path)
    publisher = StoppedEvidencePublisher(EVIDENCE, data / 'manifest.json', image_roots=(data,))
    if resume:
        publisher.files.update(path for path in EVIDENCE.rglob('*') if path.is_file())
    attempted = manifest['inputs'][:436]
    for row in attempted:
        for name in row['images']:
            publisher.source_image(name)
            key = publisher.sources[name]
            for alias in (name, str(data / name), '/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_vqa_extension/data/chexbench/' + name):
                publisher.alias(alias, key)
    by_id = {row['question_id']: row for row in attempted}
    for path in sorted((GEN / 'services/tool_selections/R50-AGENT').glob('*/*.json')):
        selection = read(path)
        row = by_id[path.parent.name]
        publisher.alias(selection.get('original_image'), publisher.sources[row['images'][selection.get('image_index', 1) - 1]])
        derived_assets(publisher, GEN / 'services', selection)
    # Include every original and derived artifact, including interrupted-worker images.
    for path in sorted(GEN.rglob('*')):
        if path.is_file() and path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
            key = publisher.put_image(publisher.read_image(path))
            publisher.alias('/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/generation/chexbench/' + path.relative_to(GEN).as_posix(), key)
    if resume:
        # Earlier request-specific image assets are already complete. Retain
        # their inherited naming IDs without re-hashing or re-reading pixels.
        for path in (EVIDENCE/'assets').iterdir():
            if path.is_file() and path.stem not in publisher.assets:
                publisher.assets[path.stem]={'target':path,'bytes':path.stat().st_size,'size':None,
                    'sha256':path.stem,'byte_preserving':True,'reused_existing_public_image':False,
                    'metadata_note':'Retained prior completed asset; filename ID reused, no new digest validation.'}
    for path in (GEN / 'services/calls').glob('*/*/*/request.json'):
        request = restore_images(read(path), GEN / 'services')
        for message in request.get('messages', []):
            content = message.get('content')
            for block in content if isinstance(content, list) else []:
                value = block.get('text', '')
                if value.startswith('BOUND CURRENT IMAGE: '):
                    metadata = json.loads(value[len('BOUND CURRENT IMAGE: '):])
                    name = metadata.get('source_filename')
                    if name in publisher.sources:
                        publisher.alias(metadata.get('path'), publisher.sources[name])
    publisher.emit(EVIDENCE / 'inputs.jsonl', manifest['inputs'][:435], jsonl=True)
    publisher.emit(EVIDENCE / 'interrupted_input.json', manifest['inputs'][435])
    publisher.emit(EVIDENCE / 'manifest.json', dict(manifest, inputs=attempted,
        export_projection='435completed plus436interrupted; original declared618; not a producer completion record'))
    publisher.emit(EVIDENCE / 'references.jsonl', read(PREP / 'reference_subset.json'), jsonl=True)
    for name in ('summary.json', 'per_question.json'):
        publisher.copy_json(REPORT / 'results/user_stopped' / name, EVIDENCE / 'scores' / name)
    copied = 0
    for path in sorted(GEN.rglob('*')):
        if not path.is_file() or path.name == 'manifest.json' or 'request_image_base64' in path.parts:
            continue
        if path.suffix not in ('.json', '.jsonl', '.txt', '.log', '.py', '.pid', '.exitcode', '.md') and path.name != 'exitcode':
            continue
        target = EVIDENCE / path.relative_to(GEN)
        if resume and target.exists():
            publisher.files.add(target)
            continue
        if path.name == 'request.json' and 'calls' in path.parts:
            publisher.emit(target, restore_images(read(path), GEN / 'services'))
        else:
            copy_records(publisher, path, target)
        copied += 1
        if copied % 1000 == 0:
            print(json.dumps({'exported_records': copied}), flush=True)
    for path in sorted((MIRROR / 'jobs').iterdir()):
        if path.is_file() and path.suffix in ('.json', '.pid', '.exitcode', '.log'):
            copy_records(publisher, path, EVIDENCE / 'job_records' / path.name)
    publisher.emit(EVIDENCE / 'USER_STOP.json', stop)
    finish_images(publisher, EVIDENCE)
    publisher.emit(EVIDENCE / 'publication_manifest.json', {'status': 'user_stopped_incomplete',
        'completed_prefix': 435, 'interrupted_ordinal': 436, 'full_declared_CheX': 618,
        'full_intended_total': 848, 'remaining_unanswered': 413,
        'separate_SLAKE114_VQA116': 'never_started', 'raw_controller_exit': 241, 'raw_runner_exit': -15,
        'inflight_outcomes': 'unknown where started has no terminal receipt; never resent',
        'new_inference_calls': 0, 'all_prior_nonzero_exits_retained': True,
        'source_attribution': 'Original question source fields and original dataset/model terms retained; source images reused from already-saved canonical data.',
        'image_storage': 'Existing unchanged asset naming/sanitizer; no new image/weight attestation.',
        'files': sorted(path.relative_to(EVIDENCE).as_posix() for path in publisher.files),
        'redactions': dict(publisher.redactions)})
    health = export_health(OLD_PREP / 'health', MIRROR / 'health_input/training_xmlab120.jpg', REPORT / 'evidence/health')
    return {'files': len(publisher.files), 'images': len(publisher.assets), 'health': health,
        'full435_plus_interrupted_request_and_all_failure_history': True, 'new_model_calls': 0}


def verify():
    import score_r50_stopped_prefix as scoring
    summary = scoring.verify_public(EVIDENCE, REPORT / 'public_reproduction/user_stopped')
    return {'questions': summary['questions'], 'correct': summary['correct'], 'public_raw_score_reproduction': True,
        'private_run_required': False, 'new_model_calls': 0}


def assemble(resume=False):
    from capture_r50_publication_sources import sanitize, HELPERS, SKILLS, SKILL_ROOT
    from publish_cxr6_r50 import SOURCE_NAMES, TEST_NAMES
    stop, collection, manifest = gate()
    assert read(PREP / 'verify.completed.json')['public_raw_score_reproduction']
    dest = REPORT / 'deployment_source'
    if resume:
        assert (PREP/'assemble.failure.json').is_file() and (PREP/'source_assembly_longpath_diagnosis.json').is_file()
        assert dest.is_dir() and not (dest/'COPY_MAP.json').exists()
    else:dest.mkdir()
    copies = []
    redactions = []
    def copy(source, relative, kind):
        assert source.is_file() and not source.is_symlink()
        body, counts = sanitize(source.read_text(encoding='utf-8-sig', errors='replace'))
        published=relative;target=dest/published
        if resume and target.is_file():
            if target.read_text(encoding='utf-8') != body:
                copies.append({'source_relative':relative,'published':relative,'kind':'retained_before_source_assembly_correction'})
                published='corrected_local_sources/'+str(len(copies)).zfill(5)+'_'+source.name
                target=dest/published
        elif len(str(target))>240:
            published='long_paths/'+str(len(copies)).zfill(5)+'_'+source.name
            target=dest/published
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('x',encoding='utf-8') as handle:handle.write(body)
        else:assert target.read_text(encoding='utf-8')==body
        source_relative = relative.removeprefix('actual_CODE/') if kind == 'actual_CODE' else relative
        copies.append({'source_relative': source_relative, 'published': published, 'kind': kind, 'credential_redactions': counts})
        if any(counts.values()):
            redactions.append({'published': published, 'counts': counts, 'private_original_preserved': True})
    for relative in collection['actual_code_files']:
        copy(MIRROR / 'actual_code_source' / relative, 'actual_CODE/' + relative, 'actual_CODE')
    assert sum(item['kind'] == 'actual_CODE' for item in copies) == collection['actual_code_count']
    assert {item['source_relative'] for item in copies if item['kind'] == 'actual_CODE'} == set(collection['actual_code_files'])
    for folder in ('jobs', 'configs', 'held_comparison'):
        for path in sorted((MIRROR / folder).rglob('*')):
            if path.is_file() and path.suffix in ('.py', '.json', '.log', '.txt', '.pid', '.exitcode'):
                copy(path, 'controls/' + path.relative_to(MIRROR).as_posix(), 'control')
    for path in MIRROR.iterdir():
        if path.is_file() and path.suffix in ('.py', '.json') and path.name != 'inventory.json':
            copy(path, 'controls/' + path.name, 'control')
    copy(GEN / 'manifest.json', 'controls/original_declared_generation_manifest.json.txt', 'original_manifest_not_completion')
    for name in SOURCE_NAMES:
        copy(ROOT / 'experiments' / name, 'local_reporting/experiments/' + name, 'local_source')
    copy(ROOT / 'experiments/score_r50_stopped_prefix.py', 'local_reporting/experiments/score_r50_stopped_prefix.py', 'local_source')
    for name in TEST_NAMES:
        copy(ROOT / 'tests' / name, 'local_reporting/tests/' + name, 'local_test_history')
    for name in (*HELPERS, 'stop_r50_and_waiting_deepseek_user_once.py', 'collect_r50_user_stop_once.py',
                 'collect_r50_user_stop_remaining_stream_once.py', 'publish_r50_user_stopped.py'):
        copy(ROOT / 'local_assets' / name, 'helpers/' + name, 'helper')
    for path in sorted(OLD_PREP.rglob('*')):
        if not path.is_file() or 'health' in path.relative_to(OLD_PREP).parts:
            continue
        if path.stat().st_size == 0 and path.name == 'maira_runtime':
            relative = 'preparation/' + path.relative_to(OLD_PREP).as_posix() + '.ZERO_BYTE_PLACEHOLDER.txt'
            if len(str(dest/relative))>240:relative='long_paths/'+str(len(copies)).zfill(5)+'_maira_runtime.ZERO_BYTE_PLACEHOLDER.txt'
            target = dest/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():
                with target.open('xb') as handle:handle.write(b'')
            assert target.stat().st_size==0
            copies.append({'source_relative':path.relative_to(OLD_PREP).as_posix(),'published':relative,
                'kind':'retained_zero_byte_placeholder_from_failed_SFTP_directory_read','source_bytes':0})
            continue
        if path.suffix in ('.py', '.json', '.jsonl', '.md', '.txt', '.log', '.pid', '.exitcode'):
            copy(path, 'preparation/' + path.relative_to(OLD_PREP).as_posix(), 'R50_preparation_and_actual_failure_history')
    for path in sorted(PREP.iterdir()):
        if path.is_file() and path.suffix in ('.py', '.json', '.md', '.txt', '.log') and 'review' not in path.name:
            copy(path, 'user_stop/' + path.name, 'explicit_user_stop')
    for relative in SKILLS:
        copy(SKILL_ROOT / relative, 'workflow_skill_sources/' + relative + '.txt', 'workflow_guidance_not_learned_Skill')
    proposal=ROOT/'local_assets/r50_cxr6_user_package_20261109/R50_CXR6'
    for path in sorted(proposal.iterdir()):
        if path.is_file() and path.suffix in ('.md','.py','.json','.patch'):
            copy(path,'original_user_proposal/'+path.name,'original_proposal_not_readiness_proof')
    for name in ('001-code','002-archive-delta'):
        trace=ROOT/'.aris/traces/experiment-bridge/run_20261109_r50_cxr6_001'/name
        for path in sorted(trace.iterdir()):
            if path.is_file() and path.suffix in ('.json','.md','.txt','.log'):
                copy(path,'actual_preflight_reviews/'+name+'/'+path.name,'actual_preflight_review_record')
    put(dest / 'COPY_MAP.json', {'files': copies, 'count': len(copies), 'actual_CODE_count': collection['actual_code_count'],
        'source_capture': 'post_execution_snapshot_not_byte_or_weight_attestation', 'credentials_or_unrelated_user_files_copied': False})
    put(dest / 'CREDENTIAL_REDACTION_RECEIPT.json', {'files': redactions, 'scope': 'outgoing copies only; originals retained'})
    text(dest / 'PROVENANCE.md', '''# User-stopped R50 source provenance

Actual_CODE contains exactly the files/count in the actual stopped-run source capture. The original11producer files and the3actual A.4 extension modules are distinct from later local reporting compatibility code. Full original jobs/native nonzero exits, explicit stop, configs, controls, failed/retried outputs, helper errors and prior user-requested420-case analysis remain in the package. The revised DeepSeek queue was held at zero requests; it is not an executed comparison.

The source is a post-execution snapshot, not a byte/weight/model identity attestation. Credential literals alone in outgoing source copies are redacted and counted; original files/predictions remain unchanged. Credential loaders/settings/keys/weights/unrelated user files are excluded. Workflow skills are installed guidance snapshots, separate from the learned card versions in raw window/context files. The publication is intentionally incomplete by explicit user instruction; original full-cohort code gates are not passed or forged. Complete-result review of this stopped scope is stored separately at report root.
''')
    return {'source_files': len(copies), 'actual_CODE_count': collection['actual_code_count'], 'outgoing_redacted_files': len(redactions)}


def write_report():
    from finalize_r50_report import INDEXES, replace_index_block
    stop, collection, manifest = gate()
    summary = read(REPORT / 'results/user_stopped/summary.json')
    details = read(REPORT / 'results/user_stopped/per_question.json')
    inputs = [json.loads(line) for line in (EVIDENCE / 'inputs.jsonl').read_text(encoding='utf-8').splitlines()]
    def link(target, document):
        return os.path.relpath(target, document.parent).replace('\\', '/')
    resources = {'status': 'user_stopped_incomplete', 'native_stop': stop, 'physical_attempts': {},
        'provider_Credits': None, 'provider_invoice_CNY': None, 'hardware_cost': None,
        'unknown_not_zero': True, 'cost_model': 'Recorded CNY usage proxies are not provider charges; overlap/retries/inflight/health/review are separate.',
        'call_groups': {}, 'unsettled_or_missing_terminal': []}
    for caller in sorted((GEN / 'services/calls').iterdir()):
        if not caller.is_dir():continue
        group = Counter();proxy = Decimal('0');tokens = Counter();elapsed = 0.0
        for started in caller.glob('*/*/started.json'):
            folder = started.parent;group['started'] += 1
            group['response_files'] += (folder / 'response.json').is_file()
            if (folder / 'result.json').is_file():
                result = read(folder / 'result.json');group['terminal_result'] += 1
                group['error'] += bool(result.get('error'))
                for name in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                    tokens[name] += (result.get('usage') or {}).get(name, 0) or 0
                elapsed += result.get('elapsed_s') or 0
                settlement = result.get('settlement') or {}
                if settlement.get('charged_cny') is not None:
                    proxy += Decimal(str(settlement['charged_cny']))
            else:
                resources['unsettled_or_missing_terminal'].append(folder.relative_to(GEN).as_posix())
        resources['call_groups'][caller.name] = dict(group, token_usage=dict(tokens), elapsed_sum_seconds=elapsed,
            recorded_CNY_proxy=str(proxy), provider_invoice=False)
    embeddings=GEN/'services/embeddings';embedding_usage=Counter();embedding_elapsed=0.0
    embedding_results=list(embeddings.rglob('result.json'))
    for path in embedding_results:
        result=read(path)
        for name,value in (result.get('usage') or {}).items():
            if isinstance(value,(int,float)):embedding_usage[name]+=value
        embedding_elapsed+=result.get('elapsed_s') or 0
    resources['embeddings']={'started_records':len(list(embeddings.rglob('started.json'))),
        'terminal_result_records':len(embedding_results),'token_usage':dict(embedding_usage),
        'elapsed_sum_seconds':embedding_elapsed,'provider_Credits_or_invoice':None,
        'all_raw_requests_responses_results':'evidence/chexbench/services/embeddings/'}
    for path in (GEN / 'services/tool_cache').glob('*/result.json'):
        result = read(path)
        resources['physical_attempts'][path.parent.name] = {'status': result.get('status'), 'backend': result.get('backend'),
            'actual_model_events': result.get('actual_model_events'), 'backend_compute_seconds': result.get('backend_compute_seconds')}
    resources['interrupted_tool_started_without_result'] = [p.parent.relative_to(GEN).as_posix() for p in (GEN / 'services/tool_cache').glob('*/started.json') if not (p.parent / 'result.json').is_file()]
    resources['prior_failure_and_retry_records']={folder:[path.relative_to(GEN).as_posix() for path in (GEN/folder).rglob('*')
        if path.is_file() and path.name in ('result.json','completed.json','failure.json','selection.json')]
        for folder in ('technical_failures','technical_recovery')}
    resources['physical_tool_accounting_limit']='Root adopted cache and explicit retry archives can describe the same successful physical attempt. Records are linked, not blindly summed or treated as new inference. Original failed attempts/partial unknowns remain separate.'
    resources['new3_health_evidence']='evidence/health/; previously captured once, not rerun; health never enters production cache/Skill/score.'
    resources['elapsed_note'] = 'Per-call elapsed sums overlap and are not total wall time or a bill. Original/controller timestamps and file mtimes are retained in controls/inventory.'
    repos=sorted((GEN/'windows').glob('*/repo.json'))
    repo=read(repos[-1]) if repos else {'skills':{}}
    resources['Skill_state_at_stop']={'completed_windows':len(repos),'total_cards':len(repo['skills']),
        'statuses':dict(Counter(item['status'] for item in repo['skills'].values())),
        'cards':[{'id':sid,'name':item['c']['name'],'status':item['status'],'source_ids':item['source_ids'],
                  'usage':item.get('usage')} for sid,item in repo['skills'].items()],
        'injected_prefix':summary['skill_injected'], 'uninjected_prefix':summary['no_skill_injected'],
        'causal_gain_identified':False}
    put(REPORT / 'RESOURCE_SUMMARY.json', resources)
    index = ['# User-stopped R50 completed prefix', '', '| Ordinal | Case | Correct | Skill injected |', '|---:|---|---|---|']
    for row, detail in zip(inputs, details):
        qid = row['question_id'];page = REPORT / 'cases/chexbench' / (qid + '.md')
        predpath = EVIDENCE / 'predictions' / ARM / (qid + '.json')
        pred = read(predpath);ctxpath = EVIDENCE / 'contexts' / (qid + '.json');ctx = read(ctxpath)
        body = [f'# {qid}', f"Ordinal {detail['ordinal']}; source {detail['subset']}; stopped-prefix record.", '', row['question'], '', '## Complete options', '']
        body += [f'- **{key}**: {value}' for key, value in row['options'].items()]
        body += ['', '## Original images', ''] + [f'![original]({link(EVIDENCE / name, page)})' for name in row['images']]
        body += ['', f"Explicit answer: **{detail['adapted']['explicit_answer']}**; reference: **{detail['reference']}**; correct: **{detail['aligned_correct']}**.", '', pred['reason'], '',
            f"[Prediction]({link(predpath, page)}) · [own post-prediction feedback]({link(EVIDENCE / 'feedback' / (qid+'.json'), page)}) · [exact context and Skill version]({link(ctxpath, page)}) · [all main requests/responses]({link(EVIDENCE / 'services/calls/R50-AGENT' / qid, page)})", '', '## Tool requests and observations', '']
        for selection in sorted((EVIDENCE / 'services/tool_selections/R50-AGENT' / qid).glob('*.json'), key=lambda p:int(p.stem)):
            value = read(selection);cache = EVIDENCE / 'services/tool_cache' / value['cache_key']
            body.append(f"- {value['tool']}: status={value['status']}; [selection]({link(selection,page)}), [full request/result/stdout/stderr artifacts]({link(cache,page)}).")
            for name in value.get('derived_images', []):body.append(f'![tool image]({link((selection.parent/name).resolve(),page)})')
        body += ['', '## Skill and prior-image provenance', '', f"Selected IDs: {detail['selected_skill_ids']}; prior same-image IDs: {detail['same_image_prior']}."]
        for skill in ctx['selected_skills']:
            body += ['', skill['c']['name'], '', skill['c']['core_action'], '', 'Actual source cases: ' + ', '.join(f'[{sid}]({sid}.md)' for sid in ctx['skill_snapshot']['skills'][skill['id']]['source_ids'])]
        body += ['', 'This is dataset-label scoring and model/tool narrative, not clinical adjudication or Skill causal verification.']
        text(page, '\n'.join(body))
        index.append(f"| {detail['ordinal']} | [{qid}](cases/chexbench/{qid}.md) | {detail['aligned_correct']} | {detail['skill_injected']} |")
    text(REPORT / 'CASE_INDEX.md', '\n'.join(index))
    nextrow = manifest['inputs'][435]
    text(REPORT / 'INTERRUPTED_CASE.md', f"# Interrupted ordinal436: {nextrow['question_id']}\n\nThe user requested stopping before this question had a committed prediction/event/feedback. It is excluded from the435-answer accuracy denominator and included in413unanswered planned questions. Any started remote request/tool may have unknown final compute/outcome; records are retained and are never resent.\n\n[Original question/options/image binding](evidence/chexbench/interrupted_input.json) · [context](evidence/chexbench/contexts/{nextrow['question_id']}.json) · [raw services](evidence/chexbench/services/)\n")
    previous = REPORT / 'README.md'
    if previous.exists():text(REPORT / 'README.running_before_user_stop.md', previous.read_text(encoding='utf-8-sig'))
    table = '| Dataset | Completed / planned | Correct | Accuracy |\n|---|---:|---:|---:|\n'
    table += f"| CheXBench | 435 / 618 | {summary['correct']} | {summary['accuracy_pct']:.2f}% |\n| SLAKE CXR | 0 / 114 | — | Not started |\n| VQA-RAD CXR | 0 / 116 | — | Not started |"
    description = f'''# R50 CXR6 — user-stopped incomplete results

The user explicitly requested stopping and publishing the existing results on2026-11-10. This archive contains **435/848 completed predictions**, an interrupted436th question, and **413 planned questions without a final prediction**. It is not a completed848-question experiment. The queued revised DeepSeek comparison was stopped before any formal request.

{table}

Scores use the unchanged common raw-answer adapter and metrics: all435 raw answers were adapted before references were opened. The earlier user-requested420-case score is retained separately and its420 answers/grades agree exactly. There is no answer-quality filtering, regeneration, repaired grounding output, or fabricated zero exit. Raw amended runner/GEN exit is **-15**, controller **241**; every original/recovery001/recovery002 exit1 remains. The idle DeepSeek wrapper exit143 is a deliberate stop, not an executed comparison failure.

The main/META model is Qwen3.7-plus with thinking=false and the six-tool menu medgemma/llava_rad/chest_xray_expert/llava_med_qa/xray_phrase_grounding/medvlm_r1. Per-dataset empty Skill/same-image state, window30/buffer20, next-window Skill, top5/branch/top6 and all-reject prescreen are retained. Own prediction/event precede own GT; earlier same-image annotation feedback may be used. This online-GT system is not closed-test evaluation or a Skill-only causal comparison.

The original11producer modules were followed by3explicitly approved A.4 failure-observation modules from CheX317. The MAIRA300-token/unclosed-tag failure remains failed; it was never regenerated/repaired or turned into successful cache. Two earlier pre-generation loading failures each had one explicit unchanged retry, with poor text preserved. Helper transport/capture errors and all stage nonzero exits are retained in source/control/failure evidence. This is amendedR50 with protocol, order, source, budget, prompt, EOS and time confounds, not an exact unchanged-paper reproduction.

The frozen420-case Skill analysis found a real one-source card and90injections, all on OpenI laterality choices: before68/92=73.91%, after62/90=68.89%; this is a different-case ordered comparison, not a causal effect. Of90dual grounding attempts,70 returned both boxes,16 neither and4 only one;3of the4single-box decisions were wrong.55same-model positive attributions include12wrong answers, which actually received negative numeric reward credit. These negative observations are retained; no clinical, Skill-causal or official-SOTA claim is made. Corrected/harmed/net versus a same-question Skill-off run are unknown, not zero. A larger model/evidence anchoring alone does not validate the heuristic.

At the later435-question stop, Skill-injected cases are {summary['skill_injected']['correct']}/{summary['skill_injected']['n']}={summary['skill_injected']['accuracy_pct']:.2f}%. This later cutoff is separate from the preserved90-injection/420-case audit. Neither subgroup score is a counterfactual Skill gain; the actual stopped repository/card state is in RESOURCE_SUMMARY.json.

- [All435case pages](CASE_INDEX.md), with complete questions/options/original images/tools/feedback/Skill sources.
- [Interrupted question436](INTERRUPTED_CASE.md) and [full raw evidence](evidence/chexbench/).
- [Stopped-prefix score](results/user_stopped/summary.json) and [actual public reproduction](public_reproduction/user_stopped/summary.json).
- [Requests, failed attempts and unknown costs/time](RESOURCE_SUMMARY.json). Provider Credits/invoice, unknown in-flight compute and hardware cost are unknown, not0. Per-call CNY proxies are not a provider bill and elapsed sums may overlap.
- [Actual source/control/copy map](deployment_source/PROVENANCE.md), including original failures, retries, helper errors, user approvals and the earlier420-case analysis.
- [Earlier420-case Skill effectiveness analysis](deployment_source/preparation/user_requested_interim_accuracy_20261110/skill_effect_analysis/ANALYSIS.md), preserving its frozen denominator and negative observations.
- [New3 health evidence](evidence/health/) is separate from scored examples and was not rerun for publication.
- [Initial protocol](PROTOCOL.json), [preparation tests](TESTS.md), and [running README preserved](README.running_before_user_stop.md).
- [Previously published complete R49 archive](https://github.com/cw462/MedRAX-reproduction/blob/main/reports/cxr_online_skill_r49_20261108/README.md); its inference/private scoring/downloads were not repeated.

Reproduce the stopped score without any model/API request: `python experiments/score_r50_stopped_prefix.py --evidence reports/cxr_online_skill_r50_cxr6_20261109/evidence/chexbench --out /path/to/new_output`. Use an empty separate output directory. Original dataset/model attribution remains in question/source records; applicable original terms continue to apply. Source copies are post-execution snapshots, not independent byte/weight/clinical attestations. All uploaded credentials are excluded/redacted; private originals remain unchanged.

An actual fresh DeepSeek review of this incomplete-result scope is required before the publication helper permits staging/push; its native metadata and raw result will be added at report root.
'''
    previous.write_text(description, encoding='utf-8')
    for relative in INDEXES:
        path = ROOT / relative
        block = '<!-- R50_CXR6_START -->\n## R50 CXR6: user-stopped incomplete archive\n\n' + table + f"\n\n[Stopped report]({os.path.relpath(REPORT/'README.md',path.parent).replace(chr(92),'/')}) · 435/848 completed;413unanswered. No Skill-causal/clinical/SOTA claim.\n<!-- R50_CXR6_END -->"
        path.write_text(replace_index_block(path.read_text(encoding='utf-8-sig'), block), encoding='utf-8')
    return {'case_pages': 435, 'status_description': 'user_stopped_incomplete', 'score_reused': True}


def git(args, data=None):
    result = subprocess.run(['git', *args], cwd=ROOT, input=data, capture_output=True)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf-8', 'replace'))
    return result.stdout


def review_gate():
    from finalize_r50_report import validate_review
    initial = read(OLD_PREP / 'CODE_REVIEW_METADATA.json')['session_id']
    metadata = validate_review(read(REPORT / 'RESULT_CLAIM_METADATA.json'), initial)
    assert metadata['audit_scope'] == ['online_feedback_and_Skill_protocol', 'request_resource_accounting', 'complete_results_and_claims']
    assert metadata['review_scope'] == 'user_stopped_435_completed_prefix_and_interrupted436'
    assert read(PREP / 'verify.completed.json')['public_raw_score_reproduction']
    return metadata


def prepare():
    from finalize_r50_report import INDEXES
    from publish_cxr6_r50 import SECRET, text_has_secret, outside_index_block, SOURCE_NAMES, TEST_NAMES
    metadata = review_gate()
    assert git(['rev-parse', 'HEAD']).decode().strip() == BASE
    assert git(['diff', '--cached', '--name-only', '-z']) == b'', 'foreign_staged_files_stop'
    files = sorted(path.relative_to(ROOT).as_posix() for path in REPORT.rglob('*') if path.is_file())
    code_paths = ['experiments/'+name for name in SOURCE_NAMES] + ['tests/'+name for name in TEST_NAMES]
    files += list(INDEXES) + ['experiments/score_r50_stopped_prefix.py'] + code_paths
    assert len(files) == len(set(files))
    for relative in INDEXES:
        assert outside_index_block((ROOT/relative).read_text(encoding='utf-8-sig')) == outside_index_block(git(['show','HEAD:'+relative]).decode('utf-8-sig'))
    for relative in files:
        path = ROOT / relative
        assert path.is_file() and not path.is_symlink() and path.stat().st_size < 100_000_000
        assert relative.startswith(REPORT.relative_to(ROOT).as_posix() + '/') or relative in (*INDEXES, 'experiments/score_r50_stopped_prefix.py', *code_paths)
        assert 'open_questions_for_later' not in relative and not any(part in ('.secrets','__pycache__','hf_modules') for part in path.parts)
        if path.suffix in ('.json','.jsonl','.md','.txt','.log','.py','.pid','.exitcode'):
            body = path.read_text(encoding='utf-8-sig')
            assert '\0' not in body and not text_has_secret(body), 'outgoing_secret_or_NUL:'+relative
            if path.suffix == '.json':json.loads(body)
            if path.suffix == '.jsonl':
                for line in body.splitlines():
                    if line.strip():json.loads(line)
    # Validate reader-facing generated links; retained historical source text is
    # a snapshot with its own original installation references, not a new site.
    from publish_cxr6_r50 import local_reference
    documents = [REPORT/name for name in ('README.md','CASE_INDEX.md','INTERRUPTED_CASE.md')]
    documents += list((REPORT/'cases').glob('*/*.md'))
    for document in documents:
        for match in re.finditer(r'!?\[[^\]]*\]\(([^\s)]+)\)', document.read_text(encoding='utf-8')):
            local_reference(match.group(1), document)
    put(PREP / 'publication_allowlist.json', {'files': files, 'base': BASE, 'review_session_id': metadata['session_id'],
        'scope': 'One stopped R50 report,18owned R50runtime/reporting modules,9owned test sources,new stopped scorer and four R50-marker-only root indexes.',
        'post_push_independent_remote_check': False})
    return {'files': len(files), 'base': BASE, 'review_session': metadata['session_id']}


def review_request():
    assert read(PREP/'write.completed.json')['case_pages'] == 435
    assembly=PREP/('assemble002.completed.json' if (PREP/'assemble002.completed.json').is_file() else 'assemble.completed.json')
    assert read(assembly)['actual_CODE_count'] > 0
    # One final local-code snapshot after bounded publication fixes. This does
    # not repeat the actual remote CODE capture or change its264-file set.
    from capture_r50_publication_sources import sanitize
    copy_map_path=REPORT/'deployment_source/COPY_MAP.json';copy_map=read(copy_map_path)
    final_sources=['local_assets/publish_r50_user_stopped.py','experiments/score_r50_stopped_prefix.py',
        'local_assets/stop_r50_and_waiting_deepseek_user_once.py','local_assets/collect_r50_user_stop_once.py',
        'local_assets/collect_r50_user_stop_remaining_stream_once.py']
    final_records=[]
    for relative in final_sources:
        body,counts=sanitize((ROOT/relative).read_text(encoding='utf-8'))
        published='final_local_sources/'+relative
        target=REPORT/'deployment_source'/published;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('x',encoding='utf-8') as handle:handle.write(body)
        record={'kind':'final_local_publication_source','source_relative':relative,'published':published,
            'credential_redactions':counts,'remote_actual_CODE_unchanged':True}
        copy_map['files'].append(record);final_records.append(record)
    copy_map['count']=len(copy_map['files'])
    copy_map_path.write_text(json.dumps(copy_map,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    put(REPORT/'deployment_source/FINAL_LOCAL_SOURCE_SNAPSHOT.json',{'files':final_records,
        'scope':'Final local stopped-publication code after actual bounded fixes; remote actualCODE remains the original once-captured264files.'})
    prompt = '''You are the ONE fresh actual user-selected DeepSeek reviewer of the stopped R50 result/archive and publication code. Read-only review; tools Read/Grep/Glob only. Never execute a command, model/tool inference, scorer, hash, Git or environment installation; never read secrets/settings/credential loaders. Give an independent honest result, not automatic approval.

The user explicitly changed the task to: stop this experiment now and upload existing results to the same GitHub. Real stop completed with435committed CheX predictions/events/feedback/steps,436contexts; current runner and one private child were terminated, raw runner/GEN-15 and wrapper controller241 remain. All original/recovery001/recovery002 native1 records remain. Revised DeepSeek waiting queue was stopped at0formal requests/native143. Do NOT require completing848 or fabricating0 to publish the user-authorized incomplete scope; those earlier full-run gates are intentionally replaced by explicit stopped-scope guards. No benchmark inference or automatic resume is authorized.413planned questions have no final answer;436is interrupted, not scored. Separate SLAKE/VQA never started.

Audit scope EXACT: online_feedback_and_Skill_protocol; request_resource_accounting; complete_results_and_claims. Here complete_results means all435completed predictions plus the interrupted436raw evidence and the full actual stop/failure/recovery history, not a claim the planned848were completed. Examine the real new stopped scorer/export/source/writer/publisher code, the initial runtime/amendment protocol and timing, actual raw score/public reproduction, unknown in-flight costs, all original/retry/capture/helper failures, source provenance and negative Skill claims. State if available context is incomplete.

Important actual history: first two stops were pre-generate loaders with one explicit unchanged retry each; poor output retained. Third MAIRA produced300tokens withoutEOS and parserAssertionError; failed output never regenerated/repaired. User approved paper A.4 failed-tool observation delivery via3new actual modules from317 onward; original11modules preserved. Current stop is intentional, not a fourth quality-retry. First user-stop file-by-file SFTP capture was intentionally killed locally after4776complete files due overhead, actualnative1; a distinct one-use serial tar stream reused those and downloaded only remaining files, with partials/native records retained. No repeated model request or old R49 private score/download occurred.

The user earlier authorized one420case interim score and a later descriptive Skill audit.435stopped score adapts ALLraw terminal answers before labels, asserts prior420answers/grades unchanged. No complete435same-question Skill-off comparator is claimed.90earlierinjections were OpenI laterality cases; within-source before68/92 and after62/90 is ordered/different-case, not causal. Grounding70bothboxes/16neither/4onebox(3wrong) is preserved.55positive same-model attributions include12wrong, whose numeric reward credit is NEGATIVE. Source anchoring and bigger models are not proven remedies. Costs/Credits/inflight compute/hardware unknown are not0; per-call CNY proxies are not invoices and elapsed sums overlap. Dataset/model original terms/source fields retained. No clinical/Skill-only-causal/closed-test/officialSOTA claim.

New publication-only failures are also retained: first export was invoked before the already-running score finished and was stopped by a missing completion-receipt guard before output. Distinct export002 later stopped at the outgoing-private-path guard: a nested serialized JSON string containing actual poor model text a: plus escaped newline was mistaken for a Windows path. A local outgoing-only semantic-string guard now parses JSON string contents before checking actual leaves;3new checks cover this false positive plus real path and real credential detection. No producer/output/score was repaired. Export003 resumes remaining documents, retains all prior completed public files/asset IDs and originals; no inference/label/score repeat. Inspect diagnosis/original source/failure records in deployment_source/user_stop.

Review new files local_assets/publish_r50_user_stopped.py, experiments/score_r50_stopped_prefix.py, local_assets/stop_r50_and_waiting_deepseek_user_once.py, both user-stop collectors, the report README/RESOURCE_SUMMARY/score/public_reproduction/COPY_MAP/PROVENANCE and relevant actual_CODE/runtime/failed cache/explicit approval/stop controls. The full source and all435case/raw records are in reports/cxr_online_skill_r50_cxr6_20261109. Published full initial protocol is historical; current README/USER_STOP are authoritative. Source copies only outgoing-credential-redacted; actual originals intact. Source is post-execution snapshot, not byte/weight attestation. Root publication allowlist is this R50 report +18owned R50runtime/reporting modules +9owned test sources +one new common stopped scorer +four marker-only indexes, so public imports work in a fresh checkout. Other modified user files/open_questions are excluded. Publisher must protect local/base/main3ab0a927526e0910328b8db2503ac0fdc0e10036, use literal-NUL stage and ordinary push/no force. User waived additional post-push remote verification.

Return concise Markdown with concrete path/trigger/evidence for any blocker. End with ONE standalone JSON object: {"scope_complete":true|false,"audit_scope":["online_feedback_and_Skill_protocol","request_resource_accounting","complete_results_and_claims"],"publication_blockers":[...],"claim_supported":"yes|partial|no","nonblocking_limitations":[...]}. Empty blockers must be a real emptylist. A negative or partial scientific claim is acceptable; only integrity/publication blockers matter. Do not invent tests, clinical truth, model identity attestations or actual costs.
'''
    text(PREP/'RESULT_REVIEW_REQUEST.md', prompt)
    return {'review_request_prepared':True,'actual_review_dispatched':False,
        'scope':'user_stopped_435_completed_prefix_and_interrupted436'}


def accept_review():
    from finalize_r50_report import validate_review
    trace = PREP/'result_review'
    raw, start, exit_record = read(trace/'stdout.json'), read(trace/'started.json'), read(trace/'exit.json')
    assert exit_record['exit_code'] == 0 and start['fresh'] is True and raw.get('is_error') is not True
    assert raw['session_id'] == start['session_id']
    result = raw['result'];decoder = json.JSONDecoder();found = []
    for match in re.finditer(r'\{', result):
        try:value, _ = decoder.raw_decode(result[match.start():])
        except ValueError:continue
        if isinstance(value,dict) and {'scope_complete','audit_scope','publication_blockers','claim_supported'} <= set(value):found.append(value)
    assert found, 'actual_reviewer_typed_verdict_missing'
    verdict = found[-1]
    metadata = dict(verdict, status='completed', native_exit_code=exit_record['exit_code'],
        is_error=bool(raw.get('is_error')), fresh=start['fresh'], session_id=raw['session_id'],
        modelUsage=raw.get('modelUsage'), duration_ms=raw.get('duration_ms'), turns=raw.get('num_turns'),
        usage=raw.get('usage'), CLI_estimated_USD=raw.get('total_cost_usd'), provider_invoice=False,
        review_scope='user_stopped_435_completed_prefix_and_interrupted436',
        independent_weight_identity_attestation=False)
    validate_review(metadata, read(OLD_PREP/'CODE_REVIEW_METADATA.json')['session_id'])
    assert metadata['audit_scope'] == ['online_feedback_and_Skill_protocol','request_resource_accounting','complete_results_and_claims']
    put(REPORT/'RESULT_CLAIM_METADATA.json',metadata)
    put(REPORT/'RESULT_CLAIM_RAW_CLI.json',raw)
    text(REPORT/'RESULT_CLAIM_REVIEW.md',result)
    text(REPORT/'CLAIMS_FROM_RESULTS.md', f"# Claims supported by the stopped archive\n\n435of848planned predictions completed;336correct/435=77.241379%. Remaining413have no final prediction, including interrupted436. No same-question Skill causal effect, clinical capability, closed-test or officialSOTA claim. All original nonzero exits/failures/poor output remain; per-call proxies are not invoices and unknown in-flight/hardware/Credits costs are not0.\n\nFresh native DeepSeek review reports claim_supported={verdict['claim_supported']}; scope_complete={verdict['scope_complete']}; actual publication_blockers={verdict['publication_blockers']}. See raw CLI metadata and full review for limitations.\n")
    path=REPORT/'README.md';body=path.read_text(encoding='utf-8')
    old='An actual fresh DeepSeek review of this incomplete-result scope is required before the publication helper permits staging/push; its native metadata and raw result will be added at report root.'
    assert old in body
    body=body.replace(old,f"An actual fresh DeepSeek review completed for this stopped435-plus-interrupted436scope: native exit0, session`{metadata['session_id']}`, scope_complete=true, publication_blockers=[]. Scientific claim_supported={verdict['claim_supported']}. [Full review](RESULT_CLAIM_REVIEW.md) · [native metadata](RESULT_CLAIM_METADATA.json) · [raw CLI](RESULT_CLAIM_RAW_CLI.json) · [claim limits](CLAIMS_FROM_RESULTS.md). No independent model-weight attestation is claimed.")
    path.write_text(body,encoding='utf-8')
    return {'native_exit':0,'session_id':metadata['session_id'],'scope_complete':True,'publication_blockers':[],
        'claim_supported':verdict['claim_supported'],'review_scope':metadata['review_scope']}


def push():
    plan = read(PREP / 'publication_allowlist.json')
    assert plan['base'] == BASE and read(PREP / 'prepare.completed.json')['status'] == 'completed'
    assert git(['rev-parse','HEAD']).decode().strip() == BASE
    remote = git(['ls-remote','origin','refs/heads/main']).decode().splitlines()
    assert len(remote) == 1 and remote[0].split()[0] == BASE, 'remote_main_changed_stop_no_force'
    assert git(['diff','--cached','--name-only','-z']) == b''
    literal = b''.join(name.encode('utf-8') + b'\0' for name in plan['files'])
    git(['--literal-pathspecs','add','--pathspec-from-file=-','--pathspec-file-nul'], literal)
    staged = {name.decode('utf-8') for name in git(['diff','--cached','--name-only','-z']).split(b'\0') if name}
    assert staged == set(plan['files'])
    git(['commit','-m','Publish user-stopped R50 CXR6 results and complete partial-run evidence'])
    commit = git(['rev-parse','HEAD']).decode().strip()
    assert git(['rev-parse','HEAD^']).decode().strip() == BASE
    native = subprocess.run(['git','push','origin','HEAD:main'],cwd=ROOT,capture_output=True)
    (PREP/'push.native.stdout.log').write_bytes(native.stdout)
    (PREP/'push.native.stderr.log').write_bytes(native.stderr)
    put(PREP/'push.native.exit.json',{'native_exit':native.returncode,'commit':commit})
    if native.returncode:raise RuntimeError('ordinary_push_failed_preserve_commit_no_force:'+native.stderr.decode('utf-8','replace'))
    output = native.stdout.decode('utf-8','replace')
    # User explicitly waived additional post-push remote verification.
    return {'commit': commit, 'successful_normal_push': True, 'stdout': output,
        'post_push_remote_check_performed': False,
        'report_url': 'https://github.com/cw462/MedRAX-reproduction/blob/main/reports/cxr_online_skill_r50_cxr6_20261109/README.md'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['score','export','export002','export003','verify','assemble','assemble002','write','review-request','accept-review','prepare','push'])
    args = parser.parse_args()
    operation = {'score':score,'export':export,'export002':export,'export003':lambda:export(resume=True),'verify':verify,'assemble':assemble,'assemble002':lambda:assemble(resume=True),'write':write_report,'review-request':review_request,'accept-review':accept_review,'prepare':prepare,'push':push}[args.phase]
    print(json.dumps(phase(args.phase, operation), ensure_ascii=False))
