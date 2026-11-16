"""Case-conditioned graph memory for the matched R55 OpenI pilot."""

from collections import Counter, defaultdict
from itertools import combinations
import json
import math
from pathlib import Path
import re


ARM = 'R55-M14-GSEM'
NODE_LEARNING_RATE = .10
EDGE_LEARNING_RATE = .05
RANK_DECAY = .80
WORD = re.compile(r'[a-z][a-z0-9]+')
TARGETS = {
    'pleura': r'pleur\w*|effusion|pneumothorax|hydrothorax|costophrenic',
    'diaphragm': r'(?:hemi)?diaphragm\w*|subpulmonic|gastric bubble|eventration',
    'lung_opacity': r'opacity|opacities|atelecta\w+|infiltrat\w*|consolidat\w*|pneumonia|edema|airspace',
    'nodule': r'nodul\w*|mass(?:es)?|granuloma\w*|calcif\w*',
    'heart_mediastinum': r'cardio\w*|heart|aort\w*|mediastin\w*|vascular|hilum|hilar',
    'bone': r'rib\w*|fractur\w*|scolio\w*|clavicl\w*|vertebr\w*|spine|osseous|skeletal',
    'device': r'cath\w*|pacemaker|tube\w*|lead\w*|stent|clip\w*|hardware|wire\w*',
    'lung_volume': r'hyperinflat\w*|emphysema|copd|volume loss|low volumes?',
}
VIEWS = {'frontal', 'lateral', 'mixed', 'unknown'}
TASKS = {'laterality', 'localization', 'finding', 'device'}
CONFLICTS = {'present', 'unknown'}
SIDES = re.compile(r'\b(left|right)\b', re.I)
CONFLICT = re.compile(r'\b(disagree(?:s|d|ment)?|discordan\w*|conflict(?:s|ing)?|contradict\w*)\b', re.I)
STOP = set('a an the this these of in to if and or on is are as for which what when with chest x ray'.split())


def read(path):
    return json.loads(Path(path).read_bytes())


def record(path, value):
    """Commit a new receipt atomically and check exact equality during replay."""
    path = Path(path)
    if path.exists():
        if read(path) != value:
            raise ValueError(f'replayed GSEM receipt differs: {path.name}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def words(text):
    return [w for w in WORD.findall(text.lower()) if w not in STOP]


def image_name(path):
    return Path(path.replace('\\', '/')).stem.lower()


def features(row, views, prior=''):
    question = row['question']
    options = list(row.get('options', {}).values())
    text = ' '.join([question, *options])
    s = text.lower()
    sides = {side.lower() for side in SIDES.findall(text)}
    targets = sorted(name for name, pattern in TARGETS.items() if re.search(r'\b(?:' + pattern + r')\b', s))
    if len(sides) == 2 or re.search(r'which side|laterality|left or right|right or left', s):
        task = 'laterality'
    elif re.search(r'\b(?:where|which (?:lobe|zone|part|region|lung|hemithorax)|locat\w*)\b', question.lower()):
        task = 'localization'
    else:
        task = 'device' if targets == ['device'] else 'finding'
    present = {views.get(image_name(path), 'unknown') for path in row['images']}
    known_view = next(iter(present)) if len(present) == 1 else 'mixed'
    return {'view': known_view, 'task': task, 'targets': targets,
            'conflict': 'present' if CONFLICT.search(question + '\n' + (prior or '')) else 'unknown'}


def query_text(row, f):
    return ' '.join([f['view'], f['task'], *[t.replace('_', ' ') for t in f['targets']],
                     'evidence conflict' if f['conflict'] == 'present' else '',
                     row['question'], *row.get('options', {}).values()])


def card_text(card):
    return ' '.join([*card['views'], *card['tasks'], *[t.replace('_', ' ') for t in card['targets']],
                     card['condition'], card['procedure']])


def eligible(card, f):
    return ((not card['views'] or f['view'] in card['views'])
            and f['task'] in card['tasks']
            and (not card['targets'] or bool(set(card['targets']).intersection(f['targets'])))
            and (card['conflict'] == 'any' or f['conflict'] == 'present'))


def entity_keys(card):
    return ([f'view:{x}' for x in card['views']] + [f'task:{x}' for x in card['tasks']]
            + [f'target:{x}' for x in card['targets']] + [f'conflict:{card["conflict"]}'])


def cosine(left, right):
    denom = math.sqrt(sum(v * v for v in left) * sum(v * v for v in right))
    return sum(a * b for a, b in zip(left, right, strict=True)) / denom if denom else 0.0


class BM25:
    def __init__(self, docs):
        self.docs = {key: Counter(words(text)) for key, text in docs.items()}
        self.sizes = {key: doc.total() for key, doc in self.docs.items()}
        self.average = sum(self.sizes.values()) / max(1, len(docs)) or 1.0
        freq = Counter(word for doc in self.docs.values() for word in doc)
        self.idf = {w: math.log1p((len(docs) - n + .5) / (n + .5)) for w, n in freq.items()}

    def score(self, key, tokens):
        doc = self.docs[key]
        norm = 1.5 * (.25 + .75 * self.sizes[key] / self.average)
        return sum(self.idf[w] * 2.5 * doc[w] / (doc[w] + norm) for w in tokens if w in doc)


def build_graph(cards, vectors):
    """Typed intra-experience roles and inter-experience compatibility edges."""
    roles = []
    for card in cards:
        roles.extend([{'experience': card['id'], 'entity': k, 'role': 'requires'} for k in entity_keys(card)])
        roles.append({'experience': card['id'], 'entity': card['id'] + ':procedure',
                      'role': 'recommend' if card['kind'] == 'indication' else 'avoid'})
    edges = []
    for a, b in combinations(cards, 2):
        if not set(a['tasks']).intersection(b['tasks']):
            continue
        if a['views'] and b['views'] and not set(a['views']).intersection(b['views']):
            continue
        if a['targets'] and b['targets'] and not set(a['targets']).intersection(b['targets']):
            continue
        ia, ib = a['id'], b['id']
        lex_a, lex_b = set(words(card_text(a))), set(words(card_text(b)))
        overlap = len(lex_a & lex_b) / max(1, len(lex_a | lex_b))
        semantic = max(0.0, cosine(vectors[ia], vectors[ib]))
        weight = .25 + .45 * semantic + .30 * overlap
        if weight >= .42:
            edges.append({'left': ia, 'right': ib, 'weight': round(weight, 8)})
    return {'roles': roles, 'edges': edges}


class GraphState:
    """The same mutable qualities and edge weights are used by every traversal."""

    def __init__(self, bank):
        self.cards = {c['id']: c for c in bank['cards']}
        self.vectors = bank['vectors']
        if set(self.vectors) != set(self.cards) or any(not all(map(math.isfinite, v)) or not v
                                                      for v in self.vectors.values()):
            raise ValueError('invalid GSEM vector membership or values')
        self.quality = {i: c['quality'] for i, c in self.cards.items()}
        self.edges = {}
        self.adj = defaultdict(set)
        self.roles = defaultdict(set)
        for role in bank['graph']['roles']:
            self.roles[role['entity']].add(role['experience'])
        for e in bank['graph']['edges']:
            self.set_edge(e['left'], e['right'], e['weight'])
        self.initial_weights = dict(self.edges)
        self.corrections = dict.fromkeys(self.edges, 0.0)
        self.bm25 = BM25({key: card_text(card) for key, card in self.cards.items()})
        self.revision = 0

    def set_edge(self, a, b, weight):
        self.edges[tuple(sorted((a, b)))] = weight
        self.adj[a].add(b)
        self.adj[b].add(a)

    def neighbors(self, key, allowed):
        result = []
        for node in self.adj[key] & allowed:
            weight = self.edges[tuple(sorted((key, node)))]
            result.append((node, (weight + self.quality[node]) / 2, weight))
        return sorted(result, key=lambda item: (-item[1], item[0]))

    def search(self, f, query, vector, *, seed_count=3, max_cards=3, min_seed=.32):
        possible = self.roles['task:' + f['task']]
        allowed = {node for node in possible if eligible(self.cards[node], f) and self.quality[node] >= .25}
        tokens = sorted(set(words(query)))
        lexical = {node: self.bm25.score(node, tokens) for node in allowed}
        best_lex = max(lexical.values(), default=0)
        hits = []
        for node in sorted(allowed):
            semantic = max(0.0, cosine(vector, self.vectors[node]))
            bm25 = lexical[node] / best_lex if best_lex else 0.0
            score = .60 * semantic + .30 * bm25 + .10 * self.quality[node]
            hits.append({'id': node, 'score': score, 'semantic': semantic, 'bm25': lexical[node],
                         'quality': self.quality[node]})
        hits.sort(key=lambda h: (-h['score'], h['id']))
        seeds = [h for h in hits if h['score'] >= min_seed and (h['semantic'] >= .22 or h['bm25'] >= 1.0)][:seed_count]
        routes = {}
        semantic = {h['id']: h['semantic'] for h in hits}
        for seed in seeds:
            start = (seed['id'],)
            frontier = [(start, seed['score'], [])]
            for _ in range(3):
                next_frontier = []
                for path, score, hops in frontier:
                    node = path[-1]
                    prev = routes.get(node)
                    if prev is None or score > prev['score']:
                        routes[node] = {'id': node, 'score': score, 'path': list(path), 'hops': hops}
                    for neighbor, weight, real_edge in self.neighbors(node, allowed - set(path))[:4]:
                        if weight >= .36 and semantic[neighbor] >= .16:
                            next_frontier.append((path + (neighbor,), .55 * score + .45 * weight - .04,
                                                  [*hops, {'edge_weight': real_edge, 'neighbor_score': weight}]))
                frontier = next_frontier
        ranked = sorted(routes.values(), key=lambda x: (-x['score'], x['id']))
        # Preserve a supporting path when selecting a graph-expanded experience.
        chosen = []
        for entry in ranked:
            missing = [node for node in entry['path'] if node not in chosen]
            if len(chosen) + len(missing) <= max_cards:
                chosen.extend(missing)
        return {'revision': self.revision, 'recall': hits, 'seeds': [h['id'] for h in seeds],
                'traversal': ranked, 'injected': chosen}

    def update(self, activated, reward):
        changes = {'nodes': [], 'edges': []}
        delta = 1 if reward else -1
        rank_weights = [RANK_DECAY ** rank for rank in range(len(activated))]
        total = sum(rank_weights)
        credits = {node: weight / total for node, weight in zip(activated, rank_weights, strict=True)}
        for node in activated:
            old = self.quality[node]
            credit = credits[node]
            new = min(1, max(0, old + NODE_LEARNING_RATE * credit * delta))
            self.quality[node] = new
            changes['nodes'].append({'id': node, 'credit': credit, 'before': old, 'after': new})
        joint = {(a, b): credits[a] * credits[b] for a, b in combinations(sorted(activated), 2)
                 if (a, b) in self.edges}
        joint_mass = sum(joint.values())
        for (a, b), product in joint.items():
            key = (a, b)
            old = self.edges[key]
            credit = product / joint_mass
            before_correction = self.corrections[key]
            after_correction = before_correction + EDGE_LEARNING_RATE * credit * delta
            self.corrections[key] = after_correction
            new = min(1, max(0, self.initial_weights[key] + after_correction))
            self.set_edge(a, b, new)
            changes['edges'].append({'left': a, 'right': b, 'credit': credit, 'before': old, 'after': new,
                                     'correction_before': before_correction, 'correction_after': after_correction})
        if activated:
            self.revision += 1
        return changes


ADOPTION = re.compile(
    r'\b(?:appl(?:ied|ying)|us(?:ed|ing)|follow(?:ed|ing)|per|according to|in line with|as (?:advised|required|recommended) by)'
    r'\s+(?:(?:the\s+)?(?:rule|experience|procedure)\s+)?\[?(G\d{3,4})\b\]?', re.I)
PROCEDURE = re.compile(r'\b(?:check\w*|inspect\w*|verify|verif\w+|confirm\w*|compar\w+|resolv\w+|'
                       r'mapp?\w*|align\w*|orient\w*|review\w*|crosso?\w*|avoid\w*|disambiguat\w+|'
                       r'concordan\w*|discordan\w*|match\w*|excluded?|prioriti[sz]\w+)\b', re.I)
DECLINED = re.compile(r"\b(?:not|never|without|cannot|didn't|don't|did not|could not)\s+(?:actually\s+)?$", re.I)


def adoption(trace, allowed):
    """Bind a natural-language adoption declaration to a delivered decision."""
    found = {}
    prediction = trace['prediction']
    observations = prediction.get('observations', [])
    cursor = 0
    for step in trace['steps']:
        raw = step['response'].strip()
        if raw.startswith('```') and raw.endswith('```') and '\n' in raw:
            raw = raw.split('\n', 1)[1].rsplit('```', 1)[0].strip()
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict) or not isinstance(obj.get('reason'), str):
            continue
        reason = obj['reason']
        calls = obj.get('calls')
        observed = []
        if isinstance(calls, list):
            for action in calls:
                if (cursor == len(observations) or not isinstance(action, dict)
                        or observations[cursor].get('tool') != action.get('tool')):
                    break
                observation = observations[cursor]
                cursor += 1
                if observation.get('status') == 'completed' and not observation.get('failure_observation'):
                    observed.append(observation['tool'])
        final = (prediction['status'] == 'completed' and bool(obj.get('answer'))
                 and step['response'] == prediction.get('terminal_raw'))
        if not (observed or final) or not PROCEDURE.search(reason):
            continue
        for match in ADOPTION.finditer(reason):
            node = match[1].upper()
            if node in allowed and not DECLINED.search(reason[:match.start()]):
                found[node] = {'id': node, 'step': step['step_index'], 'reason': reason[:450],
                               'evidence': 'delivered_tool' if observed else 'saved_answer_reason',
                               'observed_tools': observed}
    return [found[node] for node in sorted(found)]


class Memory:
    def __init__(self, bank, out, encode):
        self.state = GraphState(bank)
        self.out = Path(out)
        self.encode = encode
        self.views = bank['views']

    def retrieve(self, row, *, prior=''):
        q = row['question_id']
        path = self.out / q / 'retrieval.json'
        f = features(row, self.views, prior)
        query = query_text(row, f)
        if path.exists():
            event = read(path)
            if (event['features'], event['query'], event['revision']) != (f, query, self.state.revision):
                raise ValueError('saved GSEM retrieval does not match replayed state')
            return event['text']
        result = self.state.search(f, query, self.encode([query])[0])
        selected = []
        for node in result['injected']:
            card = self.state.cards[node]
            verb = 'Consider' if card['kind'] == 'indication' else 'Avoid'
            selected.append(f"[{node}] If {card['condition']}, {verb.lower()} this decision procedure: {card['procedure']}")
        text = ''
        if selected:
            text = ('Optional procedural experience from other cases. Use a rule only if its condition is met in the current image '
                    'and evidence. Verify independently. Preserve the required action/final JSON. In its existing reason string, '
                    'when you actually apply a rule, write "Applied Gnnn: <what you did>". Do not list unused IDs.\n'
                    + '\n'.join(selected))
        record(path, dict(result, features=f, query=query, text=text))
        return text

    def ingest(self, row, trace, feedback):
        pred = trace['prediction']
        if (feedback['saved_prediction'] != pred or feedback['question_id'] != row['question_id']
                or feedback['timing'] != 'after_immutable_prediction'
                or feedback['released_at'] < pred['prediction_saved_at']):
            raise ValueError('GSEM update requires feedback for the saved prediction')
        folder = self.out / row['question_id']
        retrieval = read(folder / 'retrieval.json')
        before = self.state.revision
        if before != retrieval['revision']:
            raise ValueError('GSEM update is out of sequence')
        activated = retrieval['injected']
        adopted = adoption(trace, set(activated))
        outcome = self.state.update(activated, bool(trace['reward']))
        record(folder / 'ingest.json', {'ordinal': feedback['ordinal'], 'reward': int(trace['reward']),
                                       'prediction_saved_at': pred['prediction_saved_at'],
                                       'feedback_released_at': feedback['released_at'], 'adoption': adopted,
                                       'credited_ids': activated, 'credit_rule': 'ranked_prompted_experiences',
                                       'revision_before': before,
                                       'revision_after': self.state.revision, **outcome})
