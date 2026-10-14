# Repository Agent Instructions

任何时候都不要切worktree，这只是一个学习的仓库，直接主分支进行更新

## 课程目录与历史引用

- 新版 20 章课程统一位于 `agents/s01_*` 至 `agents/s20_*`，入口为 [`agents/README.md`](./agents/README.md)。旧版 `agents/*.py` 与 `docs/en`、`docs/zh`、`docs/ja` 教材已移除。
- `docs/agent-engineering/` 与 `docs/plans/` 是工程方法笔记和历史设计文档，属于非旧版教材内容，继续保留。
- 历史文档中的根目录章节路径和旧版路径允许暂时保留。遇到失效引用时，先查找新版实际位置，仅修正当前任务涉及的引用，不自动批量修改笔记或索引。
- 旧根目录 `sXX_主题/` 对应 `agents/sXX_主题/`；旧版 12 章编号与新版编号存在错位，禁止仅凭编号替换。对应关系见课程入口。
- 教学代码仍从仓库根目录执行，例如 `python agents/s01_agent_loop/code.py`；移动脚本不代表改变运行工作目录，根目录的 `.env`、`skills/` 和运行状态目录继续按原方式使用。
- `mini-swe-agent` 子模块已移除；不自动重新克隆或恢复。

## Spec 工作流

本仓库使用 [`specs/README.md`](./specs/README.md) 定义的轻量 Spec 工作流。涉及方案、实现或任务整理时，先按该文档判断是否需要创建或更新 Spec。

### 何时读取 Spec

- 开始多文件改动、重要功能或需求仍含歧义的实现前，先阅读 `specs/README.md`；
- 同时检查 `specs/current/`、`specs/changes/` 和 `specs/decisions/` 中与任务相关的现有约束；
- 单文件、行为明确且预计少于 30 分钟的改动，可以直接处理，不强制创建 Spec。

### 任务如何流转

- 已知但暂不开始的工作记录到 `specs/work-pool/`；不要因为它存在就自动开始，等待用户明确启动；
- 开始 Work Pool 任务时，按规范创建对应的 `specs/changes/C-*.md`，并移除原 Work Pool 文件；
- 暂时无法决定的问题进入 `specs/review-pool/`；
- 会长期影响项目的重要决定进入 `specs/decisions/`；
- Change 完成后，按需更新 `specs/current/`，并在 `specs/implementation/` 记录实现、验证和遗留事项。

### 维护原则

- 一个事实只保留一个主要来源，其他文件使用相对链接引用；
- `specs/README.md` 是目录、命名、状态与流转规则的唯一规范来源，本文件只负责告诉 Agent 何时使用它；
- 章节学习过程仍记录在对应章节的 `LEARNING_NOTES.md`，不要把聊天笔记重复写入 Spec；
- 不要为了满足形式而创建空 Spec；仅在任务复杂度、风险或后续追踪价值值得时使用。

## 代码注释

- 新增或修改代码时，关键逻辑、数据流、缓存判断、边界条件和非显而易见的设计意图，必须补充简洁准确的中文注释；
- 注释应解释代码为什么这样做、状态如何变化以及容易混淆的边界，不要求对每一行显而易见的语法逐行注释；
- 代码行为变化时同步更新相关注释，避免保留与实现不一致的学习说明。

## 学习者画像与讲解要求

仓库维护者当前以 **初学者** 身份系统学习本课程（Agent / Harness / 多 Agent 协作等）。与之协作时，Agent 应主动降低术语门槛，并补足教材默认省略的背景知识。

### 必须主动做的事

- **术语科普**：专业词汇首次出现或在本章语境中关键时，补充中文含义、英文或全称、所在系统层次（如 Git / Harness / Runtime / LLM），以及与相邻概念的边界；不要用术语覆盖用户的原始心智模型。
- **关联扩展**：在回答或整理笔记时，适当串联前后章节、README、`LEARNING_NOTES.md` 与 Work Pool 中的相关条目，说明「这个概念从哪来、后面去哪」。
- **横向对比**：对易混淆机制（如 subagent vs teammate、上下文隔离 vs 目录隔离、task board vs todo）给出对照表或简短对比，避免只讲当前章。
- **生产级补充**：区分「教学实现」「通用原理」「真实产品行为（若未核验须标明）」；点出失败场景、竞态、审计、回滚、权限、合并冲突等生产环境常见考量，但不喧宾夺主。
- **笔记中的术语标记**：更新或共创 `LEARNING_NOTES.md` / `LEARNING_NOTES.draft.md` 时，维护「术语速查」或对首次出现的术语做 inline 标注，便于复习。

### 讲解风格

- 先接住用户的直观理解，再给出校准后的专业表述；
- 区分 🟢 已验证、🟡 部分正确、🔴 待验证，不把推断写成事实；
- 回答篇幅与问题复杂度相称；涉及方案或多轮技术讨论时，按用户规则在末尾保留「反思」小节。

## Learned User Preferences

- 普通学习讨论默认只在聊天中讲解，不自动把关键理解、术语校准、源码与结论写入 Markdown 或更新索引；仅在用户明确要求记录时，按指定范围写入。
- Git 提交按逻辑范围拆分（例如章节学习笔记与 Work Pool 文档分开 commit）；仅在用户明确要求时 push。

## Learned Workspace Facts

- Work Pool 引用的第三方源码按需浅克隆到本仓库外的独立目录（如 `source-reading/`）；勿用 git submodule，也不在 `learn-claude-code` 内存放外部项目源码。
- 章节正式学习前的前置疑问与讨论可先写入 `LEARNING_NOTES.draft.md`，完成章节后按 `PROMPT_3_COMPLETE_LEARNING_NOTES.md` 合并进正式笔记。
- `learn-claude-code` 只保留 spec、Work Pool、教学代码与学习笔记；外部项目阅读笔记链接回 Work Pool，不把第三方仓库纳入版本管理。
- Work Pool 正式学习过程记录在 `learning-notes/work-pool/W-YYYY-NNN-readable-name/`；其中 `LEARNING_NOTES.md` 保存总结、路线和进度，通用知识、任务实验与验收证据按需放入子目录；章节过程仍保留在对应 `agents/sXX_主题/LEARNING_NOTES.md`。
- 具体开源项目的模块实现学习集中在 `开源项目学习/<项目名>/<中文模块名>.md`，使用 [Prompt 7](./PROMPT_7_OPEN_SOURCE_PROJECT_LEARNING.md) 初始化入口与索引；前置正文只做简短初始化，后续不自动追加内容或更新进度。用户主要阅读并自行维护“我的笔记”，该区域默认只读，用户明确授权时才按指定范围编辑。Work Pool 引用这些主要来源；旧专题默认保留，不自动迁移。
