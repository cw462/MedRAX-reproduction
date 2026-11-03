"""Call official config, read/write/assess/govern and rendering implementations.

Linux runtime required by upstream fcntl storage. Paid services must be supplied
by the existing budget-aware transport; this module creates no network clients.
Actual A0 runner binding is deliberately unresolved until its run is identified.
"""
from contextlib import contextmanager,ExitStack
import importlib
from pathlib import Path
import sys
from unittest.mock import patch

UPSTREAM_COMMIT='a640474590e384669dd71b657c441264beef73d2'
REPO=Path(__file__).resolve().parents[2]
UPSTREAM=REPO/'third_party/skemex'


def official_modules():
    if sys.platform=='win32':raise RuntimeError('official_skill_storage_requires_Linux; source retained unmodified')
    sys.path.insert(0,str(UPSTREAM/'src'))
    names=('config','types','storage','retrieve','encode','utility','governance','buffer','prompts','trajectory','categories')
    return {name:importlib.import_module('medmem_agent.evolution.'+name) for name in names}


@contextmanager
def budgeted_llm_bindings(modules,factory):
    """Route every official LLM call to the injected accounted implementation."""
    if factory is None:raise ValueError('budgeted_client_factory_required_no_direct_official_API')
    with ExitStack() as stack:
        for name in ('retrieve','encode','governance','categories'):
            stack.enter_context(patch.object(modules[name],'build_llm',factory))
        yield


def components(workspace,source_fold,embeddings,llm_factory,read_only=False,model=None):
    if source_fold not in ('A','B'):raise ValueError('source_fold_required')
    if embeddings is None or llm_factory is None or not model:
        raise ValueError('explicit_budgeted_services_and_matched_A0_model_required')
    m=official_modules()
    cfg=m['config'].load_evo_config(UPSTREAM/'configs/evolution/default.json',UPSTREAM/'configs/evolution/offline.json')
    # Default/offline experiment values are parsed first, not class defaults.
    cfg.storage.root_dir='fold_'+source_fold
    cfg.storage.experiment_root='fold_'+source_fold+'/memory'
    cfg.encode.model=model;cfg.retrieval.pre_screen.model=model
    cfg.categories.classifier_model=model
    store=m['storage'].SkillStore(repo_root=str(workspace),evo_config=cfg,read_only=read_only)
    if not read_only:store.ensure_initialized()
    return {'modules':m,'config':cfg,'store':store,'llm_factory':llm_factory,
        'retriever':m['retrieve'].SkillRetriever(store,embeddings,cfg),
        'encoder':m['encode'].TrajectoryEncoder(store,cfg),
        'utility':m['utility'].UtilityUpdater(store,cfg),
        'governance':m['governance'].SkillGovernance(store,embeddings,cfg),
        'buffer':m['buffer'].GatedTrajectoryBuffer(cfg.buffer)}


def read_once(runtime,query,categories,available_tools,current_window):
    with budgeted_llm_bindings(runtime['modules'],runtime['llm_factory']):
        return runtime['retriever'].retrieve(query,categories,current_window,available_tools)


def assess_source_window(runtime,trajectories,source_case_ids,current_window,tools_text=''):
    if runtime['store'].read_only:raise ValueError('target_fold_cannot_update_library')
    allowed=set(source_case_ids)
    for t in trajectories:
        if t.metadata.get('case_id') not in allowed or not t.metadata.get('prediction_saved_before_feedback'):
            raise ValueError('source_case_and_prediction_before_feedback_required')
    encodes={};created=[]
    runtime['buffer'].clear()
    for trajectory in trajectories:runtime['buffer'].add(trajectory)
    with budgeted_llm_bindings(runtime['modules'],runtime['llm_factory']):
        for trajectory in runtime['buffer'].all_items():
            encoded=runtime['encoder'].encode(trajectory,tools_text)
            encodes[trajectory.id]=encoded
            skill=runtime['governance'].apply_encode_result(encoded)
            if skill:created.append(skill.to_dict())
        utility=runtime['utility'].update_window(trajectories,encodes,current_window)
        governed=runtime['governance'].manage() if (current_window+1)%runtime['config'].governance.manage_every_n_windows==0 else None
    return {'encode_results':{k:v.__dict__ for k,v in encodes.items()},'created':created,'utility':utility,'governance':governed}
