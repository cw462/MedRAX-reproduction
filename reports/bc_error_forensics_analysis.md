# V7: mechanism grading for the six common-harm cases

Companion to `bc_error_forensics.md` (mechanical evidence) — this file adds the grading the
plan asks for: `confirmed / supported / unknown`. It covers the first priority group, the
6 questions where both B and C changed A's correct answer.

**What counts as evidence here.** The injected text is rebuilt from the frozen pool / skill
library and matches the run's logged length and sha256 (60/60 for both arms). The "own
observations" are the facts the arm's own tool calls returned, from `semantic_trace.jsonl`.
A keyword test is a *proxy*: "the word does not appear in the visible context" is weaker
than "the attribute was not visible", but it is checkable and reproducible.

## The pattern

In 5 of the 6 cases, the answer's decisive attribute does **not** appear in either the
injected block or the arm's own observations. The model asserted it.

| question | A/B/C | decisive attribute of the wrong option | in its own facts? | in its injection? | grade |
|---|---|---|---|---|---|
| 15314_8353800558683 | C/B/B | "peripheral distribution" (standard: central) | **no** | **no** | supported: unsupported attribute |
| 16568_8353800483171 | B/A/A | "unilateral, confined to right middle lobe" (standard: bilateral lower+middle) | B: no; C: "unilateral" yes | no | supported (C), unknown (B) |
| 17621_8143559684844 | D/A/A | "resolved / new lesions / lower zones" | **no** | **no** | unknown + official answer/rationale conflict |
| 4491_8353801523228 | B/E/E | "no abnormal findings" (standard: pneumomediastinum + subcutaneous emphysema) | no; and the standard's finding is absent from the visible facts | no | supported: positive finding was not in the visible observations |
| 722_8353802117601 | D/C/C | "similar size" plus swapped laterality (standard: left lower > right middle) | sides yes, "size" no | "similar" only from the block header | supported: size comparison unsupported |
| 8300_8353800861859 | D/B/B | "tuberculous cavity" (standard: aspergilloma) | **yes** | no | supported: driven by the tool observation, not the block |

## Case notes (only what the evidence supports)

**15314** — both arms moved to "bilateral ground-glass, peripheral, hypersensitivity
pneumonitis" while the standard is "multifocal patchy, central, right middle lobe
consolidation, PJP". Neither "peripheral" nor "central" appears in the arms' facts or
blocks. B's block is tool trajectories only (no clinical content). C's block includes a
skill whose trigger is *Legionella pneumonia* and whose checklist is "consolidation vs
ground-glass" — GGO vocabulary is present, but the distribution attribute is not. The
decisive change is therefore not explained by either source. This is the clearest case
for an acceptance gate: the changed attribute has no visible support.

**16568** — the standard is "bilateral alveolar infiltrates, lower lobes + right middle
lobe". Both arms wrote "unilateral, confined to right middle lobe". C's own facts do
contain "unilateral" (a report tool described the right side only); B's do not. This is
the plan's "工具只说右侧≠左侧没有异常" failure: absence of a mention was converted into a
negation. A gate rule that treats "not mentioned" as "not evidence" blocks this.

**17621** — the official answer says the right middle opacity decreased while upper-zone
nodules increased; the official explanation says both decreased. B and C both picked the
option with "resolved + new lower-zone lesions". The decisive attributes appear nowhere in
their context, and the item itself is ambiguous, so no mechanism claim should be made.
Keep the official score, flag the item.

**4491** — A correctly found pneumomediastinum and subcutaneous emphysema; B and C
answered "no abnormal findings". The standard's finding does not appear in B/C's visible
facts either — so the failure is upstream of the final option mapping: the positive
finding was not in the observations the model was working from. That is a tool/observation
problem, not an injection problem.

**722** — both arms swapped laterality and replaced "larger than" with "similar size".
Laterality words are in their facts; "size" is not, and the only "similar" in the context
comes from the memory block's boilerplate ("similar task features"), which is a false
positive of the keyword test, not evidence. The size comparison is unsupported.

**8300** — both arms' own facts contain "tuberculous cavity", and the injection contains
none of the discriminating vocabulary. So the change follows what the tools reported; the
block is not implicated. Whether the tools were right is a separate question.

## The control that kills the obvious gate rule

The tempting rule is: *accept a change only if every changed attribute appears in this
case's own observations*. Before recommending it, the same keyword test was run on the
**corrections** — the cases where an arm fixed A's wrong answer.

| group | mean share of the decisive words present in the arm's own facts |
|---|---:|
| corrections (16 arm-questions) | **0.226** |
| harms (23 arm-questions) | **0.362** |

The harms score *higher* than the corrections. So "the word is in the facts" does not
separate good changes from bad ones: used as a gate it would reject more corrections than
harms. Two reasons are visible in the cases: a correct change often follows a *combination*
of observations that never contains the option's wording, while a harmful change can echo a
tool's own phrase verbatim (8300's "tuberculous cavity" is in both arms' facts).

**This is a real negative result and it changes the design.** The keyword-traceability rule
must not be shipped as the gate. It survives only as a diagnostic in this file.

## What this means for the V7 design

1. **Do not use verbatim traceability as the acceptance rule.** The control above shows it
   would block more corrections than harms. Whether a semantic version (a model asked "is
   this attribute supported by these observations?") separates them is an open question and
   must be measured with the plan's own metrics — correction retention and harm prevention
   — on both groups, not assumed.
2. **The gate has to be evaluated on corrections and harms together.** Any rule that only
   reports how many harms it blocked is unfalsifiable: blocking everything blocks all harm.
   The plan's `纠正保留率 / 损害阻止率` pair is the right instrument, and this file is the
   first evidence that it matters.
3. **Not all harm is memory's fault.** 8300's harm tracks the tool observation; 4491's
   failure is at the observation layer (the positive finding never reached the model). A
   gate that only inspects the memory block would miss these, and a retrieval fix would not
   repair them.
4. The remaining 22 questions have the same mechanical evidence extracted
   (`runs/v7_forensics/bc_error_forensics.jsonl`) but are not yet graded. Next in the
   plan's order: the 8 C-only harms, then 3 B-only harms, then the 11 corrections.

## Caveats

* Keyword absence is a proxy. A phrase can be supported by a differently-worded
  observation; the tool facts are summaries, not the raw model context. That weakness cuts
  both ways and is part of why the rule failed the control.
* The 6 cases are the ones where both arms changed a correct answer; selecting on outcome
  can make a pattern look more uniform than it is. The control group above is exactly the
  guard against that.
