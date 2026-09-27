# CrewAI 项目学习入口

## 项目简介

CrewAI 是一个用于构建和编排 Agent 应用的框架。Context7 于 2026-09-27 返回的官方维护资料将其基本对象概括为 Agent、Task、Crew 和 Flow：Crew 组织 Agent/Task 按流程执行；Flow 提供较明确的状态与事件驱动控制，并可在流程步骤中调用 Crew。此处仅作为资料预览，具体 API 和行为需按学习时的官方版本重新核验。

## 适合回答的学习问题

- Agent、Task、Crew 和 Process 如何组合成一次执行？
- 顺序执行时，前序任务结果怎样影响后序任务？
- 管理者协调与明确顺序的流程有什么控制权差异？
- Flow 怎样持有状态、控制分支并与 Crew 协作？
- 文档里的角色定义与运行时真正限制的权限有什么区别？

## 推荐观察重点

1. 从最小 `Crew.kickoff` 或官方 quickstart 找入口，不一开始就学习复杂应用。
2. 追踪输入如何绑定到 Task、Task 由谁调度、结果怎样传到下一个 Agent。
3. 分辨由框架确定的执行步骤和由 LLM 动态决定的行为。
4. 核对停止条件、异常传播、重试、工具执行与最终结果结构。
5. 只有需要回答某个问题时，再固定版本并读源码；记录 Commit、文件与行号。

## 官方资料入口

- [CrewAI 官方文档](https://docs.crewai.com/)
- [CrewAI GitHub 仓库](https://github.com/crewAIInc/crewAI)
- Context7 查询到的 [Crew 与顺序 Process 文档来源](https://github.com/crewaiinc/crewai/wiki/Creating-a-Crew-and-kick-it-off)

## 当前证据状态

- `documented`：Context7 于 2026-09-27 查询官方资料，初步核对 Agent/Task/Crew/Flow 术语和 Crew/Flow 的组合定位。
- `source-verified`：未进行。
- `observed-runtime`：未进行。
- 版本、Commit、许可证、源码入口和运行表现：正式学习时核验。
