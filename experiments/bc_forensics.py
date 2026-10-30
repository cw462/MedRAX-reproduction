"""V7 step 1: offline forensics for the 28 questions where A/B/C disagree.

No API calls. Reads only what the S2 round-1 runs already saved:

  * the official question/options/answer/explanation from the benchmark metadata;
  * each arm's terminal letter and outcome from its scored sidecar;
  * the **actually injected** text, rebuilt from the run's retrieval log and the
    frozen pool / skill library (verified to match the logged length and sha256);
  * each arm's real tool sequence and observation facts from `semantic_trace.jsonl`.

What the script can settle mechanically: which option attributes differ, whether
those attributes were present in the injected block, and where the tool paths first
diverge. What it cannot settle: why a model changed its answer. Those rows are marked
`mechanism_level: unknown` unless the evidence decides them, and the report says so.

Output: jsonl rows (one per question) plus a markdown digest.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

GROUPS = {
    "common_correct": ["15189_8353800545058", "3436_8353801521068", "5369_8353801533158",
                       "548_8353802023456", "7738_8353800850751"],
    "b_only_correct": ["11858_8353800664572", "13154_8353800587826", "3359_8353801515597"],
    "c_only_correct": ["11804_8353800651404", "18780_8143559008557", "3546_8353801521080"],
    "common_harm": ["15314_8353800558683", "16568_8353800483171", "17621_8143559684844",
                    "4491_8353801523228", "722_8353802117601", "8300_8353800861859"],
    "b_only_harm": ["18202_8143559000122", "4118_8353801523564", "5533_8353801540251"],
    "c_only_harm": ["12721_8353800681884", "13238_8353800603808", "16663_8353800455763",
                    "1678_8353802279918", "3397_8353801520783", "3561_8353801511489",
                    "3686_8353801520174", "3834_8353801523222"],
}

# One line per question: what the plan's appendix says to check (kept short, and only
# as a pointer - it is not evidence).
PLAN_FOCUS = {
    "15189_8353800545058": "正侧位对应、气液平面是否真实存在",
    "3436_8353801521068": "是否有真实的肋骨/肋间定位步骤",
    "5369_8353801533158": "疝入内容物是否有影像支持",
    "548_8353802023456": "是否检视骨性结构/相关图像",
    "7738_8353800850751": "实变变化与残余磨玻璃影是否分开记录",
    "11858_8353800664572": "肺内/肺外与胸壁关系证据",
    "13154_8353800587826": "钙化判断来源、侧位绑定",
    "3359_8353801515597": "是否遗漏前纵隔肿块",
    "11804_8353800651404": "两种病征分别绑定左右，禁止互相传播",
    "18780_8143559008557": "完全/部分与持续/加重分别判断",
    "3546_8353801521080": "病灶存在性 + 选项否定/因果表达",
    "15314_8353800558683": "分布属性来源与任务目标（问 PJP 支持证据）",
    "16568_8353800483171": "逐图逐侧核对，工具只说右侧≠左侧正常",
    "17621_8143559684844": "标准答案与解释冲突，单列歧义",
    "4491_8353801523228": "阳性观察是否被后续报告遗漏覆盖",
    "722_8353802117601": "对象-图像-侧别-大小关系表",
    "8300_8353800861859": "当前腔内征象 vs 既往结核关键词",
    "18202_8143559000122": "“可能出现的征象”vs“本图存在的征象”",
    "4118_8353801523564": "左右绑定与气胸证据",
    "5533_8353801540251": "结肠袋影存在性（否定属性）",
    "12721_8353800681884": "完成失败，不是判断翻转；查冗余轨迹",
    "13238_8353800603808": "右/中央、胸壁关系、肋间、气管",
    "16663_8353800455763": "分布与新增病因分别核对（歧义题）",
    "1678_8353802279918": "正侧位、投影重叠、阴性观察",
    "3397_8353801520783": "空洞来自当前输出还是经验引入",
    "3561_8353801511489": "正侧位同一病灶与膈肌关系",
    "3686_8353801520174": "输入背景不足，单列",
    "3834_8353801523222": "基础慢性改变 vs 本次急性叠加",
}


def read_jsonl(path):
    if not Path(path).exists():
        return []
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_options(question):
    """Split the official question text into stem + {A..F: text}."""
    lines = question.splitlines()
    options, stem, current = {}, [], None
    for line in lines:
        match = re.match(r"^([A-F])\)\s*(.*)$", line.strip())
        if match:
            current = match.group(1)
            options[current] = match.group(2).strip()
        elif current and line.strip():
            options[current] += " " + line.strip()
        else:
            stem.append(line)
    return "\n".join(stem).strip(), options


TOKEN = re.compile(r"[A-Za-z]+|\d+(?:\.\d+)?%?|[\u4e00-\u9fff]|[^\sA-Za-z0-9\u4e00-\u9fff]")


def tokenize(text):
    return [(m.group(), m.start(), m.end()) for m in TOKEN.finditer(text or "")]


def diff_spans(a, b, limit=70, max_spans=8):
    """Word/character-level spans that differ between two option texts.

    Tokenising first keeps the output readable ("unilateral" vs "bilateral") instead of
    the character-level fragments a raw SequenceMatcher produces on shared boilerplate.
    The span is sliced from the original string, so spacing survives.
    Punctuation-only differences are dropped: they are not attributes.
    """
    ta, tb = tokenize(a), tokenize(b)
    out = []
    sm = difflib.SequenceMatcher(None, [t[0] for t in ta], [t[0] for t in tb], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        left = a[ta[i1][1]:ta[i2 - 1][2]].strip() if i2 > i1 else ""
        right = b[tb[j1][1]:tb[j2 - 1][2]].strip() if j2 > j1 else ""
        if not re.search(r"[A-Za-z0-9\u4e00-\u9fff]", left + right):
            continue
        if len(left) + len(right) < 2:
            continue
        out.append({"left": left[:limit], "right": right[:limit]})
        if len(out) >= max_spans:
            break
    return out


KEYWORD = re.compile(r"[A-Za-z]{4,}|[\u4e00-\u9fff]{2,}")


def keywords(span):
    seen, out = set(), []
    for side in (span.get("left"), span.get("right")):
        for word in KEYWORD.findall(side or ""):
            key = word.lower()
            if key not in seen:
                seen.add(key)
                out.append(word)
    return out[:6]


def normalise(text):
    return re.sub(r"\s+", "", text or "").lower()


class Evidence:
    def __init__(self, run_root):
        self.root = Path(run_root)
        self.inputs = {r["question_id"]: r for r in
                       read_jsonl(self.root / "runs/v4_validation60/inputs.jsonl")}
        self.meta = {}
        for row in read_jsonl(self.root / "data/chest-agent-bench/metadata.jsonl.new"):
            self.meta[row["question_id"]] = row
        self.pool = read_json(self.root / "runs/memory_pool_v3/pool.json")["payload"]["records"]
        self.by_id = {rec["memory_id"]: rec for rec in self.pool}
        self.skills = read_json(self.root / "runs/skills_v0/skills.json")["skills"]
        sys.path.insert(0, str(self.root / "code"))
        sys.path.insert(0, str(self.root / "code/experiments"))
        from memory_pipeline.core import _context
        from memory_pipeline.injection import build_memory_block
        from skill_policy import SkillIndex
        from skill_render import render_block
        self._context = _context
        self._build_memory_block = build_memory_block
        self._index = SkillIndex(self.skills)
        self._render = render_block
        self.retrieval = {
            "B": self._dedupe(read_jsonl(self.root / "runs/v4_B_r1/retrieval.jsonl")),
            "C": self._dedupe(read_jsonl(self.root / "runs/v4_C_r1/retrieval.jsonl")),
        }
        self.terminals = {}
        for arm in ("A", "B", "C"):
            self.terminals[arm] = {
                r["question_id"]: r for r in
                read_jsonl(self.root / f"runs/v4_{arm}_r1/results.jsonl")
                if r.get("record_type") == "terminal"}
        self.traces = {
            arm: self._group_traces(read_jsonl(self.root / f"runs/v4_{arm}_r1/semantic_trace.jsonl"))
            for arm in ("A", "B", "C")}

    @staticmethod
    def _dedupe(rows):
        out = {}
        for row in rows:
            out.setdefault(row["question_id"], row)     # first run is the scored one
        return out

    @staticmethod
    def _group_traces(rows):
        out = {}
        for row in rows:
            out.setdefault(row["question_id"], []).append(row)
        return out

    def injected(self, arm, qid):
        if arm == "B":
            row = self.retrieval["B"].get(qid)
            if not row:
                return {"text": "", "source": "no retrieval row"}
            hits = [{"memory_id": mid, "score": sc,
                     "context": self._context(self.by_id[mid], summary_mode=False,
                                              include_outcome=False)}
                    for mid, sc in zip(row["memory_ids"], row["scores"])]
            text, audit = self._build_memory_block(hits, max_chars=1400)
            return {"text": text, "returned": audit["returned"], "rendered": audit["rendered"],
                    "ids": audit["memory_ids"], "chars": len(text),
                    "log_match": len(text) == row["injected_chars"] and
                                 hashlib.sha256(text.encode()).hexdigest() == row["injected_sha256"]}
        if arm == "C":
            row = self.retrieval["C"].get(qid)
            if not row:
                return {"text": "", "source": "no retrieval row"}
            hits = self._index.search(self.inputs[qid]["question"], top_k=3, topic_filter=True)
            text = self._render(hits, max_chars=1400)
            return {"text": text, "skills": [h.get("skill_id") for h in hits], "chars": len(text),
                    "log_match": [h.get("skill_id") for h in hits] == row["skills"]
                                 and len(text) == row["skill_chars"]}
        return {"text": "", "source": "no injection"}

    def tool_path(self, arm, qid):
        out = []
        for row in self.traces[arm].get(qid, []):
            args = row.get("arguments") or {}
            preview = {k: (str(v)[:60] if not isinstance(v, (int, float)) else v)
                       for k, v in list(args.items())[:3]}
            out.append({"tool": row.get("tool_name"), "status":
                        (row.get("observation") or {}).get("execution_status"),
                        "arguments": preview})
        return out

    def facts_text(self, arm, qid):
        chunks = []
        for row in self.traces[arm].get(qid, []):
            facts = (row.get("observation") or {}).get("facts")
            if facts:
                chunks.append(json.dumps(facts, ensure_ascii=False, default=str))
        return "\n".join(chunks)


def first_divergence(a_rows, x_rows):
    for i, (ar, xr) in enumerate(zip(a_rows, x_rows)):
        if ar["tool"] != xr["tool"]:
            return {"index": i, "a_tool": ar["tool"], "x_tool": xr["tool"]}
    if len(a_rows) != len(x_rows):
        i = min(len(a_rows), len(x_rows))
        extra = "x_extra" if len(x_rows) > len(a_rows) else "a_extra"
        return {"index": i, "a_tool": a_rows[i]["tool"] if i < len(a_rows) else None,
                "x_tool": x_rows[i]["tool"] if i < len(x_rows) else None, "note": extra}
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out-jsonl", type=Path, required=True)
    ap.add_argument("--out-md", type=Path, required=True)
    args = ap.parse_args(argv)
    ev = Evidence(args.root)

    rows = []
    for group, qids in GROUPS.items():
        for qid in qids:
            meta = ev.meta[qid]
            stem, options = parse_options(meta["question"])
            standard = str(meta["answer"]).strip().upper()
            predictions = {}
            for arm in ("A", "B", "C"):
                term = ev.terminals[arm].get(qid) or {}
                letter = term.get("answer_letter")
                predictions[arm] = {"letter": letter, "status": term.get("status"),
                                    "option": options.get(letter or "", ""),
                                    "correct": letter == standard}
            inject = {"B": ev.injected("B", qid), "C": ev.injected("C", qid)}
            paths = {arm: ev.tool_path(arm, qid) for arm in ("A", "B", "C")}
            facts = {arm: ev.facts_text(arm, qid) for arm in ("A", "B", "C")}

            # what each arm's answer changed relative to the standard option
            disc = {}
            for arm in ("A", "B", "C"):
                letter = predictions[arm]["letter"]
                if letter and letter != standard:
                    disc[arm] = diff_spans(options.get(letter, ""), options.get(standard, ""))
                else:
                    disc[arm] = []

            # For each wrong arm: which attributes of the *standard* option were visible to it,
            # and which attributes it asserted without any support in its own context.
            support = {}
            for arm in ("B", "C"):
                spans = disc.get(arm) or []
                std_words, claimed_words = [], []
                for span in spans:
                    for word in keywords({"left": span["right"], "right": ""}):      # standard side
                        if word not in std_words:
                            std_words.append(word)
                    for word in keywords({"left": span["left"], "right": ""}):       # arm's side
                        if word not in claimed_words:
                            claimed_words.append(word)
                inj_norm, fact_norm = normalise(inject[arm]["text"]), normalise(facts[arm])
                support[arm] = {
                    "standard_attributes": std_words,
                    "standard_in_facts": [w for w in std_words if normalise(w) in fact_norm],
                    "standard_in_injection": [w for w in std_words if normalise(w) in inj_norm],
                    "claimed_attributes": claimed_words,
                    "claimed_in_facts": [w for w in claimed_words if normalise(w) in fact_norm],
                    "claimed_in_injection": [w for w in claimed_words if normalise(w) in inj_norm],
                    "claimed_unsupported": [w for w in claimed_words
                                            if normalise(w) not in fact_norm
                                            and normalise(w) not in inj_norm],
                }
            checks = []
            for arm in ("B", "C"):
                for span in (disc.get(arm) or [])[:6]:
                    words = keywords(span)
                    if not words:
                        continue
                    inj_norm = normalise(inject[arm]["text"])
                    fact_norm = normalise(facts[arm])
                    checks.append({
                        "arm": arm, "span": f"{span['left']} | {span['right']}",
                        "keywords": words,
                        "in_injection": [w for w in words if normalise(w) in inj_norm],
                        "in_own_facts": [w for w in words if normalise(w) in fact_norm],
                    })

            # Control for the traceability rule: when A was wrong, do the arms that *fixed*
            # it actually have the standard option's decisive words in their own facts? If the
            # corrections look the same as the harms, the rule has no discriminative power.
            correction_check = None
            if not predictions["A"]["correct"] and predictions["A"]["letter"]:
                a_spans = diff_spans(options.get(predictions["A"]["letter"], ""),
                                     options.get(standard, ""))
                words = []
                for span in a_spans:
                    for word in keywords({"left": span["right"], "right": ""}):
                        if word not in words:
                            words.append(word)
                correction_check = {
                    "standard_words_from_A": words,
                    "B_in_facts": [w for w in words if normalise(w) in normalise(facts["B"])],
                    "C_in_facts": [w for w in words if normalise(w) in normalise(facts["C"])],
                    "B_in_injection": [w for w in words if normalise(w) in normalise(inject["B"]["text"])],
                    "C_in_injection": [w for w in words if normalise(w) in normalise(inject["C"]["text"])],
                }

            rows.append({
                "question_id": qid, "group": group, "type": meta.get("categories"),
                "images": meta.get("images"),
                "official": {"answer": standard, "stem": stem[:400],
                             "option_standard": options.get(standard, ""),
                             "explanation": meta.get("explanation", "")[:600]},
                "predictions": predictions,
                "discriminators": disc,
                "injection": {arm: {k: v for k, v in inject[arm].items() if k != "text"}
                              for arm in ("B", "C")},
                "injection_text": {arm: inject[arm].get("text", "") for arm in ("B", "C")},
                "tool_paths": paths,
                "first_divergence": {"B_vs_A": first_divergence(paths["A"], paths["B"]),
                                     "C_vs_A": first_divergence(paths["A"], paths["C"])},
                "attribute_checks": checks,
                "standard_support": support,
                "correction_check": correction_check,
                "mechanism_level": "unknown",
                "plan_focus": PLAN_FOCUS.get(qid, ""),
                "note": ("b/c 的注入文本由冻结池/技能库逐字节重建，log_match=true 表示与运行时"
                         "记录的字符数和 sha256 一致；不等于模型一定使用了它。"),
            })

    args.out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with args.out_jsonl.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    # ---------------- markdown digest
    lines = ["# V7 step 1: offline forensics of the 28 changed questions", ""]
    lines.append("No API calls. Answers come from the scored sidecars; injected text is rebuilt")
    lines.append("from each run's retrieval log and checked against the logged length and sha256")
    lines.append("(`log_match`); tool paths come from `semantic_trace.jsonl`.")
    lines.append("")
    lines.append("**Mechanism level is `unknown` for every row unless stated otherwise.** What this")
    lines.append("file establishes is what was visible and what changed, not why the model changed.")
    lines.append("")
    counts = {g: sum(1 for r in rows if r["group"] == g) for g in GROUPS}
    lines.append("| group | n | log_match B/C | questions |")
    lines.append("|---|---:|---|---|")
    for group in GROUPS:
        group_rows = [r for r in rows if r["group"] == group]
        ok = sum(1 for r in group_rows
                 if r["injection"]["B"].get("log_match") and r["injection"]["C"].get("log_match"))
        lines.append(f"| {group} | {counts[group]} | {ok}/{len(group_rows)} | "
                     + ", ".join(r["question_id"].split("_")[0] for r in group_rows) + " |")
    lines.append("")
    for group in ("common_harm", "c_only_harm", "b_only_harm", "common_correct",
                  "c_only_correct", "b_only_correct"):
        lines.append(f"## {group}")
        lines.append("")
        for r in [x for x in rows if x["group"] == group]:
            p = r["predictions"]
            std = r["official"]["answer"]
            lines.append(f"### {r['question_id']} ({r['type']}, std {std})")
            lines.append("")
            lines.append(f"A/B/C = {p['A']['letter']}/{p['B']['letter']}/{p['C']['letter']}")
            lines.append("")
            if r["plan_focus"]:
                lines.append(f"Plan focus: {r['plan_focus']}")
                lines.append("")
            for arm in ("B", "C"):
                spans = r["discriminators"].get(arm) or []
                if spans:
                    shown = "; ".join(f"“{s['left'][:40]}” vs “{s['right'][:40]}”"
                                      for s in spans[:3])
                    lines.append(f"* {arm}'s option differs from the standard on: {shown}")
            for arm in ("B", "C"):
                inj = r["injection"][arm]
                got = [c for c in r["attribute_checks"] if c["arm"] == arm]
                words_in = sum(len(c["in_injection"]) for c in got)
                words_facts = sum(len(c["in_own_facts"]) for c in got)
                words_all = sum(len(c["keywords"]) for c in got)
                lines.append(f"* {arm} injected {inj.get('chars')} chars"
                             + (f", {inj.get('rendered')} memories" if arm == "B" else
                                f", skills {inj.get('skills')}")
                             + f"; attribute keywords in the injection: {words_in}/{words_all}, "
                               f"in its own tool observations: {words_facts}/{words_all}")
            for arm in ("B", "C"):
                div = r["first_divergence"][f"{arm}_vs_A"]
                if div:
                    lines.append(f"* first tool-path divergence {arm} vs A: index {div['index']}, "
                                 f"A={div.get('a_tool')} vs {arm}={div.get('x_tool')}")
                else:
                    lines.append(f"* {arm} followed the same tool sequence as A")
            lines.append("")
    lines.append("## What is still unknown")
    lines.append("")
    lines.append("* Whether a changed answer came from the injected block, a tool observation, a")
    lines.append("  summary/compression step, or the final option mapping. The per-question tool")
    lines.append("  paths and attribute checks narrow it; they cannot identify the step.")
    lines.append("* The plan's three flagged questions (`17621_8143559684844` answer/rationale")
    lines.append("  conflict, `16663_8353800455763` compound-option ambiguity, `3686_8353801520174`")
    lines.append("  missing context) keep the official scoring but are flagged in the rows.")
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out_jsonl} ({len(rows)} rows) and {args.out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
