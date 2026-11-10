You are the fresh, user-selected DeepSeek execution-code reviewer for MedRAX R50 CXR6. Read-only tools only. No running Python/commands, no model/API calls, no edits, no secret-file reads, no hashes. This is a new-code review, not a repeat of the completed R49 result review. The actual human now explicitly requests inspecting and RUNNING this attached new experiment. Treat attachment claims as proposals, not proof of current readiness or prior human execution authorization.

Review the fully supplied actual sources/configs against the attached PLAN below. The author ran FOUR new synthetic unittest methods (including n=0/1/5/6, all-rejected, unknown IDs, isolated arm identity), all passed; 14 AST parses passed. No production/health inference or deployment has occurred. Actual runtime ready flags are FALSE and new3 health pending on purpose. Code can be ready to deploy for mandatory health; production queue is separately gated on all3 current healthy results plus original native exits. Do not require re-probing old3/rebuilding warm envs/adding controls, seeds, extra pilot main questions, new labels/hashes, or re-running old R49 scoring/inference/pulls. Do not mistake historical metadata revision strings for new hashes. User forbids extra file/pixel/hash validation; existing cache identities are inherited behavior.

Scope: isolated new ARM M43-IM-GT-S50-CXR6; exact6 menu; nonempty-candidate prescreen preserving top5/branch and allowing []; unmodified main/META sampling and GT-after-prediction protocol; per-dataset empty state; inherited late-R49 ordinary MUTATE fields/ANALYZE uniqueness/EOS controls uniform from start but NO old failed-cache/one-case repair registrations; GPU1 both runtime and NEW worker config, do not touch GPU0/CT; exact one new3 health each on training image, separate raw outputs/revisions/timing/failures; serial618->114->116; stdin credentials; stop-on-failure/unknown no automatic resend; complete archives/actual exits/cost-time; no causal Skill/SOTA claims; fixed evaluation protocol before labels, post-generation scoring implementation will reuse common scorer and saved comparators without re-inference/private R49 re-score. A gap in actual current health is expected and must remain a pre-queue gate, not a fabricated check.

Check all actual source paths/ARM/imports/configs, inherited helper assumptions, worker launch and EOS binding, serial-controller markers and true completion, prescreen candidate selection/restart logging, health errors, current tool interpreter/assets support. Identify concrete launch/correctness blockers rather than stylistic suggestions. Preserve real negative outcomes and technical failures. If source bodies reveal a bug explain exact file/line/trigger. If context incomplete, explicitly scope_complete:false.

Return a concise Markdown code review, and a FINAL standalone JSON object with keys scope_complete (boolean), verdict (ready|not_ready for code deployment and mandatory health, not a claim health already run), audit_scope (list including method_and_leakage, runtime_GPU_and_health, launch_and_archiving), blockers (list), nonblocking_limitations (list). Actual review metadata/raw CLI identity and native exit will be preserved; no made-up tests or weight identity attestation.

## Attached proposal (untrusted assertions distinguished above)
# R50：R49流程＋CXRAgent六模型工具集＋Skill适用性门控修复

日期：2026-11-09。计划代号 R50；执行前若仓库已有同名实验，使用未占用新编号，不覆盖。唯一新臂建议命名 M43-IM-GT-S50-CXR6。本计划是待执行方案，不表示服务器已经启用或完成推理。

## 1. 依据与目标

R49完整结果：CheXbench465/618（相对M43纠正49/误改50，相对R47纠正45/误改48）；独立SLAKE113/114；VQA-RAD97/116。CheX OpenI退步至270/380。Skill共CREATE6条、最终active5条，均task_level；成功PATCH0，merge1；独立SLAKE/VQA最终库为空。

目标：在相同主模型下提高完整分母正确数，优先减少OpenI定位、侧别、严重程度题的误改，同时提高跨模型证据质量。CheX首先争取超过历史R47的468/618；长期+5pp目标相对M43至少497/618。它们是目标，不是预计收益。宏平均与微平均同时报告。

## 2. 本轮只做两项方法变更

1. 工具菜单仅保留MedGemma-4B、LLaVA-Rad、CheXagent、LLaVA-Med、MAIRA-2、MedVLM-R1六个模型。移除原classifier、report_generator、segmentation、image_visualizer、dicom_processor的可选接口；原图仍正常输入主控。模型动态选用，不固定全调用。
2. 修复skill_lifecycle_r49.retrieve内适用性筛选：`if len(candidates)>5 and prescreen:`改为`if candidates and prescreen:`。沿用现有PRESCREEN，允许返回空列表。不另加知识规则、人工答案、手工Skill库或新的强制复核阶段。

这是一组组合改进，不能把总差值单独归因工具或门控。暂不新增无Skill对照或消融，不重跑已有基线。

## 3. 工具名单

| 接口 | 模型/作用 |
|---|---|
| medgemma | google/medgemma-4b-it，医学视觉问答 |
| llava_rad | microsoft/llava-rad，胸片发现描述/报告 |
| chest_xray_expert | CheXagent，胸片问答 |
| llava_med_qa | LLaVA-Med，医学视觉问答 |
| xray_phrase_grounding | MAIRA-2，当前使用短语定位接口 |
| medvlm_r1 | JZPeterPan/MedVLM-R1，推理型视觉问答 |

MAIRA-2当前接口不等同于完整grounded report generation；六模型身份对齐，不宣称接口和CXRAgent完整实现等价。

复用现有cxr_vqa_extended_backends.py和历史C臂私人runtime中的模型路径、解释器、固定revision。不默认换成MedGemma1.5，不重新实现已有后端。历史记录显示三个工具曾部署过，但本次服务器状态仍需实际确认。

## 4. 保留设置

- 主模型qwen3.7-plus；temperature0.2、top_p0.95、max_output_tokens2048、thinking=false；META继续同主模型。部署时对照实际R49配置，不擅自改模型或采样。
- R49同图反馈机制、原图绑定、先保存预测后读取本题反馈；不读取未来题或当前未提交答案。
- 30题/学习窗口、最多20条学习轨迹、general/task/action三个分支、起始窗口快照固定、新Skill下一窗口生效；每两窗口治理。
- 每题主模型/工具调用总次数不设固定上限；保留有效终答、无进展和技术故障退出规则。
- 保留已完成R49的技术修复，包括MAIRA EOS guard和META schema修复，整轮采用一致已修复版本；记录与R49早期阶段的差异。
- 保留embedding模型text-embedding-v4/1024维及已有缓存规则。不得把缓存命中记作新模型推理，也不强制清空缓存重跑。

## 5. 实施顺序

### A. 零推理配置修改

从真实部署位置取R49 config和历史C臂PRIVATE runtime，不使用GitHub里[REDACTED]路径。运行：

```bash
python enable_r50_cxr6_tools.py --config /actual/r49/config.json --donor-runtime /actual/c/runtime_c_ready.json --out-dir /actual/new/r50_config
```

脚本同时更新M与R49-AGENT（R49启动会从M重建R49-AGENT），保留主模型配置和三个已有模型接口配置；输出新config.json和runtime.json，不覆盖原配置，不自动推理。路径为占位符，Codex使用已有服务器真实路径替换。

应用附带apply_fix.py中的单条件门控修复。新实验使用独立runner/module和ARM名，或在隔离checkout中修改ARM常量；不要改已归档R49代码与预测。检查日志、评分器、导出器使用一致的新臂名；不能只改目录而所有证据仍误标R49。

### B. 最小工具可用性检查

复用原部署环境。每个新增工具只做一次原图加载与推理健康检查，保存模型revision、输入图、输出、耗时和错误；优先使用非本轮计分健康样例。探针不进入Skill库、同图记忆或计分结果。不要重新测试全部旧工具，不建立重复审计/哈希门槛。

若三个工具均有健康结果，运行唯一新臂；若失败，修复具体部署问题并保留记录，不静默将工具剔除后仍称6工具实验。不要占用用户正在训练CT任务的GPU，沿已有调度选择空闲设备。

### C. 唯一新臂正式运行

依次CheXbench618 → 独立SLAKE114 → 独立VQA-RAD116。每组独立空Skill、空同图记忆；沿原始顺序与原图，全部848题新生成。不得用历史答案填充分母，也不得跨数据集导入最终库。

沿实际部署R49启动命令，只替换新runner、新config和新输出目录；API密钥继续原stdin/环境渠道，不写入计划或公开配置。保留每组先完成生成再统一计分。技术中断续跑已保存状态，不重写已完成预测。

本计划不自动增加其他实验臂。正式付费实验仅在执行环境已有相应授权时启动；当前对话交付计划和代码不等于已启动。

## 6. 必须输出的结果

1. 完整分母正确数、微平均、CheX三个子集及等权宏平均；技术终态保留在分母。
2. 与保存的M43/R47/R49逐题对齐：纠正、误改、净增；独立VQA历史100/116臂名为M42。旧直接作答记录若同题同图同主模型则复用对齐，不重跑；缺少可比档案就明确缺失。
3. 首次/单例与同图后续分组；有无Skill注入分组只作描述，不作随机对照。
4. 三个新工具各自选择题数、调用数、新推理/缓存数、错误数；实际0调用就写0，不能仅凭菜单启用认定有效。
5. PRESCREEN请求数、筛选前后候选数、全部拒绝题数、异物Skill在不相关题的注入例子；不得以提高命中率本身为目标。
6. CREATE/PATCH/merge/deprecate/mature实际事件、三分支数量、首产/首用、采用信用及正负例；继续允许零Skill结果，不降低门槛凑产出。
7. 主模型、META、embedding、工具成本/耗时分开，未知成本明确未知。同步输出工具新增前后的重复无进展调用情况。
8. 重点检查OpenI错误、chexbench_slake_0065、openi_0092/0302/0378及VQA回答类型；这些是事后分析切片，不只重跑这些题后拼接总成绩。

## 7. 结果判断

先看完整CheX正确数是否超过468，再看OpenI是否恢复、误改是否减少；宏平均单独记录。SLAKE113/114已接近上限，重点看是否保持；VQA目标先恢复至100/116以上。若整体不升，先分析新工具实际调用与冲突处理，而非自动扩展更多实验。

本轮是R49反馈/Skill流程＋6工具＋筛选修复的项目适配，不是CXRAgent完整复现；没有新增其完整Director/EDV/MDT架构，也不能叫Skill单独因果收益或未见测试SOTA。

## 8. 当前交付状态

配置转换脚本已完成；本地公开模板中6工具已列入M/R49-AGENT；六工具配置检查通过，门控包5项离线测试已通过。服务器实际模型加载、本轮探针、848题正式运行尚未在本对话执行。公开模板含脱敏路径，仅供检查，不能直接运行。

## 本版替代关系
本CXR6版本替代上一份CXR11计划。只运行CXR6新组，不并行运行CXR11。新增和移除工具、门控修复的共同变化必须披露。原始R49 Skill库保持归档，新实验仍空库；旧依赖classifier/report/segmentation的Skill不得导入。


## Actual source/config: experiments/cxr_online_primitives_r50.py
```
"""R50 semantic identities and healthy memory, without byte/pixel validation."""
import copy
import json
from pathlib import Path, PurePosixPath

from cxr_image_memory_r44 import tool_failure_reason


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


def digest(value):
    """Semantic comparison key, not a file/code/pixel checksum or path name."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def schedule(inputs, data=None, historical_order=None):
    """Reuse declared historical groups or canonical IDs/ordered relative paths."""
    ids = [row['question_id'] for row in inputs]
    if historical_order is not None:
        if isinstance(historical_order, dict):
            historical_order = historical_order['order']
        if [item['question_id'] for item in historical_order] != ids:
            raise ValueError('historical_order_ids_changed')
        seen, result, aliases = {}, [], {}
        for item in historical_order:
            raw = item['image_key']
            key = aliases.setdefault(raw, 'original_group_' + str(len(aliases) + 1))
            prior = seen.setdefault(key, [])
            if item['previous_ids'] != prior:
                raise ValueError('invalid_historical_processed_prefix')
            result.append({'question_id': item['question_id'], 'image_key': key, 'previous_ids': list(prior)})
            prior.append(item['question_id'])
        return result
    seen, bindings, result = {}, {}, []
    for row in inputs:
        images = []
        for name in row['images']:
            path = PurePosixPath(name.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or ':' in str(path):
                raise ValueError('image_outside_root')
            images.append(str(path))
        if not images:
            raise ValueError('no_original_images')
        key = digest(['image_id', row['image_id']] if row.get('image_id') is not None else ['relative_paths', images])
        if key in bindings and bindings[key] != images:
            raise ValueError('canonical_image_identity_path_conflict')
        bindings[key] = images
        prior = seen.setdefault(key, [])
        result.append({'question_id': row['question_id'], 'image_key': key, 'previous_ids': list(prior)})
        prior.append(row['question_id'])
    return result


def memory_entry(row, result):
    observations = result.get('observations') or result.get('inherited_observations') or []
    evidence = [{key: copy.deepcopy(value[key]) for key in ('tool', 'image_index', 'observation') if key in value}
                for value in observations if tool_failure_reason(value) is None]
    return {'question_id': row['question_id'], 'question': row['question'], 'options': row.get('options', {}),
            'previous_answer': result.get('answer'), 'previous_model_reason': result.get('reason'),
            'previous_status': result.get('status'), 'tool_evidence': evidence,
            'provenance': 'earlier_model_output_not_ground_truth'}


def assert_closed_sends(root, *, require_receipts=False):
    root = Path(root)
    for path in (root / 'services' / 'calls').glob('*/*/*/started.json'):
        if not (path.parent / 'response.json').is_file():
            raise RuntimeError('unknown_sent_no_reissue:' + str(path.parent.relative_to(root)))
        result = path.parent / 'result.json'
        if (require_receipts and not result.is_file()) or (result.is_file() and
                (read(result).get('error') or read(result).get('response_received') is not True)):
            raise RuntimeError('unclosed_request_receipt:' + str(path.parent.relative_to(root)))
    for path in (root / 'services' / 'embeddings').glob('*/started.json'):
        if not (path.parent / 'response.json').is_file():
            raise RuntimeError('unknown_embedding_send_no_retry')

```


## Actual source/config: experiments/online_memory_r50.py
```
"""R47 same-image memory primitives, preserved for the R50 online composition."""
import copy,json,os,uuid
from datetime import datetime,timezone
from pathlib import Path
from cxr_online_primitives_r50 import memory_entry as model_memory_entry,read
def now():
    return datetime.now(timezone.utc).isoformat()

def save_once(path, value):
    """Atomically publish JSON once; identical restarts never rewrite a file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if read(path) != value:
            raise ValueError('immutable_artifact_changed:' + path.name)
        return False
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if read(path) != value:
                raise ValueError('immutable_artifact_changed:' + path.name) from None
            return False
    finally:
        if temporary.exists():
            temporary.unlink()
    return True

def safe_qid(qid):
    if not isinstance(qid, str) or not qid or Path(qid).name != qid or '/' in qid or '\\' in qid or qid in ('.', '..'):
        raise ValueError('unsafe_question_id')
    return qid

class ReferenceVault:
    """One reference-file read, permitted only after its prediction is on disk."""
    def __init__(self, directory, manifest):
        self.directory = Path(directory)
        self.manifest = manifest

    def after_prediction(self, qid, prediction_path):
        safe_qid(qid)
        prediction_path = Path(prediction_path)
        if not prediction_path.is_file():
            raise ValueError('reference_before_prediction_save')
        prediction = read(prediction_path)
        if prediction.get('question_id') != qid:
            raise ValueError('prediction_identity_changed')
        event_path = prediction_path.parents[2] / 'prediction_events' / (qid + '.json')
        if not event_path.is_file():
            raise ValueError('reference_before_prediction_event_save')
        event = read(event_path)
        if event.get('question_id') != qid or event.get('saved_prediction') != prediction:
            raise ValueError('saved_prediction_event_binding_changed')
        item = self.manifest[qid]
        if item['file'] != qid + '.json':
            raise ValueError('invalid_reference_file_manifest')
        path = self.directory / item['file']
        reference = read(path)
        if reference.get('question_id') != qid or not isinstance(reference.get('answer'), str) or not reference['answer'].strip():
            raise ValueError('invalid_reference_record')
        if 'answer_text' in reference and not isinstance(reference['answer_text'], str):
            raise ValueError('invalid_reference_answer_text')
        return reference

def memory_entry(row, result, event):
    qid = row['question_id']
    if event['question_id'] != qid or result.get('question_id') != qid:
        raise ValueError('memory_identity_changed')
    entry = model_memory_entry(row, result)
    annotation = copy.deepcopy(event['reference_annotation'])
    options = row.get('options') or {}
    if annotation['answer'] in options:
        annotation['option_text'] = options[annotation['answer']]
    entry['reference_annotation'] = annotation
    entry['provenance'] = 'unchanged_prior_model_output_with_post_prediction_dataset_feedback'
    # Internal binding is omitted from the model-facing serialization.
    entry['_feedback_event'] = copy.deepcopy(event)
    return entry

def context(entries, current_item, ordinal, max_chars=12000, max_entries=8):
    """Select whole records from exactly this image's already-processed prefix."""
    allowed = set(current_item['previous_ids'])
    eligible = []
    for entry in entries:
        event = entry['_feedback_event']
        if (entry['question_id'] in allowed and entry['question_id'] != current_item['question_id']
                and event['image_key'] == current_item['image_key'] and event['ordinal'] < ordinal):
            eligible.append(entry)
    # Expected order is authoritative; reject duplicates and omit unrelated/future entries.
    by_id = {entry['question_id']: entry for entry in eligible}
    if len(by_id) != len(eligible):
        raise ValueError('duplicate_memory_entry')
    eligible = [by_id[qid] for qid in current_item['previous_ids'] if qid in by_id]
    if set(by_id) != allowed:
        raise ValueError('incomplete_committed_same_image_prefix')
    picked, used = [], 0
    for entry in reversed(eligible[-max_entries:]):
        displayed = {key: copy.deepcopy(value) for key, value in entry.items() if not key.startswith('_')}
        displayed['tool_evidence'] = [value for value in displayed['tool_evidence'] if len(json.dumps(value, ensure_ascii=False)) <= 4000]
        size = len(json.dumps(displayed, ensure_ascii=False))
        if used + size > max_chars:
            continue
        picked.append(displayed)
        used += size
    picked.reverse()
    if not picked:
        if allowed:
            raise ValueError('repeat_question_has_empty_memory')
        return None, []
    prompt = (
        'Earlier questions about the EXACT SAME supplied original image(s), in chronological order. '
        'The prior model answers, reasons and statuses are unchanged fallible model judgments. '
        'reference_annotation contains the dataset reference answer released AFTER that earlier prediction was saved. '
        'These are feedback annotations for their originating questions, not additional patient history or clinical adjudication. '
        'Bind each reference answer to its own earlier question and options; never copy an earlier option letter to the CURRENT question. '
        'Tool observations are auxiliary evidence. Reinspect the original pixels and answer the CURRENT wording and options. '
        'This same-image section contains no current or future reference answer, future question/options, or other-image episodes. Separately supplied procedural skills may derive from earlier completed cases.\n'
        + json.dumps(picked, ensure_ascii=False)
    )
    return prompt, [entry['question_id'] for entry in picked]

```


## Actual source/config: experiments/prepare_feedback_r50.py
```
"""Convert label JSONL to separate feedback files. Run before the inference process."""
import argparse
from pathlib import Path
from cxr_online_primitives_r50 import rows
from online_memory_r50 import safe_qid,save_once

def main():
 p=argparse.ArgumentParser();p.add_argument('--references',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 records=rows(a.references);ids=[safe_qid(x['question_id']) for x in records]
 if len(set(ids))!=len(ids):raise ValueError('duplicate_reference_id')
 for r in records:
  if not isinstance(r.get('answer'),str) or not r['answer'].strip():raise ValueError('answer_must_be_canonical_string')
  save_once(a.out/(r['question_id']+'.json'),{k:r[k] for k in ('question_id','answer','answer_text') if k in r})
 print({'reference_files':len(records),'model_calls':0})
if __name__=='__main__':main()

```


## Actual source/config: experiments/run_online_skill_r50.py
```
"""Single-arm online R47 same-image feedback + SkeMex-inspired window skill evolution.
No target label reaches inference before that question's immutable prediction.
"""
import argparse,copy,json,math,sys
from pathlib import Path
from cxr_online_primitives_r50 import read,rows,schedule,assert_closed_sends,tool_failure_reason
from online_memory_r50 import save_once,now,safe_qid,ReferenceVault,memory_entry,context
from skill_lifecycle_r50 import DEFAULTS,initial,retrieve,category
from skill_prompts_r50 import PRESCREEN
from skill_services_r50 import Services,conditioning
from skill_evolve_r50 import evolve
ARM='M43-IM-GT-S50-CXR6'

def released_reward(row,result,reference):
    from cxr_author_alignment import extract,choice,m4cxr_normalize
    answer=extract(result.get('terminal_raw'),row['question_id'],row.get('options')).answer
    y=reference['answer']
    if answer is None:return 0
    return int(choice(answer,row['options'])==y if row.get('options') else m4cxr_normalize(answer)==m4cxr_normalize(y))

def validate_prefix(out,ids):
    predictions={p.stem for p in (out/'predictions'/ARM).glob('*.json')}
    feedback={p.stem for p in (out/'feedback').glob('*.json')}
    n=len(predictions)
    if predictions!=set(ids[:n]):raise ValueError('predictions_not_sequential_prefix')
    if feedback not in (set(ids[:n]),set(ids[:max(0,n-1)])):raise ValueError('feedback_not_saved_prediction_prefix')
    for name in ('contexts','steps'):
        members={p.stem for p in (out/name).glob('*.json')}
        if members not in (set(ids[:n]),set(ids[:min(len(ids),n+1)])):raise ValueError(name+'_not_sequential_prefix')
    events={p.stem for p in (out/'prediction_events').glob('*.json')}
    if events not in (set(ids[:n]),set(ids[:max(0,n-1)])):raise ValueError('prediction_events_not_saved_prefix')

def run_stream(inputs,order,data,out,service,vault,tools,config=None,*,evolver=evolve,reward_fn=released_reward):
    """Replay saved commits on restart; only unfinished work invokes cached API services."""
    out=Path(out);cfg=copy.deepcopy(config or DEFAULTS);ids=[r['question_id'] for r in inputs]
    if not inputs or len(set(ids))!=len(ids):raise ValueError('empty_or_duplicate_stream')
    if [x['question_id'] for x in order]!=ids:raise ValueError('order_mismatch')
    validate_prefix(out,ids);assert_closed_sends(out);repo=initial();memory={};history=[]
    for wi,start in enumerate(range(0,len(inputs),cfg['window'])):
        window=out/'windows'/f'{wi:04d}';snapshot=copy.deepcopy(repo);batch=[]
        save_once(window/'read_snapshot.json',snapshot)
        for index in range(start,min(start+cfg['window'],len(inputs))):
            row=inputs[index];item=order[index];q=safe_qid(row['question_id']);ordinal=index+1
            predpath=out/'predictions'/ARM/(q+'.json');ctxpath=out/'contexts'/(q+'.json')
            prior=memory.setdefault(item['image_key'],[])
            same_text,same_ids=context(prior,item,ordinal)
            if ctxpath.exists():
                ctx=read(ctxpath)
                if ctx['skill_snapshot']!=snapshot or ctx['same_image_ids']!=same_ids or ctx['same_image_context']!=same_text:raise ValueError('resume_context_changed')
                selected=ctx['selected_skills']
                for selected_item in selected:
                    source=snapshot['skills'].get(selected_item['id'])
                    if not source or selected_item['c']!=source['c'] or source['status'] not in ('active','mature'):
                        raise ValueError('selected_skill_not_in_window_snapshot')
            else:
                selected=[]
                if any(s['status'] in ('active','mature') for s in snapshot['skills'].values()):
                    vec=service.embed(row['question']+' '+json.dumps(row.get('options',{})))
                    def screen(pool):
                        chosen=service.meta('screen_'+q,PRESCREEN,{'question':row['question'],'options':row.get('options',{}),'candidates':pool})['ids']
                        save_once(out/'prescreen_events'/(q+'.json'),{'question_id':q,'window':wi,
                            'input_pool_ids':[x['id'] for x in pool],'input_pool_count':len(pool),
                            'returned_ids':copy.deepcopy(chosen),'returned_count':len(chosen),
                            'all_rejected':not bool(chosen),'scope':'actual prescreen input after unchanged per-branch top5; no current label'})
                        return chosen
                    selected=retrieve(snapshot,vec,category(row['question']),tools,cfg,screen)
                ctx={'question_id':q,'ordinal':ordinal,'window':wi,'skill_snapshot':copy.deepcopy(snapshot),
                     'selected_skills':selected,'same_image_ids':same_ids,'same_image_context':same_text}
                save_once(ctxpath,ctx)
            if predpath.exists():result=read(predpath)
            else:
                sections=[s for s in (conditioning(selected),same_text) if s]
                result,calls=service.execute(row,'r50_unbounded',data,'\n\n'.join(sections) or None)
                # Persist steps first; no feedback reader has been called for q yet.
                save_once(out/'steps'/(q+'.json'),calls)
                result.update(question_id=q,arm=ARM,ordinal=ordinal,prediction_saved_at=now(),
                              selected_skill_ids=[s['id'] for s in selected],same_image_ids=same_ids)
                save_once(predpath,result)
            if (result.get('question_id')!=q or result.get('arm')!=ARM or result.get('ordinal')!=ordinal
                    or result.get('selected_skill_ids')!=[s['id'] for s in selected] or result.get('same_image_ids')!=same_ids):
                raise ValueError('saved_prediction_context_identity_changed')
            if any(tool_failure_reason(value) for value in result.get('observations',[])):
                raise RuntimeError('saved_prediction_contains_failed_tool')
            prediction_event={'question_id':q,'arm':ARM,'ordinal':ordinal,'image_key':item['image_key'],'saved_prediction':copy.deepcopy(result)}
            save_once(out/'prediction_events'/(q+'.json'),prediction_event)
            eventpath=out/'feedback'/(q+'.json')
            if eventpath.exists():
                event=read(eventpath)
                if event['saved_prediction']!=result or event['ordinal']!=ordinal or event['question_id']!=q or event['image_key']!=item['image_key']:raise ValueError('feedback_binding_changed')
            else:
                reference=vault.after_prediction(q,predpath)
                event={'question_id':q,'ordinal':ordinal,'image_key':item['image_key'],'saved_prediction':copy.deepcopy(result),
                       'reference_annotation':{k:reference[k] for k in ('answer','answer_text') if k in reference},
                       'released_at':now(),'timing':'after_immutable_prediction','provenance':'dataset_annotation_feedback_not_patient_history'}
                save_once(eventpath,event)
            # Only released feedback is now eligible for same-image memory and Skill learning.
            prior.append(memory_entry(row,result,event))
            trace={'id':q,'row':row,'category':category(row['question']),
                   'reward':reward_fn(row,result,event['reference_annotation']),
                   'source_label':event['reference_annotation']['answer'],'prediction':result,
                   'steps':read(out/'steps'/(q+'.json')),'injected':[s['id'] for s in selected],
                   'injected_content':selected,'same_image_context':same_text,'feedback_ordinal':ordinal,
                   'technical_failure':False,'max_step_failure':False,
                   'repeated_no_progress':result.get('status','').startswith('repeated_')}
            save_once(window/'trajectories'/(q+'.json'),trace);batch.append(trace)
        finish=window/'repo.json'
        if finish.exists():repo=read(finish)
        else:
            repo=evolver(service,snapshot,batch,wi,window,data,tools,cfg)
            save_once(finish,repo)
        history.append({'window':wi,'episodes':len(batch),'correct':sum(t['reward'] for t in batch),
                        'active_skills':sum(s['status'] in ('active','mature') for s in repo['skills'].values()),
                        'skill_hit_questions':sum(bool(t['injected']) for t in batch)})
    assert_closed_sends(out,require_receipts=True)
    expected=set(ids)
    for folder in (out/'predictions'/ARM,out/'contexts',out/'steps',out/'prediction_events',out/'feedback'):
        if {p.stem for p in folder.glob('*.json')}!=expected:raise ValueError('incomplete_artifact_membership:'+folder.name)
    for p in (out/'services'/'tool_selections'/'R50-AGENT').glob('*/*.json'):
        if tool_failure_reason(read(p)):raise RuntimeError('unhealthy_tool_selection')
    save_once(out/'final_repo.json',repo)
    save_once(out/'complete.json',{'status':'generation_complete','arm':ARM,'questions':len(inputs),'windows':history,'mode':'online_post_prediction_feedback',
              'fixed_main_call_limit':None,'fixed_tool_call_limit':None,'final_repo':copy.deepcopy(repo)})
    return history

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','data','reference-dir','out'):p.add_argument('--'+k,type=Path,required=True)
    p.add_argument('--embedding-model',required=True)
    p.add_argument('--embedding-base-url',required=True)
    p.add_argument('--order-manifest',type=Path)
    p.add_argument('--dataset',choices=('chexbench','slake','vqarad'),default='chexbench')
    p.add_argument('--expect-questions',type=int,default=618)
    p.add_argument('--execute',action='store_true');p.add_argument('--api-key-stdin',action='store_true');a=p.parse_args()
    inputs=rows(a.data/'inputs.jsonl');ids=[safe_qid(x['question_id']) for x in inputs]
    if len(inputs)!=a.expect_questions or len(set(ids))!=len(ids):raise ValueError('cohort_size_or_ids')
    allowed={'question_id','question','images','image_id','source','options'}
    if any(set(x)-allowed for x in inputs):raise ValueError('inference_fields_include_labels')
    order=schedule(inputs,a.data,read(a.order_manifest) if a.order_manifest else None);cfg=read(a.config);protocol=read(cfg['protocol']);runtime=read(cfg['runtime'])
    from cxr_image_memory_gt_r47 import validate_protocol
    validate_protocol(protocol)
    if a.dataset=='chexbench' and a.expect_questions==618 and (len({x['image_key'] for x in order})!=488 or sum(bool(x['previous_ids']) for x in order)!=130):raise ValueError('original_CheXbench_group_partition_required')
    tools=runtime['arms']['M']['tools'];runtime['arms']={x:copy.deepcopy(runtime['arms']['M']) for x in ('M','R50-AGENT')}
    for row in inputs:
        for name in row['images']:
            image=(a.data/name).resolve()
            if not image.is_relative_to(a.data.resolve()) or not image.is_file():raise ValueError('missing_or_outside_original_image')
    refs={q:{'file':q+'.json'} for q in ids}
    # Existence checks do not open any current/future annotation during inference setup.
    if any(not (a.reference_dir/(q+'.json')).is_file() for q in ids):raise ValueError('missing_reference_file')
    manifest={'schema':'r50_online_semantic_v1','arm':ARM,'dataset':a.dataset,'inputs':copy.deepcopy(inputs),'order':order,
              'reference_files':refs,'config':cfg,'protocol':protocol,'runtime':runtime,'defaults':DEFAULTS,
              'embedding_model':a.embedding_model,'embedding_base_url':a.embedding_base_url,'policy':'unbounded_adapted_M43_components',
              'r50_method_changes':['six_model_tool_menu','prescreen_for_any_nonempty_candidate_pool'],
              'r50_baseline_controls':{'MAIRA_EOS_guard':'uniform_from_start','MUTATE_fields_clarification':True,'ANALYZE_unique_adoption_clarification':True,'old_failure_registrations_imported':False},
              'initial_repo':'empty','same_image_entries':8,'same_image_chars':12000,
              'grouping':'declared_historical_metadata' if a.order_manifest else 'canonical_image_id_or_relative_paths',
              'implementation_files':sorted(f.name for f in Path(__file__).parent.glob('*r50.py'))}
    if not a.execute:
        print(json.dumps({'questions':len(inputs),'groups':len({x['image_key'] for x in order}),
          'same_image_followups':sum(bool(x['previous_ids']) for x in order),'windows':math.ceil(len(inputs)/30),
          'arms':[ARM],'paid_calls':0,'needs_separate_source_pool':False},ensure_ascii=False));return
    if not a.api_key_stdin:raise ValueError('stdin_key_required')
    key=sys.stdin.readline().strip()
    if not key:raise ValueError('missing_key')
    import run_cxr_vqa_toolsets as base
    a.out.mkdir(parents=True,exist_ok=True)
    with base.exclusive_lock(a.out/'.online.lock'):
        save_once(a.out/'manifest.json',manifest)
        vault=ReferenceVault(a.reference_dir,refs)
        from r50_baseline_controls import validate_runtime
        validate_runtime(runtime)
        service=Services(cfg,protocol,runtime,a.out/'services',key,a.embedding_model,a.embedding_base_url)
        history=run_stream(inputs,order,a.data,a.out,service,vault,tools)
        print({'completed':len(inputs),'arm':ARM,'windows':len(history)})
if __name__=='__main__':main()

```


## Actual source/config: experiments/skill_services_r50.py
```
"""Cached API services and adapted M43 components for online R50; no automatic retries."""
import copy,json,math,os,time
from pathlib import Path
from cxr_online_primitives_r50 import read,digest,tool_failure_reason
from online_memory_r50 import save_once as write,now
from skill_lifecycle_r50 import category
class Services:
    @staticmethod
    def text_semantics(value):
        """Compare text/control flow while explicitly excluding image payloads."""
        if isinstance(value,list):return [Services.text_semantics(item) for item in value]
        if isinstance(value,dict):
            if value.get('type')=='image_url':
                image=value.get('image_url')
                parameters={key:item for key,item in image.items() if key!='url'} if isinstance(image,dict) else {}
                return {**{key:Services.text_semantics(item) for key,item in value.items() if key!='image_url'},'image_url':parameters}
            return {key:Services.text_semantics(item) for key,item in value.items()}
        return value
    def call(self,row,arm,ordinal,messages):
        folder=self.out/'calls'/arm/row['question_id']/str(ordinal)
        if (folder/'response.json').is_file():
            if not (folder/'request.json').is_file():raise ValueError('saved_response_without_request')
            request=read(folder/'request.json')
            if self.text_semantics(request.get('messages'))!=self.text_semantics(messages):
                raise ValueError('saved_request_text_semantics_changed')
            for key,value in (('model',self.protocol['model']),('temperature',self.protocol['temperature']),
                              ('top_p',self.protocol['top_p']),('max_tokens',self.protocol['max_output_tokens'])):
                if request.get(key)!=value:raise ValueError('saved_request_model_parameter_changed:'+key)
        return self.paid.call(row,arm,ordinal,messages)
    def __init__(self,cfg,protocol,runtime,out,key,embedding_model,embedding_base_url=None):
        import run_cxr_vqa_toolsets as base
        self.base=base;self.runtime=runtime;self.protocol=copy.deepcopy(protocol);self.out=Path(out);self.embed_model=embedding_model
        self.protocol.update(experiment_id='skill_lifecycle_r50',request_archive='inline_original_images_semantic_restart_r50')
        self.protocol['main_call_limits']={}  # No numerical per-question ceiling; local ledger disabled below.
        self.protocol['budget']={'existing_shared_ledger':False,'enforce_money_cap':False}
        self.protocol['tool_call_limits']={}
        self.paid=base.PaidCalls(cfg,self.protocol,self.out,key)
        from openai import OpenAI
        self.embedding_client = OpenAI(api_key=os.environ.get('R50_EMBEDDING_API_KEY') or key,
            base_url=embedding_base_url or self.paid.profile.base_url,max_retries=0,
            timeout=cfg.get('request_timeout_seconds',120))
        self.tools=None
    def embed(self,text):
        request={'model':self.embed_model,'input':text}
        root=self.out/'embeddings';root.mkdir(parents=True,exist_ok=True)
        folder=None
        for candidate in sorted(root.iterdir()):
            if candidate.is_dir() and (candidate/'request.json').is_file() and read(candidate/'request.json')==request:
                folder=candidate;break
        if folder is None:folder=root/f'{len(list(root.iterdir()))+1:06d}'
        path=folder/'response.json'
        if path.is_file():
            response=read(path)
            if not (folder/'result.json').exists():
                write(folder/'result.json',{'response_received':True,'model_returned':response.get('model'),
                    'usage':response.get('usage'),'elapsed_s':None,'error':None,'recovered_from_saved_response':True,
                    'accounting':'embedding_provider_usage_record_only_not_invoice','utc':now()})
        else:
            if (folder/'started.json').exists():raise RuntimeError('unknown_embedding_send_no_retry')
            write(folder/'request.json',request);write(folder/'started.json',{'sent_intent':True,'utc':now()})
            tick=time.monotonic()
            try:
                response=self.embedding_client.embeddings.create(**request).model_dump();write(path,response)
            except Exception as exc:
                write(folder/'result.json',{'response_received':False,'error_type':type(exc).__name__,
                    'elapsed_s':time.monotonic()-tick,'usage':None,'utc':now()})
                raise RuntimeError('embedding_api_failure_no_automatic_retry:'+type(exc).__name__) from None
            write(folder/'result.json',{'response_received':True,'model_returned':response.get('model'),
                'usage':response.get('usage'),'elapsed_s':time.monotonic()-tick,'error':None,
                'accounting':'embedding_provider_usage_record_only_not_invoice','utc':now()})
        if response.get('model')!=self.embed_model:raise RuntimeError('embedding_returned_model_identity_mismatch')
        data=response.get('data')
        if not isinstance(data,list) or len(data)!=1:raise ValueError('invalid_embedding_response')
        vector=data[0].get('embedding')
        if not isinstance(vector,list) or not vector or any(type(x) not in (int,float) or not math.isfinite(x) for x in vector):raise ValueError('invalid_embedding_vector')
        return vector
    def meta(self,event,system,payload,image_row=None,data=None):
        content=[{'type':'text','text':json.dumps(payload,ensure_ascii=False)}]
        if image_row is not None:content+=self.base.content(image_row,Path(data))
        messages=[{'role':'system','content':system},{'role':'user','content':content}]
        raw=self.call({'question_id':event},'R50-META',1,messages)
        # Preserve raw failure; no unbudgeted JSON repair.
        from run_cxr_action_r41 import parse
        return parse(raw)
    def execute(self,row,policy,data,conditioning):
        # policy retained only as provenance. BOTH new arms use this unbounded executor.
        from run_cxr_action_r41 import parse,answer
        from cxr_task_completion_r43 import prompt
        if self.tools is None:self.tools=self.base.Tools(self.runtime,Path(data),self.out)
        system=self.base.agent_system('M').replace('You may select zero, one or two registered tools, with early stopping when appropriate.',
            'Select useful registered tools as needed; there is no fixed total call-count limit. Stop when sufficient evidence supports an answer.')
        if conditioning:system=system.replace('No cross-case skills, sibling question context or additional patient history is available.',
            'Optional learned procedural skills and previously completed same-image questions with post-prediction dataset feedback may be supplied. Skills are not current-patient facts. No current or future reference answer is supplied.')
        messages=[{'role':'system','content':system},{'role':'user','content':self.base.content(row,Path(data))}]
        if conditioning:messages.append({'role':'user','content':conditioning})
        observations=[];calls=[];seen={};n=0;used=0;invalid=0;next_prompt=None
        action=self.base.ACTION.replace('At most two selectable tool calls total.','No fixed total tool-call count limit.')
        if len(row['images'])>1:action=action.replace('"args":{}','"args":{},"image_index":1').replace('Each call applies only to the bound original.','Select numbered original via image_index.')
        while True:
            n+=1
            messages.append({'role':'user','content':next_prompt or action+json.dumps(self.base.evidence_catalog(self.runtime,'M'))})
            raw=self.call(row,'R50-AGENT',n,messages);calls.append({'step_index':n-1,'response':raw})
            messages.append({'role':'assistant','content':raw});next_prompt=None
            try:obj=parse(raw)
            except (ValueError,IndexError):obj={}
            result=answer(obj)
            if result:
                from cxr_task_completion_r43 import unscorable
                if not unscorable(row,result):
                    result.update(main_calls=n,tool_calls=used,observations=observations,terminal_raw=raw)
                    return result,calls
            actions=obj.get('calls')
            if not isinstance(actions,list) or not actions:
                invalid+=1
                if invalid>=3:return {'answer':None,'reason':None,'status':'repeated_invalid_output','main_calls':n,'tool_calls':used,'observations':observations,'terminal_raw':raw},calls
                next_prompt=prompt(row);continue
            try:actions=self.base.validate_actions(obj,self.runtime,'M',len(actions),len(row['images']))
            except (ValueError,TypeError,KeyError):
                invalid+=1
                if invalid>=3:return {'answer':None,'reason':None,'status':'repeated_invalid_plan','main_calls':n,'tool_calls':used,'observations':observations,'terminal_raw':raw},calls
                next_prompt='Use only registered tool names and valid arguments, or give final answer/reason JSON.';continue
            fresh=[]
            for action_item in actions:
                actual=self.base.resolve_action(action_item,observations);signature=digest(actual);seen[signature]=seen.get(signature,0)+1
                if seen[signature]>=3:
                    return {'answer':None,'reason':None,'status':'repeated_identical_action_no_progress','main_calls':n,'tool_calls':used,'observations':observations,'terminal_raw':raw},calls
                used+=1;obs=self.tools.call(row,actual,'R50-AGENT',used)
                failure=tool_failure_reason(obs)
                if failure:raise RuntimeError('tool_failure_stop_no_automatic_retry:'+failure)
                observations.append(obs);fresh.append(obs)
            self.base.append_observations(messages,fresh,self.out,'M')


def conditioning(skills):
    if not skills:return None
    return ('Source-derived procedural skills, not observations or answers about the current patient. '
      'Use only when their conditions are met; unsupported prior conclusions must not override current pixels. '
      'Tool use remains optional.\n'+json.dumps([{'skill_id':x['id'],**x['c']} for x in skills],ensure_ascii=False))

```


## Actual source/config: experiments/skill_lifecycle_r50.py
```
"""Three-branch lifecycle. Paper mechanisms with explicitly documented CXR adaptations."""
import copy,math,json,hashlib
from collections import Counter,defaultdict
BRANCHES=('general','task_level','action_level')
DEFAULTS=dict(window=30,buffer=20,top_k=6,similarity_min=.2,merge_similarity=.8,
             weights=[.4,.4,.2],ema=.2,baseline_min=3,lr_base=.05,lr_max=.2,warmup=5,decay=20,
             positive=1.,negative=.1,harm=.5,epsilon=.02,strength_tau=60,
             govern_every=2,deprecate=.3,mature=.75,mature_usage=15,
             capacities={'general':12,'task_level':8,'action_level':5})
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def cosine(a,b):
    if len(a)!=len(b):raise ValueError('embedding_dimension')
    d=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    return sum(x*y for x,y in zip(a,b))/d if d else 0.
def initial():return {'schema':'r50','skills':{},'baselines':{},'window':0,'clock':0,'frozen':False}
def validate(c,tools):
    required={'name','description','applicable_conditions','branch','tool_name','task_category','required_tools','risk_level','core_action'}
    if set(c)!=required:raise ValueError('skill_fields')
    for k in ('name','description','applicable_conditions','task_category','core_action'):
        if not isinstance(c[k],str) or not c[k].strip() or len(c[k])>2400:raise ValueError('text:'+k)
    if c['branch'] not in BRANCHES or c['risk_level'] not in ('low','medium','high'):raise ValueError('branch_or_risk')
    if not isinstance(c['required_tools'],list) or not set(c['required_tools'])<=set(tools):raise ValueError('unknown_tools')
    if c['branch']=='action_level' and (c['tool_name'] not in tools or c['tool_name'] not in c['required_tools']):raise ValueError('action_tool')
    if c['branch']!='action_level' and c['tool_name'] is not None:raise ValueError('unexpected_tool_name')
    return c
def scope(c):return (c['branch'], c['tool_name'] if c['branch']=='action_level' else c['task_category'] if c['branch']=='task_level' else 'all')
def category(question):
    # Deterministic CXR task router, explicitly differs from paper LLM category classification.
    import re
    q=question.lower()
    for label,pat in [('comparison','prior|previous|interval|compared|change'),('location','where|location|lobe|left|right|side'),
      ('severity','severity|size|extent|mild|moderate'),('view','view|projection|position|plane'),('diagnosis','diagnos|likely|cause'),
      ('count','how many|number of'),('morphology','shape|pattern|appearance|describe')]:
        if re.search(pat,q):return label
    return 'presence'
def learning_rate(n,cfg):
    if n<=cfg['warmup']:return cfg['lr_base']+(cfg['lr_max']-cfg['lr_base'])*n/cfg['warmup']
    progress=min(1,(n-cfg['warmup'])/cfg['decay'])
    return cfg['lr_base']+(cfg['lr_max']-cfg['lr_base'])*.5*(1+math.cos(math.pi*progress))
def retrieve(repo,query_vector,cat,tools,cfg,prescreen=None):
    candidates=[]
    for sid,m in repo['skills'].items():
        c=m['c']
        if m['status'] not in ('active','mature') or not set(c['required_tools'])<=set(tools):continue
        if c['branch']=='task_level' and c['task_category']!=cat:continue
        sim=cosine(query_vector,m['vector'])
        if sim<cfg['similarity_min']:continue
        u=m['u_by_category'].get(cat,m['u']) if c['branch']=='general' else m['u']
        h=math.exp(-max(0,repo['clock']-m['last_reinforced'])/cfg['strength_tau'])
        score=sum(w*v for w,v in zip(cfg['weights'],[sim,u,h]))*(1.1 if m['status']=='mature' else 1)
        candidates.append({'id':sid,'branch':c['branch'],'score':score,'similarity':sim,'c':c})
    candidates.sort(key=lambda x:(-x['score'],x['id']))
    if candidates and prescreen:
        pool=[x for b in BRANCHES for x in [y for y in candidates if y['branch']==b][:5]]
        chosen=prescreen(pool)
        if not set(chosen)<={x['id'] for x in pool}:raise ValueError('prescreen_unknown_id')
        candidates=[x for x in pool if x['id'] in chosen];candidates.sort(key=lambda x:(-x['score'],x['id']))
    # Round-robin branch balancing is our explicit allocation rule (paper leaves tie details open).
    queues={b:[x for x in candidates if x['branch']==b] for b in BRANCHES};selected=[]
    while len(selected)<cfg['top_k']:
        added=False
        for b in BRANCHES:
            if queues[b] and len(selected)<cfg['top_k']:selected.append(queues[b].pop(0));added=True
        if not added:break
    return selected

def gate(t):
    if t.get('technical_failure') or t.get('max_step_failure') or t.get('repeated_no_progress'):return False
    steps=t['steps']
    if t['reward']==1 and len(steps)<=2:return False
    signatures=Counter(digest(x) for x in steps)
    return not any(n>=3 for n in signatures.values())
def buffer_select(trajectories,cfg):
    valid=[t for t in trajectories if gate(t)];counts=Counter(t['category'] for t in valid)
    def rank(t):return (math.log1p(len(t['steps']))+bool(t['injected']))/(1+counts[t['category']])
    good=sorted([t for t in valid if t['reward']>0],key=lambda t:(-rank(t),t['id']))
    bad=sorted([t for t in valid if t['reward']<=0],key=lambda t:(-rank(t),t['id']))
    cap=cfg['buffer'];selected=good[:cap//2]+bad[:cap//2];ids={t['id'] for t in selected}
    rest=sorted([t for t in valid if t['id'] not in ids],key=lambda t:(-rank(t),t['id']))
    return selected+rest[:cap-len(selected)]

def assess(repo,trajectories,analyses,cfg):
    if repo['frozen']:raise ValueError('frozen_repo')
    contributions=defaultdict(list);events=[]
    for t in trajectories:
        baseline=repo['baselines'].get(t['category'],{'n':0,'mean':.5})
        adv=t['reward']-(baseline['mean'] if baseline['n']>=cfg['baseline_min'] else .5)
        attributed=set()
        for adoption in analyses.get(t['id'],{}).get('skill_adoption',[]):
            sid=adoption['skill_id'];status=adoption['status']
            if sid in attributed:raise ValueError('duplicate_skill_adoption')
            attributed.add(sid)
            if sid not in t['injected'] or sid not in repo['skills']:raise ValueError('adoption_not_injected')
            if status not in ('ADOPTED_POSITIVE','ADOPTED_NEGATIVE','IGNORED'):raise ValueError('adoption_status')
            if status=='IGNORED':continue
            # An evidence index is mandatory; adoption is an LLM attribution, not causal proof.
            index=adoption['step_index']
            if type(index)!=int or not 0<=index<len(t['steps']) or not adoption.get('evidence'):raise ValueError('adoption_evidence')
            m=repo['skills'][sid];u=m['u_by_category'].get(t['category'],m['u']) if m['c']['branch']=='general' else m['u']
            credit=cfg['positive']*adv if status=='ADOPTED_POSITIVE' else -(cfg['negative']+cfg['harm']*max(0,-adv))-cfg['epsilon']*u
            key=(sid,t['category'] if m['c']['branch']=='general' else '*');contributions[key].append(credit)
            events.append({'trajectory':t['id'],'skill':sid,'advantage':adv,'credit':credit,'status':status})
            m['usage']+=1
            if status=='ADOPTED_POSITIVE':m['last_reinforced']=repo['clock']
    for (sid,cat),values in contributions.items():
        m=repo['skills'][sid];old=m['u_by_category'].get(cat,m['u']) if cat!='*' else m['u']
        new=max(0,min(1,old+learning_rate(m['usage'],cfg)*sum(values)/len(values)))
        if cat=='*':m['u']=new
        else:m['u_by_category'][cat]=new;m['u']=sum(m['u_by_category'].values())/len(m['u_by_category'])
    groups=defaultdict(list)
    for t in trajectories:
        if not t.get('technical_failure'):groups[t['category']].append(t['reward'])
    for cat,values in groups.items():
        old=repo['baselines'].get(cat,{'n':0,'mean':.5});mean=sum(values)/len(values)
        repo['baselines'][cat]={'n':old['n']+len(values),'mean':(1-cfg['ema'])*old['mean']+cfg['ema']*mean}
    return events

def commit(repo,operation,content,vector,source_ids,tools,target=None):
    if repo['frozen']:raise ValueError('frozen_repo')
    validate(content,tools)
    if operation=='CREATE':
        sid='s_'+digest([content,source_ids])[:16]
        if sid in repo['skills']:return sid
        repo['skills'][sid]={'k':content['name']+' '+content['description'],'c':content,'u':.5,'u_by_category':{},'usage':0,
            'vector':vector,'status':'active','last_reinforced':repo['clock'],'source_ids':source_ids,'versions':[]}
    elif operation=='PATCH':
        sid=target
        if sid not in repo['skills']:raise ValueError('patch_missing')
        m=repo['skills'][sid]
        if scope(m['c'])!=scope(content):raise ValueError('patch_scope_changed')
        m['versions'].append({'c':m['c'],'vector':m['vector'],'window':repo['window']})
        m.update(c=content,k=content['name']+' '+content['description'],vector=vector,
            source_ids=sorted(set(m['source_ids']+source_ids)))
    else:raise ValueError('operation')
    return sid

def govern(repo,cfg,merge):
    if repo['frozen']:raise ValueError('frozen_repo')
    events=[];skills=repo['skills']
    for sid,m in skills.items():
        if m['status'] not in ('active','mature'):continue
        if m['u']<cfg['deprecate'] and m['usage']>0:m['status']='deprecated';events.append(['deprecate',sid])
        elif m['u']>=cfg['mature'] and m['usage']>=cfg['mature_usage']:m['status']='mature';events.append(['mature',sid])
    ids=sorted(skills,key=lambda sid:(-skills[sid]['u'],sid))
    for i,a in enumerate(ids):
        x=skills[a]
        if x['status'] not in ('active','mature'):continue
        for b in ids[i+1:]:
            y=skills[b]
            if y['status'] not in ('active','mature') or scope(x['c'])!=scope(y['c']):continue
            if cosine(x['vector'],y['vector'])>=cfg['merge_similarity']:
                result=merge(a,x,b,y)
                if result is not None:
                    content,vector=result;x['versions'].append({'c':x['c'],'window':repo['window'],'merged':b})
                    x.update(c=content,vector=vector,k=content['name']+' '+content['description'],source_ids=sorted(set(x['source_ids']+y['source_ids'])))
                    y['status']='merged';y['merged_into']=a;events.append(['merge',a,b])
    groups=defaultdict(list)
    for sid,m in skills.items():
        if m['status'] in ('active','mature'):groups[scope(m['c'])].append(sid)
    for group,ids in groups.items():
        ids.sort(key=lambda sid:(-skills[sid]['u'],-skills[sid]['usage'],sid))
        for sid in ids[cfg['capacities'][group[0]]:]:skills[sid]['status']='capacity_archived';events.append(['capacity_archive',sid])
    return events

```


## Actual source/config: experiments/skill_evolve_r50.py
```
"""One post-window Read/Write/Assess/Govern transition; no future input access."""
import copy,json
from skill_lifecycle_r50 import *
from skill_prompts_r50 import *
from online_memory_r50 import save_once as write

def evolve(service,snapshot,batch,wi,window,data,tools,config):
    analyses={}
    retained=buffer_select(batch,config);retained_ids={t['id'] for t in retained};writepath=window/'buffer.json'
    if not writepath.exists():write(writepath,{'retained':sorted(retained_ids),'all':[t['id'] for t in batch]})
    # Analyze all eligible injected episodes for utility, including trivial successes excluded from writing.
    for t in batch:
        if t['id'] in retained_ids or t['injected']:
            analyses[t['id']]=service.meta('analysis_'+t['id'],ANALYZE,{'trajectory':t,'available_tools':tools},t['row'],data)
    changes=[];repo=copy.deepcopy(snapshot);repo['clock']+=len(batch);repo['window']=wi+1
    for t in retained:
        analysis=analyses[t['id']];intent=analysis['output_intent']
        if intent=='NONE':continue
        draft=service.meta('mutation_'+t['id'],MUTATE,{'analysis':analysis,'trajectory':t,'snapshot':snapshot['skills'],'tools':tools})
        op=draft['operation'];target=draft.get('patch_target_id')
        if op=='NONE':continue
        if op=='PATCH':
            if target not in snapshot['skills']:raise ValueError('patch_not_in_window_snapshot')
            section=draft['patch_section']
            if section not in ('name','description','applicable_conditions','required_tools','risk_level','core_action'):raise ValueError('invalid_patch_section')
            # A second local patch in this window must preserve the first one's
            # unrelated fields. Eligibility is bound to the read snapshot;
            # applying the patch uses the current write-side record.
            content=copy.deepcopy(repo['skills'][target]['c']);content[section]=draft['patch_content']
        else:content=draft['content']
        validate(content,tools);vector=service.embed(json.dumps(content,sort_keys=True))
        neighbors=[{'id':sid,'c':m['c']} for sid,m in repo['skills'].items() if scope(m['c'])==scope(content) and m['status'] in ('active','mature') and cosine(vector,m['vector'])>=config['merge_similarity']]
        review=service.meta('review_'+t['id'],REVIEW,{'candidate':content,'source':t,'neighbors':neighbors,'tools':tools},t['row'],data)
        if review.get('quality') is not True:changes.append({'source':t['id'],'rejected':review});continue
        duplicate=review.get('duplicate_of')
        if op=='CREATE' and duplicate:
            if duplicate not in [x['id'] for x in neighbors]:raise ValueError('invalid_novelty_target')
            patch=service.meta('redirect_'+t['id'],MUTATE,{'instruction':'PATCH only the duplicate skill, preserving unrelated fields','target':duplicate,'existing':repo['skills'][duplicate]['c'],'candidate':content,'source':t})
            if patch.get('operation')!='PATCH' or patch.get('patch_target_id')!=duplicate:raise ValueError('redirect_not_patch')
            section=patch['patch_section']
            if section not in ('description','applicable_conditions','core_action'):raise ValueError('redirect_scope')
            content=copy.deepcopy(repo['skills'][duplicate]['c']);content[section]=patch['patch_content'];validate(content,tools)
            second=service.meta('review_redirect_'+t['id'],REVIEW,{'candidate':content,'source':t,'neighbors':[],'tools':tools},t['row'],data)
            if second.get('quality') is not True:continue
            vector=service.embed(json.dumps(content,sort_keys=True));op='PATCH';target=duplicate
        sid=commit(repo,op,content,vector,[t['id']],tools,target);changes.append({'source':t['id'],'operation':op,'id':sid})
    credits=assess(repo,batch,analyses,config)
    def merge(aid,x,bid,y):
        value=service.meta(f'merge_{wi}_{aid}_{bid}',MERGE,{'a':x['c'],'b':y['c'],'tools':tools})
        if value.get('merge') is not True:return None
        c=value['content'];validate(c,tools)
        if scope(c)!=scope(x['c']):raise ValueError('merge_scope_changed')
        return c,service.embed(json.dumps(c,sort_keys=True))
    governance=govern(repo,config,merge) if (wi+1)%config['govern_every']==0 else []
    if not (window/'events.json').exists():write(window/'events.json',{'write':changes,'credit':credits,'govern':governance})
    return repo

```


## Actual source/config: experiments/skill_prompts_r50.py
```
ANALYZE = """Analyze a completed PAST trajectory (feedback already released) using its released released label/reward and actual images/observations.
Identify a transferable turning point, not a diagnosis lookup or current answer. Attribute each injected skill:
ADOPTED_POSITIVE, ADOPTED_NEGATIVE, or IGNORED. For adoption cite a zero-based step_index and concise evidence
of changed action/interpretation; mere presence in context is not adoption. Attribution is provisional, not causal proof.
Return JSON: {"skill_adoption":[{"skill_id":"...","status":"...","step_index":0,"evidence":"..."}],
"extracted_pattern":"...","output_intent":"CREATE|PATCH|NONE","patch_target_id":null,
"branch":"general|task_level|action_level"}.
General = concrete domain-agnostic process; task_level = clinical task/tool choice or sequence;
action_level = one tool's input/output operation. NONE for unsupported, case-specific or trivial lessons.
Do not infer a specific lesion solely from a binary source answer. State uncertainty. Never assume unexecuted tools ran.
"""
MUTATE = """Convert the approved source analysis into ONE reusable procedural skill or a local patch.
Only source observations support the content. No fixed source answer, option letter, figure number or patient identity.
Trigger must specify applicability. core_action must specify observable checks, appropriate tool actions, failure/unknown
handling and when to stop; never require access to the current task's unknown reference answer.
Return JSON {"operation":"CREATE|PATCH|NONE","patch_target_id":null,"patch_section":null,"patch_content":null,
"content":{"name":"...","description":"...","applicable_conditions":"...","branch":"general|task_level|action_level",
"tool_name":null,"task_category":"provided category","required_tools":[],"risk_level":"low|medium|high","core_action":"..."}}.
For PATCH only return patch_target_id, patch_section (one content field), patch_content and operation;
do not replace unrelated sections. Scope fields branch, task_category and tool_name cannot change.
NONE may omit all other fields. Registered tools only. No invented measurements or blanket disease exclusion.
"""
REVIEW = """Review a candidate against the actual source trajectory, source image, existing nearest skills and tool menu.
Reject unsupported clinical specifics, rules requiring unknown current labels, copied source answers, vague reminders,
unsafe generalization or incompatible tool capabilities. A binary label does not verify all findings in a model explanation.
Return JSON {"quality":true/false,"reason":"specific source evidence or failure","duplicate_of":null or exact existing ID}.
Duplicate means same reusable operation within the same branch/scope; different conditions may require a local PATCH.
Do not approve merely because JSON is valid. You are a same-model reviewer, not an independent clinician.
"""
PRESCREEN = """Select relevant candidate skill IDs for the current question and its supplied options.
Use applicable_conditions, not answer guesses. Return JSON {"ids":[...]}. At most five per branch.
Never invent IDs. Keep applicable candidates; exclude clearly unmet contextual preconditions.
"""
MERGE = """Consider two same-scope procedural skills. Merge ONLY if preconditions and actions are compatible.
Preserve conditional exceptions, unknown handling and provenance; do not combine incompatible advice.
Return JSON {"merge":false,"reason":"..."} or {"merge":true,"content":{...complete content schema unchanged...},"reason":"..."}.
No new medical claim beyond the two skills. This is repository maintenance, not access to new patient labels.
"""

# Source here means an already completed episode, never a future/current unsubmitted question.

# Inherited late-R49 ordinary schema clarifications, uniform from R50 start.
ANALYZE += "\n\nEXPLICIT ATTRIBUTION UNIQUENESS CONTRACT; no new clinical information or source evidence.\nReport each injected skill_id at most once in skill_adoption. A single entry must represent that skill's adoption in this trajectory using the one best supported actual zero-based step_index and its concise evidence; do not create separate entries for multiple steps.\nKeep the original ADOPTED_POSITIVE, ADOPTED_NEGATIVE and IGNORED meanings, original source-evidence requirements and all other output fields unchanged. Never invent an injected ID, step, tool execution or patient fact. This is a uniqueness/schema clarification, not a new clinical guideline.\n"
MUTATE += '\n\nEXPLICIT MUTATION FIELD CONTRACT; no new clinical information or source evidence.\nFor operation PATCH, patch_section must be exactly one of: name, description, applicable_conditions, required_tools, risk_level, core_action.\nThe names "c" and "content" denote the whole content container and are not permitted patch_section values.\nA PATCH changes one such field of an eligible target already present in the supplied window snapshot. Do not change branch, task_category or tool_name.\nKeep the original CREATE, PATCH and NONE meanings and the original source-evidence requirements. This clarification introduces no new clinical rule or permission to infer facts.\n'

```


## Actual source/config: experiments/r50_baseline_controls.py
```
"""R50 baseline controls inherited uniformly; no old recovery registrations."""
import os
from pathlib import Path
import json
TOOLS=('medgemma','llava_rad','chest_xray_expert','llava_med_qa','xray_phrase_grounding','medvlm_r1')
def validate_runtime(runtime):
    if runtime['arms']['M']['tools']!=list(TOOLS):raise ValueError('exact_six_tool_menu_required')
    if set(runtime['tools'])!=set(TOOLS):raise ValueError('only_six_registered_tools_required')
    if any(v.get('gpu')!='1' for v in runtime['tools'].values()):raise ValueError('GPU1_only')
    device=json.loads((Path(__file__).resolve().parents[1]/'configs/cxr_vqa_tool_worker_gpu.json').read_text())
    if device.get('cuda_visible_devices')!='1':raise ValueError('new_CODE_worker_must_mask_GPU1')
    for name in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES'):os.environ.pop(name,None)

```


## Actual source/config: experiments/maira_guard_worker_r50.py
```
import json
from pathlib import Path
CODE='/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109'
RUN='/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109'
TOOL='xray_phrase_grounding'
POLICY_ID='maira_unclosed_tag_eos_guard_v1'
def read(path):return json.loads(Path(path).read_text())

def write_once(path,value):
    import os,uuid
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_file():
        if read(path)!=value:raise ValueError('immutable_phrase_guard_record_changed')
        return
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('x') as handle:json.dump(value,handle,ensure_ascii=False,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())
        os.link(temporary,path)
    finally:temporary.unlink(missing_ok=True)

def token_values(value):
    """Copy token IDs only; do not inspect image tensors or model parameters."""
    value=getattr(value,'sequences',value)
    if hasattr(value,'detach'):value=value.detach()
    if hasattr(value,'cpu'):value=value.cpu()
    if hasattr(value,'tolist'):value=value.tolist()
    if isinstance(value,(list,tuple)):return [token_values(item) for item in value]
    if type(value) is int:return value
    raise TypeError('unexpected_token_ids_type')

def capture_tool(tool,captures):
    """Context manager: original results/kwargs survive; swallowed exceptions are visible."""
    import contextlib,sys,traceback
    from unittest.mock import patch
    @contextlib.contextmanager
    def active():
        processor=tool.processor;generate=tool.model.generate
        target=getattr(tool._run,'__func__',tool._run).__code__
        previous=sys.gettrace()
        if previous is not None:raise RuntimeError('unexpected_existing_python_trace')
        def note_error(stage):
            captures['observability_errors'].append({'stage':stage,'traceback':traceback.format_exc()})
        class ProcessorProxy:
            def __getattr__(self,name):return getattr(processor,name)
            def decode(self,*args,**kwargs):
                value=processor.decode(*args,**kwargs)
                try:
                    captures['decodes'].append({'input_token_ids':token_values(args[0]),'kwargs':kwargs,'decoded_text':value})
                except Exception:note_error('decode_record_only')
                return value
            def convert_output_to_plaintext_or_grounded_sequence(self,*args,**kwargs):
                try:captures['conversion_inputs'].append({'text':args[0],'kwargs':kwargs})
                except Exception:note_error('conversion_input_record_only')
                return processor.convert_output_to_plaintext_or_grounded_sequence(*args,**kwargs)
        def observed_generate(*args,**kwargs):
            value=generate(*args,**kwargs)
            try:
                ids=token_values(value);input_ids=kwargs.get('input_ids')
                length=int(input_ids.shape[-1]) if hasattr(input_ids,'shape') else None
                captures['generations'].append({'output_token_ids':ids,'prompt_length':length,
                  'generated_token_ids':[row[length:] for row in ids] if length is not None else None,
                  'max_new_tokens':kwargs.get('max_new_tokens'),'use_cache':kwargs.get('use_cache'),
                  'model_class':type(tool.model).__name__,'model_device':str(getattr(tool.model,'device',None)),
                  'model_dtype':str(getattr(tool.model,'dtype',None))})
            except Exception:note_error('generation_record_only')
            return value
        def local_trace(frame,event,arg):
            if event=='exception':
                try:
                    kind,error,tb=arg
                    captures['swallowed_exceptions'].append({'exception_type':kind.__name__,'exception_module':kind.__module__,
                      'exception_repr':repr(error),'exception_message':str(error),'filename':frame.f_code.co_filename,
                      'line':frame.f_lineno,'traceback':''.join(traceback.format_exception(kind,error,tb))})
                except Exception:note_error('exception_record_only')
            return local_trace
        def trace(frame,event,arg):return local_trace if frame.f_code is target else None
        try:
            tool.processor=ProcessorProxy()
            with patch.object(tool.model,'generate',observed_generate):
                sys.settrace(trace)
                yield
        finally:
            sys.settrace(previous);tool.processor=processor
    return active()

def capture_state(captures,factory_calls,failure):
    tokens=(len(captures['generations'])==1 and captures['generations'][0].get('prompt_length') is not None
      and bool(captures['generations'][0].get('output_token_ids')))
    decoded=(len(captures['decodes'])==1 and isinstance(captures['decodes'][0].get('decoded_text'),str)
      and isinstance(captures['decodes'][0].get('input_token_ids'),list))
    converted=(len(captures['conversion_inputs'])==1 and decoded
      and captures['conversion_inputs'][0]['text']==captures['decodes'][0]['decoded_text'])
    exception=bool(captures['swallowed_exceptions'])
    complete=(len(factory_calls)==1 and tokens and decoded and converted and not captures['observability_errors']
      and (failure not in ('nested_backend_error','analysis_status_not_completed') or exception))
    return {'status':'failed' if failure else ('completed_healthy' if complete else 'observability_failed'),
      'capture_complete':complete,'token_capture_complete':tokens,'decode_capture_complete':decoded,
      'conversion_capture_complete':converted,'exception_recorded':exception}


import contextlib,os,socket,sys,time,traceback
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent));sys.path.insert(0,str(Path(CODE)/'experiments'))
from maira_eos_guard_r50 import install_eos_guard
request=json.load(sys.stdin);folder=Path(request['artifact_dir']);folder.mkdir(parents=True,exist_ok=True)
assert request['tool']==TOOL and request['backend']==TOOL and os.environ.get('CUDA_VISIBLE_DEVICES')=='1'
assert read(Path(CODE)/'configs/cxr_vqa_tool_worker_gpu.json')['cuda_visible_devices']=='1'
ready=read(Path(RUN)/'EXECUTION_REVIEW_READY.json')
assert ready['scope_complete'] is True and ready['verdict']=='ready'
captures={'generations':[],'decodes':[],'conversion_inputs':[],'swallowed_exceptions':[],'observability_errors':[]};policy={};factory=[];events=[];began=time.monotonic()
def deny_network(*args,**kwargs):raise RuntimeError('guarded_local_tool_network_forbidden')
with contextlib.ExitStack() as stack:
 stack.enter_context(patch.object(socket.socket,'connect',deny_network));stack.enter_context(patch.object(socket.socket,'connect_ex',deny_network))
 stack.enter_context(patch.object(socket,'create_connection',deny_network))
 import requests
 stack.enter_context(patch.object(requests.sessions.Session,'request',deny_network))
 import cxr_vqa_tool_worker as worker
 import maira_smoke as smoke
 from cxr_image_memory_r44 import tool_failure_reason
 original_factory=smoke.create_maira_tool
 def create(*args,**kwargs):
  if factory:raise RuntimeError('second_guarded_tool_factory_forbidden')
  tool,provenance=original_factory(*args,**kwargs)
  factory.append({'model_revision':provenance['assets'][0]['revision'],'source_commit':provenance['source']['commit'],
    'cuda_visible_devices':os.environ['CUDA_VISIBLE_DEVICES'],'model_device':str(tool.model.device),'model_dtype':str(tool.model.dtype),
    'is_loaded_in_8bit':bool(getattr(tool.model,'is_loaded_in_8bit',False))})
  assert factory[-1]['model_revision']=='795a2b1cd4a310624b4e3d14b5a23e41fd273deb'
  stack.enter_context(capture_tool(tool,captures));stack.enter_context(install_eos_guard(tool,policy))
  return tool,provenance
 stack.enter_context(patch.object(smoke,'create_maira_tool',create))
 with contextlib.redirect_stdout(sys.stderr):
  try:
   with worker.inference_events(request,events):result=worker.execute(request)
  except Exception as error:
   traceback.print_exc(file=sys.stderr)
   write_once(folder/'outer_exception.json',{'type':type(error).__name__,'repr':repr(error),'traceback':traceback.format_exc()})
   result={'status':'failed','observation':None,'error_type':type(error).__name__,'error':str(error)}
 result.update(actual_model_events=events,cuda_visible_devices='1',adapter_revision='cxr-vqa-existing-snapshot-binding-3')
 failure=tool_failure_reason(result)
 write_once(folder/'original_worker_result.json',result)
for name,value in [('generation_tokens.json',captures['generations']),('decode.json',captures['decodes']),('conversion_inputs.json',captures['conversion_inputs']),
                   ('swallowed_exceptions.json',captures['swallowed_exceptions']),('observability_errors.json',captures['observability_errors']),('factory.json',factory),('eos_guard.json',policy)]:
 write_once(folder/name,value)
capture=capture_state(captures,factory,failure)
final_ids=[x['generated_token_ids'][0][-1] if x.get('generated_token_ids') and x['generated_token_ids'][0] else None for x in captures['generations']]
eos_terminated=final_ids==[2]
policy_healthy=not failure and capture['capture_complete'] and eos_terminated and len(policy.get('calls',[]))==1
evidence={**policy,**capture,'generation_policy_changed':True,'same_generation_settings':False,'factory':factory,'cuda_visible_devices':'1',
 'final_generated_token_ids':final_ids,'eos_terminated':eos_terminated,'policy_healthy':policy_healthy,
 'status':'completed_healthy' if policy_healthy else 'failed',
 'elapsed_s':time.monotonic()-began,'clinical_prompt_changed':False,'parser_changed':False,'diagnostic_result_reused':False}
result['generation_policy_evidence']=evidence
if not policy_healthy and result['status']=='completed':
 result['status']='failed';result['error']='guard_policy_incomplete_or_non_eos_termination';result['observation']=None
write_once(folder/'policy_status.json',{'policy_id':POLICY_ID,**capture,'status':'completed_healthy' if policy_healthy else 'failed',
 'health_failure_reason':failure,'eos_terminated':eos_terminated,'policy_healthy':policy_healthy,
 'generation_policy_changed':True,'same_generation_settings':False})
print('CXR_VQA_RESULT='+json.dumps(result,ensure_ascii=False))

```


## Actual source/config: experiments/maira_eos_guard_r50.py
```
"""Late-R49 EOS guard inherited uniformly from the start of R50.

This is a declared generation-policy change, not parsing repair or a clinical result.
It loads no models, performs no inference, and changes no production records on import.
"""
from contextlib import contextmanager

POLICY_ID='maira_unclosed_tag_eos_guard_v1'
TOKENS={'obj_start':32000,'obj_end':32001,'box_start':32202,'box_end':32203,'eos':2}
TOKEN_TEXT={'obj_start':'<obj>','obj_end':'</obj>','box_start':'<box>','box_end':'</box>'}


def open_depths(token_ids):
    """Independent unmatched tag depths; this does not validate the full grammar."""
    obj=box=0
    for token in token_ids:
        if token==TOKENS['obj_start']:obj+=1
        elif token==TOKENS['obj_end']:obj=max(0,obj-1)
        elif token==TOKENS['box_start']:box+=1
        elif token==TOKENS['box_end']:box=max(0,box-1)
    return obj,box


class UnclosedTagEOSGuard:
    """A Transformers-compatible callable; all non-EOS scores stay identical."""
    def __init__(self,prompt_length,evidence):
        if type(prompt_length) is not int or prompt_length<0:raise ValueError('invalid_prompt_length')
        self.prompt_length=prompt_length;self.evidence=evidence;self.steps=0

    def __call__(self,input_ids,scores):
        if len(input_ids.shape)!=2 or len(scores.shape)!=2 or input_ids.shape[0]!=scores.shape[0] or scores.shape[1]<=TOKENS['eos']:
            raise ValueError('invalid_eos_guard_tensor_shape')
        if input_ids.shape[1]<self.prompt_length:raise ValueError('generated_suffix_precedes_prompt')
        self.steps+=1;changed=None
        for row in range(input_ids.shape[0]):
            suffix=input_ids[row,self.prompt_length:].tolist()
            obj,box=open_depths(suffix)
            if obj or box:
                if changed is None:changed=scores.clone()
                changed[row,TOKENS['eos']]=float('-inf')
                if not changed[row].isfinite().any().item():
                    raise RuntimeError('eos_guard_no_finite_non_eos_token_stop')
                self.evidence.append({'step':self.steps,'batch_row':row,'generated_length':len(suffix),
                  'unclosed_obj_depth':obj,'unclosed_box_depth':box,'masked_token_id':TOKENS['eos']})
        return scores if changed is None else changed


def validate_original_profile(tool):
    tokenizer=tool.processor.tokenizer;config=tool.model.generation_config
    actual={key:tokenizer.convert_tokens_to_ids(text) for key,text in TOKEN_TEXT.items()}
    if actual!={key:TOKENS[key] for key in TOKEN_TEXT}:raise ValueError('pinned_maira_tag_token_mapping_changed')
    if tokenizer.eos_token_id!=TOKENS['eos'] or config.eos_token_id!=TOKENS['eos']:
        raise ValueError('pinned_maira_eos_identity_changed')
    if any(token in tokenizer.all_special_ids for token in actual.values()):raise ValueError('grounding_tags_unexpectedly_special')
    if (config.do_sample is not False or config.num_beams!=1 or getattr(config,'forced_eos_token_id',None) is not None or
        not getattr(tool.model,'is_loaded_in_8bit',False) or getattr(tool.model,'is_loaded_in_4bit',False) or
        str(tool.model.dtype)!='torch.float16' or str(tool.model.device)!='cuda:0'):
        raise ValueError('original_maira_generation_profile_changed')
    return {'tag_token_ids':actual,'eos_token_id':TOKENS['eos'],'do_sample':False,'num_beams':1,'forced_eos_token_id':None,
      'is_loaded_in_8bit':True,'model_dtype':'torch.float16','visible_model_device':'cuda:0'}


@contextmanager
def install_eos_guard(tool,record):
    """Candidate integration after the original factory; no tool/parser replacement."""
    from unittest.mock import patch
    from transformers import LogitsProcessorList
    profile=validate_original_profile(tool);original=tool.model.generate
    record.update(policy_id=POLICY_ID,profile=profile,inserted_tokens=0,parse_fallback=False,forced_box=False,calls=[])
    def guarded_generate(*args,**kwargs):
        if args or kwargs.get('input_ids') is None:raise ValueError('original_keyword_generation_call_required')
        if kwargs.get('max_new_tokens')!=300 or kwargs.get('use_cache') is not True:
            raise ValueError('original_300_token_generation_arguments_required')
        prompt_length=int(kwargs['input_ids'].shape[-1])
        masking=[];guard=UnclosedTagEOSGuard(prompt_length,masking)
        supplied=kwargs.get('logits_processor')
        if supplied is not None and any(isinstance(item,UnclosedTagEOSGuard) for item in supplied):
            raise ValueError('duplicate_eos_guard_forbidden')
        changed=dict(kwargs);changed['logits_processor']=LogitsProcessorList([*(supplied or []),guard])
        call={'prompt_length':prompt_length,'max_new_tokens':300,'use_cache':True,'masking_steps':masking,
          'existing_logits_processors':len(supplied or []),'generation_policy_changed':True}
        record['calls'].append(call)
        try:return original(*args,**changed)
        finally:call['processor_invocations']=guard.steps;call['masking_step_count']=len(masking)
    with patch.object(tool.model,'generate',guarded_generate):yield record

```


## Actual source/config: local_assets/r50_cxr6_preparation/support/run_cxr_vqa_toolsets.py
```
"""Label-blind bounded D/M/C/X execution using the existing client and money ledger.

One run directory is a frozen protocol. A saved send intent without a response is
never resent. Reference answers are not opened by this program.
"""
import argparse
import base64
from contextlib import ExitStack, contextmanager, nullcontext
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

# Load the deployed ledger before the legacy helper modules add their own path.
from provider_ledger import LedgerIntegrityError, LedgerLocked
from v12_ledger import ConcurrentV12Ledger, LedgerReadError, LedgerSnapshotChanged, V12ProviderLedger
from run_sampled_vlm import profile_for, invoke, exclusive_lock, safe_error
from run_direct_vlm import write


def now(): return datetime.now(timezone.utc).isoformat()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p): return [json.loads(s) for s in Path(p).read_text(encoding='utf-8').splitlines() if s]


def save(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    temp=p.with_name('.'+p.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('x', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.link(temp,p)  # Atomic publication, refuses an existing destination.
    finally:
        if temp.exists():temp.unlink()


def freeze_protocol(out, protocol):
    path = out / 'protocol.json'
    try:
        save(path, protocol)
    except FileExistsError:
        if read(path) != protocol:
            raise ValueError('protocol_changed')


@contextmanager
def tool_worker_slot(path):
    # Only tool subprocesses share the accelerator. API calls and cache hits
    # remain independent.
    with ExitStack() as stack:
        while True:
            try:
                stack.enter_context(exclusive_lock(path))
                break
            except BlockingIOError:
                time.sleep(.25)
        yield


IMAGE_DATA_URI = re.compile(r'data:(image/[a-z0-9.+-]+);base64,([A-Za-z0-9+/=]+)\Z')


def archive_request(payload, asset_dir):
    """Represent each original request image with a lossless content reference."""
    def visit(value):
        if isinstance(value, dict):
            return {k: visit(v) for k,v in value.items()}
        if isinstance(value, list):
            return [visit(item) for item in value]
        match = IMAGE_DATA_URI.fullmatch(value) if isinstance(value, str) else None
        if match:
            media_type, encoded = match.groups()
            digest = hashlib.sha256(encoded.encode('ascii')).hexdigest()
            asset = asset_dir / digest
            if not asset.is_file():
                asset_dir.mkdir(parents=True, exist_ok=True)
                temp = asset.with_name('.'+digest+'.'+uuid.uuid4().hex+'.tmp')
                try:
                    temp.write_bytes(encoded.encode('ascii'))
                    os.replace(temp, asset)
                finally:
                    temp.unlink(missing_ok=True)
            return {'cxr_request_image_base64_sha256': digest, 'media_type': media_type}
        return value
    return visit(payload)


ANSWER = ('Answer the current question using the original image. Return exactly one JSON object '
          'with two string fields: {"answer":"short direct answer","reason":"one short sentence"}. '
          'Do not add options or change the question. Do not put the answer only in reason. '
          'Respect image labels. Tool observations may be incorrect; verify against original pixels. '
          'Classifier scores are not disease probabilities or severity measurements. '
          'Single-image reports cannot establish interval change. No prior patient history is supplied.')
AGENT_SYSTEM = ('You are an image-grounded medical tool agent. Intermediate planning, evidence validation '
                'and expert stages must use the stage-specific schema requested in the current instruction. '
                'You may select zero, one or two registered tools, with early stopping when appropriate. '
                'Only at the FINAL ANSWERING stage, output exactly {"answer":"short direct answer",'
                '"reason":"one short sentence"}. Original image labels and coordinates must be preserved. '
                'Tool claims are unverified: inspect original pixels, do not treat classifier scores as '
                'severity, and do not infer temporal change from a single-image report. '
                'No cross-case skills, sibling question context or additional patient history is available.')
ACTION = ('You may answer directly with the final answer/reason JSON, or request useful auxiliary evidence '
          'with {"calls":[{"tool":"registered name","args":{}}],"reason":"brief purpose"}. '
          'Each call applies only to the bound original. At most two selectable tool calls total. '
          'No fixed voting and no mandatory tool use. Tool catalog: ')
EDV = ('Evidence-driven validation: compare every tool claim with the original image. Identify supported, '
       'contradicted and unverifiable claims, respecting anatomy, laterality, modality and acquisition. '
       'Return {"validation":[{"tool":"name","supported":"brief","limitations":"brief"}],'
       '"collaboration_needed":true/false,"expert_task":"one focused unresolved clinical question"}. '
       'No tool call or final answer is required at this validation stage.')

MANUAL_EVIDENCE_RULES = ('do not treat classifier scores as severity, and do not infer temporal change '
                         'from a single-image report.')
M_MINUS_R_SYSTEM = AGENT_SYSTEM.replace(
    'Tool claims are unverified: inspect original pixels, ' + MANUAL_EVIDENCE_RULES,
    'Tool claims are unverified: inspect original pixels.')
M_MINUS_R_TOOL_DESCRIPTIONS = {
    'chest_xray_classifier': ('args={}. Single original CXR finding scores, never severity or localization.',
                              'args={}. Single original CXR finding scores.'),
    'chest_xray_report_generator': ('args={}. Single original CXR report; temporal claims unsupported.',
                                    'args={}. Single original CXR report.'),
}


def agent_system(arm):
    if arm == 'D-H':
        return ANSWER.replace('No prior patient history is supplied.', 'Use only the independently supplied history.')
    if arm == 'M-H':
        return AGENT_SYSTEM.replace('No cross-case skills, sibling question context or additional patient history is available.',
                                    'Use only the independently supplied history. No cross-case skills or sibling questions are available.')
    return ANSWER if arm == 'D' else M_MINUS_R_SYSTEM if arm == 'M-R' else AGENT_SYSTEM


def evidence_catalog(runtime, arm):
    catalog = {k: runtime['tools'][k]['description'] for k in runtime['arms'][arm]['tools']}
    if arm == 'M-R':
        for name, (before, after) in M_MINUS_R_TOOL_DESCRIPTIONS.items():
            if name in catalog:
                if catalog[name] != before:
                    raise ValueError('unexpected_manual_rule_catalog:' + name)
                catalog[name] = after
    return catalog


def parse_final(raw):
    try:
        obj = json.loads(raw)
        if set(obj) != {'answer', 'reason'} or any(not isinstance(obj[k], str) for k in obj): raise ValueError()
        if not obj['answer'].strip() or len(obj['answer']) > 300: raise ValueError()
        return {**obj, 'status': 'completed'}
    except (ValueError, TypeError):
        return {'answer': None, 'reason': None, 'status': 'missing_invalid_final_json'}


def content(row, data_root):
    question = 'Question ID: ' + row['question_id'] + '\nQuestion: ' + row['question']
    if 'options' in row:
        question += '\n' + '\n'.join(f'{key}. {value}' for key, value in row['options'].items())
        question += '\nUse an original option letter or the complete original option text as answer.'
    result = [{'type': 'text', 'text': question}]
    for i, relative in enumerate(row['images'], 1):
        path = (data_root / relative).resolve()
        if not path.is_relative_to(data_root.resolve()): raise ValueError('image_outside_data_root')
        result.append({'type': 'text', 'text': 'Original image ' + str(i) + ': ' + relative})
        mime = mimetypes.guess_type(path.name)[0] or 'image/jpeg'
        result.append({'type': 'image_url', 'image_url': {'url': 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()}})
    return result


def append_observations(messages, observations, out, arm=None):
    presented = observations
    if arm == 'M-R':
        presented = []
        for item in observations:
            value = item.get('observation')
            if item['tool'] in M_MINUS_R_TOOL_DESCRIPTIONS and isinstance(value, dict):
                value = {k: v for k, v in value.items() if k != 'limitations'}
                item = dict(item, observation=value)
            presented.append(item)
    parts=[{'type':'text','text':'Bound tool observations (untrusted):\n'+json.dumps(presented,ensure_ascii=False)}]
    for observation in observations:
        for name in observation.get('derived_images',[]):
            path=Path(name).resolve()
            if not path.is_relative_to((out/'tool_cache').resolve()):raise ValueError('tool_image_outside_artifacts')
            mime=mimetypes.guess_type(path.name)[0] or 'image/png'
            parts.extend([{'type':'text','text':'Derived evidence from '+observation['tool']+'; retain original coordinate binding.'},
                {'type':'image_url','image_url':{'url':'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()}}])
    messages.append({'role':'user','content':parts})


class PaidCalls:
    def __init__(self, cfg, protocol, out, key, *, parallel=False):
        from openai import OpenAI
        self.cfg, self.protocol, self.out = cfg, protocol, out
        self.profile = profile_for(cfg)
        self.key = key
        self.parallel = parallel
        self.client = OpenAI(api_key=key, base_url=self.profile.base_url, max_retries=0,
                             timeout=cfg.get('request_timeout_seconds', 120))

    @property
    def uses_shared_ledger(self):
        return self.protocol.get('budget', {}).get('existing_shared_ledger') is not False

    def response_cost(self, raw):
        usage = raw.get('usage') if raw else None
        valid = isinstance(usage, dict) and all(
            type(usage.get(k)) is int and usage[k] >= 0 for k in ('prompt_tokens', 'completion_tokens'))
        amount = None
        if valid:
            amount = str((usage['prompt_tokens'] * self.profile.input_cny_per_million +
                          usage['completion_tokens'] * self.profile.output_cny_per_million) / Decimal(1000000))
        return {'status': 'recorded_local' if valid else 'usage_unknown', 'currency': 'CNY',
                'charged_cny': amount, 'remaining_cny': None, 'reservation_id': None,
                'provider_bill_amount': False, 'accounting': 'per_request_usage_only'}

    def record_saved_response_cost(self, folder, raw, request_id):
        if not self.uses_shared_ledger and not (folder / 'result.json').exists():
            save(folder / 'result.json', {'request_id': request_id, 'model_returned': raw.get('model'),
                 'usage': raw.get('usage'), 'settlement': self.response_cost(raw), 'elapsed_s': None,
                 'error': None, 'response_received': True, 'utc': now(), 'recovered_from_saved_response': True})

    def open_ledger(self):
        cfg = self.cfg
        root = Path(cfg['root'])
        ledger_path = root / cfg['ledger']
        waiting_for_read = False
        while True:
            try:
                ledger_class = ConcurrentV12Ledger if self.parallel else V12ProviderLedger
                return ledger_class(ledger_path, self.profile, cap_cny=str(cfg['cap_cny']),
                                    inherit_ledger_path=root / cfg['inherit_ledger'])
            except LedgerLocked:
                # The current holder can be settling a paid call. This call
                # has made no reservation and will wait before sending.
                time.sleep(1)
            except (json.JSONDecodeError, UnicodeDecodeError, LedgerIntegrityError) as exc:
                # Wait at the pre-send boundary until the budget can be read.
                read_error = exc.__cause__ if isinstance(exc, LedgerIntegrityError) else exc
                if not isinstance(exc, LedgerReadError) and not isinstance(read_error, (json.JSONDecodeError, UnicodeDecodeError)):
                    raise
                if not waiting_for_read:
                    print('Waiting to read the shared ledger before sending.', file=sys.stderr, flush=True)
                    waiting_for_read = True
                time.sleep(10)

    def update_accounting(self, operation):
        while True:
            try:
                with self.open_ledger() as ledger:
                    return operation(ledger)
            except LedgerSnapshotChanged:
                continue
            except (LedgerReadError, KeyError) as exc:
                if isinstance(exc, KeyError) and exc.args != ('charged_cny',):
                    raise
                print('Waiting to update the shared SQLite ledger.', file=sys.stderr, flush=True)
                time.sleep(10)

    def reserve(self, ledger, request_id, arm, qid):
        return ledger.reserve(
            request_id=request_id, estimated_input_tokens=self.profile.max_input_tokens,
            max_output_tokens=2048, model=self.protocol['model'],
            enforce_amount_cap=self.protocol.get('budget', {}).get('enforce_money_cap') is not False,
            metadata={'run': self.protocol['experiment_id'], 'arm': arm, 'qid': qid})

    @contextmanager
    def reserve_call(self, request_id, arm, qid):
        if not self.uses_shared_ledger:
            yield None, None
            return
        if self.parallel:
            # The transaction records both the request ID and its reservation.
            # Its connection is closed before entering the network call.
            reservation = self.update_accounting(lambda ledger: self.reserve(ledger, request_id, arm, qid))
            yield None, reservation
            return
        counter_path = Path(self.cfg['root']) / self.cfg['global_request_counter']
        waiting_for_charge = False
        while True:
            with self.open_ledger() as ledger:
                with exclusive_lock(str(counter_path) + '.lock'):
                    state = read(counter_path)
                    if request_id in state['request_ids']:
                        raise RuntimeError('already_claimed_no_reissue')
                    try:
                        reservation = self.reserve(ledger, request_id, arm, qid)
                    except KeyError as exc:
                        if exc.args != ('charged_cny',):
                            raise
                        # The charge calculation failed before persisting a reservation.
                        reservation = None
                    if reservation is not None:
                        state['request_ids'].append(request_id)
                        state.setdefault('scoped_request_limits', {})[self.protocol['experiment_id']] = {
                            'normal': None, 'hard': None, 'authorization': '[REDACTED]', 'monetary_cap_changed': False}
                        write(counter_path, state)
                if reservation is not None:
                    yield ledger, reservation
                    return
            if not waiting_for_charge:
                print('Waiting for the shared ledger charge field before sending.', file=sys.stderr, flush=True)
                waiting_for_charge = True
            time.sleep(10)

    def call(self, row, arm, ordinal, messages, *, api_tools=None):
        folder = self.out / 'calls' / arm / row['question_id'] / str(ordinal)
        request_id = f"cxrvqa:{self.protocol['experiment_id']}:{self.out.name}:{arm}:{row['question_id']}:{ordinal}"
        stored_response = (folder / 'response.json').exists()
        dedup = self.protocol.get('request_archive') == 'image_base64_content_addressed_v1'
        if stored_response and not dedup:
            raw = read(folder / 'response.json')
            if not self.profile.identity_ok(raw.get('model')): raise RuntimeError('returned_model_identity_mismatch')
            self.record_saved_response_cost(folder, raw, request_id)
            message = raw['choices'][0]['message']
            return message if api_tools is not None else message['content']
        if not stored_response and (folder / 'started.json').exists(): raise RuntimeError('unknown_sent_no_reissue:' + row['question_id'])
        payload = {'model': self.protocol['model'], 'messages': messages, 'temperature': self.protocol['temperature'],
                   'top_p': self.protocol['top_p'], 'max_tokens': self.protocol['max_output_tokens'],
                   'extra_body': {'enable_thinking': False}, 'stream': False}
        if api_tools is not None:
            payload['tools'] = api_tools
        archived = archive_request(payload, self.out/'request_image_base64') if dedup else payload
        # Request saved before reservation, and send intent saved before network access.
        if not (folder / 'request.json').exists(): save(folder / 'request.json', archived)
        elif read(folder / 'request.json') != archived: raise ValueError('frozen_request_changed')
        if stored_response:
            raw = read(folder / 'response.json')
            if not self.profile.identity_ok(raw.get('model')): raise RuntimeError('returned_model_identity_mismatch')
            self.record_saved_response_cost(folder, raw, request_id)
            message = raw['choices'][0]['message']
            return message if api_tools is not None else message['content']
        with self.reserve_call(request_id, arm, row['question_id']) as (ledger, reservation):
            save(folder / 'started.json', {'request_id': request_id, 'utc': now(), 'reserved': reservation})
            tick = time.monotonic(); raw = None; error = None
            try:
                raw = invoke(self.client, payload, folder)
                if not self.profile.identity_ok(raw.get('model')): raise RuntimeError('returned_model_identity_mismatch')
            except Exception as exc:
                error = exc
            def settle(current):
                return current.settle(reservation, usage=raw.get('usage') if raw else None,
                                      response_received=raw is not None, error_type=type(error).__name__ if error else None)
            if not self.uses_shared_ledger:
                settlement = self.response_cost(raw)
            elif self.parallel:
                settlement = self.update_accounting(settle)
            else:
                settlement = settle(ledger)
            save(folder / 'result.json', {'request_id': request_id, 'model_returned': raw.get('model') if raw else None,
                 'usage': raw.get('usage') if raw else None, 'settlement': settlement,
                 'elapsed_s': time.monotonic() - tick, 'error': safe_error(error, self.key) if error else None,
                 'response_received': raw is not None, 'utc': now(), 'ledger_remaining_proxy_cny': settlement['remaining_cny']})
            if error: raise error
        message = raw['choices'][0]['message']
        return message if api_tools is not None else message['content']


class Tools:
    """Cache complete backend results by model version, image bytes and actual args."""
    def __init__(self, runtime, data_root, out, *, worker_gate=None):
        self.runtime, self.data_root, self.out = runtime, data_root, out
        self.worker_gate = worker_gate

    def call(self, row, call, arm, ordinal):
        selection = self.out / 'tool_selections' / arm / row['question_id'] / (str(ordinal) + '.json')
        if selection.exists(): return read(selection)
        name, args = call['tool'], call.get('args', {})
        spec = self.runtime['tools'][name]
        index = call.get('image_index', 1)
        if type(index) is not int or not 1 <= index <= len(row['images']):
            raise ValueError('invalid_bound_image_index')
        image = (self.data_root / row['images'][index-1]).resolve()
        if not image.is_relative_to(self.data_root.resolve()): raise ValueError('invalid_bound_image')
        identity = {'backend': spec['backend'], 'revision': spec.get('revision'), 'image': hashlib.sha256(image.read_bytes()).hexdigest(), 'args': args}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        folder = self.out / 'tool_cache' / key; saved = folder / 'result.json'
        gate = tool_worker_slot(self.worker_gate) if self.worker_gate and not saved.is_file() else nullcontext()
        with gate:
            result, cache_hit = self.observe(name, spec, args, image, identity, folder, saved)
        observation = {**result, 'tool': name, 'cache_hit': cache_hit, 'cache_key': key}
        if len(row['images']) > 1:
            observation['image_index'] = index
        save(selection, observation)
        return observation

    def observe(self, name, spec, args, image, identity, folder, saved):
        cache_hit = saved.exists()
        if cache_hit: result = read(saved)
        elif (folder / 'started.json').exists(): result = {'status': 'started_unknown', 'observation': None, 'automatic_retry': False}
        else:
            request = {'tool': name, 'backend': spec['backend'], 'args': args, 'image': str(image),
                       'artifact_dir': str(folder / 'artifacts'), 'runtime': self.runtime['backend_config']}
            save(folder / 'started.json', {'identity': identity, 'utc': now()})
            tick = time.monotonic()
            try:
                command = [spec['python'], spec.get('worker_script') or str(Path(__file__).with_name('cxr_vqa_tool_worker.py'))]
                if spec.get('cpu_affinity') is not None:
                    command = ['taskset', '-c', str(spec['cpu_affinity']), *command]
                env = dict(os.environ, CUDA_VISIBLE_DEVICES=spec.get('gpu', '1'), MPLBACKEND='Agg', TOKENIZERS_PARALLELISM='false')
                env.update(spec.get('worker_env', {}))
                env.update(CUDA_VISIBLE_DEVICES='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
                env.pop('CUDA_LAUNCH_BLOCKING',None);env.pop('TORCH_SHOW_CPP_STACKTRACES',None)
                completed = subprocess.run(command, input=json.dumps(request), capture_output=True, text=True, env=env, timeout=spec.get('timeout', 600))
                (folder / 'backend.stderr.log').write_text(completed.stderr, encoding='utf-8')
                if completed.returncode: raise RuntimeError('backend_exit_' + str(completed.returncode))
                result = json.loads(completed.stdout.split('CXR_VQA_RESULT=')[-1])
            except Exception as exc:
                result = {'status': 'failed', 'observation': None, 'error_type': type(exc).__name__, 'error': str(exc)[:300]}
            result.update(elapsed_s=time.monotonic() - tick, backend=spec['backend'], identity=identity, utc=now())
            save(saved, result)
        return result, cache_hit


def validate_actions(value, runtime, arm, remaining, images=1):
    calls = value.get('calls')
    if not isinstance(calls, list) or len(calls) > remaining: raise ValueError('tool_bound')
    for call in calls:
        keys = {'tool', 'args', 'image_index'} if images > 1 else {'tool', 'args'}
        if set(call) != keys or call['tool'] not in runtime['arms'][arm]['tools'] or not isinstance(call['args'], dict):
            raise ValueError('unregistered_tool_or_arguments')
        index = call.get('image_index', 1)
        if type(index) is not int or not 1 <= index <= images:
            raise ValueError('invalid_bound_image_index')
    return calls


def resolve_action(call, observations):
    if call['tool']=='roi_crop' and call['args'].get('box_from')=='region_parse':
        if 'box' in call['args']:raise ValueError('ambiguous_crop_coordinates')
        prior=next((x for x in reversed(observations) if x.get('tool')=='region_parse'
                    and x.get('image_index',1)==call.get('image_index',1)),None)
        box=((prior or {}).get('observation') or {}).get('combined_box_normalized')
        if box is None:raise ValueError('prior_region_box_unavailable')
        return dict(call,args={'box':box})
    return call


def episode(row, arm, data_root, protocol, runtime, out, paid, tools, *, conditioning=None):
    messages = [{'role': 'system', 'content': agent_system(arm)}, {'role': 'user', 'content': content(row, data_root)}]
    if conditioning:
        messages.append({'role': 'user', 'content': conditioning})
    observations = []; calls_used = 0; n = 0
    images = len(row['images'])
    action_prompt = ACTION
    if images > 1:
        action_prompt = ACTION.replace('"args":{}', '"args":{},"image_index":1').replace(
            'Each call applies only to the bound original.', 'Select the numbered original for each call via image_index.')
    def ask(text):
        nonlocal n
        n += 1
        if n > protocol['main_call_limits'][arm]: raise RuntimeError('main_call_bound')
        messages.append({'role': 'user', 'content': text})
        raw = paid.call(row, arm, n, messages)
        messages.append({'role': 'assistant', 'content': raw}); return raw
    if arm in ('D', 'D-H'): final = ask('Return the final answer JSON now.')
    else:
        catalog = evidence_catalog(runtime, arm)
        first = ask(action_prompt + json.dumps(catalog))
        direct = parse_final(first)
        if direct['status'] == 'completed' and arm != 'X': return {**direct, 'main_calls': n, 'tool_calls': 0, 'observations': []}
        try:
            actions = [] if direct['status'] == 'completed' else validate_actions(json.loads(first), runtime, arm, 2, images)
        except (ValueError, TypeError, KeyError):
            return {'answer': None, 'reason': None, 'status': 'missing_invalid_tool_plan', 'main_calls': n, 'tool_calls': 0}
        for action in actions:
            calls_used += 1
            try: actual=resolve_action(action,observations)
            except ValueError as exc:
                observations.append({'tool':action['tool'],'status':'invalid_arguments','observation':None,'error':str(exc),'backend_invoked':False});continue
            observations.append(tools.call(row, actual, arm, calls_used))
        if arm == 'X':
            for index in range(1, images+1):
                suffix = '' if images==1 else f'_{index}'
                binding = {} if images==1 else {'image_index': index}
                view = tools.call(row, dict(tool='view_check', args={}, **binding), arm, 'auto_view'+suffix)
                observations.append(view)
                if (view.get('observation') or {}).get('measurement_applicable') is True:
                    observations.append(tools.call(row, dict(tool='measurement', args={}, **binding), arm, 'auto_measurement'+suffix))
        append_observations(messages,observations,out,arm)
        if arm == 'C' and observations:
            validation = ask(EDV)
            try: collaborate = json.loads(validation).get('collaboration_needed') is True
            except (ValueError, TypeError): collaborate = False
            if collaborate:
                ask('Act as the focused independent expert requested by EDV. Reinspect the original image, resolve the stated issue concisely; no tools. Return brief findings and uncertainty, not an extended reasoning trace.')
            final = ask('As the director, reconcile original-image evidence, EDV and any expert findings. Return final answer/reason JSON only.')
        elif arm in ('M', 'M-R', 'M-S', 'M-E', 'M-H'):
            for turn in range(2, protocol['main_call_limits'][arm] + 1):
                text = ('Return final answer/reason JSON only; no further tools.' if turn == 4 or calls_used >= 2 else
                        action_prompt + json.dumps(catalog) + f' Remaining selectable calls: {2-calls_used}.')
                final = ask(text)
                if parse_final(final)['status'] == 'completed' or turn == 4: break
                try: more = validate_actions(json.loads(final), runtime, arm, 2-calls_used, images)
                except (ValueError, TypeError, KeyError): break
                for action in more:
                    calls_used += 1; observations.append(tools.call(row, action, arm, calls_used))
                append_observations(messages,observations,out,arm)
        else: final = ask('Combine the original with available auxiliary and validity-gated measurement evidence. Return final answer/reason JSON only.')
    return {**parse_final(final), 'main_calls': n, 'tool_calls': calls_used, 'observations': observations}


def main(argv=None, *, arms=('D', 'M', 'C', 'X'), episode_fn=episode, system_fn=agent_system, extra_input_fields=()):
    p = argparse.ArgumentParser(); p.add_argument('--config', type=Path, required=True); p.add_argument('--data', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--arms', nargs='+', choices=arms, required=True)
    p.add_argument('--execute', action='store_true'); p.add_argument('--api-key-stdin', action='store_true')
    p.add_argument('--parallel', action='store_true'); a = p.parse_args(argv)
    cfg = read(a.config); protocol = read(cfg['protocol']); runtime = read(cfg['runtime']); out = a.out
    inputs = rows(a.data / 'inputs.jsonl')
    for row in inputs:
        if set(row) - {'question_id', 'question', 'images', 'image_id', 'source', 'options', *extra_input_fields}: raise ValueError('unexpected_inference_fields')
    if not a.execute:
        print(json.dumps({'status': 'offline_interface_ready', 'questions': len(inputs), 'arms': a.arms, 'paid_calls': 0})); return 0
    key = sys.stdin.readline().strip() if a.api_key_stdin else ''
    if not key: raise ValueError('credential_required_stdin_only')
    out.mkdir(parents=True, exist_ok=True)
    paid = PaidCalls(cfg, protocol, out, key, parallel=a.parallel)
    tools = Tools(runtime, a.data, out, worker_gate=out.parent / '.tool-worker.lock' if a.parallel else None)
    for arm in a.arms:
        lock = out / (f'.generation_{arm}.lock' if a.parallel else '.generation.lock')
        progress = out / (f'progress_{arm}.json' if a.parallel else 'progress.json')
        with exclusive_lock(lock):
            freeze_protocol(out, protocol)
            completion = out / f'complete_{arm}.json'
            if completion.is_file():
                continue
            if not runtime['arms'][arm]['ready']: raise RuntimeError('arm_not_deployed:' + arm)
            full={'arm':runtime['arms'][arm], 'tools':{k:runtime['tools'][k] for k in runtime['arms'][arm]['tools']},
                  'backend_config':runtime['backend_config'] if arm!='D' else {},
                  'agent_system':system_fn(arm)}
            full_path=out/('runtime_full_'+arm+'.json')
            if not full_path.exists():save(full_path,full)
            elif read(full_path)!=full:raise ValueError('frozen_tool_or_agent_configuration_changed')
            if not (out / ('runtime_' + arm + '.json')).exists(): save(out / ('runtime_' + arm + '.json'), runtime['arms'][arm])
            elif read(out / ('runtime_' + arm + '.json')) != runtime['arms'][arm]: raise ValueError('arm_runtime_changed')
            for index, row in enumerate(inputs, 1):
                dest = out / 'predictions' / arm / (row['question_id'] + '.json')
                if dest.exists(): continue
                write(progress, {'status': 'running', 'arm': arm, 'index': index, 'total': len(inputs), 'qid': row['question_id'], 'utc': now()})
                tick = time.monotonic()
                try: result = episode_fn(row, arm, a.data, protocol, runtime, out, paid, tools)
                except Exception as exc:
                    write(progress, {'status': 'stopped', 'arm': arm, 'qid': row['question_id'], 'error': safe_error(exc, key), 'utc': now()})
                    raise
                save(dest, dict(result, question_id=row['question_id'], image_id=row['image_id'], arm=arm, elapsed_s=time.monotonic()-tick, utc=now()))
            save(completion, {'status': 'generation_complete', 'questions': len(inputs), 'utc': now()})
            write(progress, {'status': 'requested_arms_complete', 'arms': [arm], 'utc': now()})
    return 0


if __name__ == '__main__': raise SystemExit(main())

```


## Actual source/config: local_assets/deploy_cxr6_r50.py
```
"""Private single-use R50 preparation/deployment/health/serial launch transport.

No old predictions or private metrics are rerun. Keys enter only via stdin.
"""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import shlex
import time

from deploy_cxr_action_r41 import connect,remote_python,ROOT,PYTHON,TRANSPORT_HOME
from deploy_cxr_online_skill_r49 import DATA,REFS,DATASETS,COUNTS,EMBED_BASE,EMBED_MODEL

LOCAL=Path(__file__).resolve().parents[1]
PREP=LOCAL/'local_assets/r50_cxr6_preparation'
SAVED49=Path('D:/MedRAX_Experiment_Artifacts/online_skill_r49_20261108')
OLD_CODE=ROOT+'/code_cxr_online_skill_r49_20261108'
RUN=ROOT+'/runs/online_skill_r50_cxr6_20261109'
CODE=ROOT+'/code_cxr_online_skill_r50_cxr6_20261109'
ARM='M43-IM-GT-S50-CXR6'
TOOLS=('medgemma','llava_rad','chest_xray_expert','llava_med_qa','xray_phrase_grounding','medvlm_r1')
NEW=('medgemma','llava_rad','medvlm_r1')
DONOR=ROOT+'/runs/cxr_vqa_toolsets_20261105/vqarad/runtime_c_ready.json'
HEALTH_IMAGE=ROOT+'/runs/cxr_vqa_backend_readiness/training_xmlab120.jpg'
PATHS=('medgemma_model','medvlm_model','llavarad_source','llavarad_model','vicuna_model','biomedbert_config')


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def write_new(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def stamp():return datetime.now(timezone.utc).isoformat()


def require_review():
    v=read(PREP/'EXECUTION_REVIEW_READY.json')
    assert v['scope_complete'] is True and v['verdict']=='ready' and v['arm']==ARM
    assert v.get('session_id') and v.get('modelUsage') and v.get('code_review_completed') is True
    return v


def program(ds):
    command=[PYTHON,'-u',CODE+'/experiments/run_online_skill_r50.py',
      '--config',RUN+'/configs/'+ds+'.json','--data',DATA[ds],
      '--reference-dir',REFS[ds],'--out',RUN+'/generation/'+ds,
      '--dataset',ds,'--expect-questions',str(COUNTS[ds]),
      '--embedding-model',EMBED_MODEL,'--embedding-base-url',EMBED_BASE]
    if ds=='chexbench':command+=['--order-manifest',RUN+'/configs/chexbench_order.json']
    return command


def prepare(client):
    assert not (PREP/'configs').exists(),'configs_already_prepared_inspect_not_repeat'
    # Actual completed R49 config copies already transferred once; no duplicate pull.
    cfg49={d:read(SAVED49/'configs'/(d+'.json')) for d in DATASETS}
    runtime=read(SAVED49/'configs/runtime.json');protocol=read(SAVED49/'configs/protocol.json')
    with client.open_sftp() as s:
        with s.open(DONOR) as f:donor=json.loads(f.read())
    write_new(PREP/'donor_runtime.original.json',donor)
    for name in NEW:
        assert donor['tools'][name]['backend']==name
        runtime['tools'][name]=copy.deepcopy(donor['tools'][name])
    runtime['tools']={k:runtime['tools'][k] for k in TOOLS}
    for name,spec in runtime['tools'].items():
        spec['gpu']='1'
        spec['deployment_status']='new3_health_pending' if name in NEW else 'historical_warm_environment_reused_no_new_probe'
        spec.pop('worker_script',None)
        spec.setdefault('worker_env',{}).update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
        for envname in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES','CUDA_VISIBLE_DEVICES'):
            spec['worker_env'].pop(envname,None)
    runtime['tools']['xray_phrase_grounding']['worker_script']=CODE+'/experiments/maira_guard_worker_r50.py'
    for key in PATHS:runtime['backend_config'][key]=donor['backend_config'][key]
    arm={'ready':False,'tools':list(TOOLS),'label':ARM}
    runtime['arms']={k:copy.deepcopy(arm) for k in ('M','R50-AGENT')}
    protocol.update(experiment_id='online_skill_r50_cxr6_20261109',request_archive='inline_original_images_semantic_restart_r50')
    assert {k:protocol[k] for k in ('model','temperature','top_p','max_output_tokens','enable_thinking')}==dict(model='qwen3.7-plus',temperature=.2,top_p=.95,max_output_tokens=2048,enable_thinking=False)
    configdir=PREP/'configs';configdir.mkdir()
    write_new(configdir/'runtime.json',runtime);write_new(configdir/'protocol.json',protocol)
    for ds,cfg in cfg49.items():
        assert cfg['model']=='qwen3.7-plus' and cfg['temperature']==.2 and cfg['top_p']==.95 and cfg['max_output_tokens']==2048 and cfg['extra_body']=={'enable_thinking':False}
        cfg.update(experiment_id='online_skill_r50_cxr6_'+ds+'_20261109',protocol=RUN+'/configs/protocol.json',runtime=RUN+'/configs/runtime.json')
        write_new(configdir/(ds+'.json'),cfg)
    write_new(configdir/'chexbench_order.json',read(SAVED49/'configs/chexbench_order.json'))
    source=read(PREP/'SOURCE_PREPARATION.json')
    write_new(PREP/'CONFIG_PREPARATION.json',{'utc':stamp(),'arm':ARM,'new_tools':list(NEW),'menu':list(TOOLS),
      'all_gpu':'1','config_source':'saved actual completed R49 configs reused; donor historical C runtime read once',
      'new_inference_calls':0,'R49_source_or_output_mutation':False,'runtime_sources':source['runtime_sources']})
    print(json.dumps({'status':'prepared_not_deployed','arm':ARM,'menu':list(TOOLS),'main_model':'qwen3.7-plus','new_inference_calls':0}))


HEALTH=r'''
from pathlib import Path
import fcntl,json,os,subprocess,sys,time,shutil
sys.path.insert(0,CODE+'/experiments')
from cxr_image_memory_r44 import tool_failure_reason
root=Path(RUN)/'health';root.mkdir(exist_ok=True)
lock=(root/'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
runtime=json.loads((Path(RUN)/'configs/runtime.json').read_text())
ready=json.loads((Path(RUN)/'EXECUTION_REVIEW_READY.json').read_text())
assert ready['scope_complete'] is True and ready['verdict']=='ready'
assert json.loads((Path(CODE)/'configs/cxr_vqa_tool_worker_gpu.json').read_text())=={'cuda_visible_devices':'1'}
assert Path(HEALTH_IMAGE).is_file()
def put(p,v):
 with p.open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
records={}
for name in NEW:
 folder=root/name;folder.mkdir()
 mem=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
 assert mem<500,'GPU1_busy_do_not_probe_or_touch_other_jobs'
 assert shutil.disk_usage(root).free>3*1024**3,'insufficient_free_disk'
 spec=runtime['tools'][name];assert spec['gpu']=='1'
 req={'tool':name,'backend':spec['backend'],'args':{'question':'Describe the visible findings.'},
  'image':HEALTH_IMAGE,'artifact_dir':str(folder/'artifacts'),'runtime':runtime['backend_config']}
 put(folder/'request.json',req)
 put(folder/'started.json',{'utc':time.time(),'tool':name,'gpu':'1','revision':spec.get('revision'),
  'image':HEALTH_IMAGE,'health_only':True,'main_META_embedding_calls':0,'enter_skill_memory_or_scores':False})
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',MPLBACKEND='Agg',TOKENIZERS_PARALLELISM='false')
 env.update(spec.get('worker_env',{}));env['CUDA_VISIBLE_DEVICES']='1'
 for flag in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES'):env.pop(flag,None)
 tick=time.monotonic();rc=None;failure=None;result=None
 command=[spec['python'],CODE+'/experiments/cxr_vqa_tool_worker.py']
 if spec.get('cpu_affinity') is not None:command=['taskset','-c',str(spec['cpu_affinity']),*command]
 try:
  with (folder/'stdout.log').open('xb') as out,(folder/'stderr.log').open('xb') as err:
   p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=out,stderr=err,env=env)
   put(folder/'process.json',{'pid':p.pid,'command':command,'gpu':'1'})
   try:p.communicate(json.dumps(req).encode(),timeout=spec.get('timeout',900))
   except subprocess.TimeoutExpired:
    p.kill();p.communicate();raise RuntimeError('health_tool_timeout')
   rc=p.returncode
  (folder/'exitcode').write_text(str(rc)+'\n')
  if rc:raise RuntimeError('health_worker_exit_'+str(rc))
  result=json.loads((folder/'stdout.log').read_text().split('CXR_VQA_RESULT=')[-1])
  failure=tool_failure_reason(result)
  events=result.get('actual_model_events',[])
  if not failure and (result.get('cuda_visible_devices')!='1' or len(events)!=1 or events[0].get('status')!='completed'):
   failure='actual_gpu_or_model_event_missing'
  obs=result.get('observation') or {}
  if not failure and (not isinstance(obs,dict) or not str(obs.get('answer','')).strip()):failure='empty_health_answer'
 except Exception as error:failure=repr(error)
 record={'status':'failed' if failure else 'completed_healthy','tool':name,'failure':failure,
  'native_exit_code':rc,'elapsed_s':time.monotonic()-tick,'result':result,'revision':spec.get('revision'),
  'input_image':HEALTH_IMAGE,'health_only':True,'main_META_embedding_calls':0,'production_cache_or_skill_reuse':False}
 put(folder/'completed.json',record);records[name]=record
 if failure:
  put(root/'failure.json',{'tool':name,'records':records,'production_started':False});raise SystemExit(1)
put(root/'complete.json',{'status':'three_new_tools_healthy','tools':list(NEW),'records':records,
 'old_three_tools_reprobed':False,'main_META_embedding_calls':0,'hash_validation':False})
print(json.dumps({'health':'three_new_tools_healthy','tools':list(NEW),'production_started':False}))
'''


CONTROLLER=r'''
from pathlib import Path
import fcntl,json,os,subprocess,sys,time,shutil
r=Path(RUN);jobs=r/'jobs'
lock=(jobs/'.controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
ready=json.loads((r/'EXECUTION_REVIEW_READY.json').read_text())
assert ready['verdict']=='ready' and ready['scope_complete'] is True
health=json.loads((r/'health/complete.json').read_text());assert health['status']=='three_new_tools_healthy'
assert not any((jobs/(ds+'.pid')).exists() for ds in DATASETS)
main_key=sys.stdin.buffer.readline();embedding_key=sys.stdin.buffer.readline().strip().decode()
assert main_key.strip() and embedding_key
def state(v):
 p=jobs/'queue_status.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
for ds in DATASETS:
 while True:
  mem=int(subprocess.check_output(['nvidia-smi','--id=1','--query-gpu=memory.used','--format=csv,noheader,nounits'],text=True).strip())
  state({'state':'waiting_gpu1' if mem>=500 else 'starting_dataset','dataset':ds,'gpu1_used_mib':mem,'other_jobs_modified':False})
  if mem<500:break
  time.sleep(60)
 assert shutil.disk_usage(r).free>3*1024**3,'insufficient_free_disk'
 env=dict(os.environ,R50_EMBEDDING_API_KEY=embedding_key,LANGCHAIN_TRACING_V2='false',LANGSMITH_TRACING='false')
 for flag in ('CUDA_LAUNCH_BLOCKING','TORCH_SHOW_CPP_STACKTRACES'):env.pop(flag,None)
 with (jobs/(ds+'.log')).open('xb',buffering=0) as log:
  p=subprocess.Popen(PROGRAMS[ds]+['--execute','--api-key-stdin'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,env=env)
  (jobs/(ds+'.pid')).write_text(str(p.pid));state({'state':'running_dataset','dataset':ds,'pid':p.pid})
  p.communicate(main_key)
 rc=p.returncode;(jobs/(ds+'.exitcode')).write_text(str(rc)+'\n')
 out=r/'generation'/ds
 if out.is_dir():(out/'generation.exitcode').write_text(str(rc)+'\n')
 if rc:
  state({'state':'dataset_failed_stop_queue','dataset':ds,'exit_code':rc,'pid':p.pid});raise SystemExit(rc)
 complete=json.loads((out/'complete.json').read_text())
 assert complete['status']=='generation_complete' and complete['questions']==COUNTS[ds] and complete['arm']==ARM
state({'state':'all_three_datasets_exited_zero','datasets':DATASETS,'arm':ARM})
'''


def script(text,**values):return '\n'.join(k+'='+repr(v) for k,v in values.items())+'\n'+text


def stage(client):
    require_review();assert not (PREP/'stage.started.json').exists(),'stage_already_invoked_inspect'
    write_new(PREP/'stage.started.json',{'utc':stamp(),'code':CODE,'run':RUN})
    remote_python(client,script(r'''
from pathlib import Path
import json,shutil
r=Path(RUN);c=Path(CODE)
assert not r.exists() and not c.exists(),'R50_namespace_already_exists'
assert shutil.disk_usage(r.parent).free>3*1024**3
(r/'configs').mkdir(parents=True);(r/'jobs').mkdir();(c/'experiments').mkdir(parents=True);(c/'configs').mkdir()
for p in (Path(OLD_CODE)/'experiments').glob('*.py'):shutil.copyfile(p,c/'experiments'/p.name)
(c/'configs/cxr_vqa_tool_worker_gpu.json').write_text(json.dumps({'cuda_visible_devices':'1'})+'\n')
print(json.dumps({'independent_R50_code_created':True,'GPU':'1','models_or_env_rebuilt':False}))
''',RUN=RUN,CODE=CODE,OLD_CODE=OLD_CODE),timeout=30)
    files=read(PREP/'SOURCE_PREPARATION.json')['runtime_sources']
    with client.open_sftp() as s:
        for relative in files:s.put(str(LOCAL/relative),CODE+'/'+relative)
        s.put(str(PREP/'support/run_cxr_vqa_toolsets.py'),CODE+'/experiments/run_cxr_vqa_toolsets.py')
        for p in (PREP/'configs').glob('*.json'):s.put(str(p),RUN+'/configs/'+p.name)
        for name in ('EXECUTION_REVIEW_READY.json','EVALUATION_PROTOCOL.json'):s.put(str(PREP/name),RUN+'/'+name)
        with s.open(RUN+'/queue_controller.py','w') as f:
            f.write(script(CONTROLLER,RUN=RUN,ARM=ARM,DATASETS=DATASETS,COUNTS=COUNTS,PROGRAMS={d:program(d) for d in DATASETS}))
        with s.open(RUN+'/health_controller.py','w') as f:f.write(script(HEALTH,RUN=RUN,CODE=CODE,NEW=NEW,HEALTH_IMAGE=HEALTH_IMAGE))
    # No API, tools or annotation file opens in these cohort/config dry-runs.
    remote_python(client,script(r'''
import pathlib,subprocess,json
for ds,command in PROGRAMS.items():
 wrapper="import pathlib,runpy,sys,socket\nreference=pathlib.Path(sys.argv[1]).resolve()\nold=pathlib.Path.open\ndef guarded(self,*a,**kw):\n if self.resolve().is_relative_to(reference):raise RuntimeError('dryrun_reference_open_forbidden')\n return old(self,*a,**kw)\npathlib.Path.open=guarded\ndef deny(*a,**kw):raise RuntimeError('dryrun_network_forbidden')\nsocket.socket.connect=deny\nsys.argv=sys.argv[2:]\nsys.path.insert(0,str(pathlib.Path(sys.argv[0]).parent))\nfrom r50_baseline_controls import validate_runtime\nvalidate_runtime(__import__('json').loads(pathlib.Path(RUNTIME).read_text()))\nrunpy.run_path(sys.argv[0],run_name='__main__')\n".replace('RUNTIME',repr(RUN+'/configs/runtime.json'))
 subprocess.run(command[:1]+['-c',wrapper,REFS[ds]]+command[2:],check=True)
print(json.dumps({'three_dryruns':'passed','new_inference':0,'reference_file_opens':0,'new_tool_probes':0}))
''',PROGRAMS={d:program(d) for d in DATASETS},REFS=REFS,RUN=RUN),timeout=60)
    write_new(PREP/'stage.completed.json',{'utc':stamp(),'status':'staged_three_dryruns_passed','new_inference_calls':0})


def launch(client,name):
    require_review();assert (PREP/'stage.completed.json').is_file()
    receipt=PREP/(name+'.launch.started.json');assert not receipt.exists(),'launch_already_invoked_inspect_not_repeat'
    write_new(receipt,{'utc':stamp(),'run':RUN,'name':name})
    source=script(r'''
from pathlib import Path
import fcntl,json,os,shlex,subprocess
r=Path(RUN);j=r/'jobs';lock=(j/('.'+NAME+'.launch.lock')).open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert not (j/(NAME+'.started.json')).exists() and not (j/(NAME+'.pid')).exists(),'duplicate_launch_forbidden'
if NAME=='controller':
 assert json.loads((r/'health/complete.json').read_text())['status']=='three_new_tools_healthy'
 key=__import__('sys').stdin.buffer.readline()+__import__('sys').stdin.buffer.readline();assert len(key.splitlines())==2
 rd,wr=os.pipe();os.write(wr,key);os.close(wr)
else:rd=os.open(os.devnull,os.O_RDONLY)
wrapper=shlex.join([PYTHON,'-u',str(r/SCRIPT)])+'; rc=$?; printf "%s\n" "$rc" > '+shlex.quote(str(j/(NAME+'.exitcode')))+'; exit "$rc"'
try:
 with (j/(NAME+'.log')).open('xb',buffering=0) as log:p=subprocess.Popen(['bash','-c',wrapper],stdin=rd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 (j/(NAME+'.pid')).write_text(str(p.pid));(j/(NAME+'.started.json')).write_text(json.dumps({'pid':p.pid,'arm':ARM,'gpu':'1','utc':__import__('time').time()}))
 print(json.dumps({'launched':NAME,'pid':p.pid,'arm':ARM,'gpu':'1'}))
finally:os.close(rd)
''',RUN=RUN,NAME=name,PYTHON=PYTHON,ARM=ARM,SCRIPT='queue_controller.py' if name=='controller' else 'health_controller.py')
    keys=None
    if name=='controller':keys=(TRANSPORT_HOME/'.secrets/token_plan_api.key').read_bytes().strip()+b'\n'+(TRANSPORT_HOME/'.secrets/qwen_api.key').read_bytes().strip()+b'\n'
    remote_python(client,source,timeout=30,input_bytes=keys)
    write_new(PREP/(name+'.launch.completed.json'),{'utc':stamp(),'name':name,'launch_command_returned_zero':True})


def health(client):
    launch(client,'health')
    # Only the fresh doc-following validator owns this waiting invocation.
    with client.open_sftp() as s:
        while True:
            try:
                with s.open(RUN+'/jobs/health.exitcode') as f:rc=f.read().decode().strip()
                break
            except FileNotFoundError:time.sleep(10)
        # The health artifacts are small and newly created, not old R49 pulls.
        import stat
        def pull(remote,local):
            local.mkdir(parents=True,exist_ok=True)
            for e in s.listdir_attr(remote):
                if e.filename.startswith('.'):continue
                p=local/e.filename;r=remote+'/'+e.filename
                if stat.S_ISDIR(e.st_mode):pull(r,p)
                elif stat.S_ISREG(e.st_mode):
                    assert not p.exists(),'health_result_already_pulled_inspect'
                    s.get(r,str(p),prefetch=False)
        pull(RUN+'/health',PREP/'health')
    write_new(PREP/'HEALTH_RECEIPT.json',{'utc':stamp(),'native_exit_code':int(rc),'health_tools':list(NEW),'old_three_reprobed':False,'production_inference':False})
    if rc!='0':raise RuntimeError('health_failed_preserved_no_automatic_retry')
    print(json.dumps({'health':'three_new_tools_healthy','gpu':'1','production_started':False}))


def queue(client):launch(client,'controller')


def status(client):
    remote_python(client,script(r'''
from pathlib import Path
import json,shutil
r=Path(RUN);j=r/'jobs'
def text(p):return p.read_text().strip() if p.exists() else None
def phase(n):
 pid=text(j/(n+'.pid'));return {'pid':pid,'alive':bool(pid and Path('/proc',pid).exists()),'exit':text(j/(n+'.exitcode'))}
v={'arm':ARM,'controller':phase('controller'),'health':phase('health'),'queue':json.loads((j/'queue_status.json').read_text()) if (j/'queue_status.json').exists() else None,'datasets':{},'free_bytes':shutil.disk_usage(r).free}
for ds in DATASETS:
 g=r/'generation'/ds;s=g/'services'
 d=dict(phase(ds),saved=len(list((g/'predictions'/ARM).glob('*.json'))),contexts=len(list((g/'contexts').glob('*.json'))),feedback=len(list((g/'feedback').glob('*.json'))),main_sends=len(list((s/'calls/R50-AGENT').glob('*/*/started.json'))),main_responses=len(list((s/'calls/R50-AGENT').glob('*/*/response.json'))),meta_sends=len(list((s/'calls/R50-META').glob('*/*/started.json'))),windows=len(list((g/'windows').glob('*/repo.json'))),complete=(g/'complete.json').exists())
 if d['exit'] not in (None,'0') and (j/(ds+'.log')).exists():d['failure_tail']=(j/(ds+'.log')).read_text(errors='replace').splitlines()[-18:]
 v['datasets'][ds]=d
print(json.dumps(v))
''',RUN=RUN,ARM=ARM,DATASETS=DATASETS),timeout=30)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','stage','health','queue','status']);a=p.parse_args()
    with connect() as client:globals()[a.mode](client)

```


## Actual source/config: tests/test_cxr6_r50.py
```
"""New R50 retrieval boundaries; synthetic data, no API/model/reference access."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'experiments'))
from skill_lifecycle_r50 import retrieve,initial,DEFAULTS
from run_online_skill_r50 import ARM


def repository(n):
    repo=initial()
    for i in range(n):
        repo['skills'][str(i)]={'c':{'branch':'task_level','task_category':'location','required_tools':[]},
          'status':'active','vector':[1.,0.],'u_by_category':{},'u':.5,'last_reinforced':0}
    return repo


class RetrievalBoundaries(unittest.TestCase):
    def test_nonempty_pools_can_all_be_rejected(self):
        for n in (1,5,6):
            with self.subTest(n=n):
                calls=[]
                def reject(pool):calls.append(pool);return []
                self.assertEqual(retrieve(repository(n),[1.,0.],'location',[],DEFAULTS,reject),[])
                self.assertEqual(len(calls),1)
                self.assertEqual(len(calls[0]),min(5,n))

    def test_no_candidates_means_no_prescreen(self):
        def unexpected(pool):self.fail('empty pool must not spend a META request')
        self.assertEqual(retrieve(repository(0),[1.,0.],'location',[],DEFAULTS,unexpected),[])
        self.assertEqual(retrieve(repository(1),[1.,0.],'presence',[],DEFAULTS,unexpected),[])

    def test_only_prescreened_ids_can_enter_context(self):
        selected=retrieve(repository(5),[1.,0.],'location',[],DEFAULTS,lambda pool:['3'])
        self.assertEqual([s['id'] for s in selected],['3'])
        with self.assertRaisesRegex(ValueError,'prescreen_unknown_id'):
            retrieve(repository(1),[1.,0.],'location',[],DEFAULTS,lambda pool:['absent'])

    def test_isolated_arm_identity(self):
        self.assertEqual(ARM,'M43-IM-GT-S50-CXR6')


if __name__=='__main__':unittest.main()

```


## Actual source/config: local_assets/r50_cxr6_preparation/configs/runtime.json
```
{
  "arms": {
    "M": {
      "ready": false,
      "tools": [
        "medgemma",
        "llava_rad",
        "chest_xray_expert",
        "llava_med_qa",
        "xray_phrase_grounding",
        "medvlm_r1"
      ],
      "label": "M43-IM-GT-S50-CXR6"
    },
    "R50-AGENT": {
      "ready": false,
      "tools": [
        "medgemma",
        "llava_rad",
        "chest_xray_expert",
        "llava_med_qa",
        "xray_phrase_grounding",
        "medvlm_r1"
      ],
      "label": "M43-IM-GT-S50-CXR6"
    }
  },
  "tools": {
    "medgemma": {
      "backend": "medgemma",
      "description": "args={\"question\":\"focused image question\"}. Unverified single-image CXR interpretation.",
      "python": "/home/imss/cw/MedRAX_reproduction_20261027/.venv-maira/bin/python",
      "gpu": "1",
      "revision": "290cda5eeccbee130f987c4ad74a59ae6f196408",
      "deployment_status": "new3_health_pending",
      "worker_env": {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1"
      }
    },
    "llava_rad": {
      "backend": "llava_rad",
      "description": "args={\"question\":\"focused image question\"}. Unverified single-image CXR interpretation.",
      "python": "/home/imss/cw/MedRAX_reproduction_20261027/.venv-llavarad/bin/python",
      "gpu": "1",
      "revision": "dcdbc6caf6806c9acb66e12a827a39c86e00f6a7",
      "deployment_status": "new3_health_pending",
      "worker_env": {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1"
      }
    },
    "chest_xray_expert": {
      "backend": "chest_xray_expert",
      "description": "args={\"question\":\"focused image question\"}. CheXagent CXR visual QA.",
      "python": "/home/imss/cw/MedRAX_reproduction_20261027/.venv-chexagent/bin/python",
      "gpu": "1",
      "revision": "MedRAX-dae30e2f136ef0b2a40885a4c335386e9ffad052",
      "deployment_status": "historical_warm_environment_reused_no_new_probe",
      "worker_env": {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1"
      }
    },
    "llava_med_qa": {
      "backend": "llava_med_qa",
      "description": "args={\"question\":\"focused image question\"}. LLaVA-Med visual QA.",
      "python": "/home/imss/cw/MedRAX_reproduction_20261027/.venv-llava/bin/python",
      "gpu": "1",
      "revision": "MedRAX-dae30e2f136ef0b2a40885a4c335386e9ffad052",
      "deployment_status": "historical_warm_environment_reused_no_new_probe",
      "worker_env": {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1"
      }
    },
    "xray_phrase_grounding": {
      "backend": "xray_phrase_grounding",
      "description": "args={\"phrase\":\"visible structure or finding\"}. MAIRA-2 phrase grounding.",
      "python": "/home/imss/cw/MedRAX_reproduction_20261027/.venv-maira/bin/python",
      "gpu": "1",
      "revision": "MedRAX-dae30e2f136ef0b2a40885a4c335386e9ffad052",
      "deployment_status": "historical_warm_environment_reused_no_new_probe",
      "worker_env": {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1"
      },
      "worker_script": "/home/imss/cw/MedRAX_reproduction_20261027/code_cxr_online_skill_r50_cxr6_20261109/experiments/maira_guard_worker_r50.py"
    },
    "medvlm_r1": {
      "backend": "medvlm_r1",
      "description": "args={\"question\":\"focused image question\"}. Unverified single-image CXR interpretation.",
      "python": "/home/imss/.conda/envs/jyj/bin/python",
      "gpu": "1",
      "revision": "d256f2cfdf98c6872c1dc9f20b7dd52f49374fe9",
      "deployment_status": "new3_health_pending",
      "worker_env": {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1"
      }
    }
  },
  "backend_config": {
    "root": "/home/imss/cw/MedRAX_reproduction_20261027",
    "tool_repo": "source/MedRAX",
    "chexagent_snapshot": "/home/imss/cw/MedRAX_reproduction_20261027/models/hf_full/hub/models--StanfordAIMI--CheXagent-2-3b/snapshots/8f19b53a2eceda4c33b0acec6c81fbc293ad80d0",
    "vision_snapshot": "/home/imss/cw/MedRAX_reproduction_20261027/models/hf_full/hub/models--StanfordAIMI--XraySigLIP__vit-l-16-siglip-384__webli/snapshots/f0edbf5d90dba44edb7f4f96d8663537cb0749bf",
    "medgemma_model": "/home/imss/cw/MedRAX_reproduction_20261027/models/cxr_vqa_hf/google--medgemma-4b-it/290cda5eeccbee130f987c4ad74a59ae6f196408",
    "medvlm_model": "/home/imss/cw/MedRAX_reproduction_20261027/models/cxr_vqa_hf/JZPeterPan--MedVLM-R1",
    "llavarad_source": "/home/imss/cw/MedRAX_reproduction_20261027/source/LLaVA-Rad-1fc44096cc5766c28d8a3329240c8423100ce3df",
    "llavarad_model": "/home/imss/cw/MedRAX_reproduction_20261027/models/cxr_vqa_hf/microsoft--llava-rad",
    "vicuna_model": "/home/imss/cw/MedRAX_reproduction_20261027/models/cxr_vqa_hf/lmsys--vicuna-7b-v1.5",
    "biomedbert_config": "/home/imss/cw/MedRAX_reproduction_20261027/models/cxr_vqa_hf/biomedbert_config"
  }
}

```


## Actual source/config: local_assets/r50_cxr6_preparation/configs/protocol.json
```
{
  "experiment_id": "online_skill_r50_cxr6_20261109",
  "model": "qwen3.7-plus",
  "temperature": 0.2,
  "top_p": 0.95,
  "max_output_tokens": 2048,
  "enable_thinking": false,
  "main_call_limits": {},
  "tool_call_limits": {},
  "request_archive": "inline_original_images_semantic_restart_r50",
  "budget": {
    "existing_shared_ledger": false,
    "enforce_money_cap": false
  }
}

```


## Actual source/config: local_assets/r50_cxr6_preparation/configs/chexbench.json
```
{
  "model": "qwen3.7-plus",
  "profile": {
    "model": "qwen3.7-plus",
    "credential_slot": "token_plan",
    "base_url": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    "identity_prefixes": [
      "qwen3.7-plus"
    ],
    "input_cny_per_million": "4",
    "output_cny_per_million": "12",
    "price_basis": "Inherited conservative bookkeeping rates, not a verified upper bound on Token Plan charges: provider Credits are authoritative; no Credits-to-CNY conversion or cash invoice is inferred from tokens. The original cumulative monetary guard is retained and the runner never buys additional quota. Token Plan usage is measured in provider Credits; these CNY rates are a conservative budget proxy, not a provider invoice or Credits-to-CNY conversion. This runner never purchases additional quota automatically.",
    "max_input_tokens": 131072,
    "max_output_tokens": 8192,
    "supports_vision": true,
    "notes": "Request alias qwen3.7-plus; record actual returned alias or dated snapshot. Explicit enable_thinking=false; HiRes=true only in the declared smoke/HiRes arms. The local 131072-token input bound is an experiment limit, not the model context specification.",
    "documentation": [
      "https://help.aliyun.com/zh/model-studio/qwen3-7-plus",
      "https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-chat-completions",
      "https://help.aliyun.com/zh/model-studio/token-plan-personal-overview",
      "https://help.aliyun.com/zh/model-studio/token-plan-personal-faq"
    ]
  },
  "credential_slot": "token_plan",
  "prompt_variant": "answer",
  "temperature": 0.2,
  "top_p": 0.95,
  "max_output_tokens": 2048,
  "request_timeout_seconds": 120,
  "extra_body": {
    "enable_thinking": false
  },
  "experiment_id": "online_skill_r50_cxr6_chexbench_20261109",
  "root": "/home/imss/cw/MedRAX_reproduction_20261027",
  "protocol": "/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/configs/protocol.json",
  "runtime": "/home/imss/cw/MedRAX_reproduction_20261027/runs/online_skill_r50_cxr6_20261109/configs/runtime.json"
}

```


## Actual source/config: local_assets/r50_cxr6_preparation/EVALUATION_PROTOCOL.json
```
{
  "arm": "M43-IM-GT-S50-CXR6",
  "datasets": {
    "chexbench": 618,
    "slake": 114,
    "vqarad": 116
  },
  "baseline_correct": {
    "chexbench": {
      "M43": 466,
      "R47_online_GT": 468,
      "R49_online_GT_Skill": 465
    },
    "slake": {
      "M43": 108,
      "R49_online_GT_Skill": 113
    },
    "vqarad": {
      "M42": 100,
      "R49_online_GT_Skill": 97
    }
  },
  "metrics": "unchanged common explicit-answer/author-aligned micro, subset macro, word recall, corrected/harmed/net and paired image/patient-study cluster intervals",
  "all_arms_reference_free_adaptation_before_labels": true,
  "no_private_R49_score_rerun_or_overwrite": true,
  "not_pooled_independent_848_cases": true,
  "claim_limits": "two-method-change combination plus uniform inherited controls; no Skill-only causal, clinical, closed-test SOTA claim",
  "score_only_full_dataset_after_original_runner_exit_zero": true,
  "publish_complete_question_images_requests_feedback_skills_failure_usage_time": true
}

```


## Actual source/config: experiments/cxr_vqa_tool_worker.py
```
"""A single real local backend in its existing interpreter; no paid tool API."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


def existing_snapshot(cache_dir, spec):
    """Bind pinned existing assets without reinstating obsolete artifact audits."""
    snapshot=Path(cache_dir)/('models--'+spec['repo_id'].replace('/','--'))/'snapshots'/spec['revision']
    if not snapshot.is_dir():raise FileNotFoundError('pinned_existing_snapshot_unavailable')
    states={};artifacts=[]
    for name in spec['files']:
        path=snapshot/name
        if name=='README.md' and not path.is_file():continue  # Model card is not a loader input.
        if not path.is_file():raise FileNotFoundError('required_existing_asset_unavailable:'+name)
        stat=path.stat();states[name]=(stat.st_size,stat.st_mtime_ns)
        artifacts.append({'filename':name,'bytes':stat.st_size,'sha256':None})
    return snapshot.resolve(),{'repo_id':spec['repo_id'],'revision':spec['revision'],'files':artifacts,
        'checksum_verification':'skipped_by_user','additional_cached_files':'retained; not an inference gate'},states


def serial(value, folder, name='raw'):
    import numpy as np
    if isinstance(value, np.ndarray):
        path=folder/(name+'.npy');np.save(path,value)
        return {'array_file':str(path),'shape':list(value.shape),'dtype':str(value.dtype)}
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {str(k):serial(v,folder,name+'_'+str(k)) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [serial(v,folder,name+'_'+str(i)) for i,v in enumerate(value)]
    if isinstance(value,Path):return str(value)
    if value is None or isinstance(value,(str,int,float,bool)):return value
    return str(value)


def execute(req):
    cfg=req['runtime'];root=Path(cfg['root']);repo=root/cfg['tool_repo'];cache=root/'models/hf_full'
    folder=Path(req['artifact_dir']);folder.mkdir(parents=True,exist_ok=True)
    name=req['backend'];args=dict(req['args']);image=Path(req['image']);start=time.monotonic()
    # Paths always come from the bound executor; the model cannot open arbitrary files.
    if set(args)&{'image','image_path','image_paths','dicom_path','path','output','output_path'}:raise ValueError('model_paths_forbidden')
    raw=None;observation=None;derived=[]
    if name=='roi_crop':
        from PIL import Image
        box=args.get('box')
        if not isinstance(box,list) or len(box)!=4 or any(type(v) not in (float,int) for v in box):raise ValueError('normalized_box_required')
        x0,y0,x1,y1=box
        if not (0<=x0<x1<=1 and 0<=y0<y1<=1):raise ValueError('invalid_box')
        im=Image.open(image);w,h=im.size;pixel=[round(x0*w),round(y0*h),round(x1*w),round(y1*h)]
        crop=im.crop(pixel);crop=crop.resize((crop.width*2,crop.height*2));dest=folder/'crop.png';crop.save(dest)
        raw=observation={'original_size':[w,h],'normalized_box':box,'original_pixel_box':pixel,'zoom':2,'crop_size':list(crop.size),'coordinates':'origin top-left; x right, y down; original retained'};derived=[str(dest)]
    elif name in ['chest_xray_classifier','chest_xray_report_generator','chest_xray_segmentation','image_visualizer','dicom_processor']:
        from tool_registry_ext import build_tools
        from build_case_tool_evidence import CLASSIFIER_FILENAME
        tools,prov=build_tools(repo,cache_dir=cache,classifier_checkpoint=root/'models/home/.torchxrayvision/models_data'/CLASSIFIER_FILENAME,
            report_cache=root/'models/hf_report',segmentation_checkpoint=root/'models/home/.torchxrayvision/models_data/pspnet_chestxray_best_model_4.pth',
            temp_dir=folder/'runtime',tools=[name],device_main='cuda:0')
        tool=tools[name]
        bound_path='dicom_path' if name=='dicom_processor' else 'image_path'
        raw=tool.invoke(dict(args,**{bound_path:str(image)}))
        observation=serial(raw,folder)
        (folder/'provenance.json').write_text(json.dumps(prov,ensure_ascii=False,indent=2),encoding='utf-8')
        if name=='chest_xray_classifier':observation={'finding_scores':observation[0],'limitations':'Operating-point normalized finding scores, not calibrated disease probabilities, severity, localization or temporal change.'}
        elif name=='chest_xray_report_generator':observation={'report':observation[0],'limitations':'Unverified single-image report; interval statements have no prior-image evidence.'}
    elif name=='llava_med_qa':
        import llava_smoke as smoke
        from unittest.mock import patch
        with patch.object(smoke,'inspect_snapshot',existing_snapshot):
            tool,prov=smoke.create_llava_tool(repo,cache_dir=cache/'hub',device='cuda:0')
        raw=tool.invoke({'question':args.get('question','Describe the visible findings.'),'image_path':str(image)})
        observation=serial(raw,folder)
        (folder/'provenance.json').write_text(json.dumps(prov,ensure_ascii=False,indent=2),encoding='utf-8')
    elif name=='chest_xray_expert':
        import chexagent_smoke as smoke
        audit={'loader_calls':[],'generate_calls':0,'visual_forward_calls':0}
        raw=smoke.execute_tool(repo,Path(cfg['chexagent_snapshot']),Path(cfg['vision_snapshot']),image,
                               args.get('question','Describe the visible findings.'),512,'cuda:0',audit)
        observation=serial(raw,folder)
        (folder/'provenance.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    elif name=='xray_phrase_grounding':
        import maira_smoke as smoke
        from unittest.mock import patch
        with patch.object(smoke.audit,'inspect_snapshot',existing_snapshot):
            tool,prov=smoke.create_maira_tool(repo,cache_dir=cache/'hub',temp_dir=folder/'maira_runtime',device='cuda:0')
        raw=tool.invoke({'image_path':str(image),'phrase':args.get('phrase','lung opacity')})
        observation=serial(raw,folder)
        (folder/'provenance.json').write_text(json.dumps(prov,ensure_ascii=False,indent=2),encoding='utf-8')
    elif name in ['region_parse','view_check','measurement','evidence_lookup','medvlm_r1','llava_rad','medgemma']:
        from cxr_vqa_extended_backends import execute_extended
        raw,observation,derived=execute_extended(req)
    else:raise ValueError('unknown_backend')
    (folder/'raw.json').write_text(json.dumps(serial(raw,folder),ensure_ascii=False,indent=2),encoding='utf-8')
    def add_visuals(value):
        if isinstance(value,dict):
            for v in value.values():add_visuals(v)
        elif isinstance(value,(list,tuple)):
            for v in value:add_visuals(v)
        elif isinstance(value,(str,Path)):
            p=Path(str(value))
            if p.suffix.lower() in ['.png','.jpg','.jpeg'] and p.is_file() and p.resolve().is_relative_to(folder.resolve()):
                if str(p) not in derived:derived.append(str(p))
    add_visuals(raw)
    torch=sys.modules.get('torch')
    peak=([int(torch.cuda.max_memory_allocated(i)) for i in range(torch.cuda.device_count())]
          if torch is not None and torch.cuda.is_available() else [])
    return {'status':'completed','observation':observation,'derived_images':derived,'backend_compute_seconds':time.monotonic()-start,
            'cuda_peak_allocated_bytes_by_visible_device':peak,
            'original_image':str(image),'raw_result_file':str(folder/'raw.json'),'clinical_correctness_verified':False}


@contextlib.contextmanager
def inference_events(req, events):
    """Observe actual generation/XRV/CXAS forwards without changing model outputs."""
    if req['backend'] in ['roi_crop','view_check']:
        yield;return
    import torch
    from transformers.generation.utils import GenerationMixin
    from unittest.mock import patch
    folder=Path(req['artifact_dir']);folder.mkdir(parents=True,exist_ok=True)
    def tracked(original,model,*a,kind,**kw):
        event={'kind':kind,'model_class':type(model).__name__,'module':type(model).__module__,'status':'started_unknown','utc':time.time()}
        events.append(event);path=folder/'backend_events.json'
        path.write_text(json.dumps(events,indent=2))
        tick=time.monotonic()
        try:value=original(model,*a,**kw)
        except Exception:
            event.update(status='failed',elapsed_s=time.monotonic()-tick);path.write_text(json.dumps(events,indent=2));raise
        event.update(status='completed',elapsed_s=time.monotonic()-tick);path.write_text(json.dumps(events,indent=2));return value
    generation=GenerationMixin.generate;forward=torch.nn.Module._call_impl
    def generate(model,*a,**kw):return tracked(generation,model,*a,kind='generate',**kw)
    def call(model,*a,**kw):
        kind=type(model).__name__;module=type(model).__module__
        if (kind in ['DenseNet','PSPNet'] and module.startswith('torchxrayvision')) or kind=='BackboneUNet':
            return tracked(forward,model,*a,kind='anatomy_or_classifier_forward',**kw)
        return forward(model,*a,**kw)
    with patch.object(GenerationMixin,'generate',generate),patch.object(torch.nn.Module,'_call_impl',call):yield


if __name__=='__main__':
    req=json.load(sys.stdin);events=[]
    gpu_config = Path(__file__).resolve().parents[1] / 'configs/cxr_vqa_tool_worker_gpu.json'
    if gpu_config.is_file():
        device = json.loads(gpu_config.read_text())['cuda_visible_devices']
        if device not in ('0', '1'):
            raise ValueError('Unsupported tool worker GPU')
        os.environ['CUDA_VISIBLE_DEVICES'] = device
    with contextlib.redirect_stdout(sys.stderr):
        try:
            with inference_events(req,events):result=execute(req)
        except Exception as exc:
            import traceback;traceback.print_exc()
            result={'status':'failed','observation':None,'error_type':type(exc).__name__,'error':str(exc)[:300]}
    result['actual_model_events']=events
    result['cuda_visible_devices']=os.environ.get('CUDA_VISIBLE_DEVICES')
    result['adapter_revision']='cxr-vqa-existing-snapshot-binding-3'
    if req['backend']=='view_check' and result['status']=='completed':
        result['actual_model_events'].append({'kind':'tensorflow_predict','model_class':'OpenCXR Image Sorter','status':'completed'})
    print('CXR_VQA_RESULT='+json.dumps(result,ensure_ascii=False))

```


## Actual source/config: experiments/cxr_vqa_extended_backends.py
```
"""Real extended local backends; missing dependencies fail explicitly, never fabricate evidence."""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time


def plain(x):
    import numpy as np
    if isinstance(x,dict):return {str(k):plain(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [plain(v) for v in x]
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    return x


def cxas_masks(req):
    """One exact model-image inference shared by parsing and gated geometry."""
    import numpy as np
    from PIL import Image
    cfg=req['runtime'];root=Path(cfg['root']);image=Path(req['image'])
    key=hashlib.sha256(image.read_bytes()).hexdigest()
    cache=Path(cfg['cxas_cache'])/key;result=cache/'result.json'
    if result.exists():
        info=json.loads(result.read_text());return np.load(cache/'masks.npz')['masks'],info,False
    if (cache/'started.json').exists():raise RuntimeError('cxas_started_unknown_no_reissue')
    cache.mkdir(parents=True,exist_ok=True)
    (cache/'started.json').write_text(json.dumps({'image_sha256':key,'model':'CXAS UNet_ResNet50_default','utc':time.time()}))
    sys.path.insert(0,str(root/'models/cxr_vqa_xdeps'))
    os.environ['CXAS_PATH']=str(root/'models/cxr_vqa_xdeps');os.environ['CXAS_NO_WELCOME']='1'
    import torch
    from cxas import CXAS
    from cxas.label_mapper import id2label_dict
    tick=time.monotonic();model=CXAS(model_name='UNet_ResNet50_default',gpus='0')
    with torch.inference_mode():prediction=model.process_file(str(image),output_directory=str(cache))
    masks=prediction['segmentation_preds'][0].detach().cpu().numpy().astype(bool)
    width,height=Image.open(image).size
    masks=np.stack([np.asarray(Image.fromarray(m.astype('uint8')).resize((width,height),Image.Resampling.NEAREST)).astype(bool) for m in masks])
    info={'model':'CXAS UNet_ResNet50_default','labels':{str(k):str(v) for k,v in id2label_dict.items()},'original_size':[width,height],
          'inference_seconds':time.monotonic()-tick,'image_sha256':key,'mask_shape':list(masks.shape),'threshold':.5,
          'coordinates':'original pixel coordinates: origin top-left, x right, y down; nearest-neighbor inverse resize'}
    np.savez_compressed(cache/'masks.npz',masks=masks)
    result.write_text(json.dumps(info,ensure_ascii=False,indent=2))
    return masks,info,True


def mask_for(masks,info,name):
    matches=[int(k) for k,v in info['labels'].items() if v.lower()==name.lower()]
    if len(matches)!=1 or not 0<=matches[0]<len(masks):return None
    return masks[matches[0]]


def bbox(mask):
    import numpy as np
    y,x=np.where(mask)
    if not len(x):return None
    return [int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)]


def geometry(masks,info):
    """Declared geometry adaptation; suppress the whole bundle on failed quality."""
    import numpy as np
    width,height=info['original_size'];labels={v.lower():v for v in info['labels'].values()}
    def resolve(options):
        for name in options:
            if name in labels:return mask_for(masks,info,labels[name])
        return None
    left=resolve(['lung left','left lung']);right=resolve(['lung right','right lung']);heart=resolve(['heart'])
    central=resolve(['trachea'])
    unavailable={'measurement_available':False,'values':None,'reason':'required_masks_missing_or_failed_quality'}
    if any(m is None or not m.any() for m in [left,right,heart,central]):return unavailable
    if any(not .02<float(m.mean())<.65 for m in [left,right,heart]):return unavailable
    if np.logical_and(left,right).sum()/max(np.logical_or(left,right).sum(),1)>.1:return unavailable
    heart_spans=[(np.flatnonzero(r)[-1]-np.flatnonzero(r)[0]+1) if r.any() else 0 for r in heart]
    row=int(np.argmax(heart_spans));cols=np.flatnonzero((left|right)[row])
    if len(cols)<2:return unavailable
    thorax_width=int(cols[-1]-cols[0]+1);ctr=float(heart_spans[row]/thorax_width)
    if not 0<ctr<1:return unavailable
    bilateral=np.flatnonzero((left|right).any(axis=0));mid=float((bilateral[0]+bilateral[-1])/2)
    cy,cx=np.where(central);shift=float(cx.mean()-mid)/thorax_width
    if not math.isfinite(shift) or abs(shift)>.5:return unavailable
    return {'measurement_available':True,'values':{'CTR':ctr,'heart_widest_original_row':row,
        'heart_width_px':int(heart_spans[row]),'bilateral_lung_span_px_same_row':thorax_width,
        'lung_field_asymmetry_log_AR_over_AL':float(math.log(right.sum()/left.sum())),
        'thoracic_shift_fraction_of_thorax_width':shift,
        'thoracic_shift_direction_in_image':'right' if shift>0 else 'left' if shift<0 else 'centered'},
        'interpretation':{'CTR_gt_0_5':bool(ctr>.5)},
        'limitations':'PA-only geometric estimates from unverified anatomical masks. Shift is tracheal centroid relative to bilateral-lung horizontal midline; this explicit rule is an adaptation, not the unreleased original implementation. Image-direction sign is not converted to patient laterality.'}


def execute_extended(req):
    cfg=req['runtime'];root=Path(cfg['root']);name=req['backend'];args=req['args'];image=Path(req['image']);folder=Path(req['artifact_dir']);derived=[]
    if name=='view_check':
        sys.path.insert(0,str(root/'models/cxr_vqa_xdeps'))
        os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['TF_CPP_MIN_LOG_LEVEL']='2'
        import opencxr
        from opencxr.utils.file_io import read_file
        sorter=opencxr.load(opencxr.algorithms.image_sorter)
        readable=image
        if image.suffix.lower() in ['.jpg','.jpeg']:
            from PIL import Image
            readable=folder/'decoded_original.png'
            Image.open(image).save(readable)  # Lossless container for the same decoded pixels.
        pixels,spacing,_=read_file(str(readable));raw=plain(sorter.run(pixels))
        obs={'view_result':raw,'measurement_applicable':raw['Type']=='PA' and raw['Rotation']=='0',
             'gate_rule':'OpenCXR argmax view PA and rotation 0; geometry still requires nonempty, plausible anatomical masks.',
             'backend':'OpenCXR Image Sorter; CPU execution',
             'input_binding':'Original pixels; JPEG decoded once into lossless PNG for the official PNG reader; original retained.'}
    elif name in ['region_parse','measurement']:
        import numpy as np
        from PIL import Image,ImageDraw
        masks,info,fresh=cxas_masks(req)
        if name=='measurement':obs=geometry(masks,info)
        else:
            regions=args.get('regions') or [args.get('region','left lung')]
            if not isinstance(regions,list) or not 1<=len(regions)<=4 or any(not isinstance(x,str) for x in regions):raise ValueError('one_to_four_anatomical_regions_required')
            boxes={};selected=[]
            for region in regions:
                mask=mask_for(masks,info,region)
                if mask is None:raise ValueError('CXAS_anatomical_label_not_supported:'+region)
                b=bbox(mask);boxes[region]=b
                if b is not None:selected.append(mask)
            combined=np.logical_or.reduce(selected) if selected else np.zeros(masks.shape[1:],dtype=bool)
            b=bbox(combined);w,h=info['original_size']
            obs={'boxes_original_pixels':boxes,'combined_box_original_pixels':b,
                 'combined_box_normalized':[b[0]/w,b[1]/h,b[2]/w,b[3]/h] if b else None,
                 'original_size':[w,h],'coordinate_mapping':info['coordinates'],
                 'mask_file':str(Path(cfg['cxas_cache'])/info['image_sha256']/'masks.npz'),
                 'scope':'CXAS anatomy only. No BiomedParse pathology localization is claimed.'}
            overlay=Image.open(image).convert('RGBA')
            rgba=np.zeros((h,w,4),dtype=np.uint8);rgba[combined]=[255,0,0,70]
            overlay=Image.alpha_composite(overlay,Image.fromarray(rgba));drawing=ImageDraw.Draw(overlay)
            for region,b in boxes.items():
                if b:drawing.rectangle(b,outline='red',width=2);drawing.text((b[0],b[1]),region,fill='red')
            overlay.save(folder/'anatomy_boxes.png');derived=[str(folder/'anatomy_boxes.png')]
        obs.update(cxas_inference_performed=fresh,cxas_model=info['model'],cxas_inference_seconds_if_fresh=info['inference_seconds'] if fresh else 0)
        raw={'returned_observation':obs,'mask_provenance':info}
    elif name=='evidence_lookup':
        import torch
        from transformers import AutoProcessor,AutoModelForImageTextToText,FineGrainedFP8Config
        model_path=Path(cfg['knowledge_model']);processor=AutoProcessor.from_pretrained(model_path,local_files_only=True)
        memory=cfg.get('knowledge_gpu_memory_gib',[22,22])
        model=AutoModelForImageTextToText.from_pretrained(model_path,local_files_only=True,dtype=torch.bfloat16,
            device_map='auto',max_memory={0:f'{memory[0]}GiB',1:f'{memory[1]}GiB','cpu':'35GiB'},
            quantization_config=FineGrainedFP8Config(dequantize=True),offload_folder=str(folder/'offload'),attn_implementation='eager')
        query=args.get('query') or args.get('conditions')
        if not isinstance(query,str) or not query.strip() or len(query)>1800:raise ValueError('condition_knowledge_query_required')
        instruction = ('Give at most three short bullets of general chest-radiograph knowledge, covering relevant '
                       'findings, distribution or distinguishing features. No patient-specific diagnosis or invented citations.')
        messages = [
            {'role': 'system', 'content': [{'type': 'text', 'text': instruction}]},
            {'role': 'user', 'content': [{'type': 'text', 'text': query}]},
        ]
        inputs=processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt',enable_thinking=False).to(model.device)
        length=inputs['input_ids'].shape[-1]
        max_tokens = 96
        with torch.inference_mode():generated=model.generate(**inputs,max_new_tokens=max_tokens,do_sample=False)
        answer=processor.decode(generated[0,length:],skip_special_tokens=True)
        raw=obs={'knowledge':answer,'knowledge_source':'local model knowledge; not literature retrieval','citations':[],
            'model':'Qwen/Qwen3.5-27B-FP8','revision':'97f5941bf617e31c5e237364a8602ce3f03a551a',
            'deployment_adaptation':'official FP8 checkpoint dequantized for 3090, split GPU/CPU; not a replacement main model',
            'backend_input_tokens':length,'backend_output_tokens':int(generated.shape[-1]-length),
            'backend_max_new_tokens':max_tokens}
    elif name=='medvlm_r1':
        import torch
        from PIL import Image
        from transformers import AutoProcessor,Qwen2VLForConditionalGeneration
        model_path=Path(cfg['medvlm_model']);model=Qwen2VLForConditionalGeneration.from_pretrained(model_path,local_files_only=True,torch_dtype=torch.bfloat16,device_map='cuda:0')
        processor=AutoProcessor.from_pretrained(model_path,local_files_only=True)
        question=args.get('question','Describe the visible findings.')
        question=question+'\nThink through the question step by step in <think>...</think>, then give the result in <answer>...</answer>.'
        messages=[{'role':'user','content':[{'type':'image','image':str(image)},{'type':'text','text':question}]}]
        text=processor.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        inputs=processor(text=[text],images=[Image.open(image).convert('RGB')],padding=True,return_tensors='pt').to(model.device)
        length=inputs.input_ids.shape[-1]
        with torch.inference_mode():generated=model.generate(**inputs,max_new_tokens=1024,do_sample=False)
        raw=obs={'answer':processor.batch_decode(generated[:,length:],skip_special_tokens=True,clean_up_tokenization_spaces=False)[0],
            'model':'JZPeterPan/MedVLM-R1','revision':'d256f2cfdf98c6872c1dc9f20b7dd52f49374fe9',
            'backend_input_tokens':length,'backend_output_tokens':int(generated.shape[-1]-length),
            'adaptation':'CXRAgent MedVLM-R1 input/generation mechanism with explicit bound image and pinned local assets.'}
    elif name=='medgemma':
        import torch
        from PIL import Image
        from transformers import AutoModelForImageTextToText,AutoProcessor
        path=Path(cfg['medgemma_model']);model=AutoModelForImageTextToText.from_pretrained(path,torch_dtype=torch.bfloat16,device_map='cuda:0',local_files_only=True)
        processor=AutoProcessor.from_pretrained(path,local_files_only=True)
        messages=[{'role':'system','content':[{'type':'text','text':'You are an expert radiologist.'}]},
                  {'role':'user','content':[{'type':'image','image':Image.open(image).convert('RGB')},{'type':'text','text':args.get('question','Describe the visible findings.')}]}]
        inputs=processor.apply_chat_template(messages,add_generation_prompt=True,tokenize=True,return_dict=True,return_tensors='pt').to(model.device,dtype=torch.bfloat16)
        length=inputs['input_ids'].shape[-1]
        with torch.inference_mode():generated=model.generate(**inputs,max_new_tokens=512,do_sample=False)
        raw=obs={'answer':processor.decode(generated[0,length:],skip_special_tokens=True),'model':'google/medgemma-4b-it',
            'revision':'290cda5eeccbee130f987c4ad74a59ae6f196408','backend_input_tokens':length,'backend_output_tokens':int(generated.shape[-1]-length)}
    elif name=='llava_rad':
        import torch
        from PIL import Image
        from unittest.mock import patch
        from transformers import AutoConfig,AutoTokenizer
        source=Path(cfg['llavarad_source']);model_path=Path(cfg['llavarad_model']);base_path=Path(cfg['vicuna_model']);bert_path=Path(cfg['biomedbert_config'])
        sys.path.insert(0,str(source));os.environ['HF_HUB_OFFLINE']='1'
        from llava.model.builder import load_pretrained_model
        from llava.constants import IMAGE_TOKEN_INDEX,DEFAULT_IMAGE_TOKEN,DEFAULT_IM_START_TOKEN,DEFAULT_IM_END_TOKEN
        from llava.conversation import conv_templates
        from llava.mm_utils import tokenizer_image_token
        import llava.model.multimodal_encoder.open_clip_encoder.utils as clip_utils
        original_config=AutoConfig.from_pretrained;original_tokenizer=AutoTokenizer.from_pretrained
        original_clip=clip_utils.create_model_from_pretrained
        def local_config(path,*a,**kw):
            if str(path).startswith('microsoft/BiomedNLP-'):path=bert_path
            kw['local_files_only']=True;value=original_config(path,*a,**kw)
            if Path(str(path)).resolve()==model_path.resolve():
                value.mm_vision_tower_config=str(model_path/'biomedclipcxr_518.json')
                value.mm_vision_tower_checkpoint=str(model_path/'biomedclipcxr_518_checkpoint.pt')
            return value
        def local_tokenizer(path,*a,**kw):
            if str(path).startswith('microsoft/BiomedNLP-'):path=bert_path
            kw['local_files_only']=True;return original_tokenizer(path,*a,**kw)
        def local_clip(*a,**kw):
            # The full official CLIP checkpoint is loaded below. Initializing its
            # text tower from config avoids an unnecessary external BERT load.
            kw['pretrained_hf']=False;return original_clip(*a,**kw)
        with patch.object(AutoConfig,'from_pretrained',side_effect=local_config),patch.object(AutoTokenizer,'from_pretrained',side_effect=local_tokenizer),patch.object(clip_utils,'create_model_from_pretrained',side_effect=local_clip):
            tokenizer,model,processor,context=load_pretrained_model(str(model_path),str(base_path),'llavarad',device_map='auto',device='cuda:0')
        question=args.get('question','Describe the visible findings.')
        image_token=DEFAULT_IM_START_TOKEN+DEFAULT_IMAGE_TOKEN+DEFAULT_IM_END_TOKEN if getattr(model.config,'mm_use_im_start_end',False) else DEFAULT_IMAGE_TOKEN
        conversation=conv_templates['v1'].copy();conversation.append_message(conversation.roles[0],image_token+'\n'+question);conversation.append_message(conversation.roles[1],None)
        ids=tokenizer_image_token(conversation.get_prompt(),tokenizer,IMAGE_TOKEN_INDEX,return_tensors='pt').unsqueeze(0).cuda()
        pixels=processor.preprocess(Image.open(image).convert('RGB'),return_tensors='pt')['pixel_values'][0].unsqueeze(0).half().cuda()
        with torch.inference_mode():generated=model.generate(ids,images=pixels,do_sample=False,max_new_tokens=512,use_cache=True)
        raw=obs={'answer':tokenizer.batch_decode(generated[:,ids.shape[-1]:],skip_special_tokens=True)[0],
            'model':'microsoft/llava-rad','revision':'dcdbc6caf6806c9acb66e12a827a39c86e00f6a7',
            'base_model':'lmsys/vicuna-7b-v1.5','base_revision':'3321f76e3f527bd14065daf69dad9344000a201d',
            'official_source_commit':'1fc44096cc5766c28d8a3329240c8423100ce3df',
            'backend_input_tokens':int(ids.shape[-1]),'backend_output_tokens':int(generated.shape[-1]-ids.shape[-1]),
            'adaptation':'Original LoRA/base/BiomedCLIP loading and generation, local path binding; text tower config initialization before the complete official CLIP checkpoint load.'}
    else:raise ValueError('unsupported_extended_backend')
    return plain(raw),plain(obs),derived

```
