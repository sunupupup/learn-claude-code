# OpenTelemetry 规定了什么？

**一句话：把“怎么记录一次执行”统一起来，让不同程序、不同观测平台能理解同一套执行记录。**

本文只讲 Agent 的 Trace，不展开其他观测数据类型。官方资料核对日期：2026-10-28。

## 1. 为什么要有这个约定？

假设我们自己写观测代码：

```json
{"步骤":"调用模型","耗时毫秒":1200,"关联请求":"abc"}
```

自己的程序能看懂，但其他平台不知道“关联请求”是什么，也不知道怎样把这条记录挂到 Agent 执行下面。

OpenTelemetry（简称 OTel）提供统一的数据概念、编程接口和处理规则。SDK 是这些规范的实现；平台是数据的接收与展示方。这几件事不是同一个东西。

## 2. 它具体规定哪些事？

| 方面 | 具体规定什么 | 放到 Agent 中理解 |
|---|---|---|
| 执行数据模型 | Span 表示一个执行环节，有名称、时间、状态、属性等 | 一次模型调用可以是一条 Span |
| 关联身份 | Trace ID 表示整条链，Span ID 表示一个环节，父 Span 关联上下级 | 工具和模型记录能归到同一轮执行 |
| 编程接口 | 怎样创建 Span、添加属性、记录事件、设置状态和结束 Span | 埋点代码使用一致的操作方式 |
| 上下文传播 | 当前执行身份怎样在调用之间传递；跨进程可使用 W3C Trace Context 等传播格式 | 下游服务继续同一条 Trace |
| SDK 行为 | 采样、处理、批量导出以及资源限制等机制的规则 | 不必每个业务团队重新设计一套通用机制 |
| 语义约定 | 常见操作的属性名称、类型与含义；具体约定有各自的稳定性状态 | 不同实现尽量用一致字段表达模型、服务等信息 |

以上按理解层次归类，并非要求每个项目把全部功能都实现。出处：[OTel 概览](https://opentelemetry.io/docs/specs/otel/overview/)、[完整规范目录](https://opentelemetry.io/docs/specs/otel/)。

## 3. 对一条 Span，约定到什么程度？

下面是便于阅读的示意，**不是 OTLP 上传报文**：

```text
name: model.call
traceId: 整条执行链的身份
spanId: 本次模型调用的身份
parentSpanId: 所属 Agent 执行环节的身份
startTime / endTime: 开始、结束时间
status: Unset / Ok / Error
attributes: 模型名、业务上下文等键值信息
events: 这个环节内部发生的带时间戳事件
```

标准不只是约定字段名字，还约定含义与类型。例如 Trace ID 是 16 字节，Span ID 是 8 字节；不是随便把业务字符串填进去。状态 `Unset` 是默认状态，不能简单等同于失败。详见 [Tracing API](https://opentelemetry.io/docs/specs/otel/trace/api/)。

多个 Span 使用同一个 Trace ID，再通过父子关系组成链路。通常不用另外发送一个“Trace 大对象”才能让平台拼树。

## 4. 哪些仍然要我们自己决定？

- **在哪里埋点**：一轮 Agent、一次模型调用、一次工具执行是否分别记录。
- **记录什么业务内容**：输入输出保留原文还是摘要，哪些字段脱敏。
- **业务关系怎样映射**：Session、Turn 如何关联 Trace；OTel 不强制一个 Session 对应一条 Trace。
- **怎样判断质量**：答得对不对、任务是否完成，需要业务规则或评委，OTel 不替你评估。
- **平台展示语义**：Langfuse 怎样识别 Generation、Prompt 版本等，还涉及平台自己的属性映射约定。

因此，“有 OTel 标准”不代表自动拥有 Agent 观测，更不代表自动拥有评测。

## 5. 对照 Workshop 和 Pir

```text
Workshop：业务函数 → Langfuse SDK 包装 → 生成并导出 Span → Langfuse
Pir：关键阶段手动埋点 → 自定义观测事件 → 映射成 OTLP Span → Langfuse
```

Pir 当前读到的 Rust 链路中，`ObservationEmitter` 是自定义的统一记录与分发组件；`LangfuseTraceSink` 负责衔接映射与发送。**能发出 OTLP 数据，不等于内部全部接口都遵循 OTel SDK 规范。**

源码入口：

- [ObservationEmitter](D:/code/temp/d5/workspace-release/pir/crates/kernel/pir-observability/src/emitter.rs:19)
- [LangfuseTraceSink](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/crates/pir-observability-langfuse/src/sink.rs:11)

这些是源码核验结论，不代表线上导出已验证成功。

## 6. 与 OTLP 的关系

**OTel 是总体系，OTLP 是其中“数据怎样编码和传输”的协议部分。**二者不是两个平级竞争方案。

下一份：[OTLP规定了什么](./OTLP规定了什么.md)。

## 自测

1. 平台为什么知道两条 Span 属于同一次执行、谁是谁的父环节？
2. 自己按 OTLP 发数据，是否意味着必须使用官方 SDK？

## 反思

- 核验边界：这里解释标准与当前读取的 Pir 实现，不宣称 Pir 是完整 OTel SDK 实现。
- 学习重点：先分清数据模型、SDK 实现、传输协议、展示平台，再读实际字段映射。
