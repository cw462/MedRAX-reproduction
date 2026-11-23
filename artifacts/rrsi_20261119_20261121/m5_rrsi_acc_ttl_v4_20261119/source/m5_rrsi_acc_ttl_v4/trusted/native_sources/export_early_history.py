"""Publish retained historical experiment records; never runs inference or reads a ledger.

Input is a private, already-downloaded snapshot of explicitly selected old run folders.
Only JSON/JSONL/text experiment artifacts are handled. Reference labels are joined after
the historical runs have ended and are never supplied to an inference process.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import json
from pathlib import Path
import re


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def clean(value):
    if isinstance(value, dict):
        return {k: ("[REDACTED_SECRET]" if re.fullmatch(r"(?:api[_-]?key|authorization|password|access_token|private_key)", k, re.I) else clean(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(x) for x in value]
    if not isinstance(value, str):
        return value
    value = re.sub(r"data:image/[^;\s]+;base64,[A-Za-z0-9+/=]+", "[IMAGE_BYTES_OMITTED]", value)
    value = re.sub(r"/home/[^/\s]+/[^/\s]+/MedRAX_reproduction_\d+", "[RUN_ROOT]", value)
    value = re.sub(r"/home/[^/\s]+", "[HOME]", value)
    value = re.sub(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s]+", "[LOCAL_HOME]", value)
    value = re.sub(r"\bsk-[A-Za-z0-9_-]{16,}\b", "[REDACTED_SECRET]", value)
    value = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._-]{16,}", "Bearer [REDACTED_SECRET]", value)
    return value


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--shared-cases", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    artifacts, runs = [], []
    cases = defaultdict(lambda: {"input_variants": [], "episodes": [], "observations": [], "retrieval": [], "v7_recovery": [], "v7_forensics": []})
    labels = {}
    for name in ["memory_train.labels.jsonl", "validation.labels.jsonl"]:
        for row in read_lines(args.source / "data" / name):
            labels[row["question_id"]] = row["answer"]
    for directory in sorted(args.source.iterdir()):
        if not directory.is_dir() or directory.name == "data":
            continue
        for path in sorted(directory.iterdir()):
            is_backup_journal = path.name == "results.jsonl.bak-before-resume"
            if path.suffix not in {".json", ".jsonl", ".txt", ".md"} and not is_backup_journal:
                continue
            rel = path.relative_to(args.source)
            target = args.out / "records" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".json":
                value = read_json(path)
                dump(target, value)
                count = None
            elif path.suffix == ".jsonl" or is_backup_journal:
                value = read_lines(path)
                target.write_text("".join(json.dumps(clean(x), ensure_ascii=False) + "\n" for x in value), encoding="utf-8")
                count = len(value)
            else:
                target.write_text(clean(path.read_text(encoding="utf-8")), encoding="utf-8")
                count = None
            artifacts.append({"source_relative_path": rel.as_posix(), "published_path": target.relative_to(args.out).as_posix(), "source_bytes": path.stat().st_size, "published_bytes": target.stat().st_size, "records": count})
            if path.suffix != ".jsonl" and not is_backup_journal:
                continue
            for row in value:
                qid = row.get("question_id")
                if not qid:
                    continue
                section = None
                if (path.name == "results.jsonl" or is_backup_journal) and row.get("record_type") == "terminal":
                    section = "episodes"
                elif path.name == "semantic_trace.jsonl":
                    section = "observations"
                elif path.name == "retrieval.jsonl":
                    section = "retrieval"
                elif directory.name == "v7_recovery" and ".trace." not in path.name:
                    # The two diagnostic filenames are aliases of the retained round files.
                    if path.name not in {"keep_style_diagnostic.jsonl", "propose_optional_check_diagnostic.jsonl"}:
                        section = "v7_recovery"
                elif directory.name == "v7_forensics":
                    section = "v7_forensics"
                if section:
                    cases[qid][section].append({"source": rel.as_posix(), "record": row})
        if not (directory / "manifest.json").exists() or not (directory / "results.jsonl").exists():
            continue
        manifest = read_json(directory / "manifest.json")
        plan = manifest.get("plan", {})
        summary = read_json(directory / "summary.json") if (directory / "summary.json").exists() else {}
        terminals = [x for x in read_lines(directory / "results.jsonl") if x.get("record_type") == "terminal"]
        scored_path = args.source / (directory.name + "_scored") / "outcomes.json"
        outcome_rows = read_json(scored_path).get("outcomes", []) if scored_path.exists() else []
        outcome_by_key = {(x["question_id"], x.get("arm", "agent")): x["task_outcome"] for x in outcome_rows}
        arm_rows = []
        for arm in sorted(set(x.get("arm", "agent") for x in terminals)):
            rows = [x for x in terminals if x.get("arm", "agent") == arm]
            correct = sum(x.get("answer_letter") == labels.get(x["question_id"]) and bool(x.get("answer_letter")) for x in rows)
            saved_correct = sum(outcome_by_key.get((x["question_id"], arm)) == "correct" for x in rows) if scored_path.exists() else None
            arm_rows.append({"arm": arm, "terminal_records": len(rows), "unique_questions": len({x["question_id"] for x in rows}), "correct_from_saved_sidecar": saved_correct, "correct_posthoc_label_join": correct, "status_counts": dict(Counter(x.get("status") for x in rows)), "valid_answer_count": sum(bool(x.get("answer_letter")) for x in rows), "model_calls": sum(x.get("actual_model_calls", 0) for x in rows), "tool_attempts": sum(x.get("actual_tool_attempts", 0) for x in rows), "summed_episode_seconds": round(sum(x.get("elapsed_seconds", 0) for x in rows), 3), "settlements_in_terminal_records_cny": str(sum((Decimal(str(s.get("charged_cny", 0))) for x in rows for s in x.get("ledger_settlements", [])), Decimal(0)))})
        runs.append({"run": directory.name, "manifest": "records/" + directory.name + "/manifest.json", "results": "records/" + directory.name + "/results.jsonl", "planned_questions": plan.get("planned_question_count", summary.get("planned_question_count")), "recorded_stop_reason": summary.get("stop_reason"), "complete_run": summary.get("stop_reason") == "complete", "model": plan.get("model"), "tools": plan.get("available_tool_names"), "max_tool_calls": plan.get("max_tool_calls"), "max_model_calls": plan.get("max_model_calls"), "max_output_tokens": plan.get("max_output_tokens"), "temperature": plan.get("temperature"), "created_utc": manifest.get("created_utc"), "updated_utc": summary.get("updated_utc"), "arms": arm_rows})
    input_files = [args.source / "data" / name for name in ["inference.jsonl", "memory_train_subset_v1.jsonl", "validation_subset_v1.jsonl", "validation_subset_v2.jsonl"]]
    input_files.append(args.source / "v4_validation60" / "inputs.jsonl")
    for path in input_files:
        for row in read_lines(path):
            if row["question_id"] in cases:
                cases[row["question_id"]]["input_variants"].append({"source": path.relative_to(args.source).as_posix(), "input": row})
    shared = {p.stem for p in args.shared_cases.glob("*.json")}
    case_index = []
    for qid, case in sorted(cases.items()):
        case["question_id"] = qid
        case["reference_answer"] = labels.get(qid)
        case["reference_use"] = "Retrospective publication after completed historical inference; never inference input."
        case["v11_shared_case"] = f"../../../v11/cases/{qid}.md" if qid in shared else None
        image_refs = []
        for variant in case["input_variants"]:
            for name in variant["input"].get("images", []):
                if name.startswith("figures/"):
                    image_refs.append({"input_source": variant["source"], "original_input_path": name, "published_path": "../images/" + name})
                elif variant["source"] == "data/inference.jsonl":
                    image_refs.append({"input_source": variant["source"], "original_input_path": name, "published_path": "../images/diagnostic50/" + name})
        case["original_images"] = image_refs
        dump(args.out / "cases" / f"{qid}.json", case)
        lines = [f"# 早期实验逐题档案：{qid}", "", f"独立评分参考选项：**{labels.get(qid, '未找到')}**。此页用于完成后的复盘，参考答案未反馈给历史推理过程。", "", f"[全部保留记录 JSON]({qid}.json) 包含逐轮终态、工具语义观察、检索记录与 V7 分支原文；每条带有来源文件。工具或模型的断言仍是待核实的观察。", ""]
        if case["input_variants"]:
            lines.extend(["## 原题与完整选项", "", case["input_variants"][0]["input"]["question"], ""])
        lines.extend(["## 原图", ""])
        seen_images = set()
        for item in image_refs:
            if item["published_path"] not in seen_images:
                seen_images.add(item["published_path"])
                lines.extend([f"来源输入：`{item['input_source']}`；实际路径：`{item['original_input_path']}`。", "", f"![{item['original_input_path']}]({item['published_path']})", ""])
        if case["v11_shared_case"]:
            lines.extend([f"同一固定 60 题后续证据：[V10/V11 图文档案]({case['v11_shared_case']})。不同轮 P0 独立生成，不能把差异直接视为方法收益。", ""])
        lines.extend(["## 当时保存的逐轮结果", "", "备份/中断尝试单列，不能与最终完成版本相加。", "", "| 来源 | 臂 | 选项 | 执行状态 | 参考匹配 |", "|---|---|---|---|---|"])
        for entry in case["episodes"]:
            row = entry["record"]
            answer = row.get("answer_letter")
            lines.append(f"| `{entry['source']}` | {row.get('arm', 'agent')} | {answer or '缺答'} | {row.get('status')} | {'对' if answer and answer == labels.get(qid) else '未答对'} |")
        for entry in case["v7_recovery"]:
            row = entry["record"]
            letters = dict(row.get("letters", {}))
            letters["P1"] = row.get("branches", {}).get("P1", {}).get("letter")
            for arm, answer in letters.items():
                lines.append(f"| `{entry['source']}` | {arm} | {answer or '缺答'} | {row.get('status')} | {'对' if answer and answer == labels.get(qid) else '未答对'} |")
        lines.extend(["", f"保留的语义观察 {len(case['observations'])} 条；检索记录 {len(case['retrieval'])} 条；V7 恢复实验记录 {len(case['v7_recovery'])} 条。详见同页 JSON。早期只有摘要/哈希的响应无法从哈希还原原文；此处未补写模型输出。", ""])
        (args.out / "cases" / f"{qid}.md").write_text(clean("\n".join(lines)), encoding="utf-8")
        case_index.append({"question_id": qid, "case_path": f"cases/{qid}.json", "reference_answer": labels.get(qid), "episode_count": len(case["episodes"]), "observation_count": len(case["observations"]), "v7_recovery_count": len(case["v7_recovery"]), "input_variants": len(case["input_variants"]), "image_count": len({x["published_path"] for x in image_refs})})
    v7_rows = read_lines(args.source / "v7_recovery" / "round2_verify.jsonl")
    v7_public = []
    for row in v7_rows:
        letters = dict(row.get("letters", {}))
        letters["P1"] = row.get("branches", {}).get("P1", {}).get("letter")
        qid = row["question_id"]
        v7_public.append({"question_id": qid, "status": row["status"], "reference_answer": labels.get(qid), "letters": letters, "correct": {name: bool(letters.get(name)) and letters.get(name) == labels.get(qid) for name in ["P0", "P1", "PB", "PC", "GB", "GC"]}})
    v7_summary = {name: {"correct": sum(x["correct"][name] for x in v7_public), "planned": 60, "legal_answer_count": sum(bool(x["letters"].get(name)) for x in v7_public), "missing_answer_count": sum(not bool(x["letters"].get(name)) for x in v7_public), "correct_to_legal_wrong": sum(x["correct"]["P0"] and bool(x["letters"].get(name)) and not x["correct"][name] for x in v7_public), "correct_to_missing": sum(x["correct"]["P0"] and not x["letters"].get(name) for x in v7_public), "legal_wrong_to_correct": sum(bool(x["letters"].get("P0")) and not x["correct"]["P0"] and x["correct"][name] for x in v7_public)} for name in ["P0", "P1", "PB", "PC", "GB", "GC"]}
    dump(args.out / "v7-fixed-denominator.json", {"derivation": "Read retained prediction letters and completed-run labels; no rerun or prediction rewrite.", "variants": v7_summary, "questions": v7_public})
    dump(args.out / "runs.json", runs)
    dump(args.out / "cases.json", case_index)
    case_lines = ["# 早期实验 149 题档案导航", "", "题干、选项、原图、历史预测与保留的工具观察按 question_id 联结。训练题、旧验证题和后来的固定 60 题均保留各自来源；不是一个合并准确率分母。", "", "| 题目 | 终态记录 | 工具语义观察 | V7 记录 |", "|---|---:|---:|---:|"]
    for item in case_index:
        qid = item["question_id"]
        case_lines.append(f"| [{qid}](cases/{qid}.md) | {item['episode_count']} | {item['observation_count']} | {item['v7_recovery_count']} |")
    (args.out / "case-index.md").write_text("\n".join(case_lines) + "\n", encoding="utf-8")
    run_lines = ["# 逐轮保留记录与执行配置", "", "本表直接读历史 manifest、终态记录和原评分 sidecar。正确数另与已完成后的参考选项联结；两者分别保存在 runs.json。partial 表示当时保存的状态未完成，不能作为整轮成绩。费用只加总终态中原有结算字段，不读取账本；中断重试可能不全在终态，且这些值不是供应商账单。", "", "| 运行 | 完整状态 | 臂 | 终态/计划题数 | 正确 | 合法选项 | 模型/工具调用 | 终态记账 CNY |", "|---|---|---|---|---:|---:|---|---:|"]
    for run in sorted(runs, key=lambda x: x.get("created_utc") or ""):
        for arm in run["arms"]:
            run_lines.append(f"| [{run['run']}]({run['manifest']}) | {'complete' if run['complete_run'] else 'partial:' + str(run['recorded_stop_reason'])} | {arm['arm']} | {arm['terminal_records']}/{run['planned_questions']} | {arm['correct_posthoc_label_join']} | {arm['valid_answer_count']} | {arm['model_calls']}/{arm['tool_attempts']} | {arm['settlements_in_terminal_records_cny']} |")
    run_lines.extend(["", "模型、工具注册表、各工具版本、提示词、temperature、top_p、output cap、调用上限、输入顺序、包版本与协议偏差以各行链接的原 manifest 为准。部分旧 manifest 的文字说明未随工具集合更新；判断实际可用工具应以 available_tool_names 为准。", ""])
    (args.out / "run-index.md").write_text("\n".join(run_lines), encoding="utf-8")
    dump(args.out / "manifest.json", {"publication_date": "2026-10-31", "scope": "Retained experiment artifacts through V7, including explicitly marked interrupted attempts; no new inference.", "sanitization": ["Absolute server/user roots replaced with placeholders", "Credential-shaped values removed", "Embedded image bytes omitted; original files published separately", "No ledger file or model weights loaded", "Original source hashes are historical metadata, not hashes of these sanitized exports"], "source_limitations": ["Many early model/tool traces retain hashes and schemas only, not full response prose", "semantic_trace summaries and argument truncation cannot be reversed", "Interruption records and stale running labels are retained as historical state, not a claim the old process is still running", "Fixed 60 denominator used in the supplemental V7 table; old report denominators remain visible"], "artifacts": artifacts, "run_count": len(runs), "case_count": len(cases)})
    print(json.dumps({"artifacts": len(artifacts), "run_count": len(runs), "case_count": len(cases), "v7": v7_summary}, ensure_ascii=False))


if __name__ == "__main__":
    main()
