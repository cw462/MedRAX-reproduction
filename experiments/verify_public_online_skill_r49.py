"""Reproduce R49 common-answer scores from public evidence, offline.

Only public files, semantic records and ordinary image links are required.
No provider access, private archive paths or image/file digests are used.
"""
import argparse
import json
import os
from pathlib import Path
from unittest.mock import patch

from cxr_online_primitives_r49 import read
from online_memory_r49 import save_once
from run_online_skill_r49 import ARM
import score_online_skill_r49 as scorer
from score_cxr_author_alignment import adapt


def asset_normalizer(evidence):
    """Resolve each document's image links to one common semantic asset name."""
    assets = []
    for index, item in enumerate(read(evidence/'image_assets.json')):
        target = (evidence/item['path']).resolve()
        if not target.is_relative_to(evidence.resolve()) or not target.is_file():
            raise ValueError('self_contained_public_asset_missing_or_outside_evidence')
        assets.append((target, 'PUBLIC_ASSET:'+str(index)))
    mappings_by_parent = {}
    def normalize(value, document):
        parent = Path(document).parent
        if parent not in mappings_by_parent:
            mappings_by_parent[parent] = sorted(
                [(os.path.relpath(target, parent).replace('\\', '/'), canonical)
                 for target, canonical in assets], key=lambda pair: -len(pair[0]))
        mappings = mappings_by_parent[parent]
        def visit(item):
            if isinstance(item, dict):
                return {key: visit(child) for key, child in item.items()}
            if isinstance(item, list):
                return [visit(child) for child in item]
            if isinstance(item, str):
                for relative, canonical in mappings:
                    item = item.replace(relative, canonical)
            return item
        return visit(value)
    return normalize


def compare_public(result, details, evidence):
    saved = read(evidence/'scores/summary.json'); previous = read(evidence/'scores/per_question.json')
    for key in ('dataset', 'arm', 'questions', 'all_questions_fresh', 'mode', 'arms', 'comparisons',
                'skill_hit_questions', 'same_image_hit_questions', 'windows', 'resources',
                'references_read_after_all_arms_adapted'):
        if saved.get(key) != result.get(key):
            raise ValueError('public_score_or_resource_changed:' + key)
    by_id = {row['question_id']: row for row in previous}
    if len(previous) != len(by_id) or set(by_id) != {row['question_id'] for row in details}:
        raise ValueError('public_scored_question_membership')
    # Archive paths are intentionally portable; answer extraction and all metric
    # decisions must remain identical after that ordinary path transformation.
    ignore = {'archive_call', 'reuse_chain'}
    for row in details:
        before = by_id[row['question_id']]
        for key in ('question_id', 'window', 'skill_hit', 'same_image_hit', 'subset', 'reference'):
            if before.get(key) != row.get(key):
                raise ValueError('public_per_question_semantics_changed:' + key)
        if set(before['arms']) != set(row['arms']):
            raise ValueError('public_per_question_arm_membership')
        for arm, value in row['arms'].items():
            old = before['arms'][arm]
            if {k: v for k, v in old.items() if k not in ignore} != {k: v for k, v in value.items() if k not in ignore}:
                raise ValueError('public_answer_adaptation_changed:' + row['question_id'] + ':' + arm)


def verify(evidence, out):
    evidence, out = Path(evidence).resolve(), Path(out).resolve()
    if out.exists() or out.is_relative_to(evidence) or evidence.is_relative_to(out):
        raise ValueError('new_verification_output_separate_from_evidence_required')
    publication = read(evidence/'publication_manifest.json')
    if (publication.get('schema') != 'r49_semantic_public_evidence_v1'
            or publication.get('scope') != 'complete_scored_online_stream'
            or publication.get('arm') != ARM or publication.get('raw_generation_exit') != 0):
        raise ValueError('full_public_stream_required_not_partial_failure_report')
    dataset = publication['dataset']
    if dataset not in scorer.EXPECTED or publication['questions'] != scorer.EXPECTED[dataset][0]:
        raise ValueError('public_fixed_dataset_denominator')
    for name in publication['files']:
        target = (evidence/name).resolve()
        if not target.is_relative_to(evidence) or not target.is_file():
            raise ValueError('public_declared_file_missing_or_outside_evidence')
    normalize = asset_normalizer(evidence)
    raw_read, raw_rows = scorer.read, scorer.rows
    def public_read(path):
        return normalize(raw_read(path), Path(path))
    def public_rows(path):
        return [normalize(row, Path(path)) for row in raw_rows(path)]

    # Load each historical answer bundle only when the scorer reaches its
    # reference-free adaptation phase. It contains actual raw terminals and
    # saved predictions, not precomputed correctness or reference labels.
    names = set(read(evidence/'scores/summary.json')['comparisons'])
    baseline_name = scorer.EXPECTED[dataset][1]
    if names not in ({baseline_name}, {baseline_name, 'R47_online_GT'}):
        raise ValueError('fixed_public_historical_comparators')
    def adapted_bundle(inputs, name):
        bundle = public_read(evidence/'comparison_sources.json')
        if set(bundle) != names:
            raise ValueError('public_historical_bundle_arm_membership')
        values = bundle[name]
        if set(values) != {row['question_id'] for row in inputs}:
            raise ValueError('public_historical_bundle_question_membership')
        return {row['question_id']: adapt(row, values[row['question_id']]['prediction'], values[row['question_id']]['source'])
                for row in inputs}
    def baseline_adapter(inputs, ds, name):
        if ds != dataset or name != baseline_name:
            raise ValueError('public_historical_baseline_identity')
        return adapted_bundle(inputs, name)
    def r47_adapter(inputs, baseline, frozen_path, run):
        return adapted_bundle(inputs, 'R47_online_GT')

    # Scoped read adapters normalize paths, not answers, labels or model
    # outputs. No execution module or historical record is modified.
    with patch.object(scorer, 'read', side_effect=public_read), \
            patch.object(scorer, 'rows', side_effect=public_rows), \
            patch.object(scorer, 'adapt_historical', side_effect=baseline_adapter), \
            patch.object(scorer, 'adapt_r47', side_effect=r47_adapter):
        secondary = 'R47_online_GT' in names
        result, details = scorer.score(evidence, evidence, evidence/'references.jsonl', dataset,
                           r47_frozen=evidence/'comparison_sources.json' if secondary else None,
                           r47_run=evidence if secondary else None)
    for qid in {row['question_id'] for row in details}:
        event = read(evidence/'feedback'/(qid+'.json')); vault = read(evidence/'reference_vault'/(qid+'.json'))
        annotation = {key: vault[key] for key in ('answer', 'answer_text') if key in vault}
        if vault.get('question_id') != qid or annotation != event['reference_annotation']:
            raise ValueError('public_actual_vault_feedback_changed')
    compare_public(result, details, evidence)
    registered = result['resources']['tools'].get('registered_cuda_failed_attempts', 0)
    if (bool(publication.get('registered_cuda_tool_retry')) != bool(registered)
            or bool(publication.get('original_failed_cache_and_selection_retained')) != bool(registered)
            or publication.get('diagnostic_output_used_as_production_result') is not False):
        raise ValueError('public_registered_historical_attempt_disclosure_changed')
    if (bool(publication.get('registered_meta_schema_repair')) != bool(result['resources']['meta_schema_repair']['registered'])
            or bool(publication.get('registered_meta_schema_repair_2')) != bool(result['resources']['meta_schema_repair_2']['registered'])
            or bool(publication.get('ordinary_mutation_fields_amendment')) != bool(result['resources']['mutation_fields_amendment']['active'])
            or publication.get('automatic_invalid_META_to_NONE') is not False):
        raise ValueError('public_exact_META_schema_repair_disclosure_changed')
    embedding_recovery = result['resources']['embedding_http_recovery']
    if (bool(publication.get('registered_embedding_http_failure')) != bool(embedding_recovery['registered'])
            or bool(publication.get('original_embedding_specific_body_unknown')) != bool(embedding_recovery['original_specific_body_unknown'])
            or publication.get('original_embedding_error_body_reconstructed_from_diagnostic') is not False):
        raise ValueError('public_exact_embedding_HTTP_failure_disclosure_changed')
    if (bool(publication.get('registered_phrase_guard_retry')) != bool(result['resources']['phrase_guard_retry']['registered'])
            or bool(publication.get('declared_phrase_generation_policy_amendment')) != bool(result['resources']['phrase_guard_amendment']['active'])
            or publication.get('same_MAIRA_generation_settings_claim') is not False
            or publication.get('phrase_diagnostic_output_reused_in_R49') is not False):
        raise ValueError('public_phrase_guard_policy_amendment_disclosure_changed')
    if (bool(publication.get('registered_assessment_adoption_repair')) != bool(result['resources']['adoption_repair']['registered'])
            or bool(publication.get('analysis_unique_adoption_amendment')) != bool(result['resources']['analysis_unique_amendment']['active'])
            or publication.get('original_analysis_changed_for_mutation') is not False
            or publication.get('automatic_future_adoption_repair') is not False
            or publication.get('invalid_adoption_silently_ignored') is not False):
        raise ValueError('public_assess_only_adoption_provenance_disclosure_changed')
    result.update(scope='Public common-answer score reproduction and semantic evidence consistency only.',
                  matches_published_primary_scores_and_extractions=True,
                  matches_published_resources=True,
                  private_run_paths_required=False, image_or_file_digests_checked=False,
                  new_inference_calls=0, clinical_or_causal_verification=False)
    save_once(out/'summary.json', result); save_once(out/'per_question.json', details)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.evidence, args.out), ensure_ascii=False))
