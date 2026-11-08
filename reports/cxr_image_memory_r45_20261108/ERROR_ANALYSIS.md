# R45：纠正、误改、空答和输入异常

主结果465/618，旧M43为466/618；6纠正、7误改。这里的“正确”是固定benchmark参考和共同答案指标的一致性，不是逐张经放射科专家复核的临床判定。新结果不被反向用于调整这一轮规则。

## 答案口径与接口诊断

| 诊断 | M43 | M43-IM |
|---|---:|---:|
| 有显式答案 | 618 | 617 |
| 完整JSON及原M工程schema合规 | 618 | 617 |
| 无法匹配提供选项的字母／文本冲突 | 0 | 2 |
| 技术空答 | 0 | 1 |

`chexbench_rad_restruct_0218` 提供A=no、B=yes，模型答 `B. no`；`chexbench_rad_restruct_0231` 提供A=yes、B=no，模型答 `B. yes`。它们均有合法JSON，但显式答案自相矛盾，统一适配均留空选项、不猜字母或文本哪一个是本意。两题M43本来均错误，因此不属于7次误改。JSON格式恢复不能被单独计作医学能力提升。

技术空答 `chexbench_slake_0046` 的参考为A=yes；旧M43正确，新轮classifier崩溃后停在工具计划。原有健康expert文本不能替代最终答案，故保留null并计错。它占7误改中的1次；余下6次答案误改和6次答案纠正相抵，仅是事后分解，不能删掉故障题后把主结果改报为持平。

## 已归档请求图像异常

`chexbench_openi_0045` 的第2／3次新请求在原图位置保留了同一损坏PNG字节流；与规范原图同为209945字节，仅1个字节不同，Pillow报告IDAT校验／解码错误。第1次新请求引用有效原图，第3次还附有有效分割叠图。该题新旧均答A且均正确，未产生纠正／误改。

[损坏原始字节](evidence/invalid_request_image_bytes/400cb33af212e5d66ab9270d435ce3c5f535c93bb074c8e0008627be5229d98e.bin)、[第1次请求](evidence/calls/M43-IM/chexbench_openi_0045/1/request.json)、[第2次请求](evidence/calls/M43-IM/chexbench_openi_0045/2/request.json)、[第3次请求](evidence/calls/M43-IM/chexbench_openi_0045/3/request.json)、[实际终态](evidence/calls/M43-IM/chexbench_openi_0045/3/response.json)保留。已归档字节异常的来源、发生环节及供应商视觉解码行为未知；收到回复不能证明图像成功被理解，也不能从本地解码失败推出供应商必然拒绝。没有修图、重发或事后改分。这使端到端输入完整性的保证受到限制。

## 同图记忆的观测边界

130个后续同图题均有前序记忆。第2问74题53→52，第3问27题22→22，第4问16题15→15，第5问9题9→9，第6问4题4→4。首次／单例488题363→363来自原样复用，不能拿来证明记忆稳定。

Rad-Restruct +1和OpenI +2被CheX-SLAKE −4抵消；不能按这些已看成绩挑出有利子集再当未见提升。例：两条SLAKE关于coronal section／plane的正确yes被改成no，若据此设计适用性门槛，需要独立源／开发验证，不能直接覆盖本轮预测。OpenI0287的纠正使用跨子集同图前序Rad0157，是额外信息的实际例子，也不是独立病例泛化证据。全部前序题号见每题memory_context。

## 全部13条配对正确性变化

以下表由已完成逐题档案列出，不再请求模型。完整题干／选项／参考、原图和全部未变化题见[618题证据索引](CASE_INDEX.md)及[逐题结果](results/per_question.json)。

<!-- generated-change-table -->

| 题号 | M43 → M43-IM | 正确性变化 | 同图序号 | 实际记忆／请求 |
|---|---|---|---:|---|
| chexbench_rad_restruct_0161 | B. no → A. yes | 纠正 | 2 | [记忆](evidence/memory_context/chexbench_rad_restruct_0161.json)；[1](evidence/calls/M43-IM/chexbench_rad_restruct_0161/1/request.json)、[2](evidence/calls/M43-IM/chexbench_rad_restruct_0161/2/request.json)、[3](evidence/calls/M43-IM/chexbench_rad_restruct_0161/3/request.json) |
| chexbench_slake_0011 | B. yes → A. no | 答案误改 | 2 | [记忆](evidence/memory_context/chexbench_slake_0011.json)；[1](evidence/calls/M43-IM/chexbench_slake_0011/1/request.json) |
| chexbench_slake_0046 | A. yes → null | 技术空答误改 | 2 | [记忆](evidence/memory_context/chexbench_slake_0046.json)；[1](evidence/calls/M43-IM/chexbench_slake_0046/1/request.json)、[2](evidence/calls/M43-IM/chexbench_slake_0046/2/request.json) |
| chexbench_slake_0050 | B. no → A. yes | 纠正 | 4 | [记忆](evidence/memory_context/chexbench_slake_0050.json)；[1](evidence/calls/M43-IM/chexbench_slake_0050/1/request.json)、[2](evidence/calls/M43-IM/chexbench_slake_0050/2/request.json)、[3](evidence/calls/M43-IM/chexbench_slake_0050/3/request.json) |
| chexbench_slake_0054 | A. yes → B. no | 答案误改 | 2 | [记忆](evidence/memory_context/chexbench_slake_0054.json)；[1](evidence/calls/M43-IM/chexbench_slake_0054/1/request.json)、[2](evidence/calls/M43-IM/chexbench_slake_0054/2/request.json) |
| chexbench_slake_0061 | B. yes → A | 答案误改 | 2 | [记忆](evidence/memory_context/chexbench_slake_0061.json)；[1](evidence/calls/M43-IM/chexbench_slake_0061/1/request.json)、[2](evidence/calls/M43-IM/chexbench_slake_0061/2/request.json)、[3](evidence/calls/M43-IM/chexbench_slake_0061/3/request.json) |
| chexbench_slake_0071 | B. yes → A. no | 答案误改 | 4 | [记忆](evidence/memory_context/chexbench_slake_0071.json)；[1](evidence/calls/M43-IM/chexbench_slake_0071/1/request.json) |
| chexbench_openi_0287 | B. right indwelling catheter → A. left indwelling catheter | 纠正 | 2 | [记忆](evidence/memory_context/chexbench_openi_0287.json)；[1](evidence/calls/M43-IM/chexbench_openi_0287/1/request.json)、[2](evidence/calls/M43-IM/chexbench_openi_0287/2/request.json)、[3](evidence/calls/M43-IM/chexbench_openi_0287/3/request.json)、[4](evidence/calls/M43-IM/chexbench_openi_0287/4/request.json) |
| chexbench_openi_0296 | B. left lower lobe pulmonary atelectasis → A. left upper lobe pulmonary atelectasis | 答案误改 | 2 | [记忆](evidence/memory_context/chexbench_openi_0296.json)；[1](evidence/calls/M43-IM/chexbench_openi_0296/1/request.json)、[2](evidence/calls/M43-IM/chexbench_openi_0296/2/request.json)、[3](evidence/calls/M43-IM/chexbench_openi_0296/3/request.json) |
| chexbench_openi_0303 | B. left lower lobe pulmonary atelectasis → A. left upper lobe pulmonary atelectasis | 纠正 | 2 | [记忆](evidence/memory_context/chexbench_openi_0303.json)；[1](evidence/calls/M43-IM/chexbench_openi_0303/1/request.json)、[2](evidence/calls/M43-IM/chexbench_openi_0303/2/request.json)、[3](evidence/calls/M43-IM/chexbench_openi_0303/3/request.json) |
| chexbench_openi_0306 | A. left upper lobe pulmonary atelectasis → B. left lower lobe pulmonary atelectasis | 答案误改 | 2 | [记忆](evidence/memory_context/chexbench_openi_0306.json)；[1](evidence/calls/M43-IM/chexbench_openi_0306/1/request.json)、[2](evidence/calls/M43-IM/chexbench_openi_0306/2/request.json)、[3](evidence/calls/M43-IM/chexbench_openi_0306/3/request.json) |
| chexbench_openi_0310 | A. right upper lobe pulmonary atelectasis → B. right lower lobe pulmonary atelectasis | 纠正 | 2 | [记忆](evidence/memory_context/chexbench_openi_0310.json)；[1](evidence/calls/M43-IM/chexbench_openi_0310/1/request.json)、[2](evidence/calls/M43-IM/chexbench_openi_0310/2/request.json)、[3](evidence/calls/M43-IM/chexbench_openi_0310/3/request.json) |
| chexbench_openi_0320 | A. left upper lobe pulmonary atelectasis → B. left lower lobe pulmonary atelectasis | 纠正 | 2 | [记忆](evidence/memory_context/chexbench_openi_0320.json)；[1](evidence/calls/M43-IM/chexbench_openi_0320/1/request.json)、[2](evidence/calls/M43-IM/chexbench_openi_0320/2/request.json)、[3](evidence/calls/M43-IM/chexbench_openi_0320/3/request.json) |
