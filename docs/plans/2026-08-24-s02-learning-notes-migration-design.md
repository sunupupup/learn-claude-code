# s02 学习笔记迁移设计

## 背景

`s02_tool_use/README.md` 是项目教程的一部分，不适合承载学习者在对话中形成的个人理解、问题校准和生产化扩展。当前分支已在第一章使用 `s01_agent_loop/LEARNING_NOTES.md`，因此第二章应采用相同约定。

## 目标

1. 新建 `s02_tool_use/LEARNING_NOTES.md`，作为第二章个人学习积累的主文件。
2. 将现有 README 中新增的个人学习内容迁移到该文件并重新组织。
3. README 只保留一条简短入口链接，不再承载详细学习扩展。
4. 保留 `s02_tool_use/code.py` 中解释运行行为的关键注释。
5. 通过新增提交完成修正，不改写既有 Git 历史。

## 学习笔记结构

`LEARNING_NOTES.md` 包含：

- 本章核心结论；
- 学习者的原始理解与校准；
- `TOOLS`、`TOOL_HANDLERS` 和 `TOOL_VALIDATORS` 的职责；
- 未知工具、参数错误和工具内部异常的处理流程；
- `tool_result`、`tool_use_id` 与 `is_error` 的回传机制；
- Client Tool、Server Tool、Remote MCP Tool 和协议错误的区别；
- 手写校验、JSON Schema 与 Pydantic 的取舍；
- 消息顺序、循环预算、安全、可观测性等生产化扩展；
- 官方学习链接和待验收问题。

## README 调整

删除此前加入的详细错误处理、Pydantic 和生产清单内容。保留一段简短的“学习笔记”入口，链接到同目录下的 `LEARNING_NOTES.md`。

README 中直接描述项目当前代码事实的少量文字可以保留，例如工具结果支持错误标记；个人理解、问答和扩展阅读全部移入学习笔记。

## 验证

- `s02_tool_use/LEARNING_NOTES.md` 存在且内部链接可解析；
- README 指向学习笔记的相对链接正确；
- README 不再包含大段个人学习扩展；
- `s02_tool_use/code.py` 与迁移前一致；
- `git diff --check` 通过；
- 工作区不纳入无关的 `.cursor/`。

