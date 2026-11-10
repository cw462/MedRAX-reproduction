"""Derive R47 from frozen R45 and split raw annotations into a callback-only vault."""
import argparse
import copy
import json
from pathlib import Path

from cxr_image_memory_gt_r47 import SCHEMA, read, rows, safe_qid, save_once, validate_frozen


def prepare(r45_frozen, references, out, reference_dir=None):
    frozen = read(r45_frozen)
    ids = validate_frozen(frozen, require_reference_manifest=False)
    if frozen['schema'] != 'M43_same_image_memory_r45_20261108':
        raise ValueError('original_R45_frozen_required')
    raw = rows(references)
    if len(raw) != 618 or len({row['question_id'] for row in raw}) != 618 or {row['question_id'] for row in raw} != set(ids):
        raise ValueError('reference_cohort_mismatch')
    for row in raw:
        safe_qid(row['question_id'])
        if not isinstance(row.get('answer'), str) or not row['answer'].strip():
            raise ValueError('invalid_reference_answer')
        if 'answer_text' in row and not isinstance(row['answer_text'], str):
            raise ValueError('invalid_reference_answer_text')
    out = Path(out)
    # Raw full records remain separate from the label-free frozen manifest.
    vault = out / 'reference_vault'
    manifest = {}
    for row in raw:
        name = row['question_id'] + '.json'
        save_once(vault / name, row)
        manifest[row['question_id']] = {'file': name}
    result = copy.deepcopy(frozen)
    # R45's historical byte-validation metadata is unnecessary in the new arm.
    result.pop('inputs_sha256', None)
    result.pop('source_hashes', None)
    result.update(
        schema=SCHEMA, reference_files=manifest,
        reference_dir=str(reference_dir) if reference_dir is not None else str(vault.resolve()),
        reference_read='preparation_only_split_to_per_question_files',
        feedback_protocol='each_reference_loaded_only_after_its_immutable_prediction_save',
        run_scope='One sequential same-image dataset-feedback arm; 488 fixed M43 reuses and 130 fresh episodes. No new no-feedback arm.',
    )
    validate_frozen(result)
    save_once(out / 'frozen.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    for key in ('r45-frozen', 'references', 'out'):
        parser.add_argument('--' + key, type=Path, required=True)
    parser.add_argument('--reference-dir', help='Runtime vault location; files are prepared under OUT/reference_vault.')
    args = parser.parse_args(argv)
    prepare(args.r45_frozen, args.references, args.out, args.reference_dir)
    print(json.dumps({'questions': 618, 'image_groups': 488, 'fresh_episodes': 130,
                      'reused_M43': 488, 'feedback_events_required': 618,
                      'prepared': str(args.out / 'frozen.json')}))


if __name__ == '__main__':
    main()
