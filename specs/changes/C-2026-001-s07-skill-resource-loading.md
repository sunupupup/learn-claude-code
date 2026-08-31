# Spec: s07 Skill 辅助资源按需加载

状态：`done`

## Objective

扩展 `s07_skill_loading` 教学 Demo，使 Skill 除了 `SKILL.md` 正文外，还可以声明并按需读取同一 Skill 目录下的辅助资源，例如：

- `references/`：参考说明、模板和示例代码；
- `scripts/`：可被读取或后续执行的辅助脚本；
- `assets/`：供 Skill 使用的静态资源。

用户目标是理解“Skill 正文是入口索引，辅助资源按需展开”的完整链路，同时保留最小可控的目录边界。

## Assumptions

1. 继续使用当前 Anthropic-compatible Tool Calling 循环，不引入 Agent 框架。
2. Skill 资源索引放在 `SKILL.md` YAML frontmatter 的可选 `resources` 字段中，便于 Harness 机器解析。
3. 本次只实现**读取**辅助资源，不自动执行 `scripts/`，也不增加写入或网络能力。
4. 资源必须显式列在索引中；未声明的文件即使位于 Skill 目录下也不能通过新工具读取。
5. 主 Agent 使用新工具；教学版 Subagent 暂不继承该工具，以保持本章新增机制边界清晰。
6. 不记录、提交或回显任何 API Key；不修改原教程 `s07_skill_loading/README.md`。

## Commands

```powershell
\.venv\Scripts\python.exe -m pytest tests/test_s07_skill_resources.py -q
\.venv\Scripts\python.exe -m py_compile s07_skill_loading/code.py
\.venv\Scripts\python.exe s07_skill_loading/code.py
```

## Project Structure

```text
s07_skill_loading/code_skill_enhance.py            → 增强版注册表、Skill 加载和资源读取工具
skills/agent-builder/SKILL.md                     → 增加 resources 索引示例
tests/test_s07_skill_resources.py                 → 索引、读取、越界和错误路径测试
s07_skill_loading/LEARNING_NOTES.md               → 记录扩展后的 State/Context/Resource 边界
specs/changes/C-2026-001-s07-skill-resource-loading.md → 本变更规范
specs/implementation/I-2026-001-s07-skill-resource-loading.md → 完成后的实现与验证记录
```

## Interface and Code Style

`SKILL.md` frontmatter 允许以下可选结构：

```yaml
---
name: agent-builder
description: Design and build AI agents.
resources:
  - path: references/agent-philosophy.md
    description: Deeper explanation of the agent loop.
  - path: references/minimal-agent.py
    description: Minimal runnable implementation.
---
```

注册表中的 Skill 记录新增规范化后的资源索引。`load_skill(name)` 返回 `SKILL.md` 正文，并附带“可用辅助资源”目录；模型再调用：

```python
read_skill_resource(
    name="agent-builder",
    path="references/minimal-agent.py",
    limit=200,
)
```

新 Handler 必须：

- 只接受注册表中存在的 Skill 名称；
- 只允许索引中声明的相对路径；
- 使用 `Path.resolve()` 后确认目标仍在该 Skill 目录内；
- 拒绝 `..` 越界路径、绝对路径、目录和符号链接逃逸；
- 对不存在、未声明或无法读取的资源返回可诊断的错误字符串；
- 不执行脚本、不修改文件、不访问 Skill 目录之外的内容。

## Testing Strategy

使用 pytest 对纯本地 Handler 做确定性测试，不调用真实模型 API：

1. 资源索引被扫描并规范化；
2. `load_skill` 返回正文和可用资源目录；
3. 已声明资源可以读取并支持行数限制；
4. 未声明资源、未知 Skill、不存在文件返回明确错误；
5. `../`、绝对路径和目录读取不能越界；
6. 现有 Skill 没有 `resources` 时，原有 `load_skill` 行为保持兼容。

## Boundaries

- Always：资源通过注册表查找；验证相对路径和真实路径；资源读取只读；为索引和错误路径写测试；不把完整辅助文件预先注入 System Prompt。
- Ask first：改变资源索引格式；让 Subagent 自动继承资源工具；允许脚本执行、写文件、网络访问或动态刷新注册表；新增外部依赖。
- Never：根据模型输入直接拼接任意 Skill 路径；允许 `../` 或符号链接逃逸；把 `scripts/` 当作自动执行入口；提交 API Key。

## Success Criteria

1. 至少一个真实 Skill 在 `SKILL.md` 中声明 `references/` 或 `scripts/` 资源。
2. 启动扫描只缓存资源索引，不读取所有辅助文件正文。
3. 模型加载 Skill 后能看见资源目录，并可通过新 Tool 按名称读取被索引资源。
4. 越界、未声明、不存在和目录路径均被拒绝且不崩溃。
5. 现有四个 Skill 的目录发现和 `load_skill` 兼容测试通过。
6. 不修改原教程 README，不执行辅助脚本。

## Open Questions

- 未来是否需要让 Skill 正文中的 Markdown 链接也自动生成资源索引？本次先不做，避免同时维护 YAML 和正文两套解析规则。
- 未来是否需要资源版本、哈希或缓存失效策略？本次先记录为 s08/生产 Runtime 的后续议题。
