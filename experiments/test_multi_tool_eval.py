"""Offline multiple-tool orchestration tests; no GPU, API or reference labels."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import multi_tool_eval as multi
import diagnostic_eval as diag
import tool_variants as variants
from test_diagnostic_eval import FakeAgent, FakeGuard, FakeLimit, FakeModel, Message, arguments, fake_messages
from test_length_cap_followup import fixture, FakeChunkGuard

SECRET_REPORT = 'SYNTHETIC_REPORT_PROSE_MUST_REACH_AGENT_BUT_NEVER_LOG'


class ImageSchema:
    @classmethod
    def model_json_schema(cls):
        return {'properties': {'image_path': {'type': 'string'}}, 'required': ['image_path']}
    @classmethod
    def model_validate(cls, params):
        return params


class SegmentSchema(ImageSchema):
    @classmethod
    def model_json_schema(cls):
        return {'properties': {'image_path': {'type': 'string'}, 'organs': {'type': 'array'}}, 'required': ['image_path']}


class FakeClassifier:
    name, args_schema = 'chest_xray_classifier', ImageSchema
    def __init__(self): self.calls = []
    def invoke(self, params):
        self.calls.append(params)
        return ({name: 0.5 for name in variants.CLASSIFIER_LABELS}, {'analysis_status': 'completed'})


class FakeReport:
    name, args_schema = 'chest_xray_report_generator', ImageSchema
    def __init__(self, fail=False): self.calls, self.fail = [], fail
    def invoke(self, params):
        self.calls.append(params)
        if self.fail:
            return ('Error generating report: SYNTHETIC_PRIVATE_ERROR', {'analysis_status': 'failed'})
        return ('CHEST X-RAY REPORT\n\nFINDINGS:\n' + SECRET_REPORT + '\n\nIMPRESSION:\nsynthetic impression',
                {'analysis_status': 'completed', 'sections_generated': ['findings', 'impression']})


def runtime(model, report=None):
    classifier, report = FakeClassifier(), report or FakeReport()
    tools = {tool.name: tool for tool in (classifier, report)}
    provenance = {classifier.name: {'kind': 'classification', 'mode': 'original', 'version': 'synthetic'},
                  report.name: {'kind': 'report', 'mode': 'original', 'version': 'synthetic'}}
    return SimpleNamespace(model=model, tools=tools, tool_provenance=provenance,
        Agent=FakeAgent, MemorySaver=object, HumanMessage=Message, SystemMessage=Message,
        agent_system='synthetic system', direct_system='synthetic system')


def tool_call(name, image, call_id):
    return {'id': call_id, 'name': name, 'args': {'image_path': str(image)}}


def run_case(rt, paths, guard=None, arm='agent'):
    trace = io.StringIO(); guard = guard or FakeGuard()
    result = multi.run_arm(rt, guard, {'question_id': 'q', 'question': 'synthetic', 'images': []},
        paths, arm, {'thread_id': 'independent-thread'}, 'synthetic-run', arguments(), trace,
        limit_errors=(FakeLimit,), message_builder=fake_messages)
    return result, trace.getvalue(), guard


class MultiToolTests(unittest.TestCase):
    def test_two_real_tool_invocations_have_separate_counts_and_report_text_stays_out_of_logs(self):
        with TemporaryDirectory() as temp:
            image = Path(temp) / 'image.png'; image.write_bytes(b'synthetic')
            model = FakeModel([Message('', tool_calls=[tool_call('chest_xray_classifier', image, 'c1'),
                tool_call('chest_xray_report_generator', image, 'r1')]), Message('synthetic reasoning'), Message('B')])
            rt = runtime(model); result, trace, guard = run_case(rt, [image])
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(result['actual_model_calls'], 3)
            self.assertEqual(result['actual_tool_attempts'], 2)
            self.assertEqual(result['validated_tool_returns'], 2)
            self.assertTrue(result['all_available_tools_executed'])
            self.assertTrue(all(x['attempted'] == 1 for x in result['tool_counts'].values()))
            self.assertNotIn(SECRET_REPORT, trace + json.dumps(result))
            self.assertIn(SECRET_REPORT, str([getattr(x, 'content', '') for x in model.histories[1]]))
            events = [json.loads(x) for x in trace.splitlines() if json.loads(x).get('node') == 'tool']
            self.assertEqual({x['tool_kind'] for x in events}, {'classification', 'report'})
            self.assertTrue(all(x['clinical_evidence'] == 'unknown' and x['step_credit'] is None for x in events))
            self.assertTrue(all('tool_version_sha256' in x and 'arguments_sha256' in x for x in events))

    def test_registered_classifier_is_not_forced_when_model_selects_only_report(self):
        with TemporaryDirectory() as temp:
            image = Path(temp) / 'second.png'; image.write_bytes(b'synthetic')
            first = Path(temp) / 'first.png'; first.write_bytes(b'synthetic-first')
            rt = runtime(FakeModel([Message('', tool_calls=[tool_call('chest_xray_report_generator', image, 'r')]),
                                    Message('reasoning'), Message('A')]))
            result, _, _ = run_case(rt, [first, image])
            self.assertEqual(result['selected_tool_names'], ['chest_xray_report_generator'])
            self.assertEqual(result['tool_counts']['chest_xray_classifier']['attempted'], 0)
            self.assertFalse(result['all_available_tools_executed'])
            self.assertFalse(result['tools_forced'])
            self.assertEqual(rt.tools['chest_xray_report_generator'].calls[0]['image_path'], str(image.resolve()))

    def test_no_tool_selected_never_claims_tool_verification(self):
        result, _, _ = run_case(runtime(FakeModel([Message('reasoning'), Message('A')])), [])
        self.assertEqual(result['actual_tool_attempts'], 0)
        self.assertFalse(result['tool_execution_verified'])
        self.assertIn('no_tool_call', result['issue_tags'])

    def test_schema_extra_fields_and_cross_question_image_are_rejected_before_invocation(self):
        with TemporaryDirectory() as temp:
            image = Path(temp) / 'image.png'; image.write_bytes(b'synthetic')
            outside = Path(temp) / 'other.png'; outside.write_bytes(b'synthetic-other')
            for params in ({'image_path': str(outside)}, {'image_path': str(image), 'prompt': 'unexpected'}, {'image_path': 5}):
                rt = runtime(FakeModel([Message('', tool_calls=[{'id': 'r', 'name': 'chest_xray_report_generator', 'args': params}])]))
                result, _, _ = run_case(rt, [image])
                self.assertEqual(result['status'], 'tool_error')
                self.assertEqual(result['actual_tool_attempts'], 0)
                self.assertEqual(rt.tools['chest_xray_report_generator'].calls, [])

    def test_segmentation_optional_organs_follow_real_schema_and_allowlist(self):
        with TemporaryDirectory() as temp:
            image = Path(temp) / 'image.png'; image.write_bytes(b'synthetic')
            tool = SimpleNamespace(args_schema=SegmentSchema, organ_map={'Left Lung': 4, 'Right Lung': 5})
            for params in ({'image_path': str(image)}, {'image_path': str(image), 'organs': None},
                           {'image_path': str(image), 'organs': ['Left Lung']}):
                multi.validate_parameters(tool, 'segmentation', params, {image})
            for organs in ([], ['unknown'], ['Left Lung', 'Left Lung'], 'Left Lung', [3]):
                with self.assertRaises(ValueError):
                    multi.validate_parameters(tool, 'segmentation', {'image_path': str(image), 'organs': organs}, {image})

    def test_tool_reported_failure_is_visible_to_agent_but_is_not_validated(self):
        with TemporaryDirectory() as temp:
            image = Path(temp) / 'image.png'; image.write_bytes(b'synthetic')
            rt = runtime(FakeModel([Message('', tool_calls=[tool_call('chest_xray_report_generator', image, 'r')]),
                Message('reasoning'), Message('A')]), FakeReport(fail=True))
            result, trace, _ = run_case(rt, [image])
            self.assertEqual(result['actual_tool_attempts'], 1)
            self.assertEqual(result['validated_tool_returns'], 0)
            self.assertEqual(result['failed_tool_returns'], 1)
            self.assertIn('no_valid_tool_return', result['issue_tags'])
            self.assertNotIn('SYNTHETIC_PRIVATE_ERROR', trace + json.dumps(result))

    def test_segmentation_call_validates_private_artifact_without_exposing_its_path(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); image = root / 'image.png'; image.write_bytes(b'synthetic')
            artifact = root / 'private'; artifact.mkdir()
            overlay = artifact / 'segmentation_1234abcd.png'; overlay.write_bytes(b'\x89PNG\r\n\x1a\nSYNTHETIC')
            output = ({'metrics': {}, 'segmentation_image_path': str(overlay)},
                {'analysis_status': 'completed', 'segmentation_image_path': str(overlay),
                 'original_size': [100, 100], 'model_size': [512, 512], 'pixel_spacing_mm': 0.2,
                 'requested_organs': ['Heart'], 'processed_organs': []})
            class Segment:
                name, args_schema, organ_map = 'chest_xray_segmentation', SegmentSchema, {'Heart': 8}
                temp_dir = artifact
                def invoke(self, params): return output
            call = tool_call(Segment.name, image, 's'); call['args']['organs'] = ['Heart']
            rt = runtime(FakeModel([Message('', tool_calls=[call]), Message('reasoning'), Message('A')]))
            rt.tools[Segment.name] = Segment()
            rt.tool_provenance[Segment.name] = {'kind': 'segmentation', 'mode': 'original', 'version': 'synthetic'}
            result, trace, _ = run_case(rt, [image])
            self.assertEqual(result['validated_tool_returns'], 1)
            self.assertEqual(result['tool_counts'][Segment.name]['attempted'], 1)
            self.assertNotIn(str(overlay), trace + json.dumps(result))
            event = next(json.loads(x) for x in trace.splitlines() if json.loads(x).get('node') == 'tool')
            self.assertEqual(event['output_contract']['metrics_returned_count'], 0)
            self.assertFalse(event['output_contract']['physical_area_calibrated'])
            self.assertFalse(result['all_available_tools_executed'])

    def test_total_tool_limit_applies_across_kinds_and_prevents_third_actual_invoke(self):
        with TemporaryDirectory() as temp:
            image = Path(temp) / 'image.png'; image.write_bytes(b'synthetic')
            rt = runtime(FakeModel([Message('', tool_calls=[tool_call('chest_xray_classifier', image, 'c'),
                tool_call('chest_xray_report_generator', image, 'r'), tool_call('chest_xray_report_generator', image, 'r2')])]))
            result, _, _ = run_case(rt, [image])
            self.assertEqual(result['status'], 'case_budget_exceeded')
            self.assertEqual(result['actual_tool_attempts'], 2)
            self.assertEqual(len(rt.tools['chest_xray_report_generator'].calls), 1)

    def test_direct_arm_has_same_two_stages_and_no_tool_execution(self):
        rt = runtime(FakeModel([Message('reasoning'), Message('C')]))
        result, _, guard = run_case(rt, [], arm='direct')
        self.assertEqual(result['actual_model_calls'], 2)
        self.assertEqual(len(guard.reserved), 2)
        self.assertEqual(result['actual_tool_attempts'], 0)
        self.assertEqual(result['available_tool_names'], [])
        self.assertEqual(result['call_counts'], {'model': 2, 'tool': 0})

    def test_shared_ledger_denial_prevents_any_model_call(self):
        model = FakeModel([Message('must not run')])
        result, _, _ = run_case(runtime(model), [], FakeGuard(allowed=0), arm='direct')
        self.assertEqual(result['status'], 'monetary_budget_exceeded')
        self.assertTrue(result['stop_run'])
        self.assertEqual(len(model.histories), 0)

    def test_plan_freezes_first_five_sources_original_variants_and_new_tool_provenance(self):
        with TemporaryDirectory() as temp:
            root = Path(temp); directory, inputs, ledger, base_plan = fixture(root, ['q20'])
            baseline = multi.previous.load_completed_baseline(directory, inputs)
            settings = multi.previous.frozen_settings(baseline, ledger_path=ledger)
            (settings.repo / 'medrax/tools').mkdir(parents=True)
            (settings.repo / 'medrax/tools/report_generation.py').write_text('synthetic source')
            provenance = runtime(FakeModel([])).tool_provenance
            with patch.object(diag, 'build_plan', return_value=deepcopy(base_plan)):
                plan = multi.build_plan(baseline, inputs, settings, FakeChunkGuard(base_plan['monetary_policy']), 'prompt', provenance)
            self.assertEqual(plan['planned_question_count'], 5)
            self.assertEqual(plan['question_ids'], [f'q{i:02}' for i in range(5)])
            self.assertEqual(len(plan['schedule']), 10)
            self.assertEqual(plan['max_output_tokens'], 1024)
            self.assertEqual(plan['max_model_calls'], 4)
            self.assertEqual(plan['max_tool_calls'], 2)
            self.assertFalse(plan['is_complete_paper_toolset'])
            self.assertFalse(plan['tool_selection']['force_each_tool'])
            self.assertFalse(plan['selection']['uses_truncation'])
            self.assertIn('multi_tool_eval.py', plan['source_sha256'])
            changed = deepcopy(provenance); changed['chest_xray_report_generator']['mode'] = 'eos_only'
            with patch.object(diag, 'build_plan', return_value=deepcopy(base_plan)):
                with self.assertRaises(ValueError):
                    multi.build_plan(baseline, inputs, settings, FakeChunkGuard(base_plan['monetary_policy']), 'prompt', changed)


if __name__ == '__main__':
    unittest.main()
