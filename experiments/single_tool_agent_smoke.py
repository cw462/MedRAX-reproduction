"""Bounded single-tool MedRAX Agent smoke, not a paper reproduction.

Loads upstream Agent and classifier by file, preserving the upstream system prompt.
No reference answers are accepted. Credentials are read only at runtime.
"""
from __future__ import annotations
import argparse
import base64
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import mimetypes
import os
from pathlib import Path
import re
import sys
import time
import uuid
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'runner'))
from r0 import CaseBudget, BudgetExceeded, load_inputs, image_paths, write_line, summarize
import classifier_smoke as classifier_utils

DEVIATIONS = [
    'Only the official DenseNet classifier is available; the paper uses more tools.',
    'A new Agent/checkpointer/thread is created for each question; author notebook shares a case thread.',
    'Images are embedded as data URLs instead of the author notebook remote URLs.',
    'The first user prompt adapts notebook wording/formatting; only the original system prompt is preserved exactly by its parser.',
    'Invocation budgets, request timeout and output-token limits may truncate author behavior.',
    'Provider and requested model are recorded; a proxy model name does not verify upstream model identity.',
    'No accuracy metric, reference scoring, cross-case memory, resumption or independent medical verification.',
]
FOLLOWUP = 'If you had to choose the best option, only respond with the letter of choice (only one of A, B, C, D, E, F)'


def module_from_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def numeric_usage(message):
    data = getattr(message, 'usage_metadata', None) or {}
    fallback = (getattr(message, 'response_metadata', None) or {}).get('token_usage', {})
    result = {}
    for out, modern, legacy in [('input_tokens','input_tokens','prompt_tokens'),
                                ('output_tokens','output_tokens','completion_tokens'),
                                ('total_tokens','total_tokens','total_tokens')]:
        value = data.get(modern, fallback.get(legacy))
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[out] = value
    return result or None


def aggregate_usage(records, model_attempts):
    fields = ('input_tokens', 'output_tokens', 'total_tokens')
    observed = {name: (sum(x[name] for x in records)
                       if all(name in x for x in records) else None)
                for name in fields} if records else None
    complete = (len(records) == model_attempts and bool(records)
                and all(all(name in x for name in fields) for x in records))
    return observed, complete


def answer_letter(content):
    if not isinstance(content, str):
        return None
    match = re.fullmatch(r'\s*([A-F])[.)]?\s*', content)
    return match.group(1) if match else None


class TrackedInvoke:
    def __init__(self, wrapped, kind, name, context, expected_labels=None):
        self.wrapped, self.kind, self.name = wrapped, kind, name
        self.context, self.expected_labels = context, expected_labels

    def invoke(self, *args, **kwargs):
        ctx = self.context
        ctx['budget'].reserve(self.kind, self.name)
        started = time.monotonic()
        event = {'node': 'invocation', 'kind': self.kind, 'name': self.name,
                 'case_hash': ctx['case_hash'], 'thread_id': ctx['thread_id'],
                 'ordinal': ctx['budget'].counts[self.kind]}
        try:
            if self.kind == 'tool':
                params = args[0] if args else kwargs.get('input')
                if not isinstance(params, dict) or set(params) != {'image_path'}:
                    raise ValueError('Unexpected classifier arguments')
                if not isinstance(params['image_path'], str):
                    raise ValueError('image_path must be a string')
                path = Path(params['image_path']).resolve()
                if path not in ctx['allowed_images']:
                    raise ValueError('Tool image was not supplied for this question')
                event['image_sha256'] = classifier_utils.sha256_file(path)
                ctx['actual_tool_attempts'] += 1
            result = self.wrapped.invoke(*args, **kwargs)
            if self.kind == 'model':
                event['usage'] = numeric_usage(result)
                if event['usage'] is not None:
                    ctx['usage_records'].append(event['usage'])
                meta = getattr(result, 'response_metadata', None) or {}
                event['returned_model'] = meta.get('model_name')
                event['content_summary'] = summarize(getattr(result, 'content', ''))
                event['tool_calls'] = [
                    {'id': c.get('id'), 'name': c.get('name'),
                     'argument_keys': sorted(c.get('args',{})) if isinstance(c.get('args'),dict) else []}
                    for c in (getattr(result, 'tool_calls', None) or [])]
            else:
                try:
                    event['scores'] = classifier_utils.validate_scores(result, self.expected_labels)
                    event['tool_analysis_status'] = 'completed'
                    event['clinical_evidence'] = 'unknown'
                    ctx['validated_tool_returns'] += 1
                except (ValueError, TypeError, OverflowError):
                    event['tool_analysis_status'] = 'failed_or_invalid'
                event['observation_summary'] = summarize(result)
            event['execution'] = 'returned'
            return result
        except Exception as exc:
            event['execution'] = 'exception'
            event['error_type'] = type(exc).__name__
            raise
        finally:
            event['elapsed_ms'] = round((time.monotonic()-started)*1000)
            write_line(ctx['trace'], event)


def initial_messages(row, paths, detail):
    from langchain_core.messages import HumanMessage
    image_text = '\n'.join(f'Image located at {path}' for path in paths)
    prompt = ('Answer this question correctly using chain of thought reasoning and '
              'carefully evaluating choices. Solve using your own vision and reasoning and then '
              'use tools to complement your reasoning. Trust your own judgement over any tools.\n'
              + row['question'] + '\n' + image_text)
    content = [{'type':'text','text':prompt}]
    for path in paths:
        mime = mimetypes.guess_type(path.name)[0]
        if mime not in ('image/jpeg','image/png'):
            raise ValueError('Only JPEG and PNG images are supported')
        content.append({'type':'image_url','image_url':{
            'url':f'data:{mime};base64,'+base64.b64encode(path.read_bytes()).decode('ascii'), 'detail':detail}})
    return [HumanMessage(content=content)]


def run_question(Agent, tool, model, prompt, row, paths, args, trace):
    from langgraph.checkpoint.memory import MemorySaver
    from langchain_core.messages import HumanMessage
    case_hash = hashlib.sha256(str(row['question_id']).encode()).hexdigest()
    thread_id = str(uuid.uuid4())
    budget = CaseBudget(args.max_tool_calls,args.max_model_calls,args.max_case_seconds,trace)
    budget.case_hash, budget.thread_id = case_hash, thread_id
    ctx = {'budget':budget,'case_hash':case_hash,'thread_id':thread_id,'trace':trace,
           'allowed_images':set(paths),'actual_tool_attempts':0,'validated_tool_returns':0,'usage_records':[]}
    report = {'case_hash':case_hash,'thread_id':thread_id,'status':'running',
              'answer_letter':None,'final_content_summary':None}
    started = time.monotonic()
    try:
        agent = Agent(model, tools=[tool], checkpointer=MemorySaver(), system_prompt=prompt, log_tools=False)
        agent.model = TrackedInvoke(agent.model,'model','llm',ctx)
        agent.tools = {tool.name:TrackedInvoke(tool,'tool',tool.name,ctx,tool.model.pathologies)}
        messages = initial_messages(row,paths,args.image_detail)
        phases = [messages]
        if args.answer_mode == 'two-stage':
            phases.append([HumanMessage(content=FOLLOWUP)])
        final = None
        for phase_index, phase_messages in enumerate(phases,1):
            final = None
            for event in agent.workflow.stream({'messages':phase_messages},
                    {'configurable':{'thread_id':thread_id},'recursion_limit':args.recursion_limit}):
                for node, value in event.items():
                    for message in value.get('messages',[]):
                        if node == 'process' and not (getattr(message,'tool_calls',None) or []):
                            final = message.content
                        if node == 'execute':
                            write_line(trace,{'node':'tool_message','case_hash':case_hash,'thread_id':thread_id,
                                'phase':phase_index,'tool_call_id':getattr(message,'tool_call_id',None),
                                'tool_name':getattr(message,'name',None),
                                'observation_summary':summarize(getattr(message,'content',''))})
        report['final_content_summary'] = summarize(final)
        report['answer_letter'] = answer_letter(final)
        report['status'] = 'completed' if report['answer_letter'] else 'invalid_answer'
    except Exception as exc:
        report['status'] = 'budget_exceeded' if isinstance(exc,BudgetExceeded) else 'failed'
        report['error_type'] = type(exc).__name__
    report.update(call_counts=dict(budget.counts),actual_tool_attempts=ctx['actual_tool_attempts'],
                  validated_tool_returns=ctx['validated_tool_returns'],
                  tool_execution_verified=ctx['validated_tool_returns']>0,
                  usage_records=ctx['usage_records'], elapsed_seconds=time.monotonic()-started)
    report['observed_usage_sum'], report['usage_complete'] = aggregate_usage(
        ctx['usage_records'], budget.counts['model'])
    report['actual_cost_usd'] = None
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('repo','input','images-root','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--model',required=True)
    p.add_argument('--base-url',default=os.environ.get('OPENAI_BASE_URL','https://api.openai.com/v1'))
    p.add_argument('--api-key-stdin',action='store_true',help='Read one key line from stdin; never saved')
    p.add_argument('--device',default='cuda:0')
    p.add_argument('--max-cases',type=int,default=1)
    p.add_argument('--max-tool-calls',type=int,default=2)
    p.add_argument('--max-model-calls',type=int,default=4)
    p.add_argument('--max-case-seconds',type=float,default=180)
    p.add_argument('--request-timeout-seconds',type=float,default=60)
    p.add_argument('--max-output-tokens',type=int,default=512)
    p.add_argument('--recursion-limit',type=int,default=12)
    p.add_argument('--temperature',type=float,default=0.2)
    p.add_argument('--answer-mode',choices=['two-stage','single-stage'],default='two-stage')
    p.add_argument('--image-detail',choices=['auto','low','high'],default='auto')
    p.add_argument('--require-tool-call',action='store_true')
    a=p.parse_args(argv)
    if not 1<=a.max_cases<=3 or a.max_tool_calls<0 or a.max_model_calls<1 or a.max_output_tokens<1 or a.recursion_limit<1:
        p.error('max-cases must be 1..3; invocation/token/recursion limits must be valid')
    if any(not math.isfinite(x) or x<=0 for x in (a.max_case_seconds,a.request_timeout_seconds)):
        p.error('Time limits must be finite and positive')
    url=urlsplit(a.base_url)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        p.error('Use an HTTPS API base URL without credentials/query/fragment')
    key=sys.stdin.readline().strip() if a.api_key_stdin else os.environ.get('OPENAI_API_KEY','')
    if not key:p.error('API key is absent')
    # Only process environment; neither files nor output contain this value.
    os.environ['OPENAI_API_KEY']=key
    repo,root,output=(x.resolve() for x in (a.repo,a.images_root,a.output))
    rows=load_inputs(a.input,a.max_cases)
    selected=[]
    for row in rows:
        paths=image_paths(row,root)
        if len(paths)>4 or sum(x.stat().st_size for x in paths)>20*1024*1024 or len(row['question'])>32000:
            p.error('Smoke input exceeds the bounded image/question size')
        selected.append((row,paths))
    output.mkdir(parents=True,exist_ok=False)
    (output/'.gitignore').write_text('*\n',encoding='utf-8')
    manifest={'schema_version':1,'kind':'restricted_single_tool_agent_smoke','status':'running',
        'started_utc':datetime.now(timezone.utc).isoformat(),'model_requested':a.model,
        'provider_host':url.hostname,'provider_path':url.path,'source':classifier_utils.git_info(repo),
        'input_sha256':classifier_utils.sha256_file(a.input),'system_prompt_sha256':None,
        'answer_mode':a.answer_mode,'temperature':a.temperature,'image_detail':a.image_detail,
        'device_requested':a.device,'tool_model_name':classifier_utils.MODEL_NAME,
        'max_cases':a.max_cases,'max_tool_calls':a.max_tool_calls,'max_model_calls':a.max_model_calls,
        'max_case_seconds':a.max_case_seconds,'max_output_tokens':a.max_output_tokens,
        'request_timeout_seconds':a.request_timeout_seconds,'provider_retries':0,
        'protocol_deviations':DEVIATIONS,'environment':classifier_utils.versions(),
        'limitations':['Dollar cost is not hard limited; provider usage may be absent.',
            'Per-call deadline checks cannot cancel in-flight local tools.',
            'Weight initialization downloads and costs occur outside per-question call budgets.']}
    results=[]
    try:
        os.chdir(output)
        with open(os.devnull,'w') as sink,redirect_stdout(sink),redirect_stderr(sink):
            Agent=module_from_file('_medrax_single_agent',repo/'medrax/agent/agent.py').Agent
            cls=module_from_file('_medrax_single_classifier',repo/'medrax/tools/classification.py').ChestXRayClassifierTool
            utils=module_from_file('_medrax_single_utils',repo/'medrax/utils/utils.py')
            prompt=utils.load_prompts_from_file(str(repo/'medrax/docs/system_prompts.txt'))['MEDICAL_ASSISTANT']
            manifest['system_prompt_sha256']=hashlib.sha256(prompt.encode()).hexdigest()
            manifest['agent_sha256']=classifier_utils.sha256_file(repo/'medrax/agent/agent.py')
            from langchain_openai import ChatOpenAI
            for package in ('langgraph','langchain-openai','openai','python-dotenv'):
                manifest['environment'][package]=importlib.metadata.version(package)
            tool=cls(model_name=classifier_utils.MODEL_NAME,device=a.device)
            model=ChatOpenAI(model=a.model,base_url=a.base_url,api_key=key,temperature=a.temperature,
                top_p=0.95,timeout=a.request_timeout_seconds,max_retries=0,max_tokens=a.max_output_tokens)
            with (output/'trace.jsonl').open('x',encoding='utf-8') as trace:
                for row,paths in selected:results.append(run_question(Agent,tool,model,prompt,row,paths,a,trace))
        manifest['status']='completed' if all(r['status']=='completed' for r in results) else 'failed_or_incomplete'
        if a.require_tool_call and not any(r['tool_execution_verified'] for r in results):
            manifest['status']='tool_call_not_verified'
    except Exception as exc:
        manifest.update(status='failed',error_type=type(exc).__name__)
    finally:
        key=''
        manifest['loaded_module_versions']=classifier_utils.loaded_module_versions()
        manifest['finished_utc']=datetime.now(timezone.utc).isoformat()
        manifest['question_results']=results
        manifest['verified_tool_returns']=sum(r['validated_tool_returns'] for r in results)
        manifest['clinical_correctness_verified']=False
        with (output/'summary.json').open('x',encoding='utf-8') as f:json.dump(manifest,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({'status':manifest['status'],'questions':len(results),
                     'verified_tool_returns':manifest['verified_tool_returns'],'summary_file':'summary.json'}))
    return 0 if manifest['status']=='completed' else 1

if __name__=='__main__':raise SystemExit(main())
