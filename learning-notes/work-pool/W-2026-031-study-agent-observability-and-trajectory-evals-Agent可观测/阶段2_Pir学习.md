# 1. 沿一次用户请求找出主要执行层

整个链路：

用户发送消息
    ↓
BFF：产品后端入口
    ↓
Pir API：接收、整理本次执行请求
    ↓
Runtime：真正执行 Agent 循环
    ├─ 调模型
    ├─ 执行工具
    └─ 把工具结果交回模型，继续执行
    ↓
生成最终回复

Pir 每次调用模型，发送的并不只是用户最新一句话，而是一份组装后的 ModelRequest。
内容包括
1. system prompt: 身份职责、能力边界、工具简介、记忆规则、具体业务知识（模型选型、特点）；<active-skills> 属于动态上下文注入，具体进入 system 还是 messages 尚未核验
2. messages: 全量拉去所有messages数据 (没有做session cursor id的优化)
3. tools:  当前可用的 tools 列表


# 2. 三条数据流

工具执行
 ├─ 前端流：通知界面更新工具状态
 ├─ 历史存储：保存调用参数与结果，供后续对话使用
 └─ 观测：记录耗时、成功或错误


guance1bufen1
ObservationEmitter：统一生成、分发观测事件
    ├─ 输出到日志文件
    ├─ 生成运行指标
    └─ LangfuseTraceSink
           ↓ 转换格式、交给发送组件
        Langfuse 平台

最终是把观测数据转换成 OpenTelemetry 的 OTLP 协议格式


OpenTelemetry（简称 OTel）是一套通用的可观测标准与工具体系；OTLP（OpenTelemetry Protocol）是它传输观测数据的协议。

```yaml
POST 接收地址
Content-Type: application/x-protobuf

body：按 OTLP 结构编码后的 Protobuf 二进制数据
```

OTLP/HTTP 规定了两种编码：
- 二进制 Protobuf：application/x-protobuf
- JSON：application/json
**Pir 选择了前一种。**但接收平台不一定两种都支持，所以实际用哪种还要看 Langfuse 接口支持什么，不能只改 Content-Type。

Protobuf 的好处：
- 通常比 JSON 体积小，节省带宽。
- 编解码通常更高效。
- 有明确的字段类型和结构定义。

Protobuf 将很多固定的值用某些二进制的数据来标识，大大减小数据量
Key：双方提前约定字段编号，传输时用编号代替完整字段名。
Value：数字、布尔值等用二进制编码，通常也能省空间；字符串内容本身通常不会因此缩小。


# 3. 采集数据

哪些时机进行了数据的采集

| 采集时机 | Hook 表达 | Pir 中的性质 |
|---|---|---|
| Session 激活前后 | `before_session_activate` / `after_session_activate` | 便于理解的叫法；实际是直接记录 `runtime.session.activate` |
| Turn 开始、结束 | `before_turn` / `after_turn` | 生命周期叫法；实际有 `runtime.turn` 观测 |
| 模型调用前 | `before_model_call` | 有对应的调用前 Hook 机制 |
| 模型上下文处理前 | `before_model_context` | **实际存在的 Hook**，压缩就在这里参与处理 |
| 工具执行前 | `before_tool_call` | **实际存在的 Hook** |
| Turn 提交后 | `after_turn_committed` | **实际存在的 Hook** |
| 模型、工具执行结束 | `after_model_call` / `after_tool_call` | 这里先作为时机描述；已确认结束处会记录结果，不能据此认定存在同名 Hook |

最关键的一些采集数据

| 字段 | 作用 | 怎么带 |
|---|---|---|
| `user_id` | 哪个用户 | 通常在整轮执行上绑定 |
| `session_id` | 属于哪个会话 | 通常在整轮执行上绑定 |
| `turn_id` | 属于哪一轮 Agent 执行 | 本轮记录关联它 |
| `trace_id` | 属于哪条观测链 | 链路内各 Span 共享 |
| **`span_id`** | 当前执行环节是谁 | 每个 Span 自己一个 |
| **`parent_span_id`** | 当前环节属于哪个父环节 | 子 Span 带，根 Span 没有父级 |
| 时间 | 什么时候发生、持续多久 | 事件用时间戳；Span 用开始和结束时间 |

针对不同的hook，就多一些其他数据就行了

# 4. Pir 自己的评测 pir-eval

它和 Workshop 的 run-dataset.ts 职责类似

YAML 测试案例 -> runner 执行 Agent -> 收集回答和工具调用轨迹 -> 按案例中的断言检查 -> 生成报告 → 与 baseline（历史基线）比较


pir自己定义了一套yaml
下面这个描述了一个 session 的两个 turn ，然后assertions校验整个过程

输入 + 怎么跑 + 怎么验收 + 报告

核心 **配置驱动的测评**

## session 级别的 eval
```yaml
vars:
  path: "files/eval/write-read.txt"
  content: "PIR_EVAL_WORKSPACE_ROUNDTRIP"

trajectory:
  - id: write_file
    type: turn
    required_tool_names: ["write_workspace_file"]
    user_message: "请把 {{content}} 写入工作区文件 {{path}}，不要写入其他内容。"
    capture:
      session_id: "/session_id"

  - id: read_file
    type: turn
    session_id: "{{write_file.session_id}}"
    required_tool_names: ["read_workspace_file"]
    user_message: "请读取工作区文件 {{path}}，然后只输出文件里的完整文本。"

assertions:
  - type: turn_status
    step: "*"
    status: done
  - type: tool_called
    step: write_file
    tool: "write_workspace_file"
  - type: tool_called
    step: read_file
    tool: "read_workspace_file"
  - type: output_contains
    step: read_file
    text: "{{content}}"
```

## 单turn级别

测试思路：Session 前置状态快照 + 单轮 Turn。Pir 已有 seed_store 预置历史与 fork 回放；现有 seed 案例使用手工构造的数据。

Langfuse 只有在主动采集完整前置状态后，才能提供所需快照；尚未确认 Pir 已完整采集。
导出目标 Turn 执行前的快照，只需要补齐 agent(params) 所需输入，再用测试代码恢复环境。

扩展方案（尚未确认 Pir 已完整实现）：可以在 before_turn 或类似位置捕捉“本轮执行前的状态”，保存成快照，并关联到 Langfuse 的 Trace。

按我们要做的回放，快照里可以放：
- 历史 messages、工具调用及结果。
- 已有压缩摘要和覆盖边界。
- 本轮用户输入。
- System Prompt、工具定义、模型参数及版本。
- 相关工作区、业务状态的快照或引用。

## 单span

这边就比较纯粹了，基本上是 harness 里面各个单元的单测了

很容易从 langfuse上抠出相关数据

比如
- 参数错误 tool 能否校验出来
- llm call是否直接调用相关tool

# 4补充. Langfuse 数据快照接口

扩展方案：测试数据不需要全放在本地，可以查询 Langfuse 已采集的数据，再自行整理成快照；这不是专门的快照下载接口，Pir 尚未接通这条自动下载回放链路。

```bash
GET https://jp.cloud.langfuse.com/api/public/v2/observations
    ?traceId=目标TraceID
    &fields=core,basic,io,metadata,model,prompt
```

读取 YAML 引用
→ 从 Langfuse 下载快照
→ 恢复测试上下文、配置 mock
→ 执行目标 Turn
→ 验收


# 5. 副作用隔离

设计要求：测试代码除了恢复 params，还要接管外部依赖和工具副作用。Pir 已有部分 fixture 能力，但尚未完整实现线上依赖自动 Mock 和工作区隔离。


修改文件	写入测试工作区
创建媒体任务、支付等	Mock 返回结果，或使用专门测试环境

Mock 的核心作用：替换真实外部调用，返回可控结果，避免真实写入、创建任务或扣费。

这样重跑时，环境固定，也更容易判断 Agent 改动带来的差异。

# 6. 项目现状与面试表达

项目目前主要覆盖关键流程的回归测试，包括工具行为断言、单轮和多轮轨迹测试，以及基于已有会话上下文的回放。已经有报告和 baseline 对比能力。

目前不足是案例规模和场景多样性还有限，对 v1、v2 的整体任务成功率、质量和成本提升，还没有建立大规模、系统性的对比评测。


## 实际案例: 工具失败后虚报成功，

问题：使用不存在的图片资源生成视频

解决办法：检查工具失败后是否声称视频已生成

## 实际案例：没调用工具，却声称已生成图片


没调用工具，却声称已生成图片”——Runtime 单元测试
“没有媒体工具时不能编 URL”——Eval YAML

# 7. 假URL case 和 解决办法 ！！！ 很重要

感觉有解决办法啊

在 agent 自己吐出 content 都时候
如果有 url ，那就检查下，前面是否有相关的tool call ？
这确实能在harness层面解决

```yaml
工具返回结果
→ 收集本次生成的真实产物 URL

Agent 输出 content
→ 检测图片／视频产物 URL
→ 与真实产物 URL 比对
→ 匹配才放行；不匹配就拦截并要求纠正
```

这就是针对“虚构媒体产物链接”这种 LLM 幻觉，用 Harness 做确定性校验。

模型输出链接 → 对照工具返回的真实产物 → 校验通过才展示。

这是一个很具体的产品改进方向；再补上“假 URL 必须被拦截、真 URL 正常放行”的回归案例，就能验证效果。目前是我们确定的方案，还没实际实现。

还有，不要用url，用id来代替