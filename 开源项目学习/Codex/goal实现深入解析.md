# Codex：Goal 实现深入解析

**目标绑定当前会话，空闲时按条件注入继续消息，直到完成或停止。**

## Harness 关键组件

- **Tool**
  - `create_goal`：创建当前会话的目标。
  - `get_goal`：查询目标、状态和预算消耗。
  - `update_goal`：将目标标记为完成、阻塞或暂停。
- **Hook**
  - `on_turn_stop`：本轮结束时结算消耗、检查异常。
  - `on_thread_idle`：会话空闲时触发目标续跑检查。
- **State**
  - `ThreadGoal`：保存目标、所属会话、状态、预算及消耗，由 SQLite 持久化。
- **Scheduler**
  - `continue_if_idle`：检查目标是否仍 active、是否允许继续。
  - `start_turn_if_idle`：通过 core 检查后，启动同一会话的下一轮。
- **Prompt**
  - `continuation_steering_item`：组装下一轮的目标上下文输入。
  - `continuation.md`：规定继续工作、核验证据和完成前验收的要求。

- Tool
  - create_goal：
  - get_goal
  - update_goal

- Hook

三个 Goal tool 是独立工具；它们管理同一个会话目标，不是各自执行一份长任务。

## 工具与状态

- `create_goal({ objective, token_budget? })`：创建目标。
- `get_goal({})`：查询目标及消耗。
- `update_goal({ status })`：模型可标记 `complete`、`blocked`、`paused`。
- 用户通过 `/goal` 设置目标，也可以 `pause`、`resume`、`clear`。

`ThreadGoal` 保存目标正文、所属 thread、status、预算和消耗。
只有 `active` 才可能自动继续；`complete`、`paused`、`blocked`、`budget_limited`、`usage_limited` 都不自动继续。

## 执行主线

### 1. 设置并保存目标

`install_with_backend` 安装回调和工具；设置目标后保存为 `active`。
用户入口走 `GoalService::set_thread_goal`，模型入口走 `GoalToolExecutor::handle_create`。

### 2. 检查是否允许继续

`continue_if_idle` 读取目标状态，再申请 `start_turn_if_idle`。
目标须 active；core 还会检查是否已有工作、是否有用户输入排队等，避免抢占或并发启动。

### 3. 注入输入，执行下一轮

`continuation_steering_item` 将目标、预算和执行要求放入同一会话的 user 角色内部上下文。
历史沿用该会话上下文（可能已压缩）；agent 使用工具继续干活，不强制生成 TODO 或另起子 agent。

### 4. 本轮结束，再次触发检查

`on_turn_stop` 结算消耗、检查异常；会话空闲后 `on_thread_idle → continue_if_idle`。
符合条件就回到第 2 步。这里是事件驱动，不是后台 while 轮询。

### 5. 核验完成，更新状态

当前 agent 按 `continuation.md` 检查真实证据，没有固定独立 reviewer。
确认完成后调用 `update_goal({ status: "complete" })`，保存状态，发出 `ThreadGoalUpdated`，不再自动续跑。
状态更新代码不会独立重跑测试；程序控制续跑，模型负责实际验收。

## 与 Pi 的区别

Pi：tool 内部循环，生成清单 → worker 执行 → 独立 reviewer。
Codex：生命周期回调驱动同一会话续跑，模型核验后调用工具更新目标。

## 源码入口

2026-10-21 静态核验，未运行实验；固定 Commit：`e72da2b53805894878023d01949a25a082e0a5cb`，不代表桌面 App 全部行为。

- [extension.rs：回调与工具注册](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/ext/goal/src/extension.rs)
- [runtime.rs：续跑调度](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/ext/goal/src/runtime.rs#L425)
- [continuation.md：继续与验收提示词](https://github.com/openai/codex/blob/e72da2b53805894878023d01949a25a082e0a5cb/codex-rs/ext/goal/templates/goals/continuation.md)

## 两个自测问题

1. 本轮回复结束，为什么还会继续？
2. 谁判断完成，谁保存状态、触发下一轮？

## 我的笔记


Codex 官方描述的是“线程持久目标＋跨轮继续策略”；这个插件明确组织了“规划—执行—审查”的外层循环。Codex 官方说明

https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex

