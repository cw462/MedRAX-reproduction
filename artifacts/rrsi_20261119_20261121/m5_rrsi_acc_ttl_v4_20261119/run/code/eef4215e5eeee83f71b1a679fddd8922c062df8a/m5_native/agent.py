"""Question-wise native M5 inference, graph memory, and same-image context."""
import copy
import json
from pathlib import Path

from .context import context, memory_entry
from .executor import Executor
from .memory import Memory, save, utc

SCHEMA = 1

def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def _stream(state_dir):
    stream = _read(Path(state_dir) / 'stream.json')
    if stream['schema'] != SCHEMA:
        raise ValueError('unsupported_native_memory_schema')
    return stream

def initialize(state_dir, services):
    state = Path(state_dir)
    if any(state.iterdir()):
        raise ValueError('initial_memory_must_be_empty')
    memory = Memory(state, services)
    if memory.provider.nodes or memory.provider.edges or memory.provider.active_usage_tracking:
        raise ValueError('initial_memory_is_not_empty')
    memory.persist()
    save(state / 'stream.json', {'schema': SCHEMA, 'completed': [], 'same_image': {}})
    return {'initialized': True, 'initial_memory': 'empty', 'seed_nodes': 0}

def predict(case, state_dir, services):
    state = Path(state_dir)
    stream = _stream(state)
    metadata = services.metadata
    row = copy.deepcopy(metadata['native_row'])
    item = copy.deepcopy(metadata['order_item'])
    ordinal = metadata['ordinal']
    if row['question_id'] != case['id'] or item['question_id'] != case['id']:
        raise ValueError('current_native_case_binding_changed')
    if row['question'] != case['question']:
        raise ValueError('current_question_changed')
    native_options = row.get('options') or {}
    if list(native_options.items()) != [(option['label'], option['text']) for option in case['options']]:
        raise ValueError('current_option_order_changed')
    if row['question_id'] in stream['completed']:
        raise ValueError('current_question_already_observed')
    prior = stream['same_image'].setdefault(item['image_key'], [])
    same_text, same_ids = context(prior, item, ordinal)
    memory = Memory(state, services)
    recalled = memory.retrieve(row)
    sections = [section for section in (same_text, recalled) if section]
    result, calls = Executor(services, state).execute(row, 'r49_unbounded', state,
                                                     '\n\n'.join(sections) or None)
    result.update(question_id=row['question_id'], arm=metadata.get('arm', 'R55-M5'),
                  ordinal=ordinal, prediction_saved_at=utc(), selected_skill_ids=[],
                  same_image_ids=same_ids)
    memory.persist()
    trace = {'prediction': result, 'steps': calls, 'same_image_context': same_text,
             'same_image_ids': same_ids,
             'retrieval': _read(memory.out / 'episodes' / row['question_id'] / 'retrieval.json')}
    pending = {'case_id': case['id'], 'row': row, 'order_item': item,
               'ordinal': ordinal, 'trace': trace}
    save(state / 'pending.json', pending)
    return {'answer': result.get('answer') or '', 'terminal_raw': result.get('terminal_raw'),
            'trace': trace, 'status': result.get('status')}

def observe(case, prediction, feedback, state_dir, services):
    state = Path(state_dir)
    stream = _stream(state)
    pending = _read(state / 'pending.json')
    if pending['case_id'] != case['id'] or pending['trace'] != prediction['trace']:
        raise ValueError('feedback_prediction_binding_changed')
    if case['id'] in stream['completed']:
        raise ValueError('duplicate_native_memory_observation')
    row, item = pending['row'], pending['order_item']
    pred = prediction['trace']['prediction']
    annotation = feedback['reference']
    if not isinstance(annotation, dict):
        annotation = {'answer': annotation}
    event = {'question_id': row['question_id'], 'ordinal': pending['ordinal'],
             'image_key': item['image_key'], 'saved_prediction': copy.deepcopy(pred),
             'reference_annotation': {key: annotation[key] for key in ('answer', 'answer_text') if key in annotation},
             'released_at': utc(), 'timing': 'after_immutable_prediction',
             'provenance': 'dataset_annotation_feedback_not_patient_history'}
    prior = stream['same_image'].setdefault(item['image_key'], [])
    prior.append(memory_entry(row, pred, event))
    native_trace = {'id': row['question_id'], 'row': row, 'prediction': pred,
                    'reward': feedback['correct'], 'steps': prediction['trace']['steps'],
                    'same_image_context': prediction['trace']['same_image_context'],
                    'activated_skill_ids': pred.get('activated_skill_ids', []),
                    'candidate_skill_ids': [], 'feedback_ordinal': pending['ordinal']}
    memory = Memory(state, services)
    memory.ingest(row, native_trace, event)
    memory.persist()
    stream['completed'].append(case['id'])
    save(state / 'stream.json', stream)
    (state / 'pending.json').unlink()
    return {'observed': case['id'],
            'memory_ingest': _read(memory.out / 'episodes' / row['question_id'] / 'ingest.json')}

def migrate(state_dir, services):
    state = Path(state_dir)
    stream = _stream(state)
    graph = _read(state / 'cerebra_fusion_memory/cf_database.json')
    runtime = _read(state / 'memory_runtime.json')
    if not isinstance(graph['nodes'], list) or not isinstance(graph['edges'], list):
        raise ValueError('invalid_native_graph')
    if type(runtime['task_counter']) is not int or not isinstance(runtime['active_usage_tracking'], dict):
        raise ValueError('invalid_native_runtime_state')
    return {'compatible': True, 'schema': stream['schema'], 'completed': len(stream['completed'])}
