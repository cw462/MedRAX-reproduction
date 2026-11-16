"""Connect GSEM to the frozen R55 no-Skill generation and scoring entry points."""

from collections import Counter
import os
from pathlib import Path
import sys

from gsem_memory import ARM, EDGE_LEARNING_RATE, NODE_LEARNING_RATE, RANK_DECAY, Memory, build_graph, card_text, read, record


MODEL_DIR = 'sentence-transformers_all-MiniLM-L6-v2'


def load_encoder(runtime):
    sys.path[:0] = [str(runtime / 'deps'), str(runtime)]
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(str(runtime / 'models' / MODEL_DIR), device='cpu')

    def encode(texts):
        return model.encode(texts, normalize_embeddings=True, show_progress_bar=False).tolist()

    return encode


def initialize(run, encode):
    seed = read(run / 'accepted.private.json')
    path = run / 'initial_graph.json'
    if path.exists():
        bank = read(path)
        if any(bank[k] != seed[k] for k in ('cards', 'views')):
            raise ValueError('seed bank changed after graph initialization')
        return bank
    cards = seed['cards']
    ids = [c['id'] for c in cards]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate GSEM card id')
    vectors = dict(zip(ids, encode([card_text(c) for c in cards]), strict=True))
    bank = dict(seed, vectors=vectors, graph=build_graph(cards, vectors), embedding_model=MODEL_DIR)
    record(path, bank)
    return bank


def run_pilot(root, data, refs, runtime):
    from online_memory_r49 import ReferenceVault
    from run_cxr_vqa_toolsets import exclusive_lock
    import run_online_skill_r54 as engine
    from autodl_services import Services

    generation = root / 'generation'
    main_key = sys.stdin.readline().strip()
    if not main_key:
        raise ValueError('missing established Token Plan credential')
    manifest = read(generation / 'manifest.json')
    if manifest['arm'] != ARM or len(manifest['inputs']) != 60 or manifest['skill_enabled'] is not False:
        raise ValueError('unmatched formal R55 OpenI pilot')
    engine.ARM = ARM
    with exclusive_lock(generation / '.online.lock'):
        encode = load_encoder(runtime)
        bank = initialize(root, encode)
        memory = Memory(bank, generation / 'external_memory' / 'episodes', encode)
        print(f"Initial graph ready: {len(bank['cards'])} experience nodes, {len(bank['graph']['edges'])} edges", flush=True)
        service = Services(manifest['config'], manifest['protocol'], manifest['runtime'], generation / 'services',
                           main_key, manifest['embedding_model'], manifest['embedding_base_url'])
        engine.run_stream(manifest['inputs'], manifest['order'], data, generation, service,
                          ReferenceVault(refs, manifest['reference_files']), manifest['runtime']['arms']['M']['tools'],
                          evolver=engine.disabled_evolve, external_memory=memory)
        scores(root, bank)


def scores(root, bank):
    from cxr_author_alignment import choice, extract
    from cxr_online_primitives_r49 import tool_failure_reason

    gen = root / 'generation'
    manifest = read(gen / 'manifest.json')
    complete = read(gen / 'complete.json')
    ids = [r['question_id'] for r in manifest['inputs']]
    pointers = {p.stem: p for p in (gen / 'windows').glob('*/trajectories/*.json')}
    episodes = gen / 'external_memory' / 'episodes'
    if complete['arm'] != ARM or complete['questions'] != len(ids) or set(ids) != set(pointers):
        raise ValueError('incomplete formal predictions')
    if any({p.parent.name for p in episodes.glob('*/' + artifact)} != set(ids)
           for artifact in ('retrieval.json', 'ingest.json')):
        raise ValueError('incomplete formal graph receipts')
    details = []
    revision = 0
    for row in manifest['inputs']:
        q = row['question_id']
        trace = read(pointers[q])
        pred = read(gen / 'predictions' / ARM / (q + '.json'))
        feedback = read(gen / 'feedback' / (q + '.json'))
        ctx = read(gen / 'contexts' / (q + '.json'))
        retrieval = read(episodes / q / 'retrieval.json')
        update = read(episodes / q / 'ingest.json')
        if (trace['row'] != row or trace['prediction'] != pred or feedback['saved_prediction'] != pred
                or trace['injected'] or trace['activated_skill_ids'] or ctx['selected_skills']):
            raise ValueError('inconsistent no-Skill prediction artifacts')
        ref = feedback['reference_annotation']['answer']
        raw = extract(pred.get('terminal_raw'), q, row['options']).answer
        chosen = choice(raw, row['options']) if raw is not None else None
        correct = chosen == ref
        if (correct != bool(trace['reward']) or correct != bool(update['reward']) or trace['source_label'] != ref
                or update['revision_before'] != revision or retrieval['revision'] != revision
                or update['feedback_released_at'] != feedback['released_at']
                or feedback['released_at'] < pred['prediction_saved_at']):
            raise ValueError('inconsistent scoring or online update sequence')
        revision = update['revision_after']
        details.append({'ordinal': pred['ordinal'], 'question_id': q, 'question': row['question'],
                        'options': row['options'], 'images': row['images'], 'reference': ref,
                        'explicit_answer': raw, 'choice': chosen, 'correct': correct, 'reason': pred['reason'],
                        'status': pred['status'], 'same_image_ids': ctx['same_image_ids'],
                        'main_calls': pred['main_calls'], 'tool_calls': pred['tool_calls'],
                        'failed_tools': sum(bool(tool_failure_reason(o)) for o in pred['observations']),
                        'tools': dict(Counter(o['tool'] for o in pred['observations'])),
                        'retrieval': retrieval, 'update': update})
    usage = Counter()
    for path in sorted((gen / 'services' / 'calls').glob('*/*/*/result.json')):
        result = read(path)
        kind = path.relative_to(gen / 'services' / 'calls').parts[0]
        usage[kind + '_requests'] += 1
        usage[kind + '_responded'] += int(bool(result.get('response_received')))
        for field in ('prompt_tokens', 'completion_tokens'):
            val = (result.get('usage') or {}).get(field)
            if isinstance(val, int):
                usage[kind + '_' + field] += val
    n = len(details)
    summary = {'arm': ARM, 'questions': n, 'correct': sum(row['correct'] for row in details),
               'initial_cards': len(bank['cards']), 'initial_edges': len(bank['graph']['edges']),
               'injected_questions': sum(bool(x['retrieval']['injected']) for x in details),
               'zero_injected_questions': sum(not x['retrieval']['injected'] for x in details),
               'updated_questions': revision, 'adopted_questions': sum(bool(x['update']['adoption']) for x in details),
               'node_updates': sum(len(x['update']['nodes']) for x in details),
               'edge_updates': sum(len(x['update']['edges']) for x in details),
               'credit': {'activation': 'ranked_experiences_delivered_in_answer_prompt', 'rank_decay': RANK_DECAY,
                          'node_learning_rate': NODE_LEARNING_RATE, 'edge_learning_rate': EDGE_LEARNING_RATE,
                          'edge_activation': 'induced_edges_of_activated_experiences'},
               'main_calls': sum(x['main_calls'] for x in details),
               'tool_calls': sum(x['tool_calls'] for x in details),
               'tool_failures': sum(x['failed_tools'] for x in details), 'recorded_usage': dict(usage)}
    record(root / 'per_question.json', details)
    record(root / 'score.json', summary)
    print(f"Formal score: {summary['correct']}/{summary['questions']}", flush=True)


if __name__ == '__main__':
    root, data, refs, runtime = map(Path, sys.argv[1:])
    sys.path.insert(0, str(root / 'code/experiments'))
    run_pilot(root, data, refs, runtime)
