"""Use the pinned MedRAX graph with the shared model transport and tool workers."""

import ast
from functools import partial
import importlib.util
from pathlib import Path
import subprocess

from run_cxr_vqa_toolsets import content, parse_final, read


COMMIT = 'dae30e2f136ef0b2a40885a4c335386e9ffad052'
OFFICIAL_FILES = ('medrax/agent/agent.py', 'medrax/utils/utils.py', 'medrax/docs/system_prompts.txt', 'interface.py')
TOOL_ARGUMENTS = {
    'chest_xray_classifier': {},
    'chest_xray_segmentation': {'organs': (list[str] | None, None)},
    'llava_med_qa': {'question': (str, ...)},
    'chest_xray_expert': {'prompt': (str, ...), 'image_paths': (list[str] | None, None)},
    'chest_xray_report_generator': {},
    'xray_phrase_grounding': {'phrase': (str, ...)},
    'image_visualizer': {'title': (str | None, None), 'description': (str | None, None)},
    'dicom_processor': {'dicom_path': (str | None, None)},
}


def load_file(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OfficialMedRAX:
    def __init__(self, upstream):
        from importlib.metadata import version
        if version('langgraph') != '0.2.76':
            raise ValueError('Official stopping behavior requires LangGraph 0.2.76')
        rev = subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip()
        if rev != COMMIT:
            raise ValueError('Unexpected MedRAX checkout revision')
        subprocess.run(['git', '-C', str(upstream), 'diff', '--quiet', 'HEAD', '--', *OFFICIAL_FILES], check=True)
        self.agent_class = load_file(upstream/OFFICIAL_FILES[0], 'pinned_medrax_agent').Agent
        loader = load_file(upstream/OFFICIAL_FILES[1], 'pinned_medrax_prompts')
        self.system = loader.load_prompts_from_file(upstream/OFFICIAL_FILES[2])['MEDICAL_ASSISTANT']
        self.descriptions = {}
        for path in (upstream/'medrax/tools').glob('*.py'):
            for cls in ast.parse(path.read_text(encoding='utf-8')).body:
                if not isinstance(cls, ast.ClassDef):
                    continue
                fields = {stmt.target.id: stmt.value for stmt in cls.body
                          if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)}
                name = fields.get('name')
                if isinstance(name, ast.Constant) and name.value in TOOL_ARGUMENTS:
                    self.descriptions[name.value] = ast.literal_eval(fields['description'])

    def episode(self, row, arm, data_root, protocol, runtime, out, paid, tools):
        from langchain_core.messages import AIMessage, HumanMessage, convert_to_openai_messages
        from langchain_core.tools import StructuredTool
        from langchain_core.utils.function_calling import convert_to_openai_tool
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.errors import GraphRecursionError
        from pydantic import create_model

        allowed = {str((data_root / image).resolve()): image for image in row['images']}
        observations, steps = [], []
        model_calls, tool_choices = 0, 0

        class LedgerModel:
            def bind_tools(self, bound_tools):
                self.schemas = [convert_to_openai_tool(tool) for tool in bound_tools]
                return self

            def invoke(self, messages):
                nonlocal model_calls
                model_calls += 1
                if model_calls > protocol['main_call_limits']['O']:
                    raise ValueError('Official graph exceeded the verified model-call envelope')
                msg = paid.call(row, arm, model_calls, convert_to_openai_messages(messages), api_tools=self.schemas)
                return AIMessage(content=msg.get('content') or '', additional_kwargs={'tool_calls': msg.get('tool_calls') or []})

        def execute_tool(tool_name, image_path=None, **args):
            requested = args.pop('image_paths', None) or [args.pop('dicom_path', None) or image_path]
            if len(requested) != 1:
                return ['This deployed tool accepts one original image per execution.']
            selected = requested[0]
            if selected is None and len(allowed) == 1:
                selected = next(iter(allowed))
            if selected not in allowed:
                return ['Use exactly one of the original image paths supplied with this question.']
            if tool_name == 'dicom_processor' and Path(selected).suffix.lower() != '.dcm':
                return ['DICOM processing is unavailable for this original image format.']
            args = {k: v for k,v in args.items() if v is not None}
            if tool_name == 'chest_xray_expert':
                args['question'] = args.pop('prompt')
            call = {'tool': tool_name, 'args': args}
            if len(allowed) > 1:
                call['image_index'] = row['images'].index(allowed[selected])+1
            observed = tools.call(row, call, arm, len(observations)+1)
            observations.append(observed)
            raw = observed.get('raw_result_file')
            return read(raw) if raw and Path(raw).is_file() else observed.get('observation') or ['Tool result unavailable.']

        registered = []
        for name in runtime['arms']['O']['tools']:
            schema = create_model(name+'Input', image_path=(str | None, None), **TOOL_ARGUMENTS[name])
            registered.append(StructuredTool.from_function(
                func=partial(execute_tool, name), name=name, args_schema=schema,
                description=self.descriptions[name]))
        agent = self.agent_class(LedgerModel(), registered, checkpointer=MemorySaver(),
                                 system_prompt=self.system, log_tools=False)
        prompt = 'Return one JSON object with string fields answer (short direct answer) and reason (one short sentence).'
        image_paths = '\n'.join(f'Original image {i}: {name}' for i,name in enumerate(allowed, 1))
        messages = [HumanMessage(content=image_paths), HumanMessage(content=content(row, data_root)), HumanMessage(content=prompt)]
        final = None
        stop = 'official_end'
        try:
            for event in agent.workflow.stream({'messages': messages}, {'configurable': {'thread_id': row['question_id']}}):
                for node, output in event.items():
                    steps.append(node)
                    if node == 'process':
                        message = output['messages'][-1]
                        tool_choices += len(message.tool_calls) + len(message.invalid_tool_calls)
                        final = message.content if not message.tool_calls and not message.invalid_tool_calls else None
        except GraphRecursionError:
            final = None
            stop = 'official_graph_recursion_limit'
        return dict(parse_final(final), main_calls=model_calls, tool_calls=tool_choices,
                    observations=observations, graph_steps=len(steps), graph_nodes=steps, official_stop=stop)
