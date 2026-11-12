"""Use the pinned MemEvolve providers between R55 query and feedback."""

from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from types import ModuleType
from urllib.request import Request, urlopen


PROVIDERS = {
    'M1':'dilu', 'M2':'expel', 'M3':'memp',
    'M4':'agent_kb', 'M5':'cerebra_fusion_memory',
}
SOURCE = '078e18cb6153fdc5b888308349cb6771eb7bde8f'
MODEL_DIR = 'sentence-transformers_all-MiniLM-L6-v2'
MEMORY_CHARS = 6000


def utc():
    return datetime.now(timezone.utc).isoformat()


def plain(value):
    if isinstance(value, Enum):
        return value.value
    if type(value).__module__.startswith('numpy'):
        return value.tolist()
    raise TypeError(type(value).__name__)


def record(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, default=plain, allow_nan=False)
        f.write('\n')


def text(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=plain)


def question(row):
    return row['question']+'\nOptions: '+text(row['options'])


class AuditedModel:
    def __init__(self, root, key, fixture=None):
        self.root = root
        self.key = key
        self.fixture = fixture
        self.calls = 0
        self.failure = None
        self.scope = None

    def __call__(self, messages):
        if self.failure is not None:
            raise RuntimeError('unresolved_memory_model_request')
        if isinstance(messages, str):
            messages = [{'role':'user','content':messages}]
        if self.fixture is not None:
            return self.fixture(messages)
        phase, qid = self.scope
        self.calls += 1
        folder = self.root/qid/phase/str(self.calls)
        request = {'model':'deepseek-flash','messages':messages,'stream':False,
                   'thinking':{'type':'disabled'},'max_tokens':2048,'temperature':0}
        record(folder/'request.json', request)
        record(folder/'started.json', {'utc':utc()})
        t = time.monotonic()
        response = None
        try:
            req = Request('https://api.deepseek.com/chat/completions',
                          data=json.dumps(request, ensure_ascii=False, default=plain).encode('utf-8'),
                          headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'},
                          method='POST')
            with urlopen(req, timeout=180) as stream:
                raw = stream.read()
            (folder/'response.raw').write_bytes(raw)
            response = json.loads(raw)
            choice = response['choices'][0]
            content = choice['message']['content']
            if choice.get('finish_reason') != 'stop' or not isinstance(content,str) or not content.strip():
                raise ValueError('memory_model_returned_unusable_text')
        except Exception as error:
            self.failure = type(error).__name__
            record(folder/'result.json', {'utc':utc(),'response_received':(folder/'response.raw').is_file(),
                'usage':(response or {}).get('usage'),'error':self.failure,'elapsed_s':time.monotonic()-t})
            raise
        record(folder/'result.json', {'utc':utc(),'response_received':True,'usage':response.get('usage'),
               'model_returned':response.get('model'),'elapsed_s':time.monotonic()-t})
        return content


def provider_for(arm, runtime, model):
    from EvolveLab.config import get_memory_config
    from EvolveLab.memory_types import MemoryType, PROVIDER_MAPPING

    kind = MemoryType(PROVIDERS[arm])
    name, module = PROVIDER_MAPPING[kind]
    # Loading the selected source avoids importing unrelated generated-tool
    # backends from the eager provider package initializer.
    package_name = 'EvolveLab.providers'
    package = ModuleType(package_name)
    package.__path__ = [str(runtime/'EvolveLab/providers')]
    sys.modules.setdefault(package_name, package)
    module_name = package_name+'.'+module
    spec = importlib.util.spec_from_file_location(module_name,runtime/'EvolveLab/providers'/(module+'.py'))
    provider_module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = provider_module
    spec.loader.exec_module(provider_module)
    factory = getattr(provider_module,name)
    config = get_memory_config(kind)
    config['model'] = model
    if arm == 'M2':
        config['embedding_model'] = str(runtime/'models'/MODEL_DIR)
    if arm == 'M5':
        config['enable_tool_memory'] = False
    provider = factory(config=config)
    if arm == 'M1':
        # The raw-trajectory control keeps DiLu's store and 1-NN search.
        provider._summarize_trajectory_with_llm = provider._reconstruct_trajectory_string
    if provider.initialize() is not True:
        raise RuntimeError('memory_provider_initialization_failed:'+arm)
    return provider


class Memory:
    def __init__(self, arm, runtime, out, key, fixture=None):
        self.arm = arm
        self.out = out
        self.model = AuditedModel(out/'model_calls',key,fixture)
        self.provider = provider_for(arm,runtime,self.model)

    def checked(self):
        if self.model.failure is not None:
            raise RuntimeError('memory_model_failure:'+self.model.failure)

    def retrieve(self, row):
        from EvolveLab.memory_types import MemoryItemType, MemoryRequest, MemoryStatus

        q = row['question_id']
        folder = self.out/'episodes'/q
        self.model.scope = ('retrieve', q)
        query = question(row)
        record(folder/'retrieval.started.json', {'utc':utc(),'query':query,'phase':'begin'})
        native = self.provider.provide_memory(MemoryRequest(query=query, context='',status=MemoryStatus.BEGIN))
        self.checked()
        if any(x.type != MemoryItemType.TEXT for x in native.memories):
            raise ValueError('tool_memory_cannot_change_R55_toolset')
        items = [text(item.content) for item in native.memories]
        # Give both ExpeL retrieval tracks space under the same text budget.
        per_item = MEMORY_CHARS//max(1,len(items))
        content = '\n'.join(item[:per_item] for item in items)
        if content:
            content = ('Retrieved prior-case memory for method guidance. Historical answers, findings, '
                       'and side labels apply to their source cases. Verify the current image independently.\n'+content)
        result = {'utc':utc(),'provider':PROVIDERS[self.arm],'native':asdict(native),
                  'injected':content,'memory_chars':len(content),'items':len(items)}
        record(folder/'retrieval.json',result)
        return content

    def ingest(self, row, trace, feedback):
        from EvolveLab.memory_types import TrajectoryData

        q = row['question_id']
        pred = trace['prediction']
        assert feedback['saved_prediction'] == pred and feedback['timing'] == 'after_immutable_prediction'
        self.model.scope = ('ingest', q)
        messages = [{'role':'user','type':'task','content':question(row)}]
        for step in trace['steps']:
            messages.append({'role':'assistant','type':'action','content':text(step['response'])})
            for call in step.get('executed_calls',[]):
                observed = pred['observations'][call['observation_index']]
                observation = text(observed.get('observation'))
                if observation.startswith('data:image/'):
                    observation = '[image output retained in the R55 tool artifact]'
                messages.append({'role':'tool','type':'observation',
                                 'content':text(call['action'])+'\n'+observation[:2000]})
        annotation = feedback['reference_annotation']
        ref = annotation['answer']
        messages.append({'role':'user','type':'released_benchmark_feedback',
                         'content':'Historical reference: '+ref+'. '+row['options'][ref]})
        args = {'query':question(row),'trajectory':messages,
                'result':pred.get('answer') or '[no explicit answer]',
                'metadata':{'task_id':q,'full_query':question(row),'is_correct':bool(trace['reward']),
                            'status':'success','memory_feedback':{}}}
        folder = self.out/'episodes'/q
        record(folder/'ingest.started.json', {'utc':utc(),'trajectory':args})
        stored, info = self.provider.take_in_memory(TrajectoryData(**args))
        self.checked()
        record(folder/'ingest.json', {'utc':utc(),'accepted':bool(stored),'native_description':info,
                                    'prediction_saved_at':pred['prediction_saved_at'],
                                    'feedback_released_at':feedback['released_at']})


def load_runtime(runtime, arm_dir):
    sys.path[:0] = [str(runtime/'deps'),str(runtime)]
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    # Upstream defaults and Agent-KB's rebuild both use this relative path.
    os.chdir(arm_dir)
    storage = arm_dir/'storage'
    storage.mkdir(exist_ok=True)
    models = storage/'models'
    if not models.exists():
        models.symlink_to(runtime/'models',target_is_directory=True)
    assert models.resolve()==(runtime/'models').resolve()
    import sentence_transformers
    factory = sentence_transformers.SentenceTransformer

    def cpu_sentence_transformer(*args, **kwargs):
        kwargs['device'] = 'cpu'
        return factory(*args, **kwargs)

    sentence_transformers.SentenceTransformer = cpu_sentence_transformer


def main():
    root,arm,data,refs,runtime= sys.argv[1:]
    root, data, refs, runtime = map(Path,(root,data,refs,runtime))
    arm_dir = root/arm
    out = arm_dir/'generation'
    sys.path.insert(0,str(root/'code/experiments'))
    from online_memory_r49 import ReferenceVault, read
    from run_cxr_vqa_toolsets import exclusive_lock
    import run_online_skill_r54 as engine
    from skill_services_r55 import Services

    manifest = read(out/'manifest.json')
    engine.ARM = manifest['arm']
    assert len(manifest['inputs'])==60 and manifest['memory_provider']==PROVIDERS[arm]
    assert len(manifest['runtime']['arms']['M']['tools'])==11
    main_key, memory_key = [sys.stdin.readline().strip() for _ in range(2)]
    assert main_key and memory_key
    load_runtime(runtime,arm_dir)
    with exclusive_lock(out/'.online.lock'):
        memory=Memory(arm,runtime,out/'external_memory',memory_key)
        service=Services(manifest['config'],manifest['protocol'],manifest['runtime'],out/'services',
                         main_key,manifest['embedding_model'],manifest['embedding_base_url'])
        engine.run_stream(manifest['inputs'],manifest['order'],data,out,service,
                          ReferenceVault(refs,manifest['reference_files']),manifest['runtime']['arms']['M']['tools'],
                          evolver=engine.disabled_evolve,external_memory=memory)
    receipts = out/'external_memory/episodes'
    assert len(list(receipts.glob('*/retrieval.json')))==len(list(receipts.glob('*/ingest.json')))==60
    record(arm_dir/'memory.completed.json',{'questions':60,'provider':PROVIDERS[arm],
                                           'memory_model_calls':memory.model.calls,'utc':utc()})


def smoke():
    from reference_model_fixture import completion_for, message_text

    arm, runtime, work, sample = sys.argv[2:]
    runtime, work, sample = map(Path,(runtime,work,sample))
    work.mkdir()
    load_runtime(runtime,work)
    fixtures = []

    def fixture(messages):
        route, response = completion_for(message_text(messages))
        if route == 'unmapped':
            raise ValueError('unmapped_fixture_prompt')
        fixtures.append(route)
        return response

    row, trace, feedback = json.loads(sample.read_text(encoding='utf-8'))
    memory = Memory(arm,runtime,work/'audit','',fixture)
    assert not memory.retrieve(row)
    memory.ingest(row,trace,feedback)
    q = row['question_id']
    ep = work/'audit/episodes'/q
    assert json.loads((ep/'ingest.json').read_text())['accepted'] is True
    # The pinned fixed response stores a feather-capacity graph. Query that
    # fixture topic to exercise native thresholding and graph recall.
    probe = dict(row,question_id=q+'_fixture_recall')
    if arm == 'M5':
        probe['question'] = 'Calculate total shuttlecock feathers and the minimum goose supplier capacity.'
    assert memory.retrieve(probe)
    record(work/'smoke.json',{'provider':PROVIDERS[arm],'fixture_calls':fixtures,
                              'new_external_calls':0,'closed_loop_retrieved':True})


if __name__=='__main__':
    if sys.argv[1] == 'smoke':
        smoke()
    else:
        main()
