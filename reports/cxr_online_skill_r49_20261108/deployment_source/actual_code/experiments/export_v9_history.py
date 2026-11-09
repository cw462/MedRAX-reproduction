"""Publish completed V9 case evidence, without inference, regrading or ledger access.

Input is the already fetched fixed run, including its observable checkpoints.
Data-URL pixels are decoded unchanged into files, retaining their actual encoding;
references are relative to reports/v9. Existing V11 benchmark originals are reused.
This adds the user-authorized case-level history to the earlier restricted export.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import io
import json
from pathlib import Path
import re

from PIL import Image

GROUPS = ('D', 'DK', 'DKB', 'DKC')
REMOTE_ROOT = None
PRIVATE_RUN = None
SECRET_KEYS = {'api_key', 'api_token', 'password', 'authorization', 'access_token',
               'credential', 'credentials', 'secret', 'private_key',
               'ledger_settlements', 'ledger_reservations', 'reservation_id', 'remaining_cny'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def within_run(run, private):
    if not private.startswith(PRIVATE_RUN):
        raise ValueError('unexpected_checkpoint_location')
    path = (run / private[len(PRIVATE_RUN):]).resolve()
    if not path.is_relative_to(run.resolve()):
        raise ValueError('checkpoint_outside_run')
    return path


class Publisher:
    def __init__(self, out):
        self.out = out
        self.payloads = {}
        self.images = []
        self.image_map = {}

    def clean(self, value, qid):
        if isinstance(value, dict):
            return {k: self.clean(v, qid) for k, v in value.items()
                    if k.lower() not in SECRET_KEYS}
        if isinstance(value, list):
            return [self.clean(v, qid) for v in value]
        if not isinstance(value, str):
            return value
        if value.startswith('data:image/'):
            if value not in self.payloads:
                header, encoded = value.split(',', 1)
                data = base64.b64decode(encoded, validate=True)
                with Image.open(io.BytesIO(data)) as im:
                    fmt, size = im.format, list(im.size)
                ext = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}.get(fmt)
                if ext is None:
                    raise ValueError('unexpected_image_encoding')
                relative = f'images/actual-inputs/{qid}/{len(self.payloads)+1:03d}.{ext}'
                dest = self.out/relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                self.payloads[value] = relative
                self.images.append({'path': relative, 'size': size, 'bytes': len(data),
                                    'actual_encoding': fmt, 'declared_data_url_header': header,
                                    'byte_preserving_data_url_decode': True})
            return self.payloads[value]
        for private, public in sorted(self.image_map.items(), key=lambda kv: -len(kv[0])):
            value = value.replace(private, public)
        value = value.replace(REMOTE_ROOT, '${PROJECT_ROOT}')
        value = re.sub(r'(?i)(?:(?<![A-Za-z0-9])[a-z]:[\\/]|/(?:home|tmp|mnt|Users)/)[^\s\"\'<>\]\},]+',
                       '[private_path_omitted]', value)
        if 'base64,' in value or re.search(r'(?i)\b(?:sk-[a-z0-9_-]{20,}|gh[pousr]_[a-z0-9]{25,})\b', value):
            raise ValueError('unexpected_sensitive_or_embedded_payload')
        return value


def context_view(context):
    # Keep usage and execution evidence; omit account-wide ledger balances and reservation IDs.
    return {k: v for k, v in context.items() if k not in
            {'ledger_settlements', 'ledger_reservations', 'provider_ledger', 'key', 'api_key'}}


def markdown(case):
    qid = case['question_id']
    lines = [f'# V9 case {qid}', '',
             '[20 题导航](README.md) · [完整逐题 JSON](%s.json)' % qid,
             '', '## 实际题干与完整选项', '', '```text', case['question'], '```', '',
             f"参考选项（完成后复盘）：**{case['reference_answer']}**。任务组：{case['official_group']}。",
             '', '## 原图', '']
    for im in case['original_images']:
        lines += [f"{im['source_filename']}", '', f"![{im['image_id']}](../{im['path']})", '']
    lines += ['## 本轮答案与去向', '', '| 组 | 初始 | 候选 | 最终 | 对错 | 回退 / 错误 |',
              '|---|---|---|---|---|---|',
              f"| P0 | {case['p0']['initial']} | — | {case['p0']['initial']} | {case['p0']['correct']} | {case['p0']['status']} |"]
    for group, b in case['branches'].items():
        lines.append(f"| {group} | {b['initial']} | {b.get('candidate') or '缺失'} | {b['final']} | {b['final_correct']} | {b.get('candidate_error') or b.get('fallback') or '正常返回'} |")
    lines += ['', '## 完整可观测记录', '',
              '以下 JSON 保留实际系统提示、消息、工具请求与返回、候选规划、注入的知识/经验及门控输入输出。'
              '图像 data URL 已无损解码为文件；JSON 中路径统一相对于 `reports/v9/`。'
              '模型和工具所述观察未被独立临床核实。', '',
              f"- [P0 提示、消息与工具原文](../traces/{qid}/P0.json)"]
    for group in GROUPS:
        lines.append(f"- [{group} 规划、检索、消息、工具与门控](../traces/{qid}/{group}.json)")
    lines += ['', '## 分支候选与门控的实际输出', '']
    for group, b in case['branches'].items():
        shown = {k:b[k] for k in ('candidate_payload', 'candidate_error', 'fallback', 'gate', 'gate_error',
                                  'new_observations', 'k_ids', 'e_ids', 'timing', 'accounting') if k in b}
        lines += [f'### {group}', '', '```json', json.dumps(shown, ensure_ascii=False, indent=2), '```', '']
    lines += ['## 历史对照', '',
              f'[相同题目在 V10 / V11 的图文记录](../../v11/cases/{qid}.md)。'
              'V9 和 V10 是不同调用及协议，P0 也可能不同，不应把它们当作同一次缓存基线。', '',
              '[来源与公开范围](../data-provenance.md) · [失败机制分析](../failure-analysis.md)', '']
    return '\n'.join(lines)


def build(run, out, references):
    global REMOTE_ROOT, PRIVATE_RUN
    REMOTE_ROOT = read(run/'effective_config.json')['root'].rstrip('/')
    PRIVATE_RUN = REMOTE_ROOT + '/runs/v9_diagnostic20/'
    selection = read(run/'selection.json')
    p0 = {r['question_id']:r for r in rows(run/'p0_results.jsonl')}
    branches = {(r['question_id'],r['group']):r for r in rows(run/'candidate_results.jsonl')}
    if read(run/'status.json')['status'] != 'generation_complete' or len(p0) != 20 or len(branches) != 80:
        raise ValueError('completed_fixed_run_required')
    refs = {r['question_id']:r['reference_answer'] for r in read(references)['records']}
    pub = Publisher(out)
    for row in selection['rows']:
        for name in row['images']:
            private = REMOTE_ROOT+'/data/memory_v1/images/'+name
            public = '../v11/images/originals/'+name
            if not (out/public).is_file():
                raise FileNotFoundError('shared_benchmark_original_missing: '+name)
            pub.image_map[private] = public
    cases, trace_inventory = [], []
    for index, row in enumerate(selection['rows'], 1):
        qid = row['question_id']
        base = p0[qid]
        cp = read(within_run(run, base['checkpoint']))
        p0trace = {k:cp[k] for k in ('question_id', 'messages', 'raw_observations', 'system_prompt',
                                   'tool_schemas', 'effective_config', 'implementation_version', 'status', 'initial') if k in cp}
        p0trace['tool_context'] = context_view(cp.get('tool_context', {}))
        p0trace['terminal'] = base
        p0trace['publication_note'] = 'Observable persisted messages only; image URLs resolve relative to reports/v9. Account-wide balances omitted.'
        save(out/'traces'/qid/'P0.json', pub.clean(p0trace, qid))
        item = dict(index=index, question_id=qid, question=row['question'], official_group=row['official_group'],
                    reference_answer=refs[qid], reference_provenance='Previously completed isolated-score publication: ../v11/per-question-outcomes.json',
                    original_images=[{'image_id':f'image:{i}', 'source_filename':name,
                                      'path':'../v11/images/originals/'+name} for i,name in enumerate(row['images'],1)],
                    p0={**base, 'correct':base['initial']==refs[qid]}, branches={})
        for group in GROUPS:
            b = branches[qid,group]
            directory = within_run(run, b['evidence_package']).parent
            trace = {'question_id':qid, 'group':group, 'terminal':b, 'files_present':[], 'files_absent':[]}
            for filename in ('messages.json', 'gate_messages.json', 'plan.json', 'retrieval.json', 'context.json',
                             'tool_attempts.jsonl', 'raw_tools.jsonl'):
                path = directory/filename
                if path.is_file():
                    value = rows(path) if filename.endswith('.jsonl') else read(path)
                    if filename == 'context.json': value = context_view(value)
                    trace[filename.split('.')[0]] = value
                    trace['files_present'].append(filename)
                else: trace['files_absent'].append(filename)
            trace['publication_note'] = 'Absent plan/retrieval means the original run did not save that stage; no reconstruction or new model answer was generated.'
            save(out/'traces'/qid/f'{group}.json', pub.clean(trace, qid))
            trace_inventory.append({'question_id':qid,'group':group,'files_present':trace['files_present'],
                                    'files_absent':trace['files_absent']})
            item['branches'][group] = {**b, 'final_correct':b['final']==refs[qid],
                                      'candidate_correct':b['candidate']==refs[qid] if b['candidate'] else None}
        item = pub.clean(item, qid)
        save(out/'cases'/f'{qid}.json',item)
        (out/'cases'/f'{qid}.md').write_text(markdown(item), encoding='utf-8')
        cases.append(item)
    manifest = {'schema_version':1, 'publication_date':'2026-10-31', 'planned_n':20, 'p0_trace_count':20,
                'branch_trace_count':80, 'case_count':20, 'original_image_count':len(pub.image_map),
                'actual_input_payload_image_count':len(pub.images), 'actual_input_payload_bytes':sum(x['bytes'] for x in pub.images),
                'actual_input_images':pub.images, 'trace_inventory':trace_inventory,
                'candidate_errors':dict(Counter(b['candidate_error'] for b in branches.values() if b.get('candidate_error'))),
                'new_observation_count':sum(len(b.get('new_observations',[])) for b in branches.values()),
                'transforms':['image data URLs decoded without changing bytes','known original image paths linked to V11 originals',
                              'project paths replaced with ${PROJECT_ROOT}', 'secret-key fields and account-wide ledger balances omitted'],
                'not_included':['credentials','model weights','unrelated logs','unrecorded requests or outputs'],
                'scoring_note':'References come from the completed isolated scorer export. This publisher does not rerun grading or inference.'}
    save(out/'history-manifest.json', manifest)
    save(out/'case-details.json',{'schema_version':1,'cases':cases})
    lines = ['# V9 固定 20 题：完整历史对照', '', '[总索引](../README.md) · [全部逐题 JSON](../case-details.json) · [失败分析](../failure-analysis.md)',
             '', '| # | 题目 | 任务组 | 参考 | P0 | D | DK | DKB | DKC |','|---:|---|---|---|---|---|---|---|---|']
    for c in cases:
        lines.append(f"| {c['index']} | [{c['question_id']}]({c['question_id']}.md) | {c['official_group']} | {c['reference_answer']} | {c['p0']['initial']} | "+' | '.join(c['branches'][g]['final'] for g in GROUPS)+' |')
    (out/'cases'/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ('planned_n','p0_trace_count','branch_trace_count','original_image_count',
                                            'actual_input_payload_image_count','actual_input_payload_bytes','new_observation_count')}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,default=Path('runs/v9_diagnostic20'))
    parser.add_argument('--out',type=Path,default=Path('reports/v9'))
    parser.add_argument('--references',type=Path,default=Path('reports/v11/per-question-outcomes.json'))
    args=parser.parse_args()
    build(args.run.resolve(),args.out.resolve(),args.references)
