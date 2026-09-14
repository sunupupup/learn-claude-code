# LLM 请求完整链路学习笔记

日期：2026-09-15。沿用 [C-2026-002](../../../specs/changes/C-2026-002-study-llm-runtime-foundations.md)，本页只记录最后一项串联练习，不替代整个 Work Pool 的掌握状态。

模式：整合与验收，约 20 分钟预算。排序 3 分钟 → Demo 观察 5 分钟 → 五分钟复述 → 校准 7 分钟。当前停在排序，后续均未开始。

## 我的五分钟复述（留空等待用户）

<!-- 等待用户原话；不预填复述或掌握结论。 -->

## 第 1 步：恢复顺序

目的：串联一次普通文本请求，先凭自己的理解排序。本步不运行命令、不改变环境。

操作：把下列字母排列成完整链路；允许用箭头表示循环。

- A：Softmax 与采样/选择，追加选中的 Token，判断停止条件。
- B：Tokenizer 把模板结果变成 Token ID。
- C：遇到 EOS，停止生成；Detokenizer 将输出 ID 还原为返回文字。
- D：Chat/API 层保存结构化 messages。
- E：Decode 处理刚选中的 Token，复用历史 KV，缓存增长并产生下一组 Logits。
- F：Chat Template 展开角色、内容和控制标记。
- G：Prefill 处理输入向量，建立输入 KV，得到首个输出 Token 的 Logits。
- H：Token Embedding 将 ID 映射为模型输入向量。

我的顺序：______。循环回到哪里：______。

预期结果：一条包含全部字母、标明生成循环的顺序。
实际结果：等待用户回答。
通过条件：能定位首次预测和后续预测，区分选择 Token 与计算该 Token 的 KV。
不符合预期：保留原答案，只校准第一个分歧，再让用户调整。
下一步：收到回答并完成校准后，才运行 Demo。

## 链路校准表

以下是待对照的教学参考，不代表个人理解已经验收。建议先完成排序再阅读。

```text
[Chat/API 层] 保存结构化 messages
  → [输入适配] Chat Template（聊天模板）
  → [输入适配] Tokenizer（分词器）→ Token ID（词表编号）
  → [模型输入层] Token Embedding（编号查表得到向量）
  → [推理 Runtime 调度模型] Prefill（预填充）建立输入 KV Cache
  → [模型输出头] 首 Token Logits（未归一化候选分数）
  → [推理 Runtime] Softmax → 采样/选择 → 追加 Token → 停止判断
       ├─ 继续 → 新 Token Embedding → Decode（逐步前向计算）
       │         → KV Cache 增长 → 下一组 Logits → 回到 Softmax/选择
       └─ EOS（序列结束标记）→ 停止
  → [输出适配] Detokenizer（ID 还原文字）→ [Chat/API] 返回文本

若输出包含 Tool Call（工具调用建议）：
[Agent Runtime] 解析 → Schema（结构约束）校验 → 权限判断
  → 执行工具 → 回填 Tool Result（工具结果）→ 下一次模型请求
```

| 阶段 | 输入 → 输出 | 谁负责 / 校准点 |
| --- | --- | --- |
| 输入适配 | messages → 模板序列 → IDs | Chat/API 保存消息；模板与分词器适配模型输入 |
| Embedding | IDs → 向量 | 模型输入层；位置机制属于后续模型计算，本 Mock 省略 |
| Prefill | 完整输入 → 输入 KV、末位置预测分数 | 推理 Runtime 调度模型；首 Token 不必先经过一次 Decode |
| 选择 | Logits → 概率 → Token | 推理 Runtime；Softmax 转概率，选择策略决定 Token |
| Decode | 新 Token + 历史 KV → 新 KV、下一组分数 | 推理 Runtime 调度模型；复用 KV 仍需利用历史做 Attention |
| 停止与返回 | EOS / 其他停止条件 → 输出文字 | Runtime 管停止，Detokenizer 管文字还原 |
| 工具分支 | 模型输出建议 → 校验与业务执行 | Agent Runtime；模型不会因输出一个名字就执行业务动作 |

## 实验观察

### 第 2 步：运行 Mock（尚未开始）

目的：用可观察日志对照排序。收到第 1 步回答并校准后再执行。

当前目录：`D:\code\temp\learn-claude-code`。PowerShell 执行命令：

```powershell
python .\learning-notes\work-pool\W-2026-002-study-llm-runtime-foundations\experiments\llm-request-pipeline-basic\pipeline_trace_demo.py
```

命令说明：只运行 [标准库 Mock Demo](./experiments/llm-request-pipeline-basic/pipeline_trace_demo.py)，无第三方依赖、网络调用或文件写入。

预期结果（代码设计，尚非实测）：输入 4 个位置；Prefill 缓存为 4；两次 Decode 后为 5、6；输出 ID 依次为 4、5、6，其中 6 是 EOS；返回“你好”。EOS 被选中后未再前向计算，所以缓存不含 EOS。

实际结果：待执行。
我的观察：______。
通过条件：日志中的首次预测、循环、缓存增长和停止位置与解释一致。
不符合预期：停在此步，贴出完整错误或分歧日志，不安装额外依赖。
下一步：脱离参考做五分钟复述，再逐项校准。

## 容易混淆的边界

- Decode 是推理阶段；Detokenizer 是 ID 到文字的输出适配，两个“解码”不是一回事。真实流式返回可以边生成边还原文字，这里为看清顺序在结束后统一还原。
- 追加到 Token 序列不等于该 Token 自身 KV 已计算；只有被前向处理后才有它的 KV。Prefill 已建立输入 KV，并非到 Decode 才出现缓存。
- 推理 Runtime 负责调度 Prefill、Decode、采样、缓存与停止；模型执行张量计算并产生 Logits。Agent Runtime 负责工具与业务控制，两者可以属于同一产品但职责不同。
- 本例模板、词表、二维向量和 Logits 全部人工设定；缓存仅为位置列表，无真实 K/V 张量、Attention、GPU 延迟或 Provider 缓存证据。
- 本例选择策略为 Greedy（取最大值），不是随机抽样。EOS 是一种停止条件；生产系统还需要处理长度上限、取消、超时和工具失败，本次不扩展实验。

## 最终验收状态

- 🟢 独立笔记与 Demo 已初始化；沿用已有 Change。
- 🔴 排序、Demo 实际运行、五分钟独立复述：待完成。
- 🔴 责任边界解释与缓存增长解释：待用户回答后验收。
- 未宣称用户掌握；本练习不表示 W-2026-002 全部目标已完成。

## 关联与依据

- 前置：[聊天模板](./聊天模板与特殊Token实验笔记.md)、[词嵌入](./词嵌入与模型文件学习笔记.md)。
- 本轮串联：[采样与 EOS](./Logits、Softmax、Temperature、Top-p与EOS学习笔记.md)、[Prefill、Decode 与 KV Cache](./Prefill、Decode%20与%20KV%20Cache%20学习笔记.md)。
- 后续工具边界沿用 Change 中的 Agent Loop，不自动启动其他 Work Pool。
- 标准库 `math.exp` 已通过 Context7 `/python/cpython` 核验：[CPython 文档源码](https://github.com/python/cpython/blob/main/Doc/library/math.rst)。Softmax 与固定 Logits 是教学实现，不是外部模型 API。

## 反思

1. 未确认之处：Demo 尚未运行，没有真实模型或 Provider 的验证证据；只据代码描述预期。
2. 学习补足：验收时重点解释“谁做决定、谁执行动作”和“选中 Token 与缓存增长的时间差”，用现有两篇前置笔记复习即可。
