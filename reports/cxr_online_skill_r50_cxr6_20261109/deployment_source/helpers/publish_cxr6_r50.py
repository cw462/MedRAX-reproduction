"""Explicit R50 publication phases only after real full results and review.

No inference/scoring/exports/old audits or forced push. User waived additional
post-push verification; pre-push main-base protection remains mandatory.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path,PurePosixPath
import re
import subprocess
from urllib.parse import unquote,urlsplit

import finalize_r50_report as final_report

ROOT=Path(__file__).resolve().parents[1]
REPORT_REL='reports/cxr_online_skill_r50_cxr6_20261109'
REPORT=ROOT/REPORT_REL
RECEIPTS=ROOT/'local_assets/r50_cxr6_publication'
MANIFEST=REPORT/'PUBLICATION_MANIFEST.json'
EXPECTED_BASE='3ab0a927526e0910328b8db2503ac0fdc0e10036'
SOURCE_NAMES=('cxr_online_primitives_r50.py','online_memory_r50.py','prepare_feedback_r50.py',
 'run_online_skill_r50.py','skill_services_r50.py','skill_lifecycle_r50.py','skill_evolve_r50.py','skill_prompts_r50.py',
 'r50_baseline_controls.py','maira_guard_worker_r50.py','maira_eos_guard_r50.py','score_online_skill_r50.py',
 'export_online_skill_r50.py','verify_public_online_skill_r50.py','r50_recovery_evidence.py',
 'r50_failure_observation.py','r50_services_amended.py','r50_run_amended.py')
TEST_NAMES=('test_cxr6_r50.py','test_tool_archives_r50.py','test_postprocessing_r50.py',
 'test_public_evidence_r50.py','test_final_report_r50.py','test_publisher_r50.py')
TEST_NAMES=TEST_NAMES+('test_source_package_r50.py',)
TEST_NAMES=TEST_NAMES+('test_recovery_evidence_r50.py',)
TEST_NAMES=TEST_NAMES+('test_r50_failure_observation.py',)
SCRIPTS={'experiments/'+x for x in SOURCE_NAMES}|{'tests/'+x for x in TEST_NAMES}
INDEXES=set(final_report.INDEXES)
TEXT_SUFFIXES={'.py','.json','.jsonl','.md','.txt','.log','.pid','.exitcode','.yaml','.yml','.toml','.sh','.ps1','.csv','.patch'}
IMAGE_SUFFIXES={'.png','.jpg','.jpeg','.webp'}
FORBIDDEN_SUFFIXES={'.pt','.pth','.safetensors','.ckpt','.onnx','.npy','.npz','.pkl','.pickle','.zip','.gz','.tar','.exe','.dll','.pyd','.pem','.key'}
SECRET=re.compile(r'\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b|\bBearer\s+[A-Za-z0-9._~+/=-]{12,}|-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----')
CREDENTIAL_FIELD=re.compile(r'''(?i)["'](?:api[_-]?key|authorization|password|client[_-]?secret|access[_-]?token)["']\s*:\s*["']([^"'\r\n]{8,})["']''')
_PARENTS={}


def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def command(args,data=None):
    p=subprocess.run(args,cwd=ROOT,input=data,capture_output=True)
    if p.returncode:raise RuntimeError('command_failed:'+repr(args)+'\n'+p.stderr.decode('utf-8','replace'))
    return p.stdout
def names(data):return {x.decode('utf-8') for x in data.split(b'\0') if x}
def staged():return names(command(['git','diff','--cached','--name-only','-z']))
def head():return command(['git','rev-parse','HEAD']).decode().strip()
def remote_main():
    lines=command(['git','ls-remote','origin','refs/heads/main']).decode().splitlines()
    if len(lines)!=1 or len(lines[0].split())!=2:raise ValueError('remote_main_not_unique')
    return lines[0].split()[0]
def require_base(base):
    local,remote=head(),remote_main()
    if local!=base or remote!=base:raise ValueError(f'main_base_changed_stop_no_force: expected={base} local={local} remote={remote}')


def allowed_path(relative):
    path=PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative or '\0' in relative:
        raise ValueError('unsafe_publication_path')
    if relative not in SCRIPTS|INDEXES and not relative.startswith(REPORT_REL+'/'):raise ValueError('outside_R50_allowlist')
    if any(p in ('.git','.aris','.secrets','local_assets','review-stage','__pycache__','hf_modules') for p in path.parts):
        raise ValueError('private_or_unrelated_publication_path')
    suffix=path.suffix.lower()
    if suffix in FORBIDDEN_SUFFIXES or (suffix=='.bin' and 'invalid_request_image_bytes' not in path.parts):raise ValueError('weight_or_unrelated_binary_excluded')
    if suffix not in TEXT_SUFFIXES|IMAGE_SUFFIXES|{'.bin'} and path.name!='exitcode':raise ValueError('unapproved_publication_file_type')
    return ROOT/relative


def source_file(relative):
    target=allowed_path(relative)
    if not target.is_file() or target.is_symlink():raise ValueError('missing_or_symlink_publication_file:'+relative)
    if target.parent not in _PARENTS:_PARENTS[target.parent]=target.parent.resolve()
    if not _PARENTS[target.parent].is_relative_to(ROOT):raise ValueError('resolved_publication_file_outside_repository')
    return target


def outside_index_block(text):
    a,b=final_report.INDEX_START,final_report.INDEX_END
    if text.count(a)!=text.count(b) or text.count(a)>1:raise ValueError('ambiguous_R50_index_block')
    return re.sub(re.escape(a)+r'.*?'+re.escape(b),'',text,flags=re.S).rstrip()


def require_index_scope():
    for relative in INDEXES:
        current=(ROOT/relative).read_text(encoding='utf-8-sig')
        previous=command(['git','show','HEAD:'+relative]).decode('utf-8-sig')
        if final_report.INDEX_START not in current or outside_index_block(current)!=outside_index_block(previous):
            raise ValueError('unrelated_index_edits_outside_R50_block:'+relative)


def readiness():
    loaded,review,_,source=final_report.complete_gate()
    marker=read(final_report.PREP/'final_report.completed.json')
    if marker.get('status')!='completed' or marker.get('case_pages')!=848 or marker.get('actual_result_review_session')!=review['session_id']:
        raise ValueError('actual_completed_final_report_required')
    resource=read(REPORT/'RESOURCE_SUMMARY.json')
    if resource.get('status')!='complete' or resource.get('final_controller_exit')!=0 or resource.get('Skill_only_causality_clinical_or_official_SOTA_claim') is not False:
        raise ValueError('truthful_completed_resource_report_required')
    for name in ('README.md','CASE_INDEX.md','RESULT_TABLES.md','REPRODUCTION.md','PROTOCOL.json','TESTS.md',
                 'deployment_source/PROVENANCE.md','deployment_source/COPY_MAP.json'):
        if not (REPORT/name).is_file():raise ValueError('finished_R50_document_or_actual_source_snapshot_missing:'+name)
    if len(list((REPORT/'cases').glob('*/*.md')))!=848:raise ValueError('full_848_case_pages_required')
    copy_map=read(REPORT/'deployment_source/COPY_MAP.json')
    actual_entries=[v for v in copy_map.get('files',[]) if v.get('kind')=='actual_CODE']
    postprocessing={'score_online_skill_r50.py','export_online_skill_r50.py','verify_public_online_skill_r50.py','r50_recovery_evidence.py'}
    required_runtime={'experiments/'+n for n in SOURCE_NAMES if n not in postprocessing}|{
      'experiments/run_cxr_vqa_toolsets.py','experiments/cxr_vqa_tool_worker.py','experiments/cxr_vqa_extended_backends.py',
      'configs/cxr_vqa_tool_worker_gpu.json'}
    if not required_runtime<=set(source.get('files',[])):raise ValueError('required_actual_runtime_source_or_GPU_config_missing')
    if {v.get('source_relative') for v in actual_entries}!=set(source.get('files',[])) or len(actual_entries)!=source.get('count'):
        raise ValueError('all_actual_deployed_sources_must_be_in_public_copy_map')
    control_entries=[v for v in copy_map.get('files',[]) if v.get('kind')=='control']
    required_controls={'queue_controller.py','health_controller.py','EXECUTION_REVIEW_READY.json','EVALUATION_PROTOCOL.json',
      'configs/runtime.json','configs/protocol.json','configs/chexbench.json','configs/slake.json','configs/vqarad.json',
      'configs/chexbench_order.json','jobs/controller.started.json','jobs/controller.exitcode','jobs/chexbench.exitcode'}
    if not resource['native_controller_completion'].get('protocol_amendment_used'):
        required_controls|={'jobs/'+ds+'.exitcode' for ds in final_report.DATASETS}
    else:
        required_controls|={'queue_controller_amendment003.py','protocol_amendment003.json','amendment003_user_approval.json',
          'jobs/protocol_amendment003.json','jobs/controller_amendment003.started.json','jobs/controller_amendment003.exitcode',
          *('jobs/'+ds+'_amendment003.exitcode' for ds in final_report.DATASETS)}
    if resource['native_controller_completion']['technical_continuation_used']:
        for i,_ in enumerate(resource['native_controller_completion']['recovery_ids'],1):
            tag=str(i).zfill(3)
            required_controls|={'queue_controller_recovery'+tag+'.py','jobs/technical_continuation'+tag+'.json',
              'jobs/controller_recovery'+tag+'.started.json','jobs/controller_recovery'+tag+'.exitcode','jobs/chexbench_recovery'+tag+'.exitcode'}
    if not required_controls<={v.get('source_relative') for v in control_entries}:raise ValueError('executed_control_and_config_snapshots_missing')
    for entry in copy_map['files']:
        relative=PurePosixPath(entry['published'])
        if relative.is_absolute() or '..' in relative.parts or not (REPORT/'deployment_source'/entry['published']).is_file():
            raise ValueError('mapped_actual_source_missing_or_outside_source_snapshot')
    return {'arm':final_report.ARM,'review_session_id':review['session_id'],
      'original_controller_exit':resource['original_controller_exit'],'final_controller_exit':resource['final_controller_exit'],
      'dataset_scores':{ds:{'correct':d['summary']['arms'][final_report.ARM]['correct'],'n':d['summary']['questions']} for ds,d in loaded.items()},
      'whole_public_reproduction_passed':True,'all_848_case_pages':True,'not_a_new_inference_scoring_or_review':True}


def text_has_secret(value):
    if SECRET.search(value):return True
    return any(not m.group(1).startswith(('[REDACTED]','<','YOUR_','os.environ','getenv(')) for m in CREDENTIAL_FIELD.finditer(value))


def local_reference(value,document):
    value=value.strip().strip('<>')
    if not value or value.startswith(('#','http://','https://','mailto:','data:')):return None
    url=urlsplit(value)
    if url.scheme:raise ValueError('nonpublic_outgoing_reference_scheme')
    path=unquote(url.path)
    if not path:return None
    target=(document.parent/path).resolve()
    if not target.is_relative_to(ROOT):raise ValueError('outgoing_link_outside_repository')
    if not target.exists():raise ValueError('outgoing_local_link_missing:'+str(document.relative_to(ROOT))+':'+path)
    return target


def values_in(value):
    if isinstance(value,str):yield value
    elif isinstance(value,dict):
        for v in value.values():yield from values_in(v)
    elif isinstance(value,list):
        for v in value:yield from values_in(v)


def prepare(args):
    if MANIFEST.exists() or (RECEIPTS/'prepared.json').exists():raise ValueError('R50_publication_already_prepared_inspect')
    completed=readiness();require_index_scope()
    if staged():raise ValueError('unrelated_preexisting_index_work')
    require_base(args.expected_base)
    paths=sorted(SCRIPTS|INDEXES|{p.relative_to(ROOT).as_posix() for p in REPORT.rglob('*') if p.is_file()}|{MANIFEST.relative_to(ROOT).as_posix()})
    for relative in paths:
        if relative!=MANIFEST.relative_to(ROOT).as_posix():source_file(relative)
        else:allowed_path(relative)
    write(MANIFEST,{'status':'prepared_explicit_allowlist','scope':'complete_R50_CXR6_evidence_and_results',
      'files':paths,'count':len(paths),'completion':completed,'remote_verification_after_push':'waived_by_user'})
    write(RECEIPTS/'allowlist.json',paths)
    write(RECEIPTS/'prepared.json',{'utc':now(),'expected_base':args.expected_base,'allowlist_count':len(paths),
      'full_saved_readiness_gate':completed,'new_model_or_score_calls':0})
    print(json.dumps({'prepared':True,'allowlist_count':len(paths),'actual_generation_or_score_calls':0}))


def check(args):
    prepared=read(RECEIPTS/'prepared.json');paths=read(RECEIPTS/'allowlist.json');stats={'json':0,'jsonl_rows':0,'markdown_links':0,'image_links':0}
    if not prepared.get('full_saved_readiness_gate'):raise ValueError('actual_completed_prepare_required')
    for relative in paths:
        p=source_file(relative)
        if p.stat().st_size>100_000_000:raise ValueError('hosting_file_limit_exceeded:'+relative)
        if p.suffix.lower() not in TEXT_SUFFIXES and p.name!='exitcode':continue
        body=p.read_text(encoding='utf-8-sig')
        if text_has_secret(body):raise ValueError('credential_literal_in_outgoing_file:'+relative)
        values=None
        if p.suffix=='.json':values=json.loads(body);stats['json']+=1
        elif p.suffix=='.jsonl':
            values=[json.loads(x) for x in body.splitlines() if x.strip()];stats['jsonl_rows']+=len(values)
        elif p.suffix=='.md':
            visible=re.sub(r'```[^\n]*\n.*?```','',body,flags=re.S)
            for url in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)\)',visible):
                local_reference(url,p);stats['markdown_links']+=1
        if values is not None:
            for value in values_in(values):
                if ('assets/' in value or 'invalid_request_image_bytes/' in value) and not any(c.isspace() for c in value) \
                   and Path(urlsplit(value).path).suffix.lower() in IMAGE_SUFFIXES|{'.bin'}:
                    local_reference(value,p);stats['image_links']+=1
    write(RECEIPTS/'content_check.json',{'utc':now(),'status':'passed','files':len(paths),**stats,
      'outgoing_allowlist_only':True,'no_model_score_or_hash_checks':True,'original_readiness_gate_reused':True})
    print(json.dumps({'outgoing_content_check':'passed','files':len(paths),**stats}))


def whitespace_check():
    command(['git','-c','core.whitespace=-blank-at-eol,-blank-at-eof','diff','--cached','--check','--',
      *sorted(SCRIPTS|INDEXES),REPORT_REL+'/README.md'])


def stage(args):
    if read(RECEIPTS/'content_check.json').get('status')!='passed':raise ValueError('outgoing_content_check_required')
    require_index_scope();paths=read(RECEIPTS/'allowlist.json');allowed=set(paths)
    if not staged()<=allowed:raise ValueError('unrelated_preexisting_index_work')
    pathspec=RECEIPTS/'literal_pathspec.nul';pathspec.write_bytes(b'\0'.join(p.encode('utf-8') for p in paths)+b'\0')
    command(['git','--literal-pathspecs','add','-f','--pathspec-from-file='+str(pathspec),'--pathspec-file-nul'])
    actual=staged()
    if not actual<=allowed or not actual:raise ValueError('unexpected_or_empty_staged_scope')
    manifest=read(MANIFEST);manifest.update(status='staged_explicit_allowlist',git_index_paths=sorted(actual),git_index_path_count=len(actual))
    write(MANIFEST,manifest);command(['git','add','--',MANIFEST.relative_to(ROOT).as_posix()])
    if staged()!=actual:raise ValueError('staged_manifest_membership_changed')
    whitespace_check();write(RECEIPTS/'stage.json',{'utc':now(),'files':sorted(actual),'count':len(actual),'unrelated_user_edits_staged':False})
    print(json.dumps({'explicit_stage':'passed','files':len(actual)}))


def commit_push(args):
    prepared=read(RECEIPTS/'prepared.json');scope=read(RECEIPTS/'stage.json');base=prepared['expected_base'];receipt=RECEIPTS/'commit.json'
    if receipt.exists():
        commit=read(receipt)['commit']
        if head()!=commit or remote_main() not in (base,commit):raise ValueError('own_commit_or_remote_changed_stop')
    else:
        require_base(base)
        if staged()!=set(scope['files']):raise ValueError('index_changed_after_explicit_stage')
        whitespace_check();command(['git','commit','-m',args.message]);commit=head()
        if command(['git','rev-parse','HEAD^']).decode().strip()!=base:raise ValueError('commit_parent_changed')
        if names(command(['git','diff-tree','--no-commit-id','--name-only','-r','-z',commit]))!=set(scope['files']):raise ValueError('committed_scope_changed')
        write(receipt,{'utc':now(),'commit':commit,'base':base,'git_index_path_count':scope['count']})
    current=remote_main()
    if current not in (base,commit):raise ValueError('remote_main_changed_stop_no_force')
    if current!=commit:command(['git','push','origin','HEAD:refs/heads/main'])
    write(RECEIPTS/'push.completed.json',{'utc':now(),'status':'push_accepted','commit':commit,
      'report_url':'https://github.com/cw462/MedRAX-reproduction/blob/main/'+REPORT_REL+'/README.md',
      'additional_post_push_remote_verification_performed':False,'user_waiver':'远端核验（不需要远端核验）',
      'pre_push_main_base_protection_retained':True,'new_inference_scoring_or_review_from_publication':0})
    print(json.dumps({'push':'accepted','commit':commit,'additional_post_push_remote_verification':'waived_by_user'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['prepare','check','stage','commit-push'])
    p.add_argument('--expected-base',default=EXPECTED_BASE);p.add_argument('--message',default='Publish R50 CXR6 complete evidence, results and reproducibility')
    a=p.parse_args();{'prepare':prepare,'check':check,'stage':stage,'commit-push':commit_push}[a.mode](a)
