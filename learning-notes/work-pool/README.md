# Work Pool 学习笔记目录

这一章节的学习笔记，直接在当前主分支下开发，不准开worktree

## 目录定位

本目录保存 Work Pool 真正启动后的学习过程、源码阅读记录、实验结果和最终总结。

| 内容 | 唯一主要位置 | 说明 |
| --- | --- | --- |
| 待学习主题、目标、范围和启动条件 | `specs/work-pool/W-*.md` | 待办任务卡；启动后按 Spec 规则转入 `specs/changes/` |
| 章节学习过程 | `sXX/LEARNING_NOTES.md` | 记录对应基础章节，不把 Work Pool 全文复制回来 |
| Work Pool 学习过程 | `learning-notes/work-pool/W-*/` | 本目录；记录理解、证据、实验和生产化边界 |
| 长期架构决定 | `specs/decisions/ADR-*.md` | 只有确认过且会长期影响项目的决定才写入 |
| 外部项目源码 | 仓库外的 `source-reading/` | 只保存浅克隆或固定版本源码；本仓库只保存阅读笔记和链接 |

不要把 Work Pool 学习笔记放回 `specs/work-pool/`。那会把“待启动任务卡”和“已经发生的学习证据”混在一起，而且 Work Pool 启动后原文件会被移除。

## 每个 Work Pool 的目录

用户明确启动某个 Work Pool 后，按需创建下面的目录；不要为了形式预先创建一堆空目录。

```text
learning-notes/
└─ work-pool/
   ├─ README.md
   └─ W-2026-NNN-readable-slug-关键词/
      ├─ LEARNING_NOTES.md       # 该任务的唯一学习总结与掌握状态
      ├─ source-notes/            # 开源项目、官方文档、论文的证据化阅读记录
      ├─ experiments/             # 最小实验、脚本、输入、运行说明和结果
      ├─ evidence/                # 日志、指标、Trace、截图或其他验收证据
      └─ artifacts/               # 只有确实产生图表、报告等文件时才创建
```

目录名沿用 Work Pool 的完整编号和英文 slug，并在末尾添加简短、易辨认的中文或英文关键词（如 `-RAG`、`-Jev`、`-自进化Agent`、`-Memory`）。此规则仅适用于本目录下的学习主题文件夹；Spec 文件名保持原有规范。例如：

```text
learning-notes/work-pool/W-2026-002-study-llm-runtime-foundations-模型运行基础/
```

当前 `W-2026-001` 到 `W-2026-032` 是学习任务编号范围（其中部分编号已完成、转入 Change，或暂未占用）；新主题按 `specs/README.md` 和现有 Prompt 使用下一个未占用编号。学习顺序由总路线 `W-2026-001` 的索引维护，不再为了插入新主题反复重编号。

文件名建议使用局部顺序号，方便从小到大阅读：

```text
source-notes/01-tokenizer-and-chat-template.md
source-notes/02-runtime-cache-evidence.md
experiments/01-prompt-microscope.md
experiments/02-cache-branch-lab.md
evidence/01-measurement-table.md
```

## `LEARNING_NOTES.md` 的固定结构

它是学习结论的主要来源，不是聊天记录的逐字复制，也不是 Work Pool 任务卡的副本。建议按下面结构维护：

1. **任务范围与状态**：Work Pool 编号、开始日期、当前阶段、使用的模型/Runtime/源码版本；
2. **为什么学习它**：关联的章节、已有基础和本次要解决的问题；
3. **学习模式**：理论、源码、实验或混合，并说明选择原因；
4. **术语速查**：中文含义、英文全称、所属层次和相邻概念边界；
5. **我的原始理解**：保留用户的直观说法、问题和伪代码；
6. **校准后的结论**：标记 `🟢 已验证`、`🟡 部分正确`、`🔴 待验证`，不要把推断写成事实；
7. **调用链 / 状态机 / 数据流**：理论机制或源码中的实际路径；
8. **来源与证据**：章节、源码文件和行号、Commit、官方文档、运行日志，区分静态阅读和实际运行；
9. **实验与失败记录**：假设、预期、实际结果、失败注入、恢复方式和剩余疑问；
10. **生产级边界**：权限、租户隔离、幂等、重试、超时、竞态、审计、观测、成本、回滚和未知结果；
11. **掌握状态与下一步**：已完成、暂缓、阻塞和下一次只学习的一个小问题。

理论结论、源码事实、教学实现和 Provider/框架的版本行为必须分开写。一个外部项目的源码阅读结论，不能自动证明当前项目或其他 Provider 也采用同样实现。

## 生命周期

```text
W-*.md 待启动
   ↓ 用户明确说“开始”
创建 specs/changes/C-*.md + 创建本目录任务文件夹
   ↓
理论 / 源码 / 实验 / 混合学习
   ↓
更新 LEARNING_NOTES.md 与证据文件
   ↓
完成验收；按需写 specs/implementation/I-*.md
```

`specs/changes/` 记录任务如何被启动、范围如何变化和最终验证；`learning-notes/work-pool/` 记录你真正学到了什么、看到了什么证据以及哪些内容仍不确定。两者不要互相替代。
