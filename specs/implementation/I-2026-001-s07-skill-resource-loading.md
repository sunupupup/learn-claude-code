# Implementation: s07 Skill 辅助资源按需加载

状态：`done`

对应变更：[C-2026-001-s07-skill-resource-loading.md](../changes/C-2026-001-s07-skill-resource-loading.md)

## 实现内容

- 新增独立增强版 [`code_skill_enhance.py`](../../s07_skill_loading/code_skill_enhance.py)，保持原 `code.py` 不变；
- 支持 `SKILL.md` frontmatter 中的可选 `resources` 索引；
- 启动时只缓存资源路径和描述，不读取所有辅助文件正文；
- `enhance_skill()` 返回 Skill 正文和资源目录；
- `load_skill` 兼容映射到 `enhance_skill()`；
- `advance_skill()` 只读取已声明的单个资源；
- 使用 `Path.resolve()` 和 `is_relative_to()` 阻止路径遍历、绝对路径和符号链接越界；
- 资源读取只读、有行数上限，不执行 `scripts/`；
- `skills/agent-builder/SKILL.md` 增加 `references/` 和 `scripts/` 示例索引；
- 新增 6 个确定性资源加载测试；
- 更新 s07 学习笔记，记录 Enhance / Advance、State / Context 和安全边界。

## 验证

```text
python -m py_compile s07_skill_loading/code_skill_enhance.py tests/test_s07_skill_resources.py
python -m pytest tests/test_s07_skill_resources.py -q
......                                                                   [100%]
6 passed in 1.37s
```

另外使用真实 DeepSeek Anthropic-compatible API 完成了端到端实验：

```text
[HOOK] load_skill
[HOOK] advance_skill
[HOOK] Stop: session used 2 tool calls
```

模型先加载 `agent-builder` 的 Skill 正文和资源目录，再读取 `references/minimal-agent.py` 并生成总结。

## 遗留事项

- `resources` 目前只支持 YAML frontmatter 索引，不自动解析正文中的 Markdown 链接；
- 资源没有版本、哈希和热刷新机制；
- `scripts/` 只能读取，尚未设计人工审批后的执行流程；
- 教学版 Subagent 没有继承 `advance_skill`，角色级 Skill allowlist 留待后续章节或生产 Runtime 研究。
