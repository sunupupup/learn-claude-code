# Nanobot：个人助理 Agent 的 Context 组装

## 为什么选它

Codex CLI 的源码涉及 Rust workspace、多个传输和模型兼容分支，第一轮容易陷入大仓库导航。Nanobot 用 Python 实现个人助理 Agent，官方架构文档把核心请求链路明确拆成 `AgentLoop → ContextBuilder → AgentRunner`，适合先沿一轮用户消息追下去。

本次只研究 Context、工具、Skills、Memory 和请求前缀；渠道、WebUI、部署和自动化先不展开。

## 源码快照

- 官方仓库：[HKUDS/nanobot](https://github.com/HKUDS/nanobot)
- 固定版本：`v0.3.5`
- Commit：`1bb712d3488915ca4ed9ccc1a93067ff722f5ab9`
- 本地浅克隆：`D:/code/third-party-labs/agent/source-reading/nanobot`
- 许可证：MIT（以该版本仓库的 `LICENSE` 为准）

## 核心调用链

```text
AgentLoop 接收一轮消息并确定 workspace/session
    → ContextBuilder 生成 system prompt、历史和当前消息
    → ToolRegistry 提供当前工具定义
    → AgentRunner 向 Provider 发请求、执行工具并处理结果
```

官方源码地图：[docs/architecture.md](https://github.com/HKUDS/nanobot/blob/v0.3.5/docs/architecture.md)

## 第一轮要看的文件

| 文件 | 先回答的问题 |
|---|---|
| `nanobot/agent/loop.py` | 一轮用户消息如何到达上下文构造和 AgentRunner？会话、workspace、runtime context 在哪里确定？ |
| `nanobot/agent/context.py` | system prompt 的各部分怎样拼装？历史和当前用户消息怎样成为 transcript？ |
| `nanobot/agent/runner.py` | 模型调用、工具调用和工具结果回填如何循环？ |
| `nanobot/agent/tools/registry.py` | Tool schema 如何生成、排序和缓存？注册/注销工具后怎样失效？ |
| `nanobot/agent/tools/base.py`、`schema.py` | 单个工具怎样提供模型可见定义，参数如何校验？ |
| `nanobot/agent/skills.py` | Skill 目录摘要、常驻 Skill、显式 `$skill` 正文分别何时读取？ |
| `nanobot/agent/memory.py` | Memory 文件如何读写、整理；哪些数据被 ContextBuilder 使用？ |
| `nanobot/providers/` | 已组装的 messages/tools 怎样转换为不同 Provider 的请求？ |

## 已确认的源码线索

- `ContextBuilder.build_system_prompt` 组合身份模板、`AGENTS.md` / `SOUL.md` / `USER.md`、工具使用约定、Memory、常驻 Skill、Skill 摘要和会话摘要。
- `ContextBuilder.build_transcript` 组织 system message、历史消息与当前用户消息；`build_current_message` 可把显式 Skill 正文及其他 runtime context 附加到当前消息。
- `ToolRegistry.get_definitions` 将内置工具和 MCP 工具分别按名称排序，并缓存 schema 列表，直到工具注册或注销使缓存失效。这是值得重点追的稳定性设计；它是否让某 Provider 的前缀缓存命中，还需继续沿请求适配器和运行指标验证。
- 上述结论来自固定版本源码初读，不代表每个配置下每轮请求内容完全一致。

## 下一步学习问题

1. system prompt 哪些部分每轮重建？文件内容变化后如何被发现？
2. Skill 的目录摘要和 Skill 正文各自何时进入请求？
3. Memory 文件是否每轮进入 system prompt？哪些模式会关闭或改变它？
4. 工具定义的稳定排序和缓存失效具体如何实现？MCP 工具新增时哪些 schema 会变化？
5. Provider 适配器最终发出的请求中，system prompt、tools 和 messages 分别放在哪里？
6. 源码能证明哪些内容稳定；要证明 Provider 实际命中，还需要观察什么指标？

## 术语速查

- **Harness（Agent 应用运行框架）**：负责接收输入、构造上下文、调模型、执行工具并管理会话的应用层。
- **ContextBuilder（上下文构造器）**：把指令、历史、当前输入和动态上下文组织成模型请求内容的模块。
- **Tool schema（工具参数定义）**：给模型看的工具名称、描述和参数格式；不等同于工具的执行代码或权限控制。
- **Prefix cache（前缀缓存）**：模型服务侧复用请求开头相同 Token 前缀的机制；本地排序或内容稳定只是应用侧设计，不能单独证明命中。
