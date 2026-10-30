# V7: mechanism grading for the 28 changed questions

Companion to `bc_error_forensics.md` (mechanical evidence) — this file adds the grading the
plan asks for: `confirmed / supported / unknown`. It covers all 28 questions where A/B/C
disagree, in the plan's order: the 6 common harms, the 8 C-only harms, the 3 B-only harms,
then the 11 corrections.

**What counts as evidence here.** The injected text is rebuilt from the frozen pool / skill
library and matches the run's logged length and sha256 (60/60 for both arms). The "own
observations" are the facts the arm's own tool calls returned, from `semantic_trace.jsonl`.
A keyword test is a *proxy*: "the word does not appear in the visible context" is weaker
than "the attribute was not visible", but it is checkable and reproducible.

## The pattern in the six common harms

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

## The other 22 cases

Ordered as the plan asks: C-only harms, B-only harms, then the corrections. "Source" says
where the decisive attribute first appears in that arm's visible context — its own tool
facts, the injected block, both, or neither.

### C-only harms (8)

| question | std / C | what C changed | source of the changed attribute | grade |
|---|---|---|---|---|
| 12721_8353800681884 | B / none | no answer at all (`case_budget_exceeded`) | — | **confirmed**: completion failure, not a judgement |
| 13238_8353800603808 | B / A | dorsolateral + 3rd rib → "central mediastinal, trachea left" | both: facts contain trachea/mediastinal; block mentions "trachea, aortic arch, carina" | supported (block vocabulary + observation) |
| 16663_8353800455763 | C / B | "equally distributed" → "more extensive right + bacterial superinfection" | block: skill text says "extensive right lung pneumonia ... laterality" | supported (block vocabulary); item is flagged ambiguous |
| 1678_8353802279918 | C / A | "no air bronchogram" → "confirmed air bronchogram" | neither ("presence" only) | supported: negation flipped without support |
| 3397_8353801520783 | C / B | bibasal peripheral reticulation → "upper lobe cavitations, TB" | facts: "Upper lobe" present | supported (observation) |
| 3561_8353801511489 | B / F | Bochdalek hernia → "pseudotumor, atelectasis" | facts: pseudotumor + atelectasis both present | supported (observation) |
| 3686_8353801520174 | B / F | metastatic leiomyoma → bronchiectasis | neither | unknown; the item is flagged `input_missing_context` |
| 3834_8353801523222 | C / A | diffuse GGO + reticulation → reticulation + focal honeycombing | facts: honeycombing present | supported (observation) |

### B-only harms (3)

| question | std / B | what B changed | source | grade |
|---|---|---|---|---|
| 18202_8143559000122 | A / C | wedge-shaped pleural opacity → "focal peripheral hyperlucency" | facts contain both clauses; B chose the hyperlucency one | supported (observation, clause selection) |
| 4118_8353801523564 | B / E | two-sided bullae → "left bulla + pneumothorax" | facts: pneumothorax present | supported (observation) |
| 5533_8353801540251 | B / A | (options did not parse from the metadata text) | tool path differs at the first call | unknown |

### Corrections (11)

| question | A→std | correcting arm(s) | decisive evidence in that arm's context | grade |
|---|---|---|---|---|
| 15189_8353800545058 | E→A | B, C | standard words absent from both; C dropped a grounding call | unknown (no visible support either way) |
| 3436_8353801521068 | D→B | B, C | difference is "7th vs 8th intercostal"; no ordinal in facts | unknown (fine-grained) |
| 5369_8353801533158 | F→A | B, C | C facts contain paracardiac/Morgagni/hernia; B only "large" | supported (C observation) |
| 548_8353802023456 | C→D | B, C | C facts contain "presence"; both arms opened with image_visualizer instead of the classifier | supported partial |
| 7738_8353800850751 | B→C | B, C | facts contain bilateral/consolidations; blocks contain ground/glass | supported (observation + block) |
| 11858_8353800664572 | E→B | B only | standard words absent; B added one grounding call | unknown |
| 13154_8353800587826 | F→C | B only | B facts have margins/right; C block has smooth/margins/lateral/posterior | supported (observation + block) |
| 3359_8353801515597 | D→B | B only | facts contain anterior/mediastinal/mass | supported (observation) |
| 11804_8353800651404 | F→D | C only | C block contains "right"; facts do not | weak (block only) |
| 18780_8143559008557 | C→A | C only | C block has "presence"; C dropped a grounding call | unknown |
| 3546_8353801521080 | B→A | C only | facts contain rounded/opacity/mass; block repeats them | supported (observation) |

## What the 28 add up to

| where the decisive attribute came from | harms (17) | corrections (11) |
|---|---:|---:|
| the arm's own tool observations | 8 | 3 |
| the injected block (vocabulary or checklist) | 1 | 1 |
| both observation and block | 1 | 3 |
| neither (asserted without support) | 5 | 4 |
| completion failure / unparsed options | 2 | 0 |

Two things follow, and both cut against the way V7 was set up:

1. **The largest single source of change is the arm's own tool observations** (8/17 harms,
   3/11 corrections, plus the mixed cases where both are involved). The injected block is
   the sole source in only 1 harm and 1 correction. Memory's own contribution is small
   next to what the tools said — consistent with the full 60-question run, where post-hoc
   blocks moved almost nothing and the branch that changed answers most (P1) had no memory.
2. **"Neither" is common on both sides: 5 harms and 4 corrections.** An attribute can be
   absent from everything the model was shown and still be right. That is the same
   asymmetry that killed the keyword-traceability gate below, and it is why a rule of the
   form "only accept a change whose attribute is in the context" cannot be the gate.

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
4. All 28 cases are graded above. The full-run result (`reports/v7-recovery-round2-2026-10-30.md`)
   points the same way from a different direction: post-hoc memory blocks produced 3 candidate
   changes in 60 questions, the generic no-memory re-check produced 16 and was net −10.

## Caveats

* Keyword absence is a proxy. A phrase can be supported by a differently-worded
  observation; the tool facts are summaries, not the raw model context. That weakness cuts
  both ways and is part of why the rule failed the control.
* These 28 cases are selected on outcome (they are the ones where the arms disagree), so
  the source shares describe *the changes*, not all questions. The full-run comparison,
  where every question is counted, is the guard against that selection.
