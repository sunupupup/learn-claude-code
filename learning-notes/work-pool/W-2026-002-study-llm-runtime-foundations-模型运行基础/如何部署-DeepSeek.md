# 如何部署 DeepSeek 开源模型：概念版

> 状态：学习草稿，尚未实际部署、压测或上线。
>
> 目标：先建立“模型选择 → 硬件 → 模型资产 → 推理引擎 → 内部 API → 生产入口”的完整心智模型。本文不是可直接用于生产的最终操作手册。

## 一、先看完整链路

部署一个 DeepSeek 开源模型，大致需要：

```text
选择具体模型和精度
→ 根据权重、上下文和并发选择服务器/GPU
→ 准备 Linux、驱动、CUDA、磁盘和网络
→ 下载配置、Tokenizer、Chat Template 和模型权重
→ 使用 vLLM 等推理引擎加载模型
→ 推理引擎启动内部 HTTP API
→ 在前面增加 Gateway、HTTPS、认证和限流
→ 业务服务或 Agent 调用模型 API
```

关键校准：不是先随便购买服务器，再看它能运行什么模型。应先明确模型规模、精度、上下文长度和预计并发，再反推硬件。

## 二、第一步：选择“哪个 DeepSeek”

“DeepSeek”是一个模型系列，不是一个固定大小的模型。

以 DeepSeek-R1 系列为例，官方发布了完整的 671B MoE 模型，也发布了 1.5B、7B、8B、14B、32B、70B 等蒸馏模型。

| 类型 | 例子 | 适用场景 |
| --- | --- | --- |
| 小型蒸馏模型 | `DeepSeek-R1-Distill-Qwen-1.5B/7B` | 学习、本地验证、低成本场景 |
| 中型蒸馏模型 | `DeepSeek-R1-Distill-Qwen-14B/32B` | 更高质量，需要更多显存或多卡 |
| 完整模型 | `DeepSeek-R1`、DeepSeek-V3 系列 | 专业多 GPU 或多机环境 |

完整 DeepSeek-R1/V3 的总参数规模非常大。MoE（Mixture of Experts，混合专家）每个 Token 只激活部分参数，并不代表其余权重不需要存储和管理。

第一次学习部署可以把下面的模型作为示例：

```text
deepseek-ai/DeepSeek-R1-Distill-Qwen-7B
```

这只是教学选择。正式选型还要检查模型许可证、语言能力、上下文长度、工具调用能力和业务评测结果。

官方资料：[DeepSeek-R1 模型卡](https://huggingface.co/deepseek-ai/DeepSeek-R1)

## 三、第二步：根据模型选择服务器和 GPU

服务器需要准备：

- Linux 操作系统；
- CPU 和系统内存；
- 一张或多张支持的 GPU；
- 能容纳模型权重和镜像的磁盘；
- 匹配的 GPU 驱动、CUDA 和推理框架环境；
- 下载模型和提供服务所需的网络。

### 3.1 权重显存只是第一笔账

可以先用下面的近似公式理解权重大小：

```text
权重理论大小 ≈ 参数数量 × 每个参数占用字节
```

例如 7B 模型仅计算权重：

| 权重精度 | 理论大小 |
| --- | ---: |
| BF16 / FP16 | 约 14 GB |
| INT8 | 约 7 GB |
| INT4 | 约 3.5 GB |

这是帮助理解数量级的估算，不是采购结论。真实显存还要容纳：

- KV Cache；
- 中间计算张量；
- CUDA 和推理引擎开销；
- 并发请求；
- 更长上下文带来的缓存增长。

所以“权重能放进显存”只说明可能启动，不代表能够承载目标并发。

### 3.2 选硬件前至少回答

1. 使用哪个准确的模型 ID 和版本？
2. 使用 BF16、FP8、INT8 还是 INT4？
3. 最大上下文长度是多少？
4. 同时会有多少请求？
5. 每个请求大约生成多少 Token？
6. 接受多大的首 Token 延迟和完整响应时间？
7. 是否需要多副本和故障切换？

## 四、第三步：准备模型资产

一个 Hugging Face 格式的文本模型通常包含：

```text
config.json                         模型结构配置
tokenizer.json 等                   Tokenizer 配置与词表
chat_template / tokenizer_config    Chat 消息序列化规则
model-00001-of-000xx.safetensors    权重分片
model-00002-of-000xx.safetensors
model.safetensors.index.json        权重分片索引
generation_config.json              默认生成参数（若模型提供）
```

推理时这些资产必须互相兼容。LoRA 是可选的额外权重调整，不是启动基础模型的必需项。

模型可以由 vLLM 根据 Hugging Face 模型 ID 获取，也可以预先下载到服务器的固定目录。生产环境通常更适合提前下载、校验并固定版本，以减少启动时对外部网络的依赖。

## 五、第四步：用 vLLM 启动模型服务

vLLM 同时承担两类职责：

```text
推理引擎：加载模型、管理 GPU、调度请求、执行 Prefill/Decode
API Server：通过 HTTP 接收请求并返回生成结果
```

用于理解流程的启动形式：

```bash
vllm serve deepseek-ai/DeepSeek-R1-Distill-Qwen-7B \
  --host 127.0.0.1 \
  --port 8000 \
  --api-key "$VLLM_API_KEY"
```

这里使用 `127.0.0.1`，表示先只允许本机访问，适合第一次验证。

如果 Gateway 与 vLLM 位于不同主机，vLLM 可以监听内网地址或 `0.0.0.0`，但必须通过防火墙或安全组限制来源，不能因为端口可以访问就直接当作安全的公网服务。

vLLM 官方资料：[OpenAI-Compatible Server](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/)

## 六、第五步：验证内部 API

vLLM 默认可以提供 OpenAI 风格的接口。示例请求：

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $VLLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    "messages": [
      {
        "role": "user",
        "content": "请用一句话解释 Token"
      }
    ],
    "max_tokens": 100
  }'
```

一次请求在内部大致经过：

```text
HTTP 请求
→ Chat Template
→ Tokenizer 编码
→ vLLM 请求调度
→ 模型 Prefill
→ 逐 Token Decode
→ Tokenizer 解码
→ HTTP 或流式响应
```

此时只能证明内部推理链路可运行，不能证明已经达到生产要求。

## 七、第六步：怎样安全地暴露 API

生产环境不应把 vLLM 端口直接暴露给互联网。更完整的结构是：

```text
互联网客户端
      ↓ HTTPS
Load Balancer / API Gateway / Reverse Proxy
      ↓
认证、租户、配额、限流、请求大小和超时
      ↓
业务服务 / Agent Runtime
      ↓ 私有网络
vLLM API Server
      ↓
GPU + DeepSeek 模型资产
```

外层 Gateway 或业务服务至少负责：

- TLS / HTTPS；
- 用户和服务身份认证；
- 租户隔离；
- 请求频率与 Token 配额；
- 请求大小和最大上下文限制；
- 超时、取消和背压；
- 审计日志与敏感数据处理；
- 屏蔽不需要公开的内部端点。

vLLM 的 `--api-key` 只保护部分路径，不能作为完整公网安全边界。官方文档特别说明，某些端点不受该选项保护，因此生产环境需要反向代理、网络隔离和端点白名单。

## 八、生产环境还缺哪些部分

```text
vLLM 启动成功 ≠ 生产部署完成
```

生产部署还需要：

| 方面 | 要验证什么 |
| --- | --- |
| 容量 | 显存、上下文、并发和生成长度是否满足目标 |
| 性能 | TTFT、TPOT、吞吐量和排队时间 |
| 稳定性 | 启动失败、GPU OOM、请求取消和进程崩溃如何恢复 |
| 发布 | 模型版本、灰度、回滚和权重完整性校验 |
| 安全 | 认证、租户隔离、敏感 Prompt、日志脱敏和网络边界 |
| 观测 | 请求状态、输入/输出 Token、延迟、显存和错误分类 |
| 高可用 | 多副本、健康检查、负载均衡和故障切换 |
| 质量 | 业务 Eval、结构化输出和工具调用是否满足要求 |

## 九、各组件职责

| 组件 | 主要职责 |
| --- | --- |
| DeepSeek 模型资产 | 提供模型结构配置、Tokenizer 和训练权重 |
| GPU 服务器 | 提供计算、显存、磁盘和网络资源 |
| vLLM | 加载模型、执行推理、调度请求、管理缓存并提供模型 API |
| Gateway / Reverse Proxy | 提供安全的网络入口、TLS、认证、限流和端点控制 |
| 业务服务 / Agent Runtime | 组装业务上下文、调用工具、执行授权并保存业务状态 |
| 监控系统 | 收集性能、容量、错误和可用性指标 |

## 十、当前结论与待确认项

当前可以复述为：

> 部署 DeepSeek 时，先选择准确的模型和精度，再按模型大小、上下文和并发准备 GPU 服务器。模型配置、Tokenizer 和权重由 vLLM 加载；`vllm serve` 可以直接提供 OpenAI 兼容的内部 HTTP API。生产对外服务时，应让 vLLM 留在私有网络，并通过 Gateway 和业务服务补充 HTTPS、认证、限流、租户隔离、观测与故障恢复。

尚未决定：

- 具体部署哪个 DeepSeek 模型；
- 使用什么 GPU 和精度；
- 是学习实验、个人服务还是多租户生产服务；
- 目标上下文、并发、延迟和预算；
- 是否需要量化、多卡或 LoRA。

## 十一、下一小步

下一轮只讨论一个问题：

> 假设选择 `DeepSeek-R1-Distill-Qwen-7B`，为什么还不能只根据“7B × 2 字节 ≈ 14GB”就购买一张 16GB 显卡？

这个问题会引出模型权重、KV Cache、中间张量、上下文长度和并发之间的关系。

## 十二、证据边界

- 资料核验日期：2026-09-13。
- DeepSeek 模型规模与模型 ID来自官方模型卡。
- vLLM API 形式与安全边界来自当前官方文档，并通过 Context7 查询核对。
- 本文没有运行模型、下载权重、安装依赖或进行压测。
- 硬件数字仅用于建立数量级直觉，正式部署必须以目标模型、精度、框架版本和实际压测为准。
