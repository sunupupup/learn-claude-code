# Specs

这个目录用于个人开发与学习任务的轻量 Spec 管理。目录结构参考 Notion 页面 [内部开发 Spec 范式｜六类文档、作用与案例](https://app.notion.com/p/3c9d850183c58125a394f325e55a2ce4)。

## 目录职责

```text
specs/
├─ README.md
├─ current/          # 当前有效行为和约束
├─ changes/          # 正在规划或实施的变更
├─ work-pool/        # 已知但暂不开始的工作
├─ review-pool/      # 等待个人或负责人决策的问题
├─ decisions/        # 已确认的重要长期决策 / ADR
└─ implementation/   # 已完成工作的实现与验证记录
```

## 轻量使用规则

1. 小于 30 分钟、单文件且行为明确的工作，可以直接处理，不强制创建 Spec。
2. 已知但当前不做的事项放入 `work-pool/`。
3. 准备开始 Work Pool 项时，为它建立 `changes/C-YYYY-NNN-*.md`，并从 Work Pool 移除原文件。
4. 遇到暂时无法决定的产品、架构、权限或兼容问题，放入 `review-pool/`。
5. 只有会长期影响项目的重要决定才记录为 `decisions/ADR-YYYY-NNN-*.md`。
6. Change 完成后，按需更新 `current/`，并在 `implementation/` 记录实现、验证和遗留事项。
7. 一个事实只保留一个主要来源，其他文档通过相对链接引用，避免重复维护。

## 文件命名

```text
changes/C-YYYY-NNN-readable-name.md
work-pool/W-YYYY-NNN-readable-name.md
review-pool/R-YYYY-NNN-readable-name.md
decisions/ADR-YYYY-NNN-readable-name.md
implementation/I-YYYY-NNN-readable-name.md
```

同类编号按年份递增。文件名使用英文 kebab-case，标题和正文可以使用中文。

## 状态

- Change：`proposed → approved → active → verifying → done`，也可以进入 `blocked` 或 `cancelled`。
- Work Pool：`ready | blocked | someday`。
- Review Pool：`pending → resolved`。

这是个人学习仓库，默认不要求 Approver、截止日期或完整 ADR；只有当任务风险和协作成本值得时再补充。
