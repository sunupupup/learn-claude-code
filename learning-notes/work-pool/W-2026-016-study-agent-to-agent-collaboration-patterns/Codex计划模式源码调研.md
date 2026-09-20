# Codex Plan Mode 的实现与关键中间环节

[学习总览](我的笔记.md) · [概念前置](ReAct与规划执行的代码控制流辨析.md)

## 问题与结论

用户先提出“常见 Agent 默认是 ReAct，开启 Plan Mode 才切换规划执行”的理解，随后要求调研 Codex 的真实实现。

**公开源码中的 Plan Mode 是既有 Agent 循环之上的协作模式：模式状态 + 专用指令 + 用户澄清 + 计划输出解析 + 执行交接。公开终端客户端的普通执行分支切回 Default 并发送执行请求，没有把计划解析成步骤数组后逐项派发 Executor。**

产品流程上的“先计划后实施”成立，但不能直接等同于程序驱动步骤的 Planner-Executor 架构。

## 版本与证据边界

- 调研日期：2026-09-20；官方仓库 `https://github.com/openai/codex`。
- main 浅克隆固定 Commit：`5c5308fc9a9ee789049d646ef11e5400384b9c6f`，提交日期 2026-09-20；LICENSE 文件头为 Apache License 2.0。
- 外部源码：`C:/Users/Administrator/AppData/Local/Temp/codex-plan-mode-source-20260920`，没有放入学习仓库。临时目录可能被清理，下面保留固定 Commit 链接。
- 克隆最初遇到 Windows schannel 错误，改用 Git OpenSSL 后端取得对象；checkout 有少量超长路径快照文件失败。本笔记所列源码已实际读取，不把该工作树称为完整可运行环境。
- source-verified（静态源码）与 documented（官方文档）证据；未编译、未运行测试、未调用付费模型，无 observed-runtime 或 production-proven 结论。
- 范围是公开 Rust core、app-server 与 TUI（Terminal User Interface，终端界面）。未读取桌面端私有前端，不能断言桌面按钮、当前安装版本与公开快照完全一致。
- Context7 查询了 `/openai/codex`。其中“澄清工具只在 Plan 可用”的概括已被固定源码中的 Default 特性开关补充，以下以实际源码为准。

## 调用链与关键中间环节

```text
选择 Plan
 → 客户端更新 collaboration mode
 → app-server 补齐模式预设
 → core 注入有效的 developer 模式指令
 → 同一模型—工具反馈循环探索环境
 → 必要时 request_user_input → 用户回答 → 工具结果回填
 → 模型输出 proposed_plan 标记块
 → 解析器提取计划 → 客户端显示
 → 用户继续规划，或选择执行
 → 普通执行分支切回 Default，发送 Implement the plan.
 → 继续通用 Agent 循环完成实施和验证
```

| 环节 | 代码事实与作用 |
| --- | --- |
| 模式配置 | `ModeKind` 包含 Plan/Default，`Settings` 包含 model、reasoning_effort、developer_instructions；Plan 不等于一种独立模型 |
| 客户端切换 | `/plan` 进入 `apply_plan_slash_command()`；`set_collaboration_mask_from_user_action()` 保存模式并提交更新 |
| 服务端预设 | `normalize_collaboration_mode()` 在未提供 developer instructions 时补上所选模式的内置预设 |
| 上下文注入 | `CollaborationModeState::from_collaboration_mode()` 优先选择模型目录覆盖文本，否则使用模式 settings；以 developer 角色和 collaboration_mode 标签进入上下文，快照用于检测变化 |
| 规划过程 | 内置 `plan.md` 要求先探索环境，再明确用户意图，最后细化实现与验收；这是 Prompt 指导的阶段，不是三个硬编码顺序运行的 Agent |
| 澄清 | `RequestUserInputHandler` 校验模式/线程、规范化问题、等待 session 返回用户输入，然后序列化为工具输出；Plan 设置 `is_blocking = true` |
| 计划输出 | `AssistantTextStreamParser` 在 Plan 模式通过 `ProposedPlanParser` 提取 `<proposed_plan>` 中的 Markdown；app-server 对外提供 plan item 与流式 delta |
| 确认交接 | TUI `selection_view_params()` 的普通执行选项发出 `SubmitUserMessageWithMode`，携带 Default mask 和 `Implement the plan.`；不是解析步骤数组 |

### 三个容易误判的细节

1. **有 Prompt，但不只有 Prompt。** 配置状态、用户输入等待、计划解析及模式切换都是实在的程序逻辑。另一方面，三阶段规划本身主要由指令引导，core 的 `run_turn()` 仍沿用同一采样和工具反馈循环。
2. **Plan 的非修改指令，不等于自动改成只读沙箱。** `submit_collaboration_mode_settings_update()` 在更新模式时，对 permission profile、approval policy 等参数传入 None；`apply_patch` 使用独立的文件系统沙箱策略检查写入。不能把模式名当作硬权限保证，也不能据此断言所有客户端的写工具都可用；未做写入尝试。
3. **Plan Mode 不等于 update_plan。** 固定源码 `PlanHandler` 在 Plan 模式直接拒绝 `update_plan`；该工具用于 Todo/进度事件，不负责切模式或执行步骤。协议的 `turn/plan/updated` 进度列表，与 Plan Mode 的 Markdown `plan` item 也要分开。

### 版本和客户端可变点

- 模型目录可以覆盖内置模式文本，因此不能说所有线上模型收到逐字相同的 `plan.md`。
- `DefaultModeRequestUserInput` 特性开关允许 Default 使用澄清工具，不能把“能提问”作为 Plan 的唯一标志。
- TUI 只有本轮出现计划且没有排队跟进/冲突弹窗等情况才显示实施选择；不是每条 Plan 回复都会弹出。
- 公开 TUI 还有“清理上下文后执行”：携带完整计划到新上下文；以及“继续规划”。此处只确认公开 TUI，不冒充桌面端完整行为。
- 规划 Prompt 明确不让普通用户措辞自行结束模式；客户端真正切换后，新 developer 模式指令才表达退出 Plan。

## 固定版本源码入口

以下链接均固定在上述 Commit。行号为本次读取定位点。

| 查看什么 | 入口 |
| --- | --- |
| 模式定义 | [config_types.rs](https://github.com/openai/codex/blob/5c5308fc9a9ee789049d646ef11e5400384b9c6f/codex-rs/protocol/src/config_types.rs) |
| 模式更新与权限参数分离 | [settings.rs](https://github.com/openai/codex/blob/5c5308fc9a9ee789049d646ef11e5400384b9c6f/codex-rs/tui/src/chatwidget/settings.rs#L643) |
| 服务端补齐预设 | [turn_processor.rs](https://github.com/openai/codex/blob/5c5308fc9a9ee789049d646ef11e5400384b9c6f/codex-rs/app-server/src/request_processors/turn_processor.rs#L402) |
| 模式指令注入 | [collaboration_mode.rs](https://github.com/openai/codex/blob/5c5308fc9a9ee789049d646ef11e5400384b9c6f/codex-rs/core/src/context/world_state/collaboration_mode.rs#L24) |
| 内置规划 Prompt | [plan.md](https://github.com/openai/codex/blob/5c5308fc9a9ee789049d646ef11e5400384b9c6f/codex-rs/collaboration-mode-templates/templates/plan.md) |
| 用户输入等待 | [request_user_input.rs](https://github.com/openai/codex/blob/5c5308fc9a9ee789049d646ef11e5400384b9c6f/codex-rs/core/src/tools/handlers/request_user_input.rs#L74) |
| 通用执行循环 | [turn.rs](https://github.com/openai/codex/blob/5c5308fc9a9ee789049d646ef11e5400384b9c6f/codex-rs/core/src/session/turn.rs#L163) |
| 计划文本解析 | [assistant_text.rs](https://github.com/openai/codex/blob/5c5308fc9a9ee789049d646ef11e5400384b9c6f/codex-rs/utils/stream-parser/src/assistant_text.rs#L20) |
| 确认后切回 Default | [plan_implementation.rs](https://github.com/openai/codex/blob/5c5308fc9a9ee789049d646ef11e5400384b9c6f/codex-rs/tui/src/chatwidget/plan_implementation.rs#L29) |
| Todo 工具拒绝 Plan | [plan.rs](https://github.com/openai/codex/blob/5c5308fc9a9ee789049d646ef11e5400384b9c6f/codex-rs/core/src/tools/handlers/plan.rs#L87) |

官方协议参考：[Codex App Server](https://learn.chatgpt.com/docs/app-server)。已核对 turn/start 的模式指令默认值、plan item、用户输入事件；动态文档可能与固定源码快照有版本差异。

## 学习状态

🟢 静态调用链已核对；用户理解待复述，运行行为未实验。下一小步可以只读 `plan_implementation.rs` 普通执行分支，解释“产品先计划后实施”与“程序逐项派发步骤”的区别。本次窄范围调研不代表完成 W-016 的多 Agent 真实项目与 Eval 要求，也不启动 W-022 全部调研。
