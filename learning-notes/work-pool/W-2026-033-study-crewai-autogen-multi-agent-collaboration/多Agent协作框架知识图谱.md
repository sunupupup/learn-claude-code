# 多 Agent 协作框架知识图谱

> 本图谱先提供常见技术链路与选学导航。它是学习地图，不代表其中机制已完成源码或运行验证。

## 1. 完整技术链路

```text
用户目标与完成标准
  → 判断单 Agent、确定性 Workflow 或多 Agent 是否合适
  → 设计协作结构与控制权（顺序、管理者分派、团队对话等）
  → 创建/选择 Agent、任务与工具
  → 传递任务输入、上下文、消息或共享状态
  → Agent 推理并按需调用模型/工具
  → 按流程、管理者判断或终止条件继续、交接或停止
  → 收集结果与执行证据
  → 汇总、校验是否达成用户标准，再向用户返回结果
  → 记录轨迹、成本、延迟和失败，评估协作是否值得
```

多 Agent 框架主要帮助开发者表达和运行中间的协作过程。Agent 之间“聊完了”不等于用户任务完成；最终验收仍需依据具体完成标准和可检查证据。

## 2. 问题与扩展方案

| 面对的问题 | 改变哪个环节、怎么改 | 对应概念/观察入口 | 深入入口 |
| --- | --- | --- | --- |
| 单 Agent 难同时处理多个专业子任务 | 把工作拆成可交接的任务并安排专门 Agent | Agent、Task、角色、输入/输出契约 | [名词清单](名词清单.md)；[CrewAI](开源项目多Agent协作框架设计/CrewAI.md) |
| 多个 Agent 应按固定依赖顺序完成工作 | 由流程调度每步及结果传递 | Sequential Process、Workflow、Flow | [CrewAI](开源项目多Agent协作框架设计/CrewAI.md) |
| 任务需要动态分派或由管理者复核 | 将选择/协调职责交给 Manager 或 Selector 类组件 | Hierarchical Process、Manager、Selector Group Chat | 两个[项目笔记](开源项目多Agent协作框架设计/子项目.md) |
| 多 Agent 需要交换消息或共享上下文 | 选择显式消息、对话历史、任务输出或共享状态作为边界 | Message、Conversation、State、Context | [AutoGen](开源项目多Agent协作框架设计/AutoGen.md) |
| 团队可能持续讨论或循环执行 | 明确轮转规则、选择器、最大轮次和终止条件 | Round-robin、Selector、Termination Condition | [AutoGen](开源项目多Agent协作框架设计/AutoGen.md) |
| 协作流程需要嵌入确定性业务步骤 | 将 Agent 团队嵌入事件/状态驱动流程 | Crew 与 Flow 组合、Workflow | [CrewAI](开源项目多Agent协作框架设计/CrewAI.md) |
| 结果看起来合理但没有证明任务完成 | 由调用方独立核对输出、工具副作用和成功标准 | Result Validation、Eval、Trace | 后续按固定任务补实验和证据 |
| 框架差异被名词掩盖 | 用相同任务追踪谁发起、谁决定下一步、数据如何流动 | 控制权/状态/消息/验收对照 | [项目专题](开源项目多Agent协作框架设计/子项目.md) |

## 3. 概念之间的关系

```text
Agent（执行/决策单元）
  ├─ 被分配 Task（工作描述与预期产物）
  ├─ 可调用 Tool（外部能力）
  └─ 通过消息、共享状态或显式输出协作

Workflow / Process（控制流）
  ├─ 决定步骤顺序、分支和停止
  └─ 可以编排一个 Agent，也可以包含多个 Agent

CrewAI：Agent + Task → Crew / Process；Flow 管理更明确的状态和业务路径
AutoGen：Core 提供更底层的 Agent/消息运行基础；AgentChat 提供常见对话式应用抽象
```

CrewAI 与 AutoGen 是不同项目的具体实现，不能从概念名称相似推断两者在消息、共享状态、调度、终止或持久化上语义相同。确定性 Workflow 与多 Agent 也不是简单的先后替代关系：一个多 Agent 团队可以位于 Workflow 某一步中。

## 4. 主线与选学扩展

### 必学主线

- 单 Agent、普通 Workflow、多 Agent 的适用边界。
- 两个框架各自最常见的协作模型和一条端到端执行链。
- 控制权、状态/消息、工具、停止条件、结果汇总与验收的横向对照。
- 协调成本、错误传播、可观测和动态版本/项目状态的证据限制。

### 选学扩展

- AutoGen Core 的事件驱动 Runtime、分布式部署与组件扩展。
- CrewAI 的更复杂 Flow、持久化与企业级运行方式。
- AutoGen 官方提及的 Microsoft Agent Framework 后续方向。
- 深层团队、跨进程 Durable Agent、权限隔离和大规模评测；这些与已有生产 Runtime/团队专题相连，不阻塞本章常见用法主线。

## 5. 子笔记、Demo 与资料索引

- [术语入口](名词清单.md)
- [开源项目专题大纲](开源项目多Agent协作框架设计/子项目.md)
- [CrewAI 项目笔记](开源项目多Agent协作框架设计/CrewAI.md)
- [AutoGen 项目笔记](开源项目多Agent协作框架设计/AutoGen.md)
- 目前没有 Demo 或实验；后续确有必要时再按模块建立，不预设空目录。
