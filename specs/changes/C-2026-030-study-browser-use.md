# C-2026-030：Browser Use 学习专题

- Status: active
- Origin: W-2026-037（本次直接启动，无待办卡需要迁移）
- Started: 2026-10-26
- 启动依据：用户要求按 Prompt 4 初始化 Browser Use、Computer Use 两个学习模块。
- 学习主记录：[Browser Use 学习入口](../../learning-notes/work-pool/W-2026-037-study-browser-use-浏览器操作/LEARNING_NOTES.md)

## Objective

理解浏览器 Agent 怎样观察网页、选择动作、控制浏览器并核对结果。区分 browser use 通用能力、browser-use 开源项目和底层浏览器协议。

## Work

1. 从搜索框案例建立观察—决策—执行—验证链路。
2. 学习 DOM、可访问性树、截图和元素定位的分工。
3. 理解 CDP 命令/事件、连接与会话；按需对照 Playwright 等工具层。
4. 后续固定 browser-use 项目 Commit、版本与许可证，再追踪状态提取和动作执行。
5. 按需在本地测试页面验证一次输入、点击与结果检查，并做页面变化的失败对照。

## Expected Output / Success Criteria

- 必学：能复述模型、Harness、浏览器接口的职责；说明结构与截图如何组合；解释动作成功与任务成功的区别。
- 源码阶段：有固定版本和一条完整调用链；实验阶段：有可重复输入、实际结果和至少一个失败或对照。
- 能指出会话、权限、过期元素或重试中的至少一个风险。
- 选学：复杂 iframe、反自动化、远程浏览器集群，不阻塞主线。
- 当前仅完成入口初始化，不代表已掌握或通过上述验收。

## Boundaries / Related

- 不克隆源码、安装依赖、启动付费调用或操作真实网站账号；实验另按学习进展确定。
- 项目源码阅读时再固定版本；本次官方链接仅用于地图导航，不算源码或运行验证。
- 学习过程按 [Prompt 4](../../PROMPT_4_WORK_POOL_LEARN.md)；与 [Computer Use](C-2026-031-study-computer-use.md) 对照但独立推进。
- 用户已有未提交改动保持原样；不提交、不 push、不切换 worktree。
