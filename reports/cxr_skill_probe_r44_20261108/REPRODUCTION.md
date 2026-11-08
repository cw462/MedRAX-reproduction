# R44复现说明

## 已保存结果的0付费复现

完整证据位于evidence/，源／开发题干、分离参考与20张原图位于../../data/slake_skill_probe_r44/。归档中的请求参数未被修改，图像沿用既有R4.1无损内容引用；evidence/IMAGE_MAP.json给出原图和精确data URI重建方式。所有54次请求均只含当前题干、单张原图和系统提示；没有source_examples、开发参考、旧目标答案或工具信息。

```text
python experiments/score_cxr_skill_probe_r44.py --source reports/cxr_skill_probe_r44_20261108/evidence --data data/slake_skill_probe_r44 --skill reports/cxr_skill_probe_r44_20261108/SKILL.txt --out local_assets/r44_offline_reproduction
```

输出目录必须不存在，程序保护现有记录。该命令只离线评分，不调用API。正常阅读已发布结果不需要重跑。

## 生成协议与环境

API-only，无GPU／工具／训练／权重下载。实际运行复用已部署R4.1支持代码与现有Python虚拟环境，未安装或重建包。PREPARATION.json记录输入相同检查；预运行在服务器以无--execute命令成功返回27pairs、54ceiling、0tools。独立代码／来源审阅另有完整记录。

通用生成入口为experiments/run_cxr_skill_probe_r44.py；同目录需有仓库现有run_cxr_vqa_toolsets.py等支持模块。CONFIG_EXAMPLE.json含实际无密钥模型、端点、超时和代理价表；将root改成自己的工作目录。原有真实config不发布，API密钥仅从stdin读取。传入--execute --api-key-stdin才会产生新请求；新实验应使用独立空目录并先取得明确范围，禁止拿同一目录重启／补答本次R44。

模型：qwen3.7-plus；temperature0.2、top_p1、thinking=false、max_tokens256；每题每臂1主／0工具。P1增加固定Skill，因此提示token与金额不与P0完全相等。模型家族别名不保证服务商内部快照固定。OpenAI客户端max_retries=0；未知已发送或技术故障停止全队列，send intent永久保留。计费是Token Plan Credits对应的本地CNY代理，4CNY/百万输入token、12CNY/百万输出token，不是账单或Credits换算。

## 来源再准备

源：官方BoKelvin/SLAKE固定版本a9083ce6c34ac3ffb17671a605962924d8a8f9e9的train.json、validation.json、imgs.zip，CC-BY-4.0。本次原图直接取zip对应source.jpg字节，没有增强或派生图。全部输入与选集已冻结在data/slake_skill_probe_r44，无需再下载212MB图像包。若独立重新核对选集，可将三个源文件放到新缓存，使用prepare_cxr_skill_probe_r44.py --cache CACHE --out NEW_DATA_DIR；它用现有目标公开inputs和原图排除已暴露图像，不能写已有目录。

12个源例仅给操作方制定规则；清单中额外临床常规检查是待检验的操作方假设，未声称由这些标签自动学习。开发答案仅在两臂全部结束且退出0后打开；提取不见参考，评分不猜reason或随机答案。8图／单样本限制保留，不能对患者独立、稳定收益或SOTA作声明。
