# V9 per-question outcomes

Derived results only; original questions, options, images and explicit reference answers are excluded. See [the index](README.md) for interpretation.

| Question ID | P0 | D final | DK final | DKB final | DKC final |
|---|---|---|---|---|---|
| 16486_8353800471802 | F / incorrect | F / incorrect | F / incorrect | F / incorrect | F / incorrect |
| 17132_8143559675802 | B / correct | B / correct | B / correct | B / correct | B / correct |
| 3686_8353801520174 | B / correct | B / correct | B / correct | B / correct | B / correct |
| 562_8353802023537 | F / correct | F / correct | F / correct | F / correct | F / correct |
| 11858_8353800664572 | B / correct | B / correct | B / correct | B / correct | B / correct |
| 4510_8353801532552 | A / correct | A / correct | A / correct | A / correct | A / correct |
| 5369_8353801533158 | A / correct | F / incorrect | A / correct | A / correct | A / correct |
| 8129_8353800862240 | B / correct | B / correct | B / correct | B / correct | B / correct |
| 13154_8353800587826 | C / correct | C / correct | C / correct | C / correct | C / correct |
| 1653_8353802281156 | A / incorrect | A / incorrect | A / incorrect | A / incorrect | A / incorrect |
| 17947_8143559000377 | E / incorrect | E / incorrect | E / incorrect | E / incorrect | E / incorrect |
| 3546_8353801521080 | B / incorrect | B / incorrect | B / incorrect | B / incorrect | B / incorrect |
| 11801_8353800651620 | B / correct | B / correct | B / correct | B / correct | B / correct |
| 18001_8143559000935 | C / correct | C / correct | C / correct | C / correct | C / correct |
| 3436_8353801521068 | B / correct | B / correct | B / correct | B / correct | C / incorrect |
| 4118_8353801523564 | B / correct | B / correct | B / correct | B / correct | B / correct |
| 11804_8353800651404 | A / incorrect | A / incorrect | A / incorrect | A / incorrect | A / incorrect |
| 1281_8353802281357 | B / correct | B / correct | B / correct | B / correct | B / correct |
| 13238_8353800603808 | D / incorrect | D / incorrect | D / incorrect | D / incorrect | D / incorrect |
| 16663_8353800455763 | C / correct | C / correct | C / correct | C / correct | C / correct |

## Legal changed candidates

| Question ID | Group | P0 | Candidate | Gate | Final | Final correct |
|---|---|---|---|---|---|---|
| 5369_8353801533158 | D | A | F | accept | F | False |
| 5369_8353801533158 | DK | A | F | retain | A | True |
| 3436_8353801521068 | DKC | B | C | accept | C | False |

## Candidate output errors

| Error code | Count |
|---|---:|
| `ValueError: inconsistent_candidate_uncertainty` | 8 |
| `ValueError: observation_without_reference` | 5 |
| `ValueError: invalid_atomic_attribute` | 4 |
| `ValueError: invalid_candidate_evidence_refs` | 1 |

All 18 errors fell back to P0. The separate 46 uncertainty fallbacks are not schema errors. Three gate requests completed without execution or parsing errors. All six initially incorrect cases remained incorrect.
