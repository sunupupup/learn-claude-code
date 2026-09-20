# Prefill、Decode 与 KV Cache 学习笔记

日期：2026-09-15。归属：[C-2026-002](../../../specs/changes/C-2026-002-study-llm-runtime-foundations.md) 第五项。

## 范围与节奏

约 50 分钟：时间线 10 分钟 → KV 复用 15 分钟 → 容量观察 15 分钟 → 复述验收 10 分钟。每次只推进一个小步骤，时间为预算而非已用时间。

仅使用 Python 标准库。脚本 [runtime_demo.py](./experiments/prefill-decode-kv-cache-basic/runtime_demo.py) 不下载模型、不访问服务、不测量 GPU。先判断再运行；不研究注意力公式、PagedAttention 内部、CUDA 或分布式推理。

## 我的原始理解

待用户回答，尚无本轮原话。

第一题：假设输入已经是四个 Token：P1 P2 P3 P4，输出为 O1 O2 O3。

```text
A：处理 P1 P2 P3 P4 → 选出 O1
B：处理新加入的 O1，利用历史 → 选出 O2
C：处理新加入的 O2，利用历史 → 选出 O3
```

我的阶段判断：A=____；B=____；C=____。理由：____。

## 校准后的结论

待讨论后填写。以下仅为后续导读边界，不代表用户已掌握或实验已验证。

- Prefill（预填充，推理运行时阶段）：处理已知输入，建立历史 K/V；最后位置的预测用于选择首个输出。Decode（逐步解码）：继续处理新 Token 并预测下一个。
- TTFT（Time To First Token，首 Token 延迟）：需声明测量起止点；客户端通常还包含传输、排队、输入准备、Prefill 和输出返回。其他条件相近且无前缀命中时，长 Prompt 通常增加 TTFT；不能断言任何情况下首 Token 必然最慢。
- 自回归生成：同一序列下一步依赖前一步选出的 Token。引擎能跨请求批处理，Prefill 也能并行处理已知输入位置；不是 GPU 一次只能处理一个 Token。
- KV Cache（Key/Value 缓存，模型推理状态）：保存各层已处理位置的 K/V，避免重新计算全部历史 K/V；后续仍需利用历史做注意力计算，不是免除全部历史相关成本。
- 简化容量公式：`2 × layers × tokens × kv_heads × head_dim × bytes_per_element × concurrent_sequences`，单位 bytes。2 表示 K、V 两份；tokens 为每序列缓存长度；其他变量分别为层数、KV 头数、每头维度、每元素字节数和并发序列数。假设等长且未共享的标准稠密缓存；不等长时按各序列长度求和。
- GQA（Grouped-Query Attention，分组查询注意力）让多个查询头共享 KV 头；MQA（Multi-Query Attention，多查询注意力）使用一组 KV 头。公式使用 KV 头数，而非直接使用查询头数。
- 模型权重、KV Cache、中间激活（计算中的临时张量）、框架/分配器开销是不同显存项目。权重量化不自动意味着 KV 使用相同精度。公式不含量化元数据、内存预留或分配碎片；其他架构/运行时可能有额外差异。
- Prefix Cache（前缀缓存）：跨请求复用公共前缀计算结果的额外机制，和单请求生成的 KV Cache 不完全相同。

## 实验观察

### 观察 1：时间线

状态：待用户判断后运行。虚拟毫秒是教学假设，不能支持真实延迟结论。

仓库根目录 PowerShell 命令（先不执行）：

```powershell
.\.venv\Scripts\python.exe .\learning-notes\work-pool\W-2026-002-study-llm-runtime-foundations-模型运行基础\experiments\prefill-decode-kv-cache-basic\runtime_demo.py timeline
```

预期观察：显示各阶段输入、输出和缓存位置数。实际结果：待执行。

### 观察 2：理论容量

状态：尚未开始。到本步骤再执行相同脚本的 `capacity` 模式。

预期观察：固定其余变量，分别改变长度、并发数和每元素字节数。实际数值和用户解释：待填写。

## 当前验收状态

- 🟢 已完成当前目录只读检查及最小文件准备；保留原有未提交内容。
- 🔴 时间线判断、脚本运行、容量观察、用户复述：待完成。
- 真实模型性能、GPU 显存与服务行为：不在本次验证范围。

## 来源与关联

- [此前 Decoder-only 概念导读](./decoder-only-history.md)：架构与执行阶段的边界。
- Python argparse 用法已通过 Context7 `/python/cpython` 核验；[标准库文档](https://docs.python.org/3/library/argparse.html)。本实验不使用 Transformers/vLLM API。
- 本次理论值是教学假设；无真实模型或运行时版本证据。
