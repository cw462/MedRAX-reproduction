"""Publish the completed V10 historical records without inference or ledger access.

Inputs are a private, read-only checkpoint cache and the already scored run.
The cache replaces embedded image data with PUBLICATION_IMAGE references and
preserves decoded image bytes. This exporter publishes selected experiment files,
reuses existing V11 media, and removes private paths/credential-bearing fields.
It does not execute tools, score labels, modify predictions, or read a ledger.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import shutil


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rows(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8-sig').splitlines() if x.strip()]


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def outcome(initial, final, reference):
    if initial is None:
        return 'P0_failure_recovered_correctly' if final == reference else 'P0_failure_not_recovered_correctly'
    if initial == reference:
        return 'correct_retained' if final == reference else 'correct_answer_harmed'
    return 'legal_wrong_answer_corrected' if final == reference else 'wrong_remained'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--cache', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    cache = args.cache or root / 'local_assets/v10_history_sources'
    run, out = root / 'runs/v10_accuracy60', root / 'reports/v10'
    source = read(cache / 'manifest.json')
    v11_manifest = read(root / 'local_assets/v11_public_sources/manifest.json')
    originals = read(run / 'selection.json')['rows']
    p0 = {x['question_id']: x for x in rows(run / 'p0_results.jsonl')}
    plans = {x['question_id']: x for x in rows(run / 'shared_plans.jsonl')}
    branches = rows(run / 'candidate_results.jsonl')
    metrics = read(run / 'paired_metrics.json')
    if metrics['run_status'] != 'completed':
        raise ValueError('only_completed_run_can_be_published')
    by_group = {(x['question_id'], x['group']): x for x in branches}
    public_case = {x['question_id']: read(root / 'reports/v11/cases' / (x['question_id'] + '.json')) for x in originals}

    # Exact preserved bytes identify already published media; no ledger or input
    # integrity scan is performed. Each new image is copied once.
    cache_to_public, private_to_public, media = {}, {}, []
    attached_media = set()

    def find_attached(value):
        if isinstance(value, dict):
            for item in value.values():
                find_attached(item)
        elif isinstance(value, list):
            for item in value:
                find_attached(item)
        elif isinstance(value, str) and value.startswith('PUBLICATION_IMAGE:'):
            attached_media.add(value.split(':', 1)[1])

    find_attached(source['sources'])
    for private, info in source['image_mapping'].items():
        old = v11_manifest['image_mapping'].get(private)
        if old and (root / 'reports/v11' / old).is_file():
            cache_to_public.setdefault(info['cache_path'], '../v11/' + old)
    for path in sorted((cache / 'media').iterdir()):
        relative = path.relative_to(cache).as_posix()
        if relative not in attached_media:
            continue
        public = cache_to_public.get(relative)
        reused = public is not None
        if public is None:
            public = 'images/' + path.name
            target = out / public
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            cache_to_public[relative] = public
        media.append({'path': public, 'bytes': path.stat().st_size, 'reused_from_v11': reused,
                      'byte_preserving_copy': True})
    for private, info in source['image_mapping'].items():
        if info['cache_path'] in attached_media:
            private_to_public[private] = cache_to_public[info['cache_path']]
        else:
            private_to_public[private] = 'UNAVAILABLE_CURRENT_INPUT:' + private.split('/images/', 1)[-1]
    replacements = sorted(private_to_public.items(), key=lambda x: -len(x[0]))
    secret_keys = {'api_key', 'api_token', 'authorization', 'password', 'access_token',
                   'secret', 'private_key', 'credentials', 'credential',
                   'reservation_id', 'remaining_cny'}

    def clean(value):
        if isinstance(value, dict):
            return {key: clean(v) for key, v in value.items() if key.lower() not in secret_keys}
        if isinstance(value, list):
            return [clean(v) for v in value]
        if not isinstance(value, str):
            return value
        if value.startswith('PUBLICATION_IMAGE:'):
            return cache_to_public[value.split(':', 1)[1]]
        if 'data:image/' in value and ';base64,' in value:
            raise ValueError('unconverted_image_payload')
        for private, public in replacements:
            value = value.replace(private, public)
        # Private transport, local checkout and model/cache locations have no
        # publication value. Relevant image paths above remain usable links.
        value = re.sub(r'(?i)(?:(?<![A-Za-z0-9])[a-z]:[\\/]|/(?:home|tmp|mnt|Users)/)[^\s\"\'<>\]\},]+',
                       '[private_path_omitted]', value)
        if re.search(r'(?i)\b(?:sk-[a-z0-9_-]{20,}|gh[pousr]_[a-z0-9]{25,})\b', value):
            raise ValueError('credential_like_content')
        return value

    def cached(fullpath):
        suffix = fullpath.split('/runs/v10_accuracy60/', 1)[1]
        return source['sources'].get(suffix)

    def checkpoint_parts(branch):
        folder = branch['evidence_package'].rsplit('/', 1)[0]
        result = {}
        for name in ['messages.json', 'gate_messages.json', 'retrieval.json', 'context.json',
                     'raw_tools.jsonl', 'tool_attempts.jsonl']:
            value = cached(folder + '/' + name)
            if value is not None:
                result[name.replace('.', '_')] = value
        return result

    outcomes, retrieval, tool_counts, error_types = [], [], Counter(), Counter()
    case_index = ['# V10 全部 60 题历史对照', '',
                  '[完整说明](../README.md) · [失败分析](../failure-analysis.md)', '',
                  '每题页面链接到完整题干/选项/原图及实际保存的 P0、共享规划和三分支消息。', '',
                  '| 序号 | 题目 | 参考 | P0 | V候选→终答 | VK候选→终答 | VKE候选→终答 |',
                  '|---|---|---|---|---|---|---|']
    for index, selected in enumerate(originals, 1):
        qid = selected['question_id']
        baseline, plan, oldcase = p0[qid], plans[qid], public_case[qid]
        reference = oldcase['reference_answer']
        groups = {group: by_group[(qid, group)] for group in ['V', 'VK', 'VKE']}
        details = {group: checkpoint_parts(value) for group, value in groups.items()}
        p0_checkpoint = cached(baseline['checkpoint']) if baseline.get('checkpoint') else None
        p0_tools = cached(baseline['raw_tools']) if baseline.get('raw_tools') else []
        alltools = list(p0_tools or []) + [item for group in details.values() for item in group.get('raw_tools_jsonl', [])]
        for item in alltools:
            tool_counts[item.get('tool_name', 'unknown')] += 1
            result = item.get('result')
            result_text = json.dumps(result, ensure_ascii=False)
            if 'CUDA out of memory' in result_text:
                error_types['CUDA out of memory (returned inside tool result)'] += 1
            elif isinstance(result, dict) and result.get('error'):
                error_types[str(result['error']).split(':')[0]] += 1
        case_outcome = {'index': index, 'question_id': qid, 'reference_answer': reference,
                        'p0': baseline['initial'], 'p0_status': baseline['status'], 'branches': {}}
        for group, branch in groups.items():
            case_outcome['branches'][group] = {
                'candidate': branch['candidate'], 'final': branch['final'],
                'candidate_correct': branch['candidate'] == reference,
                'final_correct': branch['final'] == reference,
                'outcome': outcome(baseline['initial'], branch['final'], reference),
                'gate': branch['gate'], 'candidate_error': branch.get('candidate_error'),
                'gate_error': branch.get('gate_error'), 'fallback': branch.get('fallback')}
            retrieval.append({'question_id': qid, 'group': group,
                              'retrieval': details[group].get('retrieval_json')})
        outcomes.append(case_outcome)
        case = {'publication_schema_version': 1, 'index': index, 'question_id': qid,
                'question': selected['question'], 'official_group': selected.get('official_group'),
                'reference_answer': reference, 'reference_use': 'post-generation historical review only',
                'source': oldcase['source'],
                'original_images': [dict(im, path='../v11/' + im['path']) for im in oldcase['original_images']],
                'p0': baseline, 'p0_checkpoint': p0_checkpoint, 'p0_raw_tools': p0_tools,
                'shared_plan': plan, 'shared_plan_messages': cached(plan['path']),
                'branches': groups, 'branch_checkpoints': details, 'scored_outcome': case_outcome,
                'path_resolution': 'All published image paths resolve relative to reports/v10/, including those embedded in message text; they are archival references, not runnable API URLs.'}
        write(out / 'cases' / (qid + '.json'), clean(case))
        lines = [f'# V10 历史记录：{qid}', '', '[60题索引](README.md) · '
                 f'[完整保存记录]({qid}.json) · [题干、完整选项和原图](../../v11/cases/{qid}.md)', '',
                 f'参考答案：**{reference}**；仅用于完成后的历史复盘。模型/工具的文字观察尚未经过独立临床验证。', '',
                 '| 阶段 | 候选 | 最终 | 相对 P0 的事件 |', '|---|---|---|---|',
                 f"| P0 | — | {baseline['initial'] or '缺失'} | {baseline['status']} |"]
        for group, branch in groups.items():
            event = case_outcome['branches'][group]['outcome']
            lines.append(f"| {group} | {branch['candidate'] or '缺失'} | {branch['final'] or '缺失'} | {event} |")
        lines += ['', '## P0 实际终态', '', '```json', json.dumps(clean(baseline['report']), ensure_ascii=False, indent=2), '```', '',
                  '## 共享规划', '', '```json', json.dumps(clean(plan['plan']), ensure_ascii=False, indent=2), '```']
        for group, branch in groups.items():
            lines += ['', f'## {group}：独立候选与门控', '', '```json', json.dumps(clean({k: branch.get(k) for k in
                      ['candidate', 'final', 'candidate_payload', 'gate', 'candidate_error', 'gate_error',
                       'fallback', 'k_ids', 'e_ids', 'accounting', 'timing']}), ensure_ascii=False, indent=2), '```']
            model_messages = details[group].get('messages_json', [])
            gate_messages = details[group].get('gate_messages_json', [])
            for heading, messages in [('候选模型保存的回答', model_messages), ('门控模型保存的回答', gate_messages)]:
                answers = [message.get('data', {}).get('content') for message in messages if message.get('type') == 'ai']
                lines += ['', f'### {heading}', '']
                if not answers:
                    lines.append('此路径没有保存助手文本回答；以 JSON 中状态、异常和消息为准。')
                for number, content in enumerate(answers, 1):
                    lines += ['', f'回答 {number}：', '', '```text', str(clean(content)), '```']
        lines += ['', '## 图像与工具明细读取方法', '',
                  f'完整 JSON 的 `p0_checkpoint.messages`、`p0_raw_tools`、`shared_plan_messages` 和 '
                  '`branch_checkpoints` 保存了实际消息、工具请求与返回、知识/经验注入全文及检索排序。'
                  '图片 URL 已转换成仓库相对路径（基准目录为 `reports/v10/`），图像字节不变。'
                  '缺失文件与未调用路径明确区分；没有为了补写复盘再次运行模型。', '']
        (out / 'cases' / (qid + '.md')).write_text('\n'.join(lines), encoding='utf-8')
        vals = [f"{groups[g]['candidate'] or '∅'}→{groups[g]['final'] or '∅'}" for g in ['V', 'VK', 'VKE']]
        case_index.append(f"| {index} | [{qid}]({qid}.md) | {reference} | {baseline['initial'] or '∅'} | {' | '.join(vals)} |")
    (out / 'cases/README.md').write_text('\n'.join(case_index) + '\n', encoding='utf-8')
    write(out / 'per-question-outcomes.json', clean(outcomes))
    write(out / 'p0-results.json', clean(list(p0.values())))
    write(out / 'shared-plans.json', clean(list(plans.values())))
    write(out / 'branch-results.json', clean(branches))
    write(out / 'retrieval-records.json', clean(retrieval))
    write(out / 'paired-metrics.json', clean(metrics))
    write(out / 'effective-config.json', clean(read(run / 'effective_config.json')))
    write(out / 'media-manifest.json', media)
    for name in ['runtime_tools.json', 'operational_amendment.json', 'smoke_check.json']:
        if name in source['sources']:
            write(out / name.replace('_', '-'), clean(source['sources'][name]))
    amendment = root / 'local_assets/v10_smoke_amendment.json'
    if amendment.is_file():
        write(out / 'operational-amendment-local-record.json', clean(read(amendment)))
    manifest = {'publication_schema_version': 1, 'source_run': 'v10_accuracy60',
                'inference_source_commit': '2e5aa12', 'posthoc_publication_no_new_inference': True,
                'p0_records': len(p0), 'shared_plans': len(plans), 'branches': len(branches),
                'retrieval_records': len(retrieval), 'saved_source_files': len(source['sources']),
                'missing_source_files': source['missing_source_files'],
                'embedded_image_references_replaced': source['embedded_image_references'],
                'distinct_media': len(media), 'reused_v11_media': sum(x['reused_from_v11'] for x in media),
                'new_media': sum(not x['reused_from_v11'] for x in media),
                'unattached_requested_media_not_published': len(list((cache / 'media').iterdir())) - len(attached_media),
                'tool_observation_records': sum(tool_counts.values()), 'tool_observation_counts': dict(tool_counts),
                'tool_result_error_fields': dict(error_types),
                'publication_transforms': ['base64 image payload -> corresponding byte-preserved image reference',
                                           'private paths -> relevant public image path or explicit omission marker',
                                           'credential-bearing keys excluded; unknown original records not fabricated'],
                'accounting': {'ledger_increment_cny_from_completed_report': '27.448612',
                               'context_total_cny': '27.420932', 'disclosed_difference_cny': '0.027680',
                               'ledger_reread_for_this_publication': False}}
    write(out / 'publication-manifest.json', manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
