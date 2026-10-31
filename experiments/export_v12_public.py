"""Offline, allowlisted publication of a completed and scored V12 run.

Defaults: local_assets/v12_ab60 -> reports/v12/results. No inference, label-file
access, ledger access, network connection, credential lookup, or Git operation.
Use --image-root for an original-image cache and --path-map PRIVATE=LOCAL for a
downloaded artifact mirror. Existing V11 originals are searched by exact name.
Missing media must be fetched separately; this script never guesses a remote.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'experiments'))
from export_v11_cases import DATASET, DATASET_URL, REVISION, read_json, write_json

ROOT_JSON = ('metrics.json', 'per_question.json', 'effective_config.json', 'selection.json',
             'status.json', 'runtime_tools.json', 'retrieval_runtime.json', 'fatal_error.json')
ROOT_JSONL = ('initial_results.jsonl', 'branch_results.jsonl', 'execution.trace.jsonl')
INITIAL_FILES = ('terminal.json', 'context.json', 'request_started.json', 'observation.json',
                 'initial_request.json', 'initial_messages.json')
BRANCH_FILES = ('terminal.json', 'context.json', 'request_started.json', 'retrieval.json',
                'action_plan.json', 'tool_records.jsonl', 'images.json', 'new_observation.json',
                'plan_request.json', 'plan_messages.json', 'targeted_read_request.json',
                'targeted_read_messages.json', 'final_request.json', 'final_messages.json')
AMENDMENT_JSON = ('runtime_amendments/01_ledger_byte_check_removed.json',)
RECOVERY_DIRECTORY = 'recovery_history/01_ledger_byte_check_removed'
SECOND_RECOVERY_DIRECTORY = 'recovery_history/02_reservation_schema'
RECOVERY_JSON = (tuple(RECOVERY_DIRECTORY+'/'+name for name in ('fatal_error.json','status.json'))
                 +tuple(SECOND_RECOVERY_DIRECTORY+'/'+name for name in ('fatal_error.json','status.json','recovery_note.json')))
RECOVERY_TEXT = tuple(RECOVERY_DIRECTORY+'/'+name for name in
                      ('v12_ab60.log','v12_ab60.pid','v12_ab60.exitcode'))+tuple(
                      SECOND_RECOVERY_DIRECTORY+'/'+name for name in ('v12_ab60.log','v12_ab60.pid','v12_ab60.exitcode'))
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp'}
SECRET_KEYS = {'api_key', 'apikey', 'api_token', 'authorization', 'proxy_authorization',
               'password', 'passwd', 'access_token', 'refresh_token', 'session_token',
               'private_key', 'ssh_key', 'client_secret', 'secret', 'credential', 'credentials',
               'headers', 'cookies', 'cookie', 'reservation_id', 'account_balance',
               'balance_cny', 'remaining_cny', 'committed_cny', 'reserved_cny',
               'start_committed_cny', 'end_committed_cny'}
URI = re.compile(r'data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+', re.I)
SECRET = re.compile(r'(?i)\b(?:sk-[a-z0-9_-]{16,}|gh[pousr]_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,}|AKIA[A-Z0-9]{16})\b|-----BEGIN [A-Z ]*PRIVATE KEY-----|\bBearer\s+[A-Za-z0-9._~+/=-]{12,}')
PRIVATE_PATH = re.compile(r'(?i)(?<![A-Za-z0-9])[a-z]:[\\/][^\r\n\"\'<>\]\},;]+|(?<![\w:/.\-])/(?!/)[^\s\"\'<>\]\},;]+')


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def relative_name(value):
    value = str(value).replace('\\', '/')
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or ':' in value:
        raise ValueError('unsafe_relative_source_name')
    return path


def source_file(run, relative):
    candidate = (run/str(relative)).resolve()
    if not candidate.is_relative_to(run):
        raise ValueError('source_escapes_run')
    return candidate


class PublicAssets:
    """Read only named image files; preserve actual image bytes in one asset store."""
    def __init__(self, out, run, image_roots=(), mappings=()):
        self.out, self.run = Path(out), Path(run).resolve()
        self.image_roots = [Path(p).resolve() for p in image_roots]
        self.mappings = [(str(a).replace('\\', '/').rstrip('/'), Path(b).resolve()) for a,b in mappings]
        self.aliases, self.uri_cache, self.file_cache, self.manifest, self.source_names = {}, {}, {}, {}, {}
        self._replacement_cache = {}

    def put(self, data):
        from PIL import Image
        if len(data) > 100*1024*1024:
            raise ValueError('image_above_publication_size_limit')
        digest = hashlib.sha256(data).hexdigest()
        if digest in self.manifest:
            return self.manifest[digest]['path']
        with Image.open(BytesIO(data)) as im:
            suffix = {'PNG': '.png', 'JPEG': '.jpg', 'WEBP': '.webp'}.get(im.format)
            if suffix is None:
                raise ValueError('only_png_jpeg_webp_image_bytes_allowed')
            size = list(im.size);im.verify()
        relative = 'assets/'+digest+suffix
        path = self.out/relative;path.parent.mkdir(parents=True, exist_ok=True);path.write_bytes(data)
        self.manifest[digest] = {'path': relative, 'bytes': len(data), 'size': size,
                                 'sha256': digest, 'byte_preserving_copy': True}
        return relative

    def uri(self, value, alias=None):
        fingerprint = hashlib.sha256(value.encode('ascii')).hexdigest()
        if fingerprint not in self.uri_cache:
            self.uri_cache[fingerprint] = self.put(base64.b64decode(value.split(',', 1)[1], validate=True))
        public = self.uri_cache[fingerprint]
        if alias: self.alias(alias,public)
        return public

    def alias(self, private, public):
        old=self.aliases.get(str(private))
        if old is not None and old!=public:
            raise ValueError('same_private_image_path_has_conflicting_saved_bytes')
        if old != public:self._replacement_cache.clear()
        self.aliases[str(private)]=public

    def file(self, path, alias=None):
        path = Path(path).resolve(strict=True)
        allowed = [self.run, *self.image_roots, *(local for _,local in self.mappings)]
        if path.suffix.lower() not in IMAGE_EXTENSIONS or not any(path.is_relative_to(root) for root in allowed):
            raise ValueError('image_outside_declared_roots_or_disallowed_type')
        if path not in self.file_cache:
            self.file_cache[path] = self.put(path.read_bytes())
        public = self.file_cache[path]
        self.alias(str(path),public)
        if alias: self.alias(alias,public)
        return public

    def resolve(self, private):
        private = str(private)
        if private in self.aliases:
            return self.aliases[private]
        norm = private.replace('\\', '/')
        for prefix, local in sorted(self.mappings, key=lambda item: -len(item[0])):
            if norm.startswith(prefix+'/'):
                relative = relative_name(norm[len(prefix)+1:])
                candidate = (local/str(relative)).resolve()
                if candidate.is_relative_to(local) and candidate.is_file():
                    return self.file(candidate, private)
        direct = Path(private)
        if direct.is_absolute() and direct.is_file():
            return self.file(direct, private)
        raise FileNotFoundError('required_image_not_in_declared_local_roots_or_saved_request')

    def original(self, relative, private):
        relative = relative_name(relative)
        if str(relative) in self.source_names:
            public=self.source_names[str(relative)];self.alias(private,public)
            return public
        if private in self.aliases:
            return self.aliases[private]
        for root in self.image_roots:
            candidate = (root/str(relative)).resolve()
            if candidate.is_relative_to(root) and candidate.is_file():
                return self.file(candidate, private)
        return self.resolve(private)

    def collect(self, value):
        """Bind each saved request's image URL to its adjacent image metadata."""
        if isinstance(value, dict):
            for item in value.values(): self.collect(item)
        elif isinstance(value, list):
            metadata = None
            for item in value:
                if isinstance(item, dict) and item.get('type') == 'text' and str(item.get('text', '')).startswith('BOUND CURRENT IMAGE: '):
                    metadata = json.loads(item['text'].split(': ', 1)[1])
                elif isinstance(item, dict) and item.get('type') == 'image_url':
                    url = item.get('image_url', {})
                    url = url.get('url', '') if isinstance(url, dict) else url
                    if isinstance(url, str) and URI.fullmatch(url):
                        public=self.uri(url, metadata.get('path') if metadata else None)
                        if metadata and not metadata.get('parent_image_id') and metadata.get('source_filename'):
                            name=str(relative_name(metadata['source_filename']))
                            if name in self.source_names and self.source_names[name]!=public:
                                raise ValueError('original_source_filename_has_conflicting_saved_bytes')
                            self.source_names[name]=public
                    metadata = None
                self.collect(item)
        elif isinstance(value, str):
            for found in URI.finditer(value): self.uri(found.group())

    def relative(self, public, folder):
        return os.path.relpath(self.out/public, self.out/folder).replace('\\', '/')

    def clean(self, value, folder=Path('.')):
        if isinstance(value, dict):
            return {key:self.clean(item, folder) for key,item in value.items()
                    if str(key).lower().replace('-', '_') not in SECRET_KEYS
                    and not str(key).lower().endswith(('_api_key', '_password', '_private_key'))}
        if isinstance(value, list): return [self.clean(item, folder) for item in value]
        if not isinstance(value, str): return value
        # Structured JSON inside a model message can also contain credential or
        # path fields; recursively clean it while retaining all observable text.
        if value.lstrip().startswith(('{', '[')):
            try: parsed=json.loads(value)
            except (ValueError, TypeError): pass
            else: return json.dumps(self.clean(parsed, folder), ensure_ascii=False)
        value = URI.sub(lambda m: self.relative(self.uri(m.group()), folder), value)
        cache_key=str(folder)
        if cache_key not in self._replacement_cache:
            self._replacement_cache[cache_key]=[
                ({private,private.replace('\\','/'),json.dumps(private)[1:-1]},self.relative(public,folder))
                for private,public in sorted(self.aliases.items(),key=lambda item:-len(item[0]))]
        for variants,replacement in self._replacement_cache[cache_key]:
            for variant in variants:
                value=value.replace(variant, replacement)
        value=PRIVATE_PATH.sub('[private_path_omitted]', value)
        if SECRET.search(value) or 'data:image/' in value.lower() or re.search(r'(?i)(?:api[_-]?key|password|client_secret)\s*[=:]\s*[^\s,;]{8,}', value):
            raise ValueError('credential_like_or_unconverted_image_content_refused')
        return value


def completed_inputs(run):
    # Do not read case material until the saved generation AND independent
    # scorer explicitly report completion. No external label path is accepted.
    status=read_json(source_file(run, 'status.json'))
    if status.get('status') != 'generation_complete':
        raise ValueError('only_generation_complete_run_can_be_exported')
    metrics=read_json(source_file(run, 'metrics.json'))
    if metrics.get('run_status') != 'completed' or metrics.get('planned_n') != 60:
        raise ValueError('independent_scoring_must_be_complete_before_export')
    selection=read_json(source_file(run, 'selection.json'))
    initials=jsonl(source_file(run, 'initial_results.jsonl'))
    branches=jsonl(source_file(run, 'branch_results.jsonl'))
    from v12_metrics import validate_terminals
    planned,_,initial,branch=validate_terminals(selection, initials, branches, fixed_sixty=True)
    outcomes=read_json(source_file(run, 'per_question.json'))
    records=outcomes.get('records', [])
    if outcomes.get('post_generation_only') is not True or len(records)!=60 or {r['question_id'] for r in records}!=set(planned):
        raise ValueError('complete_per_question_scoring_required')
    if metrics.get('initial_terminal_n')!=60 or metrics.get('branch_terminal_n')!=120:
        raise ValueError('score_terminal_counts_do_not_match_completed_run')
    return selection,initial,branch,{r['question_id']:r for r in records},metrics


def checkpoint(run, qid, stage):
    names=INITIAL_FILES if stage=='initial' else BRANCH_FILES
    folder=Path('checkpoints')/qid/stage
    payload={}
    for name in names:
        path=source_file(run, folder/name)
        if path.is_file(): payload[name]=jsonl(path) if name.endswith('.jsonl') else read_json(path)
    if 'terminal.json' not in payload or 'context.json' not in payload:
        raise ValueError('checkpoint_export_incomplete:'+qid+':'+stage)
    return {'stage':stage, 'question_id':qid, 'source_files':list(payload),
            'allowlisted_files_not_saved':[name for name in names if name not in payload],
            'records':payload}


def case_markdown(case):
    qid=case['question_id'];lines=[f'# V12：{qid}', '', '[全部题目](README.md) · [结构化病例记录]('+qid+'.json)', '',
        f"来源：[ChestAgentBench 固定版本]({DATASET_URL})；[Eurorad case {case['source']['case_id']}]({case['source']['case_url']})。", '',
        '参考答案只来自实验结束后的既有评分结果。模型和工具文字是可观察输出，不是人工确认的患者事实。', '',
        '## 完整题干与全部选项', '', '```text', case['question'], '```', '', '## 原图与图号对应', '']
    for im in case['original_images']:
        lines += [f"**{im['image_id']} — {im['source_filename']}**", '', f"![{im['image_id']}]({im['path']})", '']
    lines += ['## 三阶段答案与失败回退', '', '| 组 | 首答 | 取证后候选 | 模型最终求解 | 控制器最终答案 | 状态 |', '|---|---|---|---|---|---|']
    for group in ('B','A'):
        r=case['branches'][group]
        lines.append('| '+ ' | '.join(str(v) if v is not None else '缺答' for v in
            [group,case['initial'].get('first_answer'),r.get('candidate_answer'),r.get('solver_answer'),r.get('answer'),r.get('status')])+' |')
    lines += ['', '失败回退保留已有合法首答，不计作新求解成功；首答和候选均未作为最终模型输入。', '',
              '## 完整调用、检索及工具记录', '']
    for stage,link in case['checkpoint_links'].items():
        lines.append(f'- [{stage}：实际保存的请求、响应、解析、观察、工具原始返回、费用与耗时]({link})')
    lines += ['', '图号、模态、初次/随访、比较对象以及派生图与原图关系保存在各阶段的 image registry / images.json / observation 中。Unknown 保持未知。', '',
              '## 已评分结果、错误、费用与耗时', '', '```json',
              json.dumps({'scored_outcome':case['scored_outcome'], 'initial':case['initial'], 'branches':case['branches']},ensure_ascii=False,indent=2), '```','']
    return '\n'.join(lines)


def runtime_amendment_note():
    return '''# 运行修订 01：移除账本原始字节一致性停机

2026-10-31 12:40 的第 6 个 B 终态记录 MonetaryStop → LedgerIntegrityError（raw-byte mismatch）。前 6 个共享首读和 B 终态保留，第 6 个 B 的控制器回退继续单列，不重跑或改写。

用户明确要求删除运行中的原始字节一致性停机。v12_ledger.py 的子类仅将 _check_disk 改为 _check_open，run_v12_resume.py 注入该子类后调用原冻结 runner。原账本身份、互斥锁、费用上限、金额验证、预留/结算及 pending 保守恢复规则仍继承；固定输入、模型、提示、调用上限及 B→A 顺序不变。修订来源和实际应用记录见 [修订 JSON](runtime_amendments/01_ledger_byte_check_removed.json)，停机证据见 recovery_history/01_ledger_byte_check_removed/ 的明确允许文件。

恢复过程已确认：12:52 新进程 PID 3130741 启动，12:53 共享首答增至 7/60、正在 B7。原冻结 runner/provider 源码和 effective_config.json 未改，运行修订单独保存。旧 B6 fatal 属于历史停机记录；不重加字节检查或替代扫描。

原 pending 预留额为 0.069056 CNY；本次可见 usage 按既有价格估算为 0.023076 CNY，差额为 0.045980 CNY。保留 pending 后，原开账恢复机制按预留额保守计账。这三项分别是预留额、用量估算和两者差额，不能将保守预留恢复额称为供应商实际账单；也不能直接加到上下文费用中造成重复计数。最终应并列保存上下文费用合计和原账本本轮增量，并据实际保存的结算记录说明差异。

本说明记录故障、授权修订、已确认的恢复进度及费用口径；恢复运行不等于完成实验，本说明也不独立证明具体结算已落盘。后续完成情况和费用以保存的进程/状态/终态、独立评分及结算摘要为准。源预测、历史停机记录和原账本均不由导出器改写或补记。

## 恢复记录 02：费用预留 schema 异常

2026-10-31 北京时间 14:36，A46 在首次费用预留时报 Invalid reservation schema，模型和工具调用均为 0，控制器保留合法首答。一次定向定位显示已落盘 reservation 字段完整、最后请求已 settled，本次报错的候选预留未落盘；进程内根因尚未确定，不能称为坏账或宣称根因已修复。随后沿用同一原接口和 run_v12_resume.py 重新启动 PID 3193115，从 A47 继续，前 106 个分支终态保留，费用和调用上限不变。历史 fatal/status/log/PID/exitcode 及 recovery_note.json 明确保存在 recovery_history/02_reservation_schema/；本导出只保留这些记录，不改写原预测或账本。
'''


def export(args):
    run=args.run.resolve();out=args.out.resolve()
    if out.exists() or out.is_relative_to(run):
        raise ValueError('output_must_be_new_and_outside_source_run')
    selection,initials,branches,outcomes,metrics=completed_inputs(run)
    cfg=read_json(source_file(run,'effective_config.json'))
    source_root=str(cfg.get('root','')).replace('\\','/').rstrip('/')
    mappings=[]
    for entry in args.path_map:
        prefix,separator,local=entry.partition('=')
        if not separator or not prefix or not local: raise ValueError('path_map_requires_PRIVATE_equals_LOCAL')
        mappings.append((prefix,Path(local)))
    mappings.append((source_root+'/runs/'+run.name,run))
    image_roots=[*args.image_root,ROOT/'reports/v11/images/originals',ROOT/'local_assets/v11_public_sources/images/originals']
    manifest=[];case_index=[]
    # Failed exports leave no half-populated public report; only the explicitly
    # allowlisted final package moves out of the private temporary directory.
    with tempfile.TemporaryDirectory(prefix='v12-public-',dir=run.parent) as temporary:
        stage=Path(temporary)/'results';stage.mkdir()
        assets=PublicAssets(stage,run,image_roots,mappings)
        for index,row in enumerate(selection['rows'],1):
            qid=str(row['question_id'])
            if not re.fullmatch(r'[A-Za-z0-9_.-]+',qid): raise ValueError('unsafe_question_id')
            packets={name:checkpoint(run,qid,name) for name in ('initial','B','A')}
            for packet in packets.values(): assets.collect(packet)
            registry={im['image_id']:im for im in packets['B']['records'].get('images.json',{}).get('originals',[])}
            originals=[]
            for number,name in enumerate(row['images'],1):
                private=source_root+'/'+str(cfg['image_root']).strip('/')+'/'+str(relative_name(name))
                public=assets.original(name,private)
                originals.append({**registry.get(f'image:{number}',{}),
                                  'image_id':f'image:{number}','source_filename':name,'path':public})
            for name,packet in packets.items():
                for record in packet['records'].get('images.json',{}).get('derived',[]):
                    assets.resolve(record['path'])
                relative=f'traces/{qid}_{name}.json'
                write_json(stage/relative,assets.clean(packet,Path('traces')))
                manifest.append({'path':relative,'question_id':qid,'stage':name,'source_files':packet['source_files']})
            case={'publication_schema_version':1,'index':index,'question_id':qid,
                  'question':row['question'],'official_group':row.get('official_group'),
                  'source':{'dataset':DATASET,'revision':REVISION,'case_id':qid.split('_',1)[0],
                            'case_url':'https://www.eurorad.org/case/'+qid.split('_',1)[0]},
                  'original_images':originals,'initial':initials[qid],
                  'branches':{g:branches[qid,g] for g in ('B','A')},'scored_outcome':outcomes[qid],
                  'checkpoint_links':{g:f'../traces/{qid}_{g}.json' for g in packets},
                  'reference_visibility':'post_generation_scoring_only'}
            case=assets.clean(case,Path('cases'))
            for im in case['original_images']: im['path']='../'+im['path']
            write_json(stage/'cases'/f'{qid}.json',case)
            (stage/'cases'/f'{qid}.md').write_text(case_markdown(case),encoding='utf-8')
            case_index.append({'question_id':qid,'path':f'cases/{qid}.md','json':f'cases/{qid}.json'})
        for name in ROOT_JSON:
            path=source_file(run,name)
            if path.is_file(): write_json(stage/name,assets.clean(read_json(path)))
        for name in ROOT_JSONL:
            path=source_file(run,name)
            if path.is_file():
                with path.open(encoding='utf-8-sig') as source, (stage/name).open('w',encoding='utf-8') as target:
                    for line in source:
                        if line.strip(): target.write(json.dumps(assets.clean(json.loads(line)),ensure_ascii=False)+'\n')
        path=source_file(run,'metrics.md')
        if not path.is_file(): raise ValueError('scorer_markdown_missing')
        (stage/'metrics.md').write_text(assets.clean(path.read_text(encoding='utf-8-sig')),encoding='utf-8')
        path=source_file(run,'ledger_final_summary.json')
        if path.is_file():
            summary=read_json(path)
            write_json(stage/path.name,assets.clean({k:summary[k] for k in ('run_increment_cny','basis','utc') if k in summary}))
        recovery_files=[]
        for name in AMENDMENT_JSON+RECOVERY_JSON:
            path=source_file(run,name)
            if path.is_file():
                write_json(stage/name,assets.clean(read_json(path),Path(name).parent));recovery_files.append(name)
        for name in RECOVERY_TEXT:
            path=source_file(run,name)
            if path.is_file():
                target=stage/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text(assets.clean(path.read_text(encoding='utf-8-sig'),Path(name).parent),encoding='utf-8')
                recovery_files.append(name)
        if recovery_files:
            (stage/'runtime-amendments.md').write_text(runtime_amendment_note(),encoding='utf-8')
            write_json(stage/'runtime_amendments/01_ledger_byte_check_removed.cost-note.json',{
                'source':'publication_annotation_for_recorded_2026-10-31_12:40_incident',
                'pending_reserved_cny':'0.069056','visible_usage_estimate_cny':'0.023076',
                'reservation_minus_visible_usage_estimate_cny':'0.045980',
                'reopen_policy':'original_pending_recovery_conservatively_charges_reservation',
                'supplier_actual_bill_cny':None,'exporter_independently_verified_settlement':False,
                'note':'Keep reservation recovery, visible-usage estimate, saved context totals and ledger run increment distinct; do not double-add or rewrite original records.'})
        write_json(stage/'asset-manifest.json',{'assets':list(assets.manifest.values()),'byte_preserving':True})
        write_json(stage/'publication-manifest.json',{'source_run':run.name,'planned_n':60,'case_count':len(case_index),
            'checkpoint_count':len(manifest),'case_index':case_index,'checkpoints':manifest,
            'allowlist':{'root_json':ROOT_JSON,'root_jsonl':ROOT_JSONL,'initial':INITIAL_FILES,'branch':BRANCH_FILES,
                         'runtime_amendments':AMENDMENT_JSON,'recovery_json':RECOVERY_JSON,'recovery_text':RECOVERY_TEXT},
            'runtime_amendment_and_recovery_files':recovery_files,
            'source_records_modified':False,'reference_label_file_or_ledger_opened':False,
            'transform':'Observable records preserved; embedded images decoded byte-for-byte, image paths linked, credential fields/private paths removed. No model weights or unrelated files.'})
        index=['# V12 全部 60 题','','[报告说明](../README.md)','','| 题目 | 完整记录 |','|---|---|']
        index += [f"| [{r['question_id']}]({r['question_id']}.md) | [JSON]({r['question_id']}.json) |" for r in case_index]
        (stage/'cases'/'README.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
        report=readme(metrics)
        if recovery_files:
            report+='\n## 运行修订与费用差额\n\n[运行修订 01、历史停机证据及费用口径](runtime-amendments.md)。原 pending 预留额 0.069056 CNY，可见 usage 估算 0.023076 CNY，差额 0.045980 CNY；保守预留恢复不是供应商实际账单。修订/历史文件按发布清单保留，不重写旧终态或直接叠加费用。\n'
        (stage/'README.md').write_text(report,encoding='utf-8')
        out.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(stage),str(out))
    return {'status':'exported_not_pushed','cases':60,'checkpoints':len(manifest),'out':str(out)}


def readme(metrics):
    return f'''# V12 完整实验归档

[结果报告](metrics.md) · [结构化指标](metrics.json) · [60 题病例/图像索引](cases/README.md) · [逐题评分](per_question.json) · [配置](effective_config.json) · [发布清单](publication-manifest.json) · [图片清单](asset-manifest.json)

本目录仅在生成状态为 `generation_complete`、独立评分完成且 60 首读/120 分支终态齐全后生成。固定分母 60，先 B 后 A；两组共享首次读图缓存，使用同一模型及相同调用上限。B 加入鉴别知识检索与训练经验动作指导，A 保留图号/模态绑定、针对性观察与完整选项求解。

## 如何回溯一题

从 cases 索引打开完整题干、全部选项及原始基准图，再查看对应 initial、B、A 三份 traces。每份 JSON 按原文件名保存明确允许的 checkpoint 文件：实际请求、可观察响应、首读/新增观察、检索知识与经验及其来源、动作计划、工具实际参数和原始返回、解析结果、终态、错误、调用计数、费用和时间。缺少的文件列在 `allowlisted_files_not_saved`，可能是对应阶段未执行或在产生响应前失败；不补造内容。

所有图像 data URI 按原字节解码到 assets，替换为相对于所在 JSON 的图片链接。原图、裁剪图及工具派生图保留图号、模态、初次/随访、比较对象、父图、裁剪框等已保存映射。源图可来自本次请求或已发布缓存；不会把别的病例、视图或时点推定为同一对象。源文件与预测不改写。

## 三阶段与回退

首答保留用于评分；取证后候选来自同一次针对性观察调用；最终模型重新匹配完整选项，输入不包含首答或候选。执行失败且存在合法首答时，由控制器回退，`fallback_initial`、`fallback_to_initial`、原始错误和 `solver_answer=null` 单列。回退正确不算新的模型求解成功，也不算首答缺答恢复。查看 metrics 中 candidate/candidate_paired、final/paired、solver 及 execution，避免混淆三个阶段。

## 效果、失败、费用的解释边界

首答正确 {metrics['initial']['correct']}/60；B 最终 {metrics['groups']['B']['final']['correct']}/60，A 最终 {metrics['groups']['A']['final']['correct']}/60。细分纠正、误改、缺答恢复、净增益及七类重叠任务结果以独立评分文件为准。模型文字和工具输出属于未独立验证的观察或假设；单字 No、孤立病名和执行错误不得解释为患者事实。逐题记录支持定位失败环节，不自动证明某一工具或检索条目导致了结果变化。

共享首读费用计一次；A/B 各列新增费用，已有账本最终简报仅公开本轮增量，费用基于保存记账口径并非供应商发票。题内耗时求和不等于端到端墙钟。B/A 上限相同而实际调用可因失败而不同，固定执行顺序未随机化。V10 只作历史对照，独立 qwen3.8-max 裁决实验不并入本结果。60 题为反复检查的开发集，不是新的盲测集。

## 来源与发布范围

基准：[{DATASET} 固定版本 {REVISION}]({DATASET_URL})。病例页面保留 Eurorad 源链接；基准媒体属于第三方数据，沿用来源条款，不作为仓库代码重新授权。本导出只使用本轮完整题目和明确引用的图像/记录，不打包模型、凭据、私有账户余额或无关本地文件。私有路径用已发布图像链接或省略标记替换。

本目录生成表示离线导出完成，不能据此宣称 GitHub 已上传；只有另行 push 成功并确认远程提交后才能报告发布成功。
'''


def self_test():
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);buffer=BytesIO();Image.new('RGB',(12,12),(20,40,60)).save(buffer,format='PNG')
        data=buffer.getvalue();uri='data:image/png;base64,'+base64.b64encode(data).decode()
        assets=PublicAssets(root/'out',root)
        private='/private/synthetic/image.png'
        packet=[{'type':'text','text':'BOUND CURRENT IMAGE: '+json.dumps({'path':private,'source_filename':'synthetic/figure1.png'})},
                {'type':'image_url','image_url':{'url':uri}}]
        assets.collect(packet)
        assert assets.original('synthetic/figure1.png','/different/mount/synthetic/figure1.png') == assets.manifest[next(iter(assets.manifest))]['path']
        clean=assets.clean({'api_key':'synthetic-key','payload':packet,'path':private,
                            'error':'failed at /private/synthetic/model.bin','input_tokens':42},Path('traces'))
        rendered=json.dumps(clean)
        assert 'api_key' not in clean and clean['input_tokens']==42
        assert 'base64,' not in rendered and '/private/' not in rendered and '../assets/' in rendered
        assert len(assets.manifest)==1
        assert (assets.out/next(iter(assets.manifest.values()))['path']).read_bytes()==data
        try: assets.clean('Bearer '+'x'*30)
        except ValueError: pass
        else: raise AssertionError('credential token not refused')
        write_json(root/'status.json',{'status':'running'})
        try: completed_inputs(root)
        except ValueError: pass
        else: raise AssertionError('running experiment not refused')
    return {'synthetic_checks':'passed','real_cases_labels_providers_ledgers_read':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=ROOT/'local_assets/v12_ab60')
    parser.add_argument('--out',type=Path,default=ROOT/'reports/v12/results')
    parser.add_argument('--image-root',type=Path,action='append',default=[])
    parser.add_argument('--path-map',action='append',default=[],metavar='PRIVATE_PREFIX=LOCAL_DIRECTORY')
    parser.add_argument('--self-test',action='store_true')
    args=parser.parse_args()
    print(json.dumps(self_test() if args.self_test else export(args),ensure_ascii=False))


if __name__=='__main__':main()
