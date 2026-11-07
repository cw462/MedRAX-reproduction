# R4.1源开发：过程与实际注入检查

第一份被固定卡库命中的独立源题devsource_10176_8353800802019用于过程检查，不按正确率选题。初次因开发source_images目录链接越过执行器数据根目录而退出1，检查确认started=0；改为同字节原图的开发目录硬链接后，两个开发臂完成且恢复进程退出0。未修改冻结推理代码/卡库/mask，也没有重发未知请求。

实际M-S41请求含r41_compare_16841，M-C41无卡。两臂各2次主模型、2次chest_xray_expert，4个工具结果全部正常。M-S41输出结构合法；M-C41把自由文本与JSON混在一起，保留missing_invalid_tool_plan，没有从自由文本抽取答案、没有补答。源开发原题引用Figure标签，但旧content函数只显示数字原图索引，未显式把源Figure标签映射进提示；因此本开发只证明实际卡片注入和健康接口通路，不证明时间绑定、临床正确性或输出格式成功。目标冻结清单没有命中配对比较卡；这一局限仍保留。

共享开发已知费用0.049004 CNY，按输入/输出4/12 CNY每百万估计，非账单。全部收到回复，无未知请求。开发结果不进入目标成绩。

[实际注入核验及限制](dev_verified.json) · [路径恢复记录](image_path_recovery.json) · [初次失败日志](initial_failure.txt) · [选题依据](selection.json) · [M-S41请求/回复](calls/M-S41/) · [M-C41请求/回复](calls/M-C41/) · [M-S41输出](predictions_M-S41.jsonl) · [M-C41输出](predictions_M-C41.jsonl) · [M-S41工具](tool_selections_M-S41.jsonl) · [M-C41工具](tool_selections_M-C41.jsonl) · [工具原始结果](tool_results/) · [用量](resources.json) · [原图](image_assets.json) · [冻结执行](r41_run.json) · [协议](protocol.json) · [白名单](publication_manifest.json)。
