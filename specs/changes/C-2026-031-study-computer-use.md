# C-2026-031：Computer Use 学习专题

- Status: active
- Origin: W-2026-038（本次直接启动，无待办卡需要迁移）
- Started: 2026-10-26
- 启动依据：用户要求按 Prompt 4 初始化 Browser Use、Computer Use 两个学习模块。
- 学习主记录：[Computer Use 学习入口](../../learning-notes/work-pool/W-2026-038-study-computer-use-桌面操作/LEARNING_NOTES.md)

## Objective

理解桌面 Agent 怎样获取画面或控件信息，将模型动作转成系统输入，并通过再次观察确认结果。Computer Use 是能力类别，不预设某个唯一产品。

## Work

1. 从桌面文本输入案例建立截图—决策—输入—再观察链路。
2. 理解截图、视觉定位、坐标转换和鼠标键盘执行器。
3. 学习无障碍树与 Windows UI Automation，比较纯视觉与结构辅助路线。
4. 后续固定一个官方演示实现的 Commit、版本与许可证，追踪工具调用到截图和系统输入；演示候选不是已选定或已运行的实现。
5. 按需在专用测试窗口验证操作和结果检查，加入焦点变化或布局变化的对照。

## Expected Output / Success Criteria

- 必学：能解释模型、Harness、系统执行器职责，画出完整闭环；能比较截图和控件信息的适用场景。
- 源码阶段：有固定版本和调用链；实验阶段：有可重复结果和至少一个失败或对照。
- 能说明焦点、缩放、权限或超时后结果未知中的至少一个风险；不把重试视为总是安全。
- 选学：远程桌面、多屏、复杂拖拽和跨平台适配，不阻塞主线。
- 当前仅完成入口初始化，不代表已掌握或完成实验。

## Boundaries / Related

- 本次不截取真实桌面、不控制其他应用、不安装或启动演示环境、不调用付费模型。
- 不将 Linux 演示的系统工具套用为 Windows 默认机制；具体产品行为待核验。
- 学习过程按 [Prompt 4](../../PROMPT_4_WORK_POOL_LEARN.md)；对照 [Browser Use](C-2026-030-study-browser-use.md)。
- 用户已有未提交改动保持原样；不提交、不 push、不切换 worktree。
