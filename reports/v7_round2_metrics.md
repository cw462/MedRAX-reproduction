# V7 recovery: round 1 metrics

Questions in file: 60; scored: 59. Denominator is every planned question, failures count as not correct.

## Accuracy by variant

| variant | correct | wrong | missing | accuracy |
|---|---:|---:|---:|---:|
| P0 | 42 | 17 | 0 | 0.7119 |
| P1 | 28 | 26 | 5 | 0.5185 |
| PB | 39 | 20 | 0 | 0.661 |
| PC | 40 | 17 | 2 | 0.7018 |
| GB | 42 | 17 | 0 | 0.7119 |
| GC | 40 | 17 | 2 | 0.7018 |

## Paired against P0

| variant | corrected | harmed | net | kept correct | still wrong |
|---|---:|---:|---:|---:|---:|
| P1 | 2 | 12 | -10 | 26 | 14 |
| PB | 0 | 3 | -3 | 39 | 17 |
| PC | 0 | 0 | +0 | 40 | 17 |
| GB | 0 | 0 | +0 | 42 | 17 |
| GC | 0 | 0 | +0 | 40 | 17 |

## Gate effectiveness (GB on PB, GC on PC)

| gate | branch corrections | retained | retention | branch harms | prevented | prevention |
|---|---:|---:|---|---:|---:|---|
| GB | 0 | 0 | None | 3 | 3 | 1.0 |
| GC | 0 | 0 | None | 0 | 0 | None |

## How often a branch changed the letter

| branch | n | changed | rate | verified (>=1 tool call) | mentions the block |
|---|---:|---:|---|---:|---:|
| P1 | 54 | 16 | 0.296 | 52 (0.963) | 0 (0.0) |
| PB | 59 | 3 | 0.051 | 28 (0.475) | 48 (0.814) |
| PC | 57 | 0 | 0.0 | 18 (0.316) | 47 (0.825) |

'Mentions the block' is a keyword test on the branch's own reasoning; it is a
crude engagement check, not proof that the branch used the experience.

## By official question type (correct counts)

| type | n | P0 | P1 | PB | PC | GB | GC |
|---|---:|---:|---:|---:|---:|---:|---:|
| classification,characterization,diagnosis,reasoning | 12 | 9 | 6 | 9 | 8 | 9 | 8 |
| classification,comparison,diagnosis,reasoning | 12 | 8 | 5 | 8 | 7 | 8 | 7 |
| detection,classification,relationship,reasoning | 12 | 8 | 6 | 7 | 8 | 8 | 8 |
| detection,localization,characterization,reasoning | 11 | 7 | 3 | 6 | 7 | 7 | 7 |
| localization,comparison,relationship,reasoning | 12 | 10 | 8 | 9 | 10 | 10 | 10 |

Twelve-question subgroups: descriptive, not powered.

## P0 against the S2 A arm

Compared 59 questions: 46 same letter, 13 different (0.22).
The same model, prompt and tools on the same questions do not reproduce the
old arm's answers, so the 28 historical corrections/harms are not a baseline for
this run; every comparison here is against this run's own P0.

