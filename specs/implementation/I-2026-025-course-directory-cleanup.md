# I-2026-025 课程目录整理实现与验证

- 日期：2026-10-15
- 对应变更：[C-2026-025](../changes/C-2026-025-course-directory-cleanup.md)
- 当前目录规则的主要来源：[根 AGENTS.md](../../AGENTS.md#课程目录与历史引用)
- 课程入口：[agents/README.md](../../agents/README.md)

## 实现

- 删除旧版 12 章 Python 代码及三语教材；保留 `docs/agent-engineering/` 和 `docs/plans/` 的 5 份非教材文档。
- 20 个章节整体移入 `agents/`。移动完成时，205 个文件的 SHA-256 与迁移前一致。
- 随后仅修改 s07 补充脚本的运行示例及仓库根路径：由 `parents[1]` 改为 `parents[2]`，保持共享 `skills/` 的读取位置不变。
- 更新三语根入口、课程索引和 Agent 维护规则。
- Web 只读取 `agents/` 的新版章节，删除旧版读取分支；先验证 s01-s20 完整再清理生成图片，避免错误目录覆盖为无内容课程。同步生成教材、代码数据和图片资源。
- 现有 Python 测试适配新版位置；烟雾测试覆盖新版主线及补充脚本；删除仅服务于已移除 `s_full.py` 的旧版后台测试。
- 纳入已授权删除的 `mini-swe-agent` 子模块及空 `.gitmodules`。

## 验证

- Python：以 `MODEL_ID=test-model`、`ANTHROPIC_API_KEY=test-key` 执行 `python -m pytest tests -q`，43 passed，24 subtests passed；未调用真实模型。
- Web 提取：20 versions、19 diffs、60 docs。
- `npx tsc --noEmit` 通过；`npm run build` 通过，生成 136 个静态页面。
- 三语根 README、课程入口和根 AGENTS.md 的本地文件链接目标全部存在。
- 迁移校验确认章节没有漏文件；除上述 s07 适配外，章节内容保持原样。

## 遗留事项

- 章节正文、个人笔记、Work Pool 和历史索引的旧链接未批量修复，按根 AGENTS.md 约定遇到时局部处理。
- 教材和代码注释中的历史运行示例也可能保留旧路径，以课程入口的新运行方式为准。
- 本次验证目录、代码编译和已有离线测试，不代表所有章节已完成真实模型调用或运行实验。
