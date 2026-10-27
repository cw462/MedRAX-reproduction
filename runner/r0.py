"""R0 benchmark adapter for official MedRAX; no cross-case memory.

Input must already be isolated JSONL with exactly question_id, question, images.
The runner deliberately refuses reference-answer fields and never scores answers.
"""
import argparse
import base64
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import json
import math
import mimetypes
import os
from pathlib import Path
import sys
import threading
import time
import uuid

TOOLS = {
    'ChestXRayClassifierTool', 'ChestXRaySegmentationTool', 'LlavaMedTool',
    'XRayVQATool', 'ChestXRayReportGeneratorTool', 'XRayPhraseGroundingTool',
    'ChestXRayGeneratorTool', 'ImageVisualizerTool', 'DicomProcessorTool',
}
FIELDS = {'question_id', 'question', 'images'}


class BudgetExceeded(RuntimeError):
    """A pre-call guard prevented another provider or tool invocation."""


class CaseBudget:
    """Per-question, thread-safe pre-invocation guard; does not bound dollars."""
    def __init__(self, max_tools, max_model_calls, max_seconds, trace):
        self.limits = {'tool': max_tools, 'model': max_model_calls}
        self.counts = {'tool': 0, 'model': 0}
        self.deadline = time.monotonic() + max_seconds
        self.trace = trace
        self.lock = threading.Lock()
        self.case_hash = None
        self.thread_id = None

    def reserve(self, kind, name):
        with self.lock:
            reason = None
            if time.monotonic() >= self.deadline:
                reason = 'deadline_before_call'
            elif self.counts[kind] >= self.limits[kind]:
                reason = f'{kind}_call_limit'
            if reason:
                write_line(self.trace, {'case_hash': self.case_hash, 'thread_id': self.thread_id,
                                        'node': 'budget', 'kind': kind, 'name': name,
                                        'decision': 'blocked', 'reason': reason,
                                        'counts': dict(self.counts)})
                raise BudgetExceeded(reason)
            self.counts[kind] += 1
            write_line(self.trace, {'case_hash': self.case_hash, 'thread_id': self.thread_id,
                                    'node': 'budget', 'kind': kind, 'name': name,
                                    'decision': 'allowed', 'counts': dict(self.counts)})


class GuardedInvoke:
    """Proxy only the sync invoke path used by the audited MedRAX Agent."""
    def __init__(self, wrapped, kind, name, current_budget):
        self.wrapped, self.kind, self.name, self.current_budget = wrapped, kind, name, current_budget

    def invoke(self, *args, **kwargs):
        budget = self.current_budget()
        if budget is None:
            raise RuntimeError('No active case budget')
        budget.reserve(self.kind, self.name)
        return self.wrapped.invoke(*args, **kwargs)


def install_budget_guards(agent, current_budget):
    # The audited official Agent.process_request/execute_tools use these attributes
    # at execution time. The model was already bound to the original tool schemas.
    agent.model = GuardedInvoke(agent.model, 'model', 'llm', current_budget)
    agent.tools = {name: GuardedInvoke(tool, 'tool', name, current_budget)
                   for name, tool in agent.tools.items()}


def load_inputs(path, max_cases):
    rows, seen = [], set()
    with open(path, encoding='utf-8') as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != FIELDS:
                raise ValueError(f'Line {line_no}: require exactly {sorted(FIELDS)}; strip answer and explanation before inference')
            if not isinstance(row['question'], str) or not row['question'].strip():
                raise ValueError(f'Line {line_no}: empty or invalid question')
            if not isinstance(row['question_id'], (str, int)):
                raise ValueError(f'Line {line_no}: question_id must be string or integer')
            if not isinstance(row['images'], list) or not all(isinstance(p, str) and p for p in row['images']):
                raise ValueError(f'Line {line_no}: images must be a list of nonempty relative paths')
            qid = str(row['question_id'])
            if qid in seen:
                raise ValueError(f'Line {line_no}: duplicate question_id')
            seen.add(qid)
            rows.append(row)
            if len(rows) == max_cases:
                break
    if not rows:
        raise ValueError('No questions selected')
    return rows


def image_paths(row, root):
    paths = []
    for raw in row['images']:
        path = (root / raw).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Image path escapes image root')
        if not path.is_file():
            raise FileNotFoundError('One or more image files missing')
        paths.append(path)
    if not paths:
        raise FileNotFoundError('No image files')
    return paths


def summarize(data):
    # Never print or save tool output/arguments, which may contain sensitive data.
    encoded = str(data).encode('utf-8', errors='replace')
    return {'bytes': len(encoded), 'sha256': hashlib.sha256(encoded).hexdigest()}


def write_line(handle, obj):
    handle.write(json.dumps(obj, ensure_ascii=False) + '\n')
    handle.flush()


def run_case(agent, row, root, trace, recursion_limit, budget=None):
    case_id = hashlib.sha256(str(row['question_id']).encode()).hexdigest()
    thread_id = str(uuid.uuid4())
    if budget:
        budget.case_hash, budget.thread_id = case_id, thread_id
    start = time.monotonic()
    status, prediction = 'error', None
    event_index = 0
    try:
        images = image_paths(row, root)
        messages = []
        for path in images:
            mime = mimetypes.guess_type(path.name)[0] or 'image/jpeg'
            if not mime.startswith('image/'):
                raise ValueError('Only encoded image files are supported')
            b64 = base64.b64encode(path.read_bytes()).decode('ascii')
            messages.append({'role': 'user', 'content': f'image_path: {path}'})
            messages.append({'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': f'data:{mime};base64,{b64}'}}]})
        prompt = ('Given the following medical case, answer the multiple-choice question. '
                  'Base your answer only on the provided images and case information. '
                  'End with the answer letter A, B, C, D, E, or F.\n' + row['question'])
        messages.append({'role': 'user', 'content': [{'type': 'text', 'text': prompt}]})
        # Official agent prints tool args; do not expose these in the console.
        with open(os.devnull, 'w') as sink, redirect_stdout(sink):
            for event in agent.workflow.stream({'messages': messages}, {'configurable': {'thread_id': thread_id}, 'recursion_limit': recursion_limit}):
                if not isinstance(event, dict):
                    continue
                for node in ('process', 'execute'):
                    if node not in event:
                        continue
                    for message in event[node].get('messages', []):
                        event_index += 1
                        entry = {'case_hash': case_id, 'thread_id': thread_id, 'event': event_index,
                                 'node': node, 'elapsed_ms': round((time.monotonic()-start)*1000)}
                        if node == 'process':
                            calls = getattr(message, 'tool_calls', []) or []
                            entry['tool_calls'] = [{'id': c.get('id'), 'name': c.get('name'),
                                                    'argument_keys': sorted(c.get('args', {}).keys()) if isinstance(c.get('args'), dict) else []} for c in calls]
                            if not calls and getattr(message, 'content', None):
                                prediction = message.content
                            entry['content_summary'] = summarize(getattr(message, 'content', ''))
                        else:
                            entry.update({'tool_name': getattr(message, 'name', None),
                                          'tool_call_id': getattr(message, 'tool_call_id', None),
                                          'observation_summary': summarize(getattr(message, 'content', '')),
                                          'tool_message_status': getattr(message, 'status', 'unknown')})
                        write_line(trace, entry)
        status = 'completed' if prediction else 'no_final_answer'
    except Exception as exc:
        # Do not log exception messages: providers may echo requests or secrets.
        status = 'budget_exceeded' if isinstance(exc, BudgetExceeded) else 'error'
        write_line(trace, {'case_hash': case_id, 'thread_id': thread_id, 'event': event_index + 1,
                           'node': 'exception', 'exception_type': type(exc).__name__,
                           'elapsed_ms': round((time.monotonic()-start)*1000)})
    return {'case_hash': case_id, 'thread_id': thread_id, 'status': status,
            'prediction': prediction, 'elapsed_ms': round((time.monotonic()-start)*1000),
            'call_counts': dict(budget.counts) if budget else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--images-root', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path, help='Must not already exist')
    parser.add_argument('--model-dir', required=True, type=Path)
    parser.add_argument('--model', required=True)
    parser.add_argument('--tools', required=True, nargs='+', choices=sorted(TOOLS))
    parser.add_argument('--max-cases', required=True, type=int)
    parser.add_argument('--device', default='cuda')
    parser.add_argument('--temperature', type=float, default=0.7)
    parser.add_argument('--top-p', type=float, default=0.95)
    parser.add_argument('--recursion-limit', type=int, default=12)
    parser.add_argument('--max-tool-calls', type=int, required=True)
    parser.add_argument('--max-model-calls', type=int, required=True)
    parser.add_argument('--max-case-seconds', type=float, required=True)
    parser.add_argument('--request-timeout-seconds', type=float, required=True)
    parser.add_argument('--max-output-tokens', type=int, required=True)
    args = parser.parse_args()
    if args.max_cases < 1 or args.recursion_limit < 1:
        parser.error('max-cases and recursion-limit must be positive')
    if (args.max_tool_calls < 0 or args.max_model_calls < 1 or
            not math.isfinite(args.max_case_seconds) or args.max_case_seconds <= 0 or
            not math.isfinite(args.request_timeout_seconds) or args.request_timeout_seconds <= 0 or
            args.max_output_tokens < 1):
        parser.error('call and time limits must be positive, except max-tool-calls may be zero')
    if len(set(args.tools)) != len(args.tools):
        parser.error('tool names must be unique')
    if not os.environ.get('OPENAI_API_KEY'):
        parser.error('OPENAI_API_KEY is not set in the environment')
    repo = args.repo.resolve()
    root = args.images_root.resolve()
    rows = load_inputs(args.input, args.max_cases)
    if not (repo / 'main.py').is_file() or not root.is_dir():
        parser.error('repo or images-root does not exist')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir.resolve()
    manifest = {'created_utc': datetime.now(timezone.utc).isoformat(), 'mode': 'R0_real_agent',
                'model': args.model, 'temperature': args.temperature, 'top_p': args.top_p,
                'tools_requested': args.tools, 'device': args.device, 'max_cases': args.max_cases,
                'recursion_limit': args.recursion_limit, 'input_sha256': hashlib.sha256(args.input.read_bytes()).hexdigest(),
                'max_tool_calls': args.max_tool_calls, 'max_model_calls': args.max_model_calls,
                'max_case_seconds': args.max_case_seconds, 'request_timeout_seconds': args.request_timeout_seconds,
                'max_output_tokens': args.max_output_tokens, 'provider_retries': 0,
                'selected_cases': len(rows), 'limitations': ['No monetary hard limit; model/provider billing and nested tool network calls are not bounded', 'Deadline applies at call boundaries, not cancellation of in-flight work', 'No scoring or resumption implemented', 'Per-question thread and single prompt differ from author notebook case thread and two-stage prompting']}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    model_dir = args.model_dir.resolve()
    (output / 'temp').mkdir()
    os.chdir(output)
    sys.path.insert(0, str(repo))
    from main import initialize_agent
    kwargs = {'base_url': os.environ['OPENAI_BASE_URL']} if os.environ.get('OPENAI_BASE_URL') else {}
    kwargs.update({'timeout': args.request_timeout_seconds, 'max_retries': 0, 'max_tokens': args.max_output_tokens})
    agent, loaded = initialize_agent(str(repo / 'medrax/docs/system_prompts.txt'), tools_to_use=args.tools,
        model_dir=str(model_dir), temp_dir=str(output / 'temp'), device=args.device,
        model=args.model, temperature=args.temperature, top_p=args.top_p, openai_kwargs=kwargs)
    if set(loaded) != set(args.tools):
        raise RuntimeError('Initialized tool set differs from requested set')
    # Official logger writes raw arguments/observations and can overwrite same-second files.
    # Disable only that logger; the original checkpointer and tool behavior are retained.
    agent.log_tools = False
    current = {'budget': None}
    install_budget_guards(agent, lambda: current['budget'])
    with (output / 'trace.jsonl').open('x', encoding='utf-8') as trace, (output / 'predictions.jsonl').open('x', encoding='utf-8') as predictions:
        for row in rows:
            current['budget'] = CaseBudget(args.max_tool_calls, args.max_model_calls, args.max_case_seconds, trace)
            write_line(predictions, run_case(agent, row, root, trace, args.recursion_limit, current['budget']))
            current['budget'] = None
    print(f'Finished {len(rows)} cases; inspect status in {output / "predictions.jsonl"}')


if __name__ == '__main__':
    main()
