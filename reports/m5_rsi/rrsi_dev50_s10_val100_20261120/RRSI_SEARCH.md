# RRSI 搜索轮次

| 开发题后 | 晋升 | 父版本回放准确率 | 选中版本回放准确率 | 变化 | 组件 |
|---:|---|---:|---:|---:|---|
| 1 | False | 0.0% | 0.0% | 0.0% |  |
| 2 | False | 0.0% | 0.0% | 0.0% |  |
| 3 | False | 33.3% | 33.3% | 0.0% |  |
| 4 | False | 25.0% | 25.0% | 0.0% |  |
| 5 | True | 20.0% | 30.0% | 10.0% | client_tool |
| 6 | True | 33.3% | 41.7% | 8.3% | client_tool |
| 7 | False | 42.9% | 42.9% | 0.0% |  |
| 8 | False | 37.5% | 37.5% | 0.0% |  |
| 9 | False | 38.9% | 38.9% | 0.0% |  |
| 10 | False | 45.0% | 45.0% | 0.0% |  |
| 11 | False | 50.0% | 50.0% | 0.0% |  |

## 候选决策

### 第 1 轮

- A：admissible=False；accuracy_only: no strictly positive accuracy gain；S=0.0；delta_S=0.0
- B：admissible=False；accuracy_only: no strictly positive accuracy gain；S=0.0；delta_S=0.0

[提案、critic 与实际补丁](search/r0/)

### 第 2 轮

- A：admissible=False；accuracy_only: no strictly positive accuracy gain；S=0.0；delta_S=0.0
- B：admissible=False；accuracy_only: no strictly positive accuracy gain；S=0.0；delta_S=0.0

[提案、critic 与实际补丁](search/r1/)

### 第 3 轮

- A：admissible=False；accuracy_only: no strictly positive accuracy gain；S=0.3333333333333333；delta_S=0.0
- B：admissible=False；accuracy_only: no strictly positive accuracy gain；S=0.3333333333333333；delta_S=0.0

[提案、critic 与实际补丁](search/r2/)

### 第 4 轮

- A：admissible=False；accuracy_only: no strictly positive accuracy gain；S=0.25；delta_S=0.0
- B：admissible=False；no_proposal；S=None；delta_S=None

[提案、critic 与实际补丁](search/r3/)

### 第 5 轮

- A：admissible=True；accuracy_only: paired gains=[0.0, 0.2]；S=0.3；delta_S=0.09999999999999998
- B：admissible=False；critic_reject；S=None；delta_S=None

[提案、critic 与实际补丁](search/r4/)

### 第 6 轮

- A：admissible=True；accuracy_only: paired gains=[0.16666666666666666, 0.0]；S=0.4166666666666667；delta_S=0.08333333333333337
- B：admissible=False；critic_reject；S=None；delta_S=None

[提案、critic 与实际补丁](search/r5/)

### 第 7 轮

- A：admissible=False；accuracy_only: no strictly positive accuracy gain；S=0.42857142857142855；delta_S=0.0
- B：admissible=False；critic_reject；S=None；delta_S=None

[提案、critic 与实际补丁](search/r6/)

### 第 8 轮

- A：admissible=False；accuracy_only: no strictly positive accuracy gain；S=0.375；delta_S=0.0
- B：admissible=False；critic_reject；S=None；delta_S=None

[提案、critic 与实际补丁](search/r7/)

### 第 9 轮

- A：admissible=False；accuracy_only: no strictly positive accuracy gain; a repeat regressed；S=0.3333333333333333；delta_S=-0.05555555555555558
- B：admissible=False；critic_reject；S=None；delta_S=None

[提案、critic 与实际补丁](search/r8/)

### 第 10 轮

- A：admissible=False；critic_reject；S=None；delta_S=None
- B：admissible=False；critic_reject；S=None；delta_S=None

[提案、critic 与实际补丁](search/r9/)

### 第 11 轮

- A：admissible=False；accuracy_only: no strictly positive accuracy gain；S=0.5；delta_S=0.0
- B：admissible=False；critic_reject；S=None；delta_S=None

[提案、critic 与实际补丁](search/r10/)

