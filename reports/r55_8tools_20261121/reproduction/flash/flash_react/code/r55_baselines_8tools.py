"""Open-budget ReAct, CRITIC and Reflexion on the common R55 tools."""

import os
from itertools import count
import json

from r55_baseline_common import dataset_out, prediction_path
from run_qwen_baselines import Baselines, FINAL, TOOL_JSON


from r55_run_plan import TOOLS as TOOL_MENU

GPU_TOOLS = set(TOOL_MENU) - {'roi_crop'}
TOOL_ARM = 'R49-AGENT'
REACT_SYSTEM = (
    'Solve the visual question by alternating brief reasoning, a useful tool action when needed, '
    'and inspection of the resulting observation. Compare tool findings with the original image. '
    'Choose when evidence is sufficient and give the final answer. ' + FINAL
)
CRITIC_SYSTEM = (
    'Critically check the initial candidate answer against evidence. Use a tool for the most '
    'important unresolved issue, review its observation, and check further concrete issues when needed. '
    'Retain or revise the candidate based on the available evidence. ' + FINAL
)



def replay_trial(session, row, saved):
    qid = row['question_id']
    record = json.loads(saved.read_bytes())
    if (record['arm'], record['question_id']) != ('react', qid):
        raise ValueError(f'ReAct replay identity mismatch for {qid}')
    model = session.manifest['protocol']['model']
    archive = session.out / 'replay' / session.dataset
    if model == 'deepseek-flash':
        from r55_deepseek_official import matches

        archive = session.api_dir
        ordinal = str(record['calls']['qwen'])
        request = None
        for role in ('react', 'react_request_retry1', 'react_request_retry2'):
            folder = archive / 'calls' / role / qid / ordinal
            receipt = folder / 'result.json'
            if not receipt.is_file():
                continue
            result = json.loads(receipt.read_bytes())
            if result['response_received']:
                response = json.loads((folder / 'response.json').read_bytes())
                raw = response['choices'][0]['message'].get('content') or ''
                if not matches(result['model_returned']) or raw != record['raw']:
                    raise ValueError(f'DeepSeek ReAct replay response mismatch for {qid}')
                request = json.loads((folder / 'request.json').read_bytes())
                break
        if request is None:
            raise ValueError(f'Missing completed DeepSeek ReAct request for {qid}')
    else:
        archived = json.loads((archive / f'{qid}.json').read_bytes())
        result = archived['result']
        if not result['response_received'] or result['model_returned'] != model or int(archived['ordinal']) != record['calls']['qwen']:
            raise ValueError(f'Historical ReAct response mismatch for {qid}')
        request = archived['request']
    if request['model'] != model:
        raise ValueError(f'ReAct replay model mismatch for {qid}')
    messages = request['messages']
    for message in messages:
        if isinstance(message['content'], str):
            continue
        for part in message['content']:
            if part['type'] != 'image_url':
                continue
            url = part['image_url']['url']
            if isinstance(url, dict):
                digest = url['cxr_request_image_base64_sha256']
                encoded = (archive / 'request_image_base64' / digest).read_text(encoding='ascii')
                part['image_url']['url'] = f"data:{url['media_type']};base64,{encoded}"
    return record['raw'], record['calls'], messages


class R55Baselines(Baselines):
    def __init__(self, root, out, dataset, key, **options):
        super().__init__(root, out, dataset, key, **options)
        from run_chexagent8_direct import MODEL, REVISION
        from r55_deepseek_rerun_runtime import guarded_tool
        from skill_services_r55 import Tools

        expert = self.runtime['tools']['chest_xray_expert']
        if (expert['deployment_status'], expert['revision']) != (MODEL, REVISION):
            raise ValueError('This baseline requires the same original CheXagent-8B as R55.')
        if set(TOOL_MENU) != set(self.runtime['arms']['M']['tools']) or set(TOOL_MENU) != set(self.runtime['tools']):
            raise ValueError('This baseline requires the complete frozen R55 tool catalog.')
        self.catalog = self.tools.evidence_catalog(self.runtime, 'M')

        class SharedTools(Tools):
            def observe(self, name, spec, args, image, identity, folder, saved):
                backend = super().observe
                run = lambda: backend(name, spec, args, image, identity, folder, saved)
                if name not in GPU_TOOLS:
                    from r55_deepseek_rerun_runtime import lease
                    key_lock = folder.parent / ".leases" / (folder.name + ".lock")
                    with lease(key_lock):
                        return run()
                return guarded_tool(root.parent, os.environ['R55_QWEN8_ARM'], name, folder, saved, run)

        self.tool_workers = {}
        for role in ('react', 'critic', 'reflexion_retry'):
            services = self.api_dir / 'tool_runs' / role / 'services'
            protocol = dict(self.paid.protocol, experiment_id=f'{self.out.name}-{role}')
            model = self.tools.PaidCalls(self.manifest['config'], protocol, services, key)
            self.tool_workers[role] = SharedTools(self.runtime, self.data, services, model.call, None)

    def runtime_for_tools(self):
        return self.runtime

    def observe_r55(self, row, action, role, ordinal, messages):
        from cxr_online_primitives_r49 import tool_failure_reason
        from failure_observation_r54 import delivered_failure

        worker = self.tool_workers[role]
        result = worker.call(row, action, TOOL_ARM, ordinal)
        failed = tool_failure_reason(result)
        if failed:
            result = delivered_failure(worker.out, row, ordinal, action, result)
        self.tools.append_observations(messages, [result], worker.out, 'M')
        return bool(failed)

    @staticmethod
    def has_answer(row, raw):
        from cxr_author_alignment import choice, extract

        options = row.get('options', {})
        explicit = extract(raw, row['question_id'], options).answer
        return explicit is not None and (not options or choice(explicit, options) is not None)

    def evidence_loop(self, row, role, messages, first_instruction=None):
        menu = TOOL_JSON + ' Or answer now. ' + FINAL + '\nTools: ' + json.dumps(self.catalog)
        calls = failed = 0
        seen_actions = {}
        invalid_reply = None
        termination = None
        instruction = first_instruction or menu
        for step in count(1):
            messages.append({'role': 'user', 'content': instruction})
            raw = self.call(row, role, step, messages)
            if self.has_answer(row, raw) or termination:
                counts = {'qwen': step, 'tools': calls, 'failed_tools': failed}
                if termination:
                    counts['termination'] = termination
                return raw, counts, messages

            action = self.action(raw)
            messages.append({'role': 'assistant', 'content': raw})
            if action is None:
                if raw == invalid_reply:
                    termination = 'repeated_invalid_reply'
                    instruction = 'Finalize with the available evidence. ' + FINAL
                else:
                    invalid_reply = raw
                    instruction = 'Please provide a usable answer or one registered tool action. ' + menu
                continue

            invalid_reply = None
            signature = json.dumps(action, sort_keys=True)
            seen_actions[signature] = seen_actions.get(signature, 0) + 1
            if seen_actions[signature] >= 3:
                termination = 'repeated_identical_action_no_progress'
                instruction = 'This exact tool action has already been tried twice. Give the final answer. ' + FINAL
                continue
            calls += 1
            failed += self.observe_r55(row, action, role, calls, messages)
            instruction = menu

    def react(self, row, arm, reflection=None):
        messages = self.original(row, REACT_SYSTEM)
        if reflection:
            messages.append({'role': 'user', 'content': 'Episodic reflection from your previous trial on this question. '
                             'Use it as guidance and independently recheck the image.\n' + reflection})
        if arm == 'react' and getattr(self, 'replay_first_trial', False):
            saved = prediction_path(dataset_out(self.out, arm, self.dataset), row)
            if not saved.is_file():
                raise RuntimeError('Reflexion needs its completed ReAct first trial')
            return replay_trial(self, row, saved)
        return self.evidence_loop(row, arm, messages)

    def critic(self, row):
        prior = prediction_path(dataset_out(self.out, 'cot', self.dataset), row)
        if not prior.is_file():
            if self.manifest['protocol']['model'] != 'deepseek-flash':
                raise ValueError('Missing frozen Qwen CoT candidate for CRITIC.')
            self.predict(row, 'cot')
        candidate, _ = self.cot(row)
        messages = self.original(row, CRITIC_SYSTEM)
        messages.append({'role': 'user', 'content': 'Initial candidate reply:\n' + candidate})
        start = ('Identify a concrete uncertainty in the candidate to check. ' + TOOL_JSON +
                 ' If no evidence check is needed, state the supported final answer. ' + FINAL +
                 '\nTools: ' + json.dumps(self.catalog))
        raw, counts, _ = self.evidence_loop(row, 'critic', messages, start)
        if not self.has_answer(row, raw):
            counts['fallback'] = 'frozen_cot_candidate'
            raw = candidate
        return raw, counts
