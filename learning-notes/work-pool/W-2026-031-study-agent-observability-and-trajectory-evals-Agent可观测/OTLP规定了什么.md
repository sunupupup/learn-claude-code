# OTLP 规定了什么？

**一句话：就是上传观测数据的接口契约，规定请求体结构、编码方式、发送方式和接收结果。不是一个额外的观测平台。**

本文只讲上传 Trace 的部分。官方资料核对日期：2026-10-28。

## 1. “协议”没那么玄

平时写一个业务接口，也会约定：

```text
请求：POST 到某个地址
请求头：Content-Type 是什么
请求体：有哪些字段、字段类型是什么
响应：成功怎么表示，失败怎么处理
```

OTLP 做的也是这类约定，只是请求体承载的是执行记录，让多个发送方和接收方不用各写一套私有上传接口。

## 2. 具体约定了什么？

| 内容 | 约定 | 直观理解 |
|---|---|---|
| 报文结构 | 使用统一的 Protobuf 消息定义 | 请求体有固定结构，不是任意 JSON |
| 编码 | 支持二进制 Protobuf；OTLP/HTTP 也规定了对应 JSON 编码 | 同一份结构可以编码成二进制或可读 JSON |
| 传输 | OTLP/gRPC 或 OTLP/HTTP | 选择对应的传输方式；接收方不一定支持全部方式 |
| HTTP 请求 | 使用 POST；Trace 默认路径为 `/v1/traces` | 实际平台可以在前面加自己的路径前缀 |
| 类型标识 | 二进制使用 `application/x-protobuf`，JSON 使用 `application/json` | 接收方知道按什么编码解析 |
| 响应与错误 | 完全成功、部分接受、失败，以及哪些情况适合重试等规则 | 不能只发完就当全部数据已保存 |

出处：[OTLP 官方规范](https://opentelemetry.io/docs/specs/otlp/)、[Protobuf 定义仓库](https://github.com/open-telemetry/opentelemetry-proto)。

Protobuf 可以先理解为“结构定义＋序列化格式”；gRPC 可以先理解为一种远程接口调用方式。当前学习不必展开它们的实现。

## 3. 上传的结构长什么样？

Trace 请求体主要按下面的层次组织：

```text
resourceSpans
  ├─ resource：记录来自哪个服务，例如 service.name = pir-agent
  └─ scopeSpans
       ├─ scope：是哪套埋点组件产生的记录
       └─ spans：这一批执行环节
            ├─ traceId / spanId / parentSpanId
            ├─ name
            ├─ startTimeUnixNano / endTimeUnixNano
            ├─ attributes
            └─ status
```

这是结构示意，不是完整可提交请求。HTTP/JSON 编码中，属性值也有自己的类型包装；不能把普通业务 JSON 原样作为 `attributes` 提交。

OTLP/JSON 中还有明确的编码细节，例如 ID 用十六进制字符串表示、枚举用数字表示。真实实现应遵守定义，而不是只把字段名字改得相似。[官方编码说明](https://opentelemetry.io/docs/specs/otlp/#json-protobuf-encoding)

## 4. 对照上传 Langfuse

```text
Pir 自定义事件
    ↓ 映射字段，生成 Span 数据
按 OTLP 结构编码成二进制 Protobuf
    ↓ HTTP POST
Langfuse 的 Trace 接收接口
    ↓
平台解析、存储、展示
```

Langfuse 的具体 Trace 地址形式为：

```text
https://jp.cloud.langfuse.com/api/public/otel/v1/traces
```

认证、项目身份、摄入版本请求头，以及 Agent / Generation 的展示属性，属于接入 Langfuse 时需要遵守的额外约定；不是 OTLP 统一规定所有平台必须使用同一把 API Key 或相同 UI。[Langfuse 官方接入文档](https://langfuse.com/integrations/native/opentelemetry)

Pir 的发送代码明确设置了 `application/x-protobuf`，可从 [transport.rs](D:/code/temp/d5/workspace-release/pir/crates/harness/popipo/crates/pir-observability-langfuse/src/transport.rs:268) 查看。本段确认的是源码发送方式，没有重新执行线上上传验证。

## 5. “送之前转个格式”够不够？

**如果此前已经正确采集了全部必要信息，最后确实可以通过映射与编码来接入。**但转换器不能凭空补出没记录的数据：

- 没有正确的父子 ID，就无法准确恢复调用层次。
- 没有开始结束时间，就不能恢复实际耗时。
- 没记录错误，就不能靠 OTLP 推断发生了什么。
- 没有 Langfuse 可识别的附加属性，不一定能得到预期的 LLM 展示效果。

因此 Pir 的工作包括“埋点采集＋身份关联＋格式映射＋网络发送”，不只是把 JSON 字段重命名。

## 6. 它没有规定什么？

- 不规定你必须使用哪个 SDK，也不要求一定经过 Collector 中转。
- 不规定数据库怎样存，也不规定前端必须画 Tree、Timeline 或 Graph。
- 不规定业务里的 Session / Turn 与 Trace 必须怎样一一对应。
- 不判断 Agent 回答正确与否，不生成测试集或完成 Eval。
- 发送请求成功也不直接证明平台界面已经可查；还需看响应、接收处理与查询结果。

## 自测

1. 为什么“HTTP POST 一个 JSON”还不一定是 OTLP？
2. OTLP 请求合法，但 Langfuse 没有展示成模型调用，应该检查哪一层约定？

## 反思

- 核验边界：OTLP 能力范围与某个平台实际支持的编码、传输方式要分别确认。
- 学习重点：数据生成正确、请求发送成功、平台可见，是三个不同的检查点。
