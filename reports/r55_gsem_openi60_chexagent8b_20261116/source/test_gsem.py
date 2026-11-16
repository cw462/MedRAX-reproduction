"""Regression checks for the production GSEM retrieval and feedback path."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from gsem_memory import GraphState, Memory, adoption, read


def card(node, procedure, *, conflict='any', quality=.60):
    return {'id': node, 'views': ['lateral'], 'tasks': ['laterality'], 'targets': ['pleura'],
            'conflict': conflict, 'condition': 'lateral image and a pleural laterality choice',
            'procedure': procedure, 'kind': 'indication', 'quality': quality}


def fixture():
    cards = [card('G001', 'Check the pleural orientation and compare candidate findings', quality=.78),
             card('G002', 'Match the supported finding to the option text'),
             card('G003', 'Recheck the available side marker independently')]
    return {'cards': cards, 'views': {'cxr1_a': 'lateral'},
            'vectors': {'G001': [1., 0.], 'G002': [.2, .98], 'G003': [.2, .98]},
            'graph': {'roles': [{'experience': c['id'], 'entity': 'task:laterality'} for c in cards],
                      'edges': [{'left': 'G001', 'right': 'G002', 'weight': .5268},
                                {'left': 'G001', 'right': 'G003', 'weight': .56}]}}


def row(q):
    return {'question_id': q, 'images': ['images/CXR1_a.png'], 'question': 'Which side is the pleural effusion on?',
            'options': {'A': 'Left pleural effusion', 'B': 'Right pleural effusion'}}


class TestGsem(unittest.TestCase):
    def test_next_retrieval_reranks_using_the_live_edge_and_quality(self):
        state = GraphState(fixture())
        f = {'view': 'lateral', 'task': 'laterality', 'targets': ['pleura'], 'conflict': 'unknown'}
        query = 'pleural orientation compare candidate findings'
        before = state.search(f, query, [1., 0.], seed_count=1, max_cards=2)
        self.assertEqual(before['injected'], ['G001', 'G003'])
        changed = state.update(['G001', 'G002'], True)
        after = state.search(f, query, [1., 0.], seed_count=1, max_cards=2)
        self.assertEqual(after['injected'], ['G001', 'G002'])
        self.assertEqual(after['revision'], 1)
        self.assertAlmostEqual(changed['edges'][0]['before'], .5268)
        self.assertAlmostEqual(changed['edges'][0]['after'], .5768)
        next_item = next(x for x in after['traversal'] if x['id'] == 'G002')
        self.assertAlmostEqual(next_item['hops'][0]['edge_weight'], .5768)
        self.assertAlmostEqual(sum(x['credit'] for x in changed['nodes']), 1)
        self.assertGreater(changed['nodes'][0]['credit'], changed['nodes'][1]['credit'])

    def test_inapplicable_view_or_conflict_is_allowed_to_return_zero(self):
        bank = fixture()
        for item in bank['cards']:
            item['conflict'] = 'required'
        state = GraphState(bank)
        f = {'view': 'lateral', 'task': 'laterality', 'targets': ['pleura'], 'conflict': 'unknown'}
        self.assertEqual(state.search(f, 'pleural orientation', [1., 0.])['injected'], [])
        self.assertTrue(state.search(dict(f, conflict='present'), 'pleural orientation', [1., 0.])['injected'])
        self.assertEqual(state.search(dict(f, conflict='present', view='frontal'),
                                      'pleural orientation', [1., 0.])['injected'], [])

    def test_post_prediction_feedback_replay_and_no_credit_for_unoffered_id(self):
        with TemporaryDirectory() as temp:
            path = Path(temp)
            encode = lambda xs: [[1., 0.] for _ in xs]
            mem = Memory(fixture(), path, encode)
            first = row('q1')
            self.assertIn('G001', mem.retrieve(first, prior=None))
            response = ('{"answer":"A", "reason":"Applied G001: checked orientation on the visible side marker; '
                        'Applied G999: ignored fake node"}')
            prediction = {'status': 'completed', 'prediction_saved_at': '2026-11-16T02:01:00+00:00', 'terminal_raw': response}
            trace = {'prediction': prediction, 'reward': 1, 'steps': [{'step_index': 0, 'response':
                     response}]}
            feedback = {'saved_prediction': prediction, 'question_id': 'q1', 'ordinal': 1,
                        'timing': 'after_immutable_prediction', 'released_at': '2026-11-16T02:01:01+00:00'}
            with self.assertRaises(ValueError):
                mem.ingest(first, trace, dict(feedback, released_at='2026-11-16T02:00:59+00:00'))
            self.assertEqual(mem.state.revision, 0)
            mem.ingest(first, trace, feedback)
            receipt = read(path / 'q1' / 'ingest.json')
            self.assertEqual([rule['id'] for rule in receipt['adoption']], ['G001'])
            self.assertEqual(receipt['credited_ids'], read(path / 'q1' / 'retrieval.json')['injected'])
            self.assertNotIn('G999', receipt['credited_ids'])
            mem.retrieve(row('q2'))
            self.assertEqual(read(path / 'q2' / 'retrieval.json')['revision'], 1)
            replay = Memory(fixture(), path, encode)
            replay.retrieve(first)
            replay.ingest(first, trace, feedback)
            self.assertEqual(replay.state.quality, mem.state.quality)
            self.assertEqual(replay.retrieve(row('q2')), mem.retrieve(row('q2')))

    def test_credit_does_not_require_reason_marker_and_stays_on_induced_edges(self):
        state = GraphState(fixture())
        changes = state.update(['G003', 'G002', 'G001'], True)
        self.assertEqual([n['id'] for n in changes['nodes']], ['G003', 'G002', 'G001'])
        self.assertEqual({(e['left'], e['right']) for e in changes['edges']},
                         {('G001', 'G002'), ('G001', 'G003')})
        self.assertAlmostEqual(sum(e['credit'] for e in changes['edges']), 1.0)
        state.update(['G003', 'G002', 'G001'], False)
        self.assertAlmostEqual(state.edges['G001', 'G002'], .5268)

    def test_natural_adoption_requires_delivered_use(self):
        import json

        action = {'calls': [{'tool': 'llava_med_qa', 'args': {}}],
                  'reason': 'Seek independent second opinion to confirm diaphragm elevation side per G017'}
        final = {'answer': 'A', 'reason': 'Checked the side marker, applying G002 orientation check. '
                                          'I did not follow G010. G099 looked relevant.'}
        prediction = {'status': 'completed', 'terminal_raw': json.dumps(final),
                      'observations': [{'tool': 'llava_med_qa', 'status': 'completed'}]}
        steps = [{'step_index': i, 'response': json.dumps(v)} for i, v in enumerate((action, final))]
        trace = {'prediction': prediction, 'steps': steps}
        actual = adoption(trace, {'G002', 'G010', 'G017', 'G099'})
        self.assertEqual([(a['id'], a['evidence']) for a in actual],
                         [('G002', 'saved_answer_reason'), ('G017', 'delivered_tool')])
        prediction['observations'][0]['failure_observation'] = {'failure_reason': 'unavailable'}
        self.assertEqual([a['id'] for a in adoption(trace, {'G002', 'G017'})], ['G002'])


if __name__ == '__main__':
    unittest.main()
