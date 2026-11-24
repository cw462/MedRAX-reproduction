# 数据来源与许可

[逐题来源清单](case-sources.jsonl)按冻结开发验证集顺序列出 100 题，其中 70 题来自 Rad-ReStruct，30 题来自 SLAKE 英文验证集。每行给出实验题号、公开原题、完整选项、参考答案及作者源文件中从 0 开始的数组下标。选项为空对象表示该题按开放答案格式提供。Rad-ReStruct 的选项字母沿用实验时对原选项顺序的编码。实验从作者验证集选题，保留原始问答语义。发布字段省略患者及研究元数据，可识别信息替换次数为 0。

## Rad-ReStruct 文字标注

Chantal Pellegrini、Matthias Keicher、Ege Özsoy 和 Nassir Navab，*Rad-ReStruct: A Novel VQA Benchmark and Method for Structured Radiology Reporting*，MICCAI 2023。问题、选项和参考答案来自作者仓库的固定提交 b293158f0c5c1c5fa27dd615c28005eb54d7b1de。逐题条目提供原始 JSON 文件链接。作者仓库附有 MIT 许可，通知全文附在本页底部。[作者仓库](https://github.com/ChantalMP/Rad-ReStruct) · [固定提交](https://github.com/ChantalMP/Rad-ReStruct/tree/b293158f0c5c1c5fa27dd615c28005eb54d7b1de) · [MIT 许可文件](https://github.com/ChantalMP/Rad-ReStruct/blob/b293158f0c5c1c5fa27dd615c28005eb54d7b1de/LICENSE)

## Open-i 胸片

Rad-ReStruct 的原始胸片来自 Indiana University 医院网络，由美国国立卫生研究院美国国立医学图书馆提供。发布清单提供 Open-i 单张图像详情链接、官方 PNG 包和原文件名。NLM 将该集合的图像标为 CC BY-NC-ND 4.0，并请求研究人员将外部数据需求引向官方渠道。原图、裁剪和叠加图保留在私有实验归档。请按 NLM 要求注明来源并引用 Demner-Fushman 等人的 *Preparing a collection of radiology examinations for distribution and retrieval*。[Open-i 集合](https://openi.nlm.nih.gov/faq#collection) · [官方 PNG 包](https://openi-vip.nlm.nih.gov/imgs/collections/NLMCXR_png.tgz) · [NLM 复用说明](https://openi.nlm.nih.gov/contactus) · [NLM 数据共享说明](https://openi-vip.nlm.nih.gov/faq) · [许可](https://creativecommons.org/licenses/by-nc-nd/4.0/) · [原始研究](https://pubmed.ncbi.nlm.nih.gov/26133894/)

## SLAKE 英文文字标注和影像来源

Bo Liu、Li-Ming Zhan、Li Xu、Lin Ma、Yan Yang 和 Xiao-Ming Wu，*SLAKE: A Semantically-Labeled Knowledge-Enhanced Dataset for Medical Visual Question Answering*，ISBI 2021。本文使用 BoKelvin 作者账号发布的固定提交 a9083ce6c34ac3ffb17671a605962924d8a8f9e9。发布的数据卡标注 CC BY 4.0。逐题条目提供作者原始验证 JSON 和图像 ZIP 中的准确成员路径。论文说明原始影像采自独立来源。各影像的权利和隐私情况经逐项核验后方可进一步发布，当前提供作者包的访问链接。[作者项目](https://www.med-vqa.com/slake/) · [固定发布及许可](https://huggingface.co/datasets/BoKelvin/SLAKE/tree/a9083ce6c34ac3ffb17671a605962924d8a8f9e9) · [原始验证 JSON](https://huggingface.co/datasets/BoKelvin/SLAKE/resolve/a9083ce6c34ac3ffb17671a605962924d8a8f9e9/validation.json) · [作者影像包](https://huggingface.co/datasets/BoKelvin/SLAKE/resolve/a9083ce6c34ac3ffb17671a605962924d8a8f9e9/imgs.zip) · [论文](https://arxiv.org/abs/2102.09542) · [许可](https://creativecommons.org/licenses/by/4.0/)

## Rad-ReStruct MIT 通知

MIT License

Copyright (c) 2021 Sedigheh (Sarah) Eslami

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
