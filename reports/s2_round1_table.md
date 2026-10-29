# S2 paired comparison

Rounds analysed: [1]. Questions with at least one result: 60.
One round only, so the paired test below is McNemar's exact test on the discordant questions.

## Per arm-run

| run | n | correct | accuracy | Wilson 95% |
|---|---:|---:|---:|---|
| A_r1 | 60 | 39 | 0.650 | [0.5236, 0.7583] |
| B_r1 | 60 | 38 | 0.633 | [0.5068, 0.7438] |
| C_r1 | 60 | 33 | 0.550 | [0.4249, 0.6691] |

## Paired difference (per question mean over rounds, bootstrap over cases)

| comparison | cases | mean diff | 95% CI | B better / A better / tied | sign-test p |
|---|---:|---:|---|---|---:|
| A->B | 60 | -0.017 | [-0.15, 0.1167] | 8/9/43 | 1.0 |
| B->C | 59 | -0.068 | [-0.2034, 0.0678] | 6/10/43 | 0.454498 |
| A->C | 59 | -0.085 | [-0.2373, 0.0678] | 8/13/38 | 0.38331 |

## By official categories

| categories | n | A | B | C | B-A (95% CI) | C-B (95% CI) |
|---|---:|---:|---:|---:|---|---|
| classification,characterization,diagnosis,reasoning | 12 | 0.833 | 0.833 | 0.667 | 0.000 [-0.25, 0.25] | -0.167 [-0.4167, 0.0] |
| classification,comparison,diagnosis,reasoning | 12 | 0.500 | 0.667 | 0.545 | 0.167 [-0.1667, 0.5] | -0.091 [-0.2727, 0.0] |
| detection,classification,relationship,reasoning | 12 | 0.583 | 0.583 | 0.500 | 0.000 [-0.3333, 0.3333] | -0.083 [-0.4167, 0.25] |
| detection,localization,characterization,reasoning | 12 | 0.583 | 0.500 | 0.500 | -0.083 [-0.4167, 0.25] | 0.000 [-0.3333, 0.3333] |
| localization,comparison,relationship,reasoning | 12 | 0.750 | 0.583 | 0.583 | -0.167 [-0.4167, 0.0] | 0.000 [-0.3333, 0.3333] |

## Cost and effort per arm-run (from the terminal records)

| run | n | tool calls / q | model calls / q | charged CNY | CNY / q |
|---|---:|---:|---:|---:|---:|
| A_r1 | 60 | 5.0 | 5.67 | 7.6983 | 0.1283 |
| B_r1 | 60 | 4.83 | 4.9 | 7.1353 | 0.1189 |
| C_r1 | 60 | 5.32 | 5.27 | 8.0272 | 0.1338 |

## Per-question matrix

Type codes: T1=classification,characterization,diagnosis,reasoning, T2=classification,comparison,diagnosis,reasoning, T3=detection,classification,relationship,reasoning, T4=detection,localization,characterization,reasoning, T5=localization,comparison,relationship,reasoning

| question | type | A | B | C |
|---|---|---|---|---|
| 10569_8353800725393 | T4 | B | B | B |
| 11624_8353800763402 | T4 | B | B | B |
| 11801_8353800651620 | T4 | A | A | A |
| 11804_8353800651404 | T5 | F | A | D |
| 11858_8353800664572 | T2 | E | B | E |
| 12255_8353800651353 | T3 | D | D | D |
| 12721_8353800681884 | T2 | B | B | case_budget_exceeded |
| 1281_8353802281357 | T5 | B | B | B |
| 13154_8353800587826 | T3 | F | C | F |
| 13238_8353800603808 | T5 | B | B | A |
| 13698_8353800603937 | T2 | F | F | F |
| 13935_8353800618951 | T1 | B | B | B |
| 1461_8353802159822 | T1 | B | B | B |
| 14838_8353800529839 | T2 | B | B | B |
| 15189_8353800545058 | T1 | E | A | A |
| 15314_8353800558683 | T3 | C | B | B |
| 16037_8353800455673 | T3 | B | B | B |
| 16486_8353800471802 | T1 | C | C | C |
| 1653_8353802281156 | T3 | A | A | A |
| 16568_8353800483171 | T5 | B | A | A |
| 16663_8353800455763 | T5 | C | C | B |
| 1678_8353802279918 | T1 | C | C | A |
| 17132_8143559675802 | T1 | B | B | B |
| 17182_8143559676067 | T1 | C | C | C |
| 17362_8143559680136 | T1 | B | B | B |
| 17621_8143559684844 | T4 | D | A | A |
| 17947_8143559000377 | T3 | E | E | E |
| 18001_8143559000935 | T4 | C | C | C |
| 18202_8143559000122 | T3 | A | C | A |
| 18780_8143559008557 | T5 | C | C | A |
| 1975_8353802257622 | T5 | B | B | B |
| 2243_8353801511231 | T3 | C | C | C |
| 3241_8353801520855 | T3 | C | C | C |
| 3359_8353801515597 | T3 | D | B | D |
| 3397_8353801520783 | T4 | C | C | B |
| 3436_8353801521068 | T4 | D | B | B |
| 3546_8353801521080 | T3 | B | B | A |
| 3561_8353801511489 | T4 | B | B | F |
| 3686_8353801520174 | T1 | B | B | F |
| 3831_8353801520459 | T4 | A | A | E |
| 3834_8353801523222 | T3 | C | C | A |
| 4118_8353801523564 | T4 | B | E | B |
| 4491_8353801523228 | T1 | B | E | E |
| 4510_8353801532552 | T2 | A | A | A |
| 4734_8353801532720 | T1 | B | B | B |
| 528_8353802130481 | T2 | F | F | F |
| 5369_8353801533158 | T2 | F | A | A |
| 548_8353802023456 | T4 | C | D | D |
| 5533_8353801540251 | T4 | B | A | B |
| 562_8353802023537 | T1 | F | F | F |
| 722_8353802117601 | T5 | D | C | C |
| 7659_8353800871660 | T5 | C | C | C |
| 7726_8353800871273 | T5 | C | C | C |
| 7738_8353800850751 | T2 | B | C | C |
| 8129_8353800862240 | T2 | B | B | B |
| 8300_8353800861859 | T2 | D | B | B |
| 8379_8353800889338 | T5 | C | C | D |
| 8911_8353800871456 | T5 | F | F | F |
| 9308_8353800801854 | T2 | B | B | B |
| 9815_8353800828253 | T2 | C | C | C |

