import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
from pydantic import BaseModel

from official_gain.evidence_agent import ToolSession, normalize_action, run_p
from official_gain.runtime import read, write


class ExpertArgs(BaseModel):
    image_paths: list[str]
    prompt: str


class GroundArgs(BaseModel):
    image_path: str
    phrase: str


class OrgansArgs(BaseModel):
    image_path: str
    organs: list[str]


class SavedResponseClient:
    """No provider client or network: execute the controller around fixed replies."""
    def __init__(self, plan):
        self.replies = [json.dumps(plan), 'Visible margins remain uncertain.', 'Answer: B']
        self.calls = []

    def invoke(self, folder, messages):
        self.calls.append((str(folder), messages))
        return SimpleNamespace(content=self.replies.pop(0))


class FakeTool:
    def __init__(self, name, schema, result=None):
        self.name, self.args_schema = name, schema
        self.description = 'Offline contract fixture; never a medical prediction.'
        self.result, self.calls = result, []

    def invoke(self, args):
        self.calls.append(args)
        return self.result if self.result is not None else {'analysis_status': 'completed', 'observation': 'not assessed by fixture'}


class ActionsTests(unittest.TestCase):
    def images(self, root):
        result = []
        for n in (1, 2):
            path = Path(root) / ('raw' + str(n) + '.png')
            Image.new('RGB', (200, 100), (n * 40, 0, 0)).save(path)
            result.append({'image_id': 'image:' + str(n), 'path': str(path),
                           'source_filename': path.name, 'size': [200, 100], 'role': 'original'})
        return result

    def plan(self, actions, second_modality='CXR'):
        return {'attributes': ['margin shape'], 'actions': actions,
                'image_metadata': [{'image_id': 'image:1', 'modality': 'CXR', 'view': 'frontal'},
                                   {'image_id': 'image:2', 'modality': second_modality, 'view': 'lateral'}]}

    def run_plan(self, root, images, plan, tools):
        client = SavedResponseClient(plan)
        row = {'question_id': 'synthetic_contract', 'question': 'Which shape?\nA) Round\nB) Angular'}
        direct = {'answer': 'A', 'raw_response': 'initial-secret-rationale'}
        folder = Path(root) / 'case/P'
        result = run_p(row, images, direct, client, tools, root, folder)
        return result, client, folder

    def test_aliases_and_actual_multisource_expert_binding(self):
        with tempfile.TemporaryDirectory() as root:
            images = self.images(root)
            tool = FakeTool('chest_xray_expert', ExpertArgs)
            actions = [
                {'kind': 'focused expert observation', 'tool': tool.name, 'image_ids': ['image:1', 'image:2'],
                 'question': 'How do the margins compare?', 'tool_args': {}},
                {'kind': 'paired-image comparison', 'image_ids': ['image:1', 'image:2'], 'question': 'Compare the margins.'},
            ]
            result, client, folder = self.run_plan(root, images, self.plan(actions), {tool.name: tool})
            self.assertEqual(result['answer'], 'B')
            self.assertEqual(result['tool_actual'], 1)
            self.assertEqual(tool.calls[0]['image_paths'], [x['path'] for x in images])
            self.assertEqual(result['new_roi_or_pair_views'], 1)
            self.assertEqual(read(folder/'plan.json')['actions'][0]['kind'], 'focused expert observation')
            self.assertEqual(read(folder/'normalized_plan.json')['actions'][0]['kind'], 'expert')
            observer = read(folder/'observer_payload.json')
            self.assertEqual(observer['tool_observations'][0]['source_image_ids'], ['image:1', 'image:2'])
            self.assertNotIn('initial-secret-rationale', json.dumps(observer))
            final_payload=json.loads(client.calls[2][1][1]['content'][0]['text'])
            self.assertEqual(final_payload['tools'][0]['source_image_ids'], ['image:1', 'image:2'])
            # Both original images plus the actual paired PNG go to the observer.
            self.assertEqual(sum(p['type']=='image_url' for p in client.calls[1][1][1]['content']), 3)

    def test_every_bound_source_must_match_modality(self):
        with tempfile.TemporaryDirectory() as root:
            images = self.images(root);tool = FakeTool('chest_xray_expert', ExpertArgs)
            action = {'kind': 'expert', 'tool': tool.name, 'image_ids': ['image:1', 'image:2'],
                      'question': 'Compare shape.', 'tool_args': {}}
            result, client, _ = self.run_plan(root, images, self.plan([action], 'CT'), {tool.name: tool})
            self.assertEqual(tool.calls, [])
            self.assertEqual(len(client.calls), 1)
            self.assertIn('every_source', result['events'][0]['error'])

    def test_single_image_tools_never_drop_extra_binding(self):
        with tempfile.TemporaryDirectory() as root:
            images = self.images(root);tool = FakeTool('xray_phrase_grounding', GroundArgs)
            action = {'kind': 'xray_phrase_grounding', 'image_ids': ['image:1', 'image:2'],
                      'question': 'Where is the opacity?', 'target_region': 'opacity'}
            result, _, _ = self.run_plan(root, images, self.plan([action]), {tool.name: tool})
            self.assertEqual(tool.calls, [])
            self.assertEqual(result['events'][0]['error'], 'medical_tool_requires_one_bound_source')

    def test_explicit_tool_paths_cannot_bypass_binding(self):
        with tempfile.TemporaryDirectory() as root:
            images = self.images(root);tool = FakeTool('chest_xray_expert', ExpertArgs)
            session = ToolSession({tool.name: tool}, images, root, Path(root)/'M', 'M')
            error = session.execute(tool.name, {'image_paths': [images[1]['path']], 'prompt': 'Describe.'}, sources=[images[0]])
            self.assertEqual(error['error'], 'tool_paths_conflict_with_bound_sources')
            self.assertEqual(tool.calls, [])
            error = session.execute(tool.name, {'image_paths': ['not-a-current-image.png'], 'prompt': 'Describe.'})
            self.assertEqual(error['error'], 'tool_image_not_a_current_original')

    def test_crop_failure_keeps_target_and_is_partial(self):
        with tempfile.TemporaryDirectory() as root:
            images = self.images(root)
            tool = FakeTool('xray_phrase_grounding', GroundArgs,
                            {'analysis_status': 'completed', 'bounding_boxes': {'image_coordinates': [[.2, .2, .7, .8]]}})
            action = {'kind': 'ground', 'tool': tool.name, 'image_ids': ['image:1'],
                      'question': 'Describe the visible margin.', 'target_region': 'opacity'}
            with patch('official_gain.evidence_agent.roi', side_effect=ValueError('injected_crop_failure')):
                result, client, folder = self.run_plan(root, images, self.plan([action]), {tool.name: tool})
            self.assertEqual(result['events'][0]['status'], 'partial')
            self.assertEqual(result['events'][0]['error'], 'injected_crop_failure')
            self.assertEqual(read(folder/'observer_payload.json')['neutral_attribute_questions'],
                             [{'image_ids':['image:1'], 'question':'Describe the visible margin.'}])
            self.assertEqual(len(client.calls), 3)
            self.assertEqual(result['new_visual_inputs'], 0)

    def test_cache_replay_preserves_hit_and_lost_output_counters(self):
        with tempfile.TemporaryDirectory() as root:
            images = self.images(root);tool = FakeTool('chest_xray_expert', ExpertArgs)
            args = {'image_paths': [images[0]['path']], 'prompt': 'Describe shape.'}
            first = ToolSession({tool.name: tool}, images, root, Path(root)/'first', 'M')
            first.execute(tool.name, args)
            cached = ToolSession({tool.name: tool}, images, root, Path(root)/'cached', 'P')
            cached.execute(tool.name, args)
            resumed = ToolSession({tool.name: tool}, images, root, Path(root)/'cached', 'P')
            resumed.execute(tool.name, args)
            self.assertEqual((cached.actual, cached.cache_hits), (0,1))
            self.assertEqual((resumed.actual, resumed.cache_hits), (0,1))
            folder = Path(root)/'interrupted'
            write(folder/'tools/1/started.json', {'tool':tool.name})
            other_args = dict(args,prompt='A different uncached shape question.')
            lost = ToolSession({tool.name: tool}, images, root, folder, 'M')
            lost.execute(tool.name, other_args)
            replay = ToolSession({tool.name: tool}, images, root, folder, 'M')
            replay.execute(tool.name, other_args)
            self.assertEqual((lost.unresolved_prior,replay.unresolved_prior), (1,1))
            self.assertEqual(len(tool.calls), 1)

    def test_organs_JSON_array_compatibility_is_logged_and_still_typed(self):
        with tempfile.TemporaryDirectory() as root:
            images = self.images(root);tool = FakeTool('chest_xray_segmentation', OrgansArgs)
            session = ToolSession({tool.name:tool}, images, root, Path(root)/'M', 'M')
            captured=[]
            session.execute=lambda name,args: captured.append(args) or {'recorded':True}
            proxy=session.proxies()[0]
            proxy.invoke({'image_path':images[0]['path'],'organs':'["Right Lung", "Heart"]'})
            self.assertEqual(captured[0]['organs'], ['Right Lung','Heart'])
            self.assertEqual(read(Path(root)/'M/argument_normalizations.json')[0]['raw'], '["Right Lung", "Heart"]')
            self.assertEqual(proxy.args_schema.model_json_schema()['properties']['organs']['type'], 'array')
            error=proxy.invoke({'image_path':images[0]['path'],'organs':'Right Lung; Heart'})
            self.assertTrue(error.startswith('TOOL_ARGUMENT_ERROR'))
            self.assertEqual(len(captured),1)

    def test_unknown_alias_and_unknown_or_duplicate_image_id_rejected(self):
        with self.assertRaisesRegex(ValueError,'unknown_action'):
            normalize_action({'kind':'invented action'})
        for ids in (['image:3'],['image:1','image:1']):
            with tempfile.TemporaryDirectory() as root:
                images=self.images(root)
                action={'kind':'paired','image_ids':ids,'question':'Compare.'}
                result,client,_=self.run_plan(root,images,self.plan([action]),{})
                self.assertTrue(result['fallback'])
                self.assertEqual(len(client.calls),1)


if __name__ == '__main__':
    unittest.main()
