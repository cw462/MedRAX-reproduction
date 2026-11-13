"""R49 semantic identities and healthy memory, without byte/pixel validation."""
import copy
import json
from pathlib import Path, PurePosixPath

from cxr_image_memory_r44 import tool_failure_reason


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def digest(value):
    """Semantic comparison key, not a file/code/pixel checksum or path name."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def schedule(inputs, data=None, historical_order=None):
    """Reuse declared historical groups or canonical IDs/ordered relative paths."""
    ids = [row['question_id'] for row in inputs]
    if historical_order is not None:
        if isinstance(historical_order, dict):
            historical_order = historical_order['order']
        if [item['question_id'] for item in historical_order] != ids:
            raise ValueError('historical_order_ids_changed')
        seen, result, aliases = {}, [], {}
        for item in historical_order:
            raw = item['image_key']
            key = aliases.setdefault(raw, 'original_group_' + str(len(aliases) + 1))
            prior = seen.setdefault(key, [])
            if item['previous_ids'] != prior:
                raise ValueError('invalid_historical_processed_prefix')
            result.append({'question_id': item['question_id'], 'image_key': key, 'previous_ids': list(prior)})
            prior.append(item['question_id'])
        return result
    seen, bindings, result = {}, {}, []
    for row in inputs:
        images = []
        for name in row['images']:
            path = PurePosixPath(name.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or ':' in str(path):
                raise ValueError('image_outside_root')
            images.append(str(path))
        if not images:
            raise ValueError('no_original_images')
        key = digest(['image_id', row['image_id']] if row.get('image_id') is not None else ['relative_paths', images])
        if key in bindings and bindings[key] != images:
            raise ValueError('canonical_image_identity_path_conflict')
        bindings[key] = images
        prior = seen.setdefault(key, [])
        result.append({'question_id': row['question_id'], 'image_key': key, 'previous_ids': list(prior)})
        prior.append(row['question_id'])
    return result


def memory_entry(row, result):
    observations = result.get('observations') or result.get('inherited_observations') or []
    evidence = [{key: copy.deepcopy(value[key]) for key in ('tool', 'image_index', 'observation') if key in value}
                for value in observations if tool_failure_reason(value) is None]
    return {'question_id': row['question_id'], 'question': row['question'], 'options': row.get('options', {}),
            'previous_answer': result.get('answer'), 'previous_model_reason': result.get('reason'),
            'previous_status': result.get('status'), 'tool_evidence': evidence,
            'provenance': 'earlier_model_output_not_ground_truth'}


def assert_closed_sends(root, *, require_receipts=False):
    root = Path(root)
    from r55_continue60_policy import accounted_empty_verify
    from r55_full848_verify_recovery import accounted_verify_failure
    import os
    from r55_full848_e_slake_main_recovery import accounted_main_failure
    for path in (root / 'services' / 'calls').glob('*/*/*/started.json'):
        if accounted_main_failure(root, path.parent, require_receipts,
                                  offline_original=os.getenv('R55_SLAKE_RETRY_OFFLINE') == '1'):
            continue
        if (accounted_empty_verify(path.parent, require_receipts)
                or accounted_verify_failure(path.parent, require_receipts)):
            continue
        if not (path.parent / 'response.json').is_file():
            raise RuntimeError('unknown_sent_no_reissue:' + str(path.parent.relative_to(root)))
        result = path.parent / 'result.json'
        if (require_receipts and not result.is_file()) or (result.is_file() and
                (read(result).get('error') or read(result).get('response_received') is not True)):
            raise RuntimeError('unclosed_request_receipt:' + str(path.parent.relative_to(root)))
    for path in (root / 'services' / 'embeddings').glob('*/started.json'):
        if not (path.parent / 'response.json').is_file():
            raise RuntimeError('unknown_embedding_send_no_retry')
