# W-2026-003：严格 JSON 输出与后训练对照实验

- Status: ready
- Area: LLM / Structured Output / JSON Schema / SFT / LoRA / Eval
- Difficulty: D4 入门（以 D2 规模的可复现实验学习模型适配）
- Discovered From: `s05_todo_write` 的 Tool Input Schema 与 Runtime 校验讨论
- Owner: personal
- Priority: medium

## Assumptions

1. 本任务当前只进入 Work Pool，不立即下载模型、安装训练环境或启动训练。
2. 学习目标不是让模型权重承担“绝对严格”的结构保证，而是区分并测量 Prompt、后训练、约束解码和程序校验各自解决的问题。
3. 不选“古早模型”作为主线。优先选择当前仍受工具链支持、许可证清晰、规模足够小，并且同一家族同时提供 Base 与 Post-trained/Instruct 版本的开放权重模型。
4. 主实验优先从小型 Instruct 模型开始，通过 LoRA 做窄任务 SFT；同家族 Base 模型作为第二阶段对照，用来学习 instruction tuning，而不是一开始同时承担通用指令跟随和 JSON 输出两项学习任务。
5. 具体模型、精度、量化方式和训练参数在启动时根据 GPU、显存、操作系统和当前官方文档决定。候选可以包括 `Qwen/Qwen3-0.6B` 与同家族 Base 版本，但本 Work Pool 不把它锁定为最终选择。
6. “严格 JSON”至少拆成语法合法、Schema 合法和语义正确三个层次；任何一个层次都不能代替另外两个。

## Problem Statement

`s05_todo_write` 向模型提供 JSON Schema 风格的 Tool Input Schema，同时在 `_normalize_todos()` 中执行程序端校验。需要通过最小后训练实验回答：

- 模型只看 Prompt 和 Schema 时，原生输出遵循率是多少？
- LoRA/SFT 能否提高未约束生成时的 JSON 与 Schema 遵循率？
- 约束解码能否保证结构合法，它对任务语义和生成质量有什么影响？
- 即使 JSON 与 Schema 都合法，模型是否仍会生成错误或危险的业务参数？
- Base、Instruct、SFT Adapter 与约束解码的收益分别来自哪里？

## Stable Mental Model

```text
Prompt / Examples
    提高模型理解任务与格式的概率

Post-training（例如 SFT + LoRA）
    调整模型分布，提高原生遵循和任务能力

Constrained Decoding
    在生成阶段屏蔽不符合语法或 Schema 的 Token

Runtime Validation
    对最终对象做确定性结构与业务校验

Authorization / Business Rules
    决定即使参数合法，操作是否允许执行
```

后训练提高概率，约束解码限制生成空间，Runtime 校验负责拒绝非法结果；生产系统不能只选择其中一层。

## Work

### Track A：冻结任务与 Eval

建立一个与 `todo_write` 相近、但独立可运行的结构化输出任务。数据至少覆盖：

- 简单扁平 object；
- object 中的 array；
- array item object；
- required、enum、数值和字符串约束；
- 嵌套对象与可选字段；
- 输入信息不足时的拒绝或 `unknown` 表达；
- Schema 合法但语义错误的案例；
- 输出截断、额外解释文本、错误字段名和错误类型。

训练集、验证集和测试集必须按任务或 Schema 家族隔离，防止只记住固定字段顺序。测试集在训练前冻结。

确定性指标至少包括：

1. JSON parse rate；
2. JSON Schema validation rate；
3. required / enum / type 等约束的分项通过率；
4. 语义 exact match 或字段级准确率；
5. 正确拒绝率与 unsafe acceptance；
6. 输出截断率；
7. 延迟、输出 Token 和显存占用。

### Track B：建立四组可归因基线

在相同 Prompt、Schema、采样参数和冻结测试集上比较：

| 组别 | 模型权重 | 解码方式 | 回答的问题 |
| --- | --- | --- | --- |
| B1 | 原始小型 Instruct | 普通生成 | Prompt-only 原生遵循率是多少？ |
| B2 | 原始小型 Instruct | 约束解码 | 不改权重时，结构约束能解决多少问题？ |
| B3 | LoRA/SFT 后模型 | 普通生成 | 后训练是否提高原生遵循和语义正确率？ |
| B4 | LoRA/SFT 后模型 | 约束解码 | 训练与约束组合后，结构和语义分别怎样变化？ |

可选第二阶段再加入同家族 Base 模型：先测 Base 原生能力，再用 instruction-style prompt-completion 数据执行 SFT。不要把 Base 与 Instruct 的差异、训练数据差异和解码差异同时改变，否则无法归因。

### Track C：最小 SFT / LoRA 实验

使用维护者当前稳定版本的 Hugging Face TRL 与 PEFT：

- 数据采用 prompt-completion 或 conversational prompt-completion 格式；
- 对 Assistant / Completion Token 计算训练损失，避免把用户 Prompt 当成目标输出；
- 使用 LoRA 训练 Adapter，保留原始模型作为可重复基线；
- 训练样本给出正确的结构化完成；非法输出样本主要留作 Eval，除非后续明确进入偏好优化或带奖励训练；
- 记录随机种子、数据版本、模型与 Tokenizer 版本、Chat Template、超参数、Checkpoint 和环境信息；
- 每个实验只改变一个主要变量。

### Track D：约束解码与 Runtime 防线

选择一个当前仍维护、支持目标 JSON Schema 子集的约束解码实现，并记录：

- 支持和不支持哪些 JSON Schema 关键字；
- Schema 编译失败、无合法 Token、输出截断和拒绝如何表示；
- 约束解码对速度、显存和任务质量的影响；
- 结构合法但语义错误时，Runtime 如何 fail closed；
- 为什么 Tool Schema、JSON Schema、业务校验和授权不能合并成一层。

具体推理 Runtime 在任务启动时通过 Context7 和维护者文档选择，不在 Work Pool 阶段提前锁定。

## Why Not an Old Base Model First

“古早、最基本的小模型”会把多个变量混在一起：旧 Tokenizer、旧训练配方、弱指令跟随、当前库兼容问题和 JSON 能力不足。最终即使实验失败，也很难判断是后训练方法、数据质量、模型容量还是工具链年代造成的。

更好的学习顺序是：

1. 当前小型 Instruct 模型，建立能工作的 Prompt-only 基线；
2. 同模型执行 LoRA/SFT，学习窄任务后训练；
3. 加入约束解码，理解“提高概率”与“强制合法”的区别；
4. 再用同家族 Base 模型做 instruction tuning，对比 Post-training 如何让 Base 获得指令跟随能力。

这样仍能学习从 Base 到 Instruct 的原理，但不会在第一个实验里同时调试所有问题。

## Advanced Learning：高级 AI Agent 工程师需要学到什么程度

🔴 **已验证理解**：即使不以模型研究或后训练工程师为职业主线，高级 AI Agent 工程师也应该理解后训练的关键知识和完整操作流程，并至少亲手完成一次小模型 LoRA/SFT 闭环；这是模型适配、实验归因和跨团队协作能力的一部分。

但需要区分“应当掌握”与“必须反复做”：

| 能力 | 建议深度 | 原因 |
| --- | --- | --- |
| Pre-training、Post-training、Instruction Tuning、SFT 的关系 | 必须能解释 | 用来判断问题来自基础能力、指令遵循还是应用层 |
| PEFT 与 LoRA / QLoRA | 必须理解并完成一次实操 | 这是 Agent 团队进行窄任务模型适配的常见低成本入口 |
| FFT — Full-Parameter Fine-Tuning（全参数微调） | 理解原理、资源与风险；有条件做一次小模型对照 | 有助于理解 Adapter 的收益和边界，但不是高级 Agent 工程师的日常必修操作 |
| 数据构造、切分、防泄漏与版本化 | 必须实操 | 后训练结果首先受数据与评测设计约束 |
| Chat Template、Tokenizer、Loss Mask | 必须能检查 | 配置错误可能让训练看似正常、实际目标错误 |
| Eval、部署、回滚与监控 | 必须实操 | 训练 Loss 下降不等于 Agent 行为或业务结果改善 |

### Learning Objectives：完成后应该能做什么

完成本进阶任务后，应当能够：

- [ ] 用自己的语言解释 Pre-training、Post-training、Instruction Tuning、SFT、FFT、PEFT、LoRA 与 QLoRA 的关系；
- [ ] 为一个窄任务判断 Prompt、Few-shot、约束解码、LoRA/SFT 或 FFT 哪一种更值得先做，并说明证据；
- [ ] 从零准备可审计的数据集，完成清洗、去重、切分、防泄漏、Tokenize 抽查和 Loss Mask 检查；
- [ ] 在约 0.6B 的开放权重模型上完成一次 LoRA/SFT 训练、评测、保存、加载、部署与回滚；
- [ ] 阅读训练日志并区分欠拟合、过拟合、数据错误、模板错误、Tokenizer 问题和显存问题；
- [ ] 用冻结 Eval 和置信区间比较 Prompt-only、约束解码、LoRA 与可选 FFT，而不是依据几个 Demo 下结论；
- [ ] 计算并实测参数量、静态训练状态、峰值显存、吞吐、GPU-hours、Checkpoint 大小和推理开销；
- [ ] 解释为什么 JSON / Schema 指标提高后，Runtime Validation、业务校验和授权仍然不能删除；
- [ ] 输出可复现的 Experiment Card，并能够向 Agent、ML 与平台工程师说明是否值得上线该 Adapter。

这里的术语边界是：

- **FFT**：训练并更新模型的全部可训练参数，资源、存储和回滚成本通常更高；
- **PEFT — Parameter-Efficient Fine-Tuning（参数高效微调）**：只训练少量新增或选定参数的方法族；
- **LoRA — Low-Rank Adaptation（低秩适配）**：一种常见 PEFT 方法，用低秩 Adapter 学习任务增量；
- **QLoRA**：通常在量化底模上训练 LoRA Adapter，以进一步降低显存需求；量化同时引入新的精度、兼容性和部署变量。

### 必做进阶实操：一次完整 LoRA / SFT 闭环

1. 写出可证伪假设，例如“LoRA/SFT 会提高普通解码下的 Raw JSON Parse Rate，但不会替代 Runtime Validation”。
2. 冻结训练、验证和测试切分，先实现 JSON、Schema 与语义的确定性 Grader。
3. 固定模型、Tokenizer、Chat Template、Prompt、采样参数和随机种子，运行未训练基线。
4. 检查训练样本在 Tokenize 后的实际形式与 Loss Mask，确认只在预期的 Assistant / Completion Token 上计算损失。
5. 运行 LoRA/SFT，记录数据版本、超参数、训练日志、Checkpoint、环境和显存峰值。
6. 保存独立 Adapter，保留原始模型；在决定合并权重前先验证 Adapter 的加载、切换和回滚。
7. 用完全相同的冻结测试集复跑 B3/B4，比较结构、语义、拒绝、延迟和资源成本，而不只比较 Training Loss。
8. 对失败样本分类，判断问题属于数据、模板、Tokenizer、训练、解码、模型容量还是 Runtime。
9. 形成 Experiment Card，并演示模型版本、Adapter 版本、Eval Gate、部署和回滚流程。

截至 2026-08-29，TRL 的 prompt-completion 数据默认可只对 completion 计算 Loss；`assistant_only_loss` 依赖能标记 Assistant 生成区间的训练 Chat Template。PEFT 支持将 LoRA Adapter 与底模分开保存、加载和切换，也支持在验证后合并权重。启动实验时仍需按锁定版本重新核对这些行为。

### Reference Experiment v1：带数字的学习目标

以下数字是第一版**实验合同和预算起点**，不是宣称所有 0.6B 模型都能达到的基础结论。准确率、峰值显存和耗时必须由实际运行填写。

#### 任务与模型

| 项目 | v1 约定 |
| --- | --- |
| 目标能力 | 只生成一个可直接 `json.loads` 的 JSON 文本，并遵循给定 JSON Schema；暂不混入完整 Tool Calling 协议 |
| Phase 1 模型 | `Qwen/Qwen3-0.6B`，0.6B 参数的 Post-trained 模型 |
| Phase 2 对照 | `Qwen/Qwen3-0.6B-Base`，用于学习 Base 到指令遵循的差异 |
| 模型结构快照 | 28 层、hidden size 1024、0.6B 总参数；启动时锁定模型 revision |
| 输出模式 | Phase 1 固定 non-thinking；thinking/non-thinking 不得在组间同时变化 |
| 最大训练序列 | 先用 1024 Token；只有失败样本证明截断时才扩大 |
| 精度 | 支持时优先 BF16；否则根据实际 GPU 改为 FP16，并把改变写入 Experiment Card |
| 随机性 | Pilot 使用 1 个 Seed；正式结果使用 3 个 Seed，并报告均值与波动 |

#### 数据规模与切分

| 阶段 | Train | Validation | Frozen Test | Adversarial / Stress | 目的 |
| --- | ---: | ---: | ---: | ---: | --- |
| Pipeline smoke test | 200 | 50 | 100 | 30 | 验证数据、训练、保存、加载和 Grader 全链路 |
| Main experiment | 2,000 | 250 | 500 | 200 | 形成可比较的 B1-B4 与 LoRA/FFT 结果 |

主实验建议覆盖至少 8 个训练 Schema 家族，并把 2-4 个 Schema 家族只保留给 Frozen Test。每条样本平均总长度先控制在 256-512 Token；训练 3 Epoch 时，主实验大约处理 150-300 万训练 Token。实际 Token 数必须从 Tokenizer 后的数据统计，不用字符数代替。

为了回答“需要多少数据”，追加一条 Data Scaling Curve：在其他条件不变时分别使用 200、500、1,000、2,000 条训练样本。只有当曲线仍明显上升且失败分析显示缺少覆盖时，才扩展到 5,000 条以上；不要先假定“数据越多必然越好”。

训练数据至少按以下维度平衡并记录数量：

- 扁平与嵌套结构、array of objects、可选字段、`enum`、数字范围和字符串转义；
- 引号、反斜杠、换行、Tab、Unicode、JSON 字符串内部出现 `{}` 或 Markdown fence；
- 字段顺序变化、未见字段组合、长数组、深层对象和接近最大长度的样本；
- 信息不足时的拒绝/`unknown`，以及 Schema 合法但业务语义错误的反例；
- 不同 Prompt 表述，避免只记忆一个固定模板。

#### LoRA 参考配置

以下配置只作为第一个可复现起点；正式实验允许在 Validation Set 上做小规模搜索，但不能查看 Frozen Test：

| 配置项 | 起点 |
| --- | --- |
| Target modules | `q_proj`、`k_proj`、`v_proj`、`o_proj` |
| Rank / Alpha / Dropout | `r=16`、`alpha=32`、`dropout=0.05` |
| Trainable bias | `none` |
| Learning rate candidates | `1e-4`、`2e-4` |
| Epoch | 最多 3；按 Validation 的语义指标和过拟合情况 Early Stop |
| Effective batch | 16 sequences；Micro-batch 与 Gradient Accumulation 根据显存调整 |
| Loss | prompt-completion 默认只训练 Completion；实际 Loss Mask 必须抽样检查 |
| Optional ablation | `target_modules="all-linear"`，与 attention-only LoRA 比较容量和成本 |

根据 Qwen3-0.6B 当前结构估算，attention-only、`r=16` 的 LoRA 约训练 459 万参数，约占 0.6B 的 0.76%；`all-linear` 约训练 1,009 万参数，约占 1.68%。该数字由模型层数和矩阵形状计算，启动时必须用 `print_trainable_parameters()` 对锁定 revision 实测确认。

#### FFT 参考配置

| 配置项 | 起点 |
| --- | --- |
| Trainable parameters | 全部约 0.6B 参数 |
| Learning rate candidates | `5e-6`、`1e-5`、`2e-5` |
| Epoch | 最多 3；使用与 LoRA 相同的停止规则 |
| Effective batch / Sequence | 与 LoRA 保持相同的有效 Batch 和 1024 Token 上限 |
| Memory controls | Gradient Checkpointing；是否使用 8-bit Optimizer 必须作为独立变量记录 |
| Checkpoint | 保留 Base、最佳权重、Optimizer/Scheduler 状态和恢复说明；限制 Checkpoint 数量 |

LoRA 与 FFT 的最佳 Learning Rate 往往不同，因此“公平比较”不是强迫二者使用同一个 Learning Rate，而是给予相同的小规模调参预算，并保持数据、测试、Prompt、Token 预算和 Grader 一致。

#### 资源开销：可计算部分与实测部分

Hugging Face 的通用显存分析给出一个传统 Mixed Precision + AdamW 的近似：可训练参数需要约 `18 bytes / parameter`，此外还有 Activation、Temporary Tensor 和框架开销。按 0.6B 参数估算：

| 项目 | 近似计算 | v1 规划结论 |
| --- | --- | --- |
| BF16 模型权重 | `0.6B × 2 bytes ≈ 1.2 GB` | 只是权重，不是训练峰值 |
| FFT 静态训练状态 | `0.6B × 18 bytes ≈ 10.8 GB` | 尚未包含 Activation、临时峰值和 CUDA 开销 |
| FFT GPU 预算 | 由 10.8 GB 再加运行峰值 | 16 GB 属于紧预算；24 GB 是更稳妥的单卡起点，但仍需 50-step Probe 验证 |
| LoRA attention-only 静态增量 | `4.59M × 18 bytes ≈ 83 MB` | 再加约 1.2 GB 冻结 BF16 底模及 Activation/框架开销 |
| LoRA GPU 预算 | 主要由底模、Activation、Batch 和 Sequence 决定 | 先按 8-12 GB 规划；6-8 GB 只有在短序列、小 Micro-batch 和显存优化下尝试 |
| LoRA Adapter 文件 | BF16 理论权重约 `4.59M × 2 bytes ≈ 9 MB` | 实际文件还包含配置与格式开销；`all-linear` 理论约 20 MB |
| FFT 模型文件 | BF16 权重约 1.2 GB | 完整恢复 Checkpoint 加上 Optimizer 等状态后会大很多 |

这些是容量级估算，不是硬件承诺。训练开始前先运行 50 个 Step 的 Resource Probe，记录 `peak_vram_gb`、`tokens_per_second` 和 `seconds_per_step`，再计算：

```text
estimated_train_seconds = total_train_tokens / measured_tokens_per_second
estimated_gpu_hours = estimated_train_seconds / 3600
estimated_cloud_cost = estimated_gpu_hours × actual_gpu_hour_price
```

不能预填一个通用“LoRA 训练 X 小时、FFT 训练 Y 小时”：GPU、驱动、内核、Sequence、Batch、Checkpointing、量化和数据管线都可能显著改变结果。LoRA 的主要稳定优势是减少可训练参数、Optimizer 状态和 Adapter 存储；它不保证按同一比例减少 Forward/Backward 计算时间。

#### 质量指标与通过门槛

“测试集准确率”必须拆开，不能用一个 Accuracy 混合结构与语义：

| 指标 | v1 目标 / 判定方式 |
| --- | --- |
| Raw JSON Parse Rate | B3 目标至少 98%，且相对 B1 的 Parse Error 至少减少 50%；若 B1 已接近 100%，改看 Schema 和语义收益 |
| JSON Schema Validation Rate | B3 目标至少 95%；按 required、type、enum 等失败原因分项报告 |
| Constrained End-to-End Success | B2/B4 在“Schema 可编译且生成正常完成”的子集目标 100% 结构合法；同时按全量分母单列编译失败、截断和拒绝 |
| Semantic Field Accuracy | 目标至少 90% |
| Semantic Exact Match | 目标至少 85%，不得被 Parse/Schema 指标替代 |
| Unseen-Schema Generalization | 相对同难度 seen-schema 测试下降不超过 5 个百分点 |
| Insufficient-input Handling | 正确拒绝或 `unknown` Recall 目标至少 90% |
| Unsafe Acceptance | 高风险案例目标为 0；若出现一次即进入失败分析，不用平均分掩盖 |
| Stability | 正式结果运行 3 个 Seed，报告均值、逐次结果和 95% Bootstrap Confidence Interval |

这些数字是预先声明的**学习项目门槛**，不是对 Qwen3-0.6B、LoRA 或 FFT 的公开基准结论。最终结果表必须保留空值，运行后填写：

| Run | Raw Parse | Schema Valid | Semantic Exact | Unsafe Acceptance | Peak VRAM | Tokens/s | GPU-hours | Artifact Size |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| B1 Instruct + normal decode | TBD | TBD | TBD | TBD | TBD | TBD | TBD | N/A |
| B2 Instruct + constrained decode | TBD | TBD | TBD | TBD | TBD | TBD | TBD | N/A |
| B3 LoRA + normal decode | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| B4 LoRA + constrained decode | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| E1 FFT + normal decode（optional） | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| E2 FFT + constrained decode（optional） | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

不得预设 FFT 的准确率一定高于 LoRA。只有当 FFT 相对 LoRA 的提升超过预先设定的实际意义阈值（v1 可取 3 个百分点）、95% 置信区间排除零、跨 Seed 稳定，并且额外资源与回滚成本可接受时，才把它判定为本任务上的有效升级。

#### Graduation Deliverables：结业证据

- 数据卡：来源、许可证、生成方式、清洗、去重、切分、泄漏检查和各类样本分布；
- 训练配置：锁定模型 revision、Tokenizer、Chat Template、依赖、Seed、超参数和硬件；
- 资源报告：50-step Probe、峰值显存、吞吐、GPU-hours、磁盘和估算误差；
- 质量报告：逐层指标、置信区间、Data Scaling Curve、失败簇和代表性反例；
- 模型产物：LoRA Adapter、加载测试、可选 Merge 产物、版本关系和完整性校验；
- 上线证据：Eval Gate、Shadow/Canary 计划、监控指标、回滚演练和 Runtime Validation 保留说明；
- 决策记录：为什么选择 LoRA、为什么追加或不追加 FFT，以及什么新证据会改变决定。

### 选修拔高：0.6B 小模型 FFT 对照

如果硬件、时间与工具链允许，可以在 LoRA 闭环稳定后追加一次 FFT；目标不是追求最佳模型，而是形成对照实验能力。FFT 与 LoRA 应尽量保持相同的：

- 初始模型与精度策略；
- 训练数据、切分和样本顺序；
- 有效训练 Token、Epoch、学习率搜索预算和随机种子；
- Prompt、Chat Template、Tokenizer、解码参数与冻结 Eval；
- Grader、统计口径和失败分类。

至少比较：任务指标、训练显存与时间、Checkpoint 大小、推理部署方式、回滚复杂度、未见 Schema 的泛化，以及非目标能力回归。若无法控制这些变量，只能把结果视为探索记录，不能声称“FFT 优于 LoRA”或相反。

对于“高级 AI Agent 工程师”目标，推荐优先级是：

```text
完整 LoRA/SFT + Eval + 部署回滚
    > 只跑通一次 FFT 训练脚本

会判断何时不该微调
    > 为了履历机械地微调

Tool 契约、权限、状态、可靠性与可观测性
    > 单纯追求更低 Training Loss
```

FFT 是有价值的进阶选修；只有当目标进一步转向 Agent 平台的模型适配、私有模型交付或 Post-training Engineer 时，才应把 FFT、分布式训练、优化器状态、混合精度、Checkpoint 分片与训练故障恢复提升为主线能力。

## Source Set

截至 2026-08-29，启动时仍需重新核对版本：

- [Hugging Face TRL：SFT Trainer](https://huggingface.co/docs/trl/sft_trainer)
- [Hugging Face TRL：PEFT Integration](https://huggingface.co/docs/trl/peft_integration)
- [Hugging Face PEFT：LoRA](https://huggingface.co/docs/peft/package_reference/lora)
- [Hugging Face Transformers：GPU memory usage](https://huggingface.co/docs/transformers/model_memory_anatomy)
- [Qwen3-0.6B 模型卡](https://huggingface.co/Qwen/Qwen3-0.6B)
- [Qwen3-0.6B-Base 模型卡](https://huggingface.co/Qwen/Qwen3-0.6B-Base)
- [Generating Structured Outputs from Language Models / JSONSchemaBench](https://arxiv.org/abs/2501.10868)
- [JSONSchemaBench 官方仓库](https://github.com/guidance-ai/jsonschemabench)
- [When JSON Is Not Enough：Schema 合法与语义可靠性的区别](https://arxiv.org/abs/2607.18261)

当前 TRL 文档支持 prompt-completion 数据、completion-only loss、PEFT/LoRA Adapter 训练和 Tool Calling 数据格式；这些是候选实现能力，不代表启动时必须全部使用。

## Relationship to Existing Work

本任务是 [`W-2026-002`](./W-2026-002-study-agent-self-evolution-harnesses.md) 中 E4 Model Evolution 的一个更小、更可控的前置实验：

- W-2026-003 回答“如何证明一次窄任务后训练真的改变了结构化输出行为”；
- W-2026-002 再研究训练数据如何从 Agent 轨迹产生、如何经过 Eval Gate 晋级，以及模型与 Harness 如何共同演化。

本任务与 [`s05 TodoWrite 学习笔记`](../../s05_todo_write/LEARNING_NOTES.md) 的关系是：s05 负责理解 Tool Schema 和 Runtime 校验；本任务负责研究模型为什么更可能或被迫遵循该结构。

## Reason Deferred

当前主线仍在学习基础 Agent Harness。后训练实验需要额外的模型基础、数据切分、训练环境、GPU 资源、Eval 和推理 Runtime；现在直接开始会打断章节学习，也无法在未知硬件条件下可靠选择模型和精度。

## Start Trigger

满足以下条件后，由用户明确启动：

- 完成 `s05_todo_write` 的运行与伪代码验收；
- 能区分 JSON、JSON Schema、Tool Input Schema、Structured Output 和 Runtime Validation；
- 提供或检查本机 GPU 型号、显存、内存、磁盘和可接受训练时间；
- 明确实验使用本机、云 GPU 还是托管 Notebook；
- 冻结第一版 Eval Set，再准备训练集；
- 启动时创建 `specs/changes/C-YYYY-NNN-*.md`，并移除本 Work Pool 文件。

## Preferred Order

1. 补齐 Token、Causal LM、Base/Instruct、SFT、LoRA 和约束解码的最小理论。
2. 盘点硬件与许可证，选择当前小型开放权重模型及固定版本。
3. 设计 Schema 难度分层和冻结测试集，先实现确定性 Grader。
4. 运行 B1/B2，建立 Prompt-only 与约束解码基线。
5. 准备可审计的 prompt-completion 训练集并运行 LoRA/SFT。
6. 运行 B3/B4，用相同 Eval 比较训练前后。
7. 对失败样本分层：语法、Schema、语义、截断、拒绝和 Runtime。
8. 可选加入 Base 模型 instruction tuning 对照。
9. 输出实验报告，说明哪些收益来自模型、解码器或校验器。

## Expected Output

- 一份 Base、Instruct、SFT、LoRA 与约束解码术语说明；
- 一套版本化的训练、验证和冻结测试数据；
- 一个确定性 JSON / JSON Schema / 语义 Grader；
- B1–B4 四组可复现实验配置与结果；
- 一个 LoRA Adapter，而不是覆盖原始模型；
- 至少一例“Schema 合法但语义错误”的失败分析；
- 一份训练收益、约束收益、成本与局限的对照报告；
- 一份模型、Adapter、数据和运行环境的 Model Card / Experiment Card。

## Acceptance Criteria

- 能解释为什么 SFT 提高遵循概率，但不能单独提供严格保证；
- 能解释约束解码为什么可以保证其支持范围内的结构合法，但不能保证业务语义正确；
- 能用冻结测试集证明训练前后的差异，而不是展示几个成功 Demo；
- 能区分 Base 到 Instruct 的 instruction tuning 与 Instruct 到窄任务 Adapter 的继续 SFT；
- 能说明训练样本、Schema 和测试集如何防止泄漏；
- 能从相同模型上的 B1–B4 对照中归因主要收益；
- 能保留原始模型、Adapter、数据版本和回滚路径；
- 所有版本敏感结论带核对日期与一手来源。

## Non-goals

- 不从零预训练语言模型；
- 不追求让模型参数替代 JSON Schema、约束解码、Runtime 校验或授权；
- 不以单次成功输出或训练 Loss 下降作为完成证据；
- 不在第一个实验中直接进入 DPO、RFT/RL 或复杂 Agent 轨迹训练；
- 不为了“更古早、更基础”而选择当前训练库已难以稳定支持的模型；
- 不在用户明确启动任务前下载模型、安装依赖或占用 GPU。
