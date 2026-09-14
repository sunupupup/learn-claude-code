# W-2026-002：LLM Runtime 基础学习笔记

## 范围与状态

- 正式启动：2026-09-13；学习进行中，第 1 小节已有讨论和概念笔记，尚未完成实验验收。
- 范围、12 个小课题和完整验收以 [C-2026-002](../../../specs/changes/C-2026-002-study-llm-runtime-foundations.md) 为准。
- 模式：混合线；理论与独立复述先行，随后固定版本做本地输入观察和最小实验。

## 已有基础与前置知识

- [s01 笔记](../../../s01_agent_loop/LEARNING_NOTES.md)：模型调用、工具执行与结果回填。
- [s08 笔记](../../../s08_context_compact/LEARNING_NOTES.md)：上下文压缩和工具结果保留。
- [s10 笔记](../../../s10_system_prompt/LEARNING_NOTES.md)：Prompt 动态组装与应用层缓存。
- 已形成初步认识：Token 切分由具体 Tokenizer 的词表和规则决定；Tokenizer 必须与模型权重匹配。
- 已扩展记录：模型训练产物、Checkpoint、LoRA、推理程序和 DeepSeek 部署；这些内容目前以概念笔记为主，尚未逐项实验验收。
- 自注意力和量化已有预习笔记；自注意力理论尚未学完，本轮不计入掌握状态。

## 术语速查

- Tokenizer（分词器，模型输入层之前）：把文本按固定词表和规则编码成 Token ID，也负责解码；它与模型的词嵌入表和输出词表必须匹配。
- Checkpoint（检查点，模型产物）：通常包含某一训练时刻的模型权重；训练检查点还可能包含优化器、学习率调度器和训练步数等恢复信息。
- LoRA（Low-Rank Adaptation，参数高效微调）：保存相对基础模型的一组低秩增量参数，不能脱离兼容的基础模型独立工作。
- Inference Runtime（推理运行时）：加载模型并组织前向计算、生成循环、显存管理、调度和 API 服务。
- Self-Attention（自注意力，Transformer 模型内部）：同一输入序列产生 Q、K、V，并按相关性聚合上下文信息；当前仅预习，尚未学完。
- Quantization（量化，模型压缩/推理优化）：用更低精度近似表示权重或激活，以减少资源占用；质量和速度变化必须结合具体模型与硬件评测。

## 学习资料与阅读方式（2026-09-13 补充）

用户反馈：“这章内容，我还是不知道咋学习啊。。。有没有学习资料啊、博客、教程、官方文档 等”。此前直接进入猜测题，缺少资料输入和示例导读。调整为：指定一小段资料 → 用户阅读/教练导读 → 讨论一个例子 → 复述 → 确认后记结论 → 最小实验。

以 Hugging Face 官方课程与文档为主线，3Blue1Brown 作者原站的动画课辅助建立直觉。以下网页本轮已打开核验；通过 Context7 查询了 Transformers 的分词和聊天模板资料。网页核验不等于实验版本已固定。

| 顺序 | 资料 | 用途与阅读边界 |
| --- | --- | --- |
| 现在 | [Hugging Face 中文：Tokenizers](https://huggingface.co/learn/llm-course/zh-CN/chapter2/4) | 第一次只读开头、基于单词、基于字符、基于子词；到“还有更多！”前停止。约 15–25 分钟，仅为阅读预算。 |
| 下一节 | [Hugging Face 中文：BPE tokenization 算法](https://huggingface.co/learn/llm-course/zh-CN/chapter6/5) | BPE（Byte Pair Encoding，字节对编码）是分词算法；先读训练和切分的小例子，到“实现 BPE 算法”前停止。 |
| 全局直觉，可选 | [3Blue1Brown：Large Language Models explained briefly](https://www.3blue1brown.com/lessons/mini-llm/) | 英文视频与图文，先看一次输入如何接出后续文字；作为概览，不承担全部严格定义。 |
| 输入格式 | [Hugging Face：Chat templates](https://huggingface.co/docs/transformers/en/chat_templating) | 英文文档；看角色消息如何展开成带控制标记的序列，先跳过加载模型的代码。 |
| 模型内部 | [3Blue1Brown：Transformers, the tech behind LLMs](https://www.3blue1brown.com/lessons/gpt/) | 英文动画与图文；到对应课题再分段看 Token、向量、模型计算与输出概率。 |
| 生成 | [Hugging Face：Generation strategies](https://huggingface.co/docs/transformers/en/generation_strategies) | 先读 Greedy search 和 Sampling；后续再用小数字实验观察选择过程。 |
| 缓存 | [Hugging Face：How caching works](https://huggingface.co/docs/transformers/en/cache_explanation) | 理解自回归生成后再看 KV Cache，不能据此推断 Provider 的计费与跨请求缓存规则。 |

这是一组分阶段入口，不要求一次读完。Token 预算、延迟测量、Prefix Cache 和 Tool Calling 的专项资料在进入对应小节时补充。

### 今天的具体学习单

1. 打开第一篇中文教程，只读指定的三个切分小节，暂不安装或运行代码。
2. 遇到 NLP，先理解为“自然语言处理”；subword 是“子词，即词的一部分”。不要求先学模型训练。
3. 观察教程为什么依次介绍单词、字符、子词三种方法；把不懂的句子原样贴回讨论。
4. 读后尝试填写下表。不会的地方留空，由教练结合原文解释，不要求凭空猜 Token 数。

| 方式 | 怎样切分 | 解决了什么问题 | 仍有什么代价 |
| --- | --- | --- | --- |
| 按单词 | 待填写 | 待填写 | 待填写 |
| 按字符 | 待填写 | 待填写 | 待填写 |
| 按子词 | 待填写 | 待填写 | 待填写 |

## 第 1 小节：字符、词、字节与 Token

当前只判断：看到文本，是否已经足以确定其 Token 数？

固定观察输入（反引号内空格属于输入）：

| 输入 | 我的 Token 数判断 | 判断依据 |
| --- | --- | --- |
| `ABC` | 应该是 1 个 | 语义是一个整体 |
| ` ABC` | 应该是 1 个 | 语义是一个整体 |
| `你好` | 应该是 1 个 | 语义是一个整体 |
| `print("hi")` | 待用户填写 | 待用户填写 |

### 我的原始理解

用户原话：“应该都是 1 个 token，因为语义都是一个整体”。回答针对当轮提出的前三项；代码输入尚未回答。

教练反馈：🟡 数量是尚未运行验证的猜测；“语义整体决定 Token 数”的依据需要校准。具体切分依赖分词器的词表与规则。用户尚未确认掌握，先补资料阅读。

### 校准后的结论

- Token 不是按“语义是否完整”直接切分，而是具体 Tokenizer 根据其算法、词表和特殊规则得到的离散单位。
- 同一段文本换一个 Tokenizer，Token 数量和 Token ID 都可能变化；前导空格、中文、代码符号也可能改变切分。
- 训练 Tokenizer 需要语料统计或训练算法，但 Tokenizer 本身通常不是神经网络参数；模型训练和推理时会把它当作固定的输入/输出编码约定。
- Tokenizer 与神经网络权重需要严格匹配，否则 Token ID 会指向错误的 Embedding 行，输出 ID 也会被错误解码。

本轮相关概念笔记：

- [Token、Checkpoint、LoRA 与推理程序](./笔记.md)
- [如何部署 DeepSeek](./如何部署-DeepSeek.md)
- [Transformer 自注意力（预习未完成）](./transformer-self-attention.md)
- [模型量化基础（预习）](./模型量化（Quantization）基础.md)
- [为什么常用 Decoder-only：架构演变与推理阶段（概念导读，未验收）](./decoder-only-history.md)

### 验收

能用自己的话区分字符、字节与 Token，并说明确定具体 Token 数所需的条件。概念讨论已进行；尚缺固定 Tokenizer 版本后的真实编码观察，因此未完成验收。

## 来源、版本与证据

- 启动流程：仓库 PROMPT_4_WORK_POOL_LEARN.md 与 specs/README.md，2026-09-13 读取。
- 章节基础：上方链接的本地笔记；只读背景，不代表所有旧结论已重新验证。
- 真实 Tokenizer、Chat Template、Runtime：未选定、未运行；使用前固定版本与输入统计口径。
- 实验、指标、失败恢复、生产级行为：尚无证据。

## 掌握状态与下一步

当前已从 Tokenizer 扩展到模型文件、推理运行时和部署的概念地图。下一步先学习不依赖注意力公式的运行链路：Chat Template → Token ID → Embedding → Logits → 采样 → 新 Token；随后进入 Prefill、Decode、KV Cache 和显存构成。自注意力暂缓，等具备这些直觉后再回来学习。
