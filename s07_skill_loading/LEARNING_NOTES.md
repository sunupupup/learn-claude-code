# s07 Skill Loading 学习笔记

> 学习进度：核心机制已理解并完成一次真实运行实验。已完成两级加载、注册表与模型上下文边界、State 与 Context、Skill 与 Tool、主 Agent 与 Subagent 的 Skill 使用边界校准；尚待独立伪代码和安全边界验收。

## 一、本章核心结论

s07 在主 Agent 的工具集合中新增 `load_skill`。Harness 启动时扫描 `skills/`，把每个 `SKILL.md` 的名称、描述和完整正文缓存到进程内的 `SKILL_REGISTRY`；同时只把名称和描述组成轻量目录，注入 `SYSTEM`。

模型从第一次 API 调用开始就能看见 Skill 目录，但看不见未加载的完整正文。任务需要某个 Skill 时，模型调用 `load_skill(name)`；Harness 从注册表取出正文，作为 `tool_result` 追加到 `messages`，正文才进入后续模型调用的上下文。

本章的“按需加载”主要指**按需向模型上下文注入 Skill 正文**，不是按需从磁盘读取文件。磁盘读取已在模块加载阶段完成。

```text
磁盘中的 SKILL.md
  ↓ 模块加载时扫描、读取
Python 进程内的 SKILL_REGISTRY
  ├─ name + description → SYSTEM → 模型从第一轮开始可见
  └─ content → 模型调用 load_skill → tool_result → messages → 模型可见
```

## 二、我的原始理解

1. `SKILL.md` 根据 `---` 分成元信息和正文；元信息包含名称和描述。
2. 应用开始时会把已有 Skill 的名称、描述和正文注册到当前 Agent 的状态中。
3. 枚举 Skill 时只返回标题和描述，这是用于选择 Skill 的关键信息。
4. Skill 元信息作为“顶层 Context”，让 Agent 知道有哪些 Skill。
5. Skill 加载属于决策层，一般应该只由主 Agent 执行；Subagent 主要负责写代码和查代码。
6. `load_skill` 用于动态加载 Skill 正文。
7. 上下文也可以看作 Agent 状态。

## 三、已经理解正确的部分

### 3.1 两级加载解决无关知识占用上下文

🔴 **已验证理解**：启动时只让模型看到 Skill 的名称和描述，需要时再把完整正文放入模型上下文，可以减少无关知识在每轮 API 调用中占用的 Token。

两层信息承担不同职责：

| 层 | 模型看到什么 | 主要用途 |
| --- | --- | --- |
| Skill Catalog | `name + description` | 发现、选择和路由 |
| Skill Content | 完整 `SKILL.md` | 指导具体任务的执行 |

### 3.2 注册表首先属于 Harness 进程

🔴 **已验证理解**：`SKILL_REGISTRY` 首先只是 Python 进程内存中的注册表；程序拥有某段数据，不等于模型已经看见这段数据。

注册表在启动时保存：

```python
{
    "name": name,
    "description": desc,
    "content": raw,
}
```

其中 `content` 已被读入内存，但只有 `name + description` 被 `build_system()` 写入 `SYSTEM`。完整正文要等 `load_skill` 返回后才进入 `messages`。

### 3.3 Skill 与 Tool 不是同一个概念

🔴 **已验证理解**：Skill 主要提供“怎样完成某类任务”的知识、流程和约束；Tool 提供“程序可以对环境执行什么动作”的接口。

例如：

```text
code-review Skill：告诉 Agent 审查顺序、检查重点和输出格式
read_file Tool：真正读取代码文件
bash Tool：真正运行测试或静态检查
```

加载 Skill 只表示模型获得了操作说明，不代表说明中的任务已经执行，也不会自动获得新的工具权限。

### 3.4 Skill 元信息参与路由，正文参与执行

🔴 **已验证理解**：Skill 的发现、选择和路由通常可以由主 Agent 或编排层负责。

校准后的完整理解是：

```text
name + description → 为路由决策提供信息
SKILL.md 正文      → 指导实际执行者完成任务
references/scripts → 为执行过程提供知识和确定性资源
工具授权           → 由 Harness / Policy 强制控制
```

因此，Skill 不是天然只属于“决策层”。它可以同时包含路由信息和执行知识。

## 四、需要校准的边界

### 4.1 Agent State、Harness State、历史消息与 Context

本章对 **Agent State** 采用以下精确定义：

> Agent State 是一次 Agent Run 为了在步骤之间继续执行、恢复、判断和验收而必须保存的可变事实与中间产物。

在当前教学代码中，典型的 Agent Run State 包括：

- `messages`：本次 Run 的协议消息历史，包括用户消息、assistant 输出、Tool Call 和 Tool Result；
- `CURRENT_TODOS`：当前任务清单；
- `rounds_since_todo`：循环控制所需的运行计数。

还要区分更大的 **Harness State**：

- `SKILL_REGISTRY`：进程级 Skill 目录和正文缓存；
- `TOOLS`、`TOOL_HANDLERS`、`HOOKS`：工具与控制配置；
- API Client、模型配置、日志和运行时资源。

`SKILL_REGISTRY` 是 Harness State，但不是某一次 Agent Run 的 State，因为它在多次 Run 之间共享，并不表示当前 Agent 已经使用了某个 Skill。

**历史消息（Message History）** 是 Harness 保存的 `messages` 协议记录；它属于 Agent Run State，但不等于模型上下文。当前 s07 没有压缩或筛选，所以历史消息基本原样参与下一次请求。

**Context（上下文）** 是某一次模型调用实际发送给 LLM 的输入快照，通常由 `system`、当前选取的历史消息、Tool Schema 和本轮需要的其他输入组成。它是“给 LLM 看什么”，而 State 是“系统保存了什么”。

```text
Harness State
├─ Agent Run State
│  ├─ messages（历史消息）
│  ├─ todos / counters
│  └─ 当前任务产物与运行状态
└─ 进程级配置与资源
   └─ SKILL_REGISTRY、Tools、Hooks、Client

State + 静态配置
   ↓ 选择、拼装、裁剪
本轮 LLM Context
```

因此，未加载的 Skill 正文可以存在于 Harness State，却不在 Context；`SYSTEM` 中的 Skill 目录则属于本轮 Context，但它主要是静态配置，不是一次 Run 产生的可变事实。

### 4.2 `name + description` 从第一轮起就是模型上下文

`_scan_skills()` 完成后，`build_system()` 立即调用 `list_skills()`，并生成 `SYSTEM`。因此名称和描述不是等真正使用 Skill 时才进入上下文，而是每轮都随 `system=SYSTEM` 发送给模型。

只有完整正文是等模型调用 `load_skill` 后才进入对话历史。

### 4.3 “顶层 Context”可以作为个人直觉，但不够精确

当前代码没有名为 `top-level context` 的独立对象。Skill 目录只是被拼接到 `SYSTEM` 字符串中。

如果“顶层 Context”指“System Prompt 中每轮都可见的全局上下文”，方向没有错；代码注释中更推荐写成：

```python
# 将 Skill 元信息注入 System Prompt，作为每轮模型调用都可见的全局上下文
```

这样可以避免把 API 请求的顶层字段、指令优先级和 Agent 全部状态混为一谈。

### 4.4 `yaml.safe_load()` 解析的是整个 YAML 映射

`yaml.safe_load(parts[1])` 不只负责解析 `name` 和 `description`，而是把整个 frontmatter 转换成 Python 对象。后续代码再通过 `meta.get("name")` 和 `meta.get("description")` 读取字段。

当前教学版使用 `name`，不是 `title`。

另外，写在 `return {}, text` 后面的注释不会被运行路径经过，应放到 `parts = text.split("---", 2)` 之前，才能正确说明后续代码。

### 4.5 “动态加载”不是运行时重新读取磁盘

`load_skill(name)` 没有调用 `read_text()`，只是查询启动时已经填充的 `SKILL_REGISTRY`：

```python
skill = SKILL_REGISTRY.get(name)
return skill["content"]
```

所以更准确的描述是：

> 模型按需请求 Skill，Harness 将注册表中缓存的正文作为 `tool_result` 注入对话上下文。

这也意味着：程序启动后再修改磁盘上的 `SKILL.md`，当前进程中的注册表通常不会自动刷新。

### 4.6 生产系统不必把 Skill 限定给主 Agent

当前教学版的 `SUB_TOOLS` 没有注册 `load_skill`，因此 Subagent 不能自行加载 Skill。这是为了让本章只增加一个核心机制，不是通用架构原则。

常见设计可以包括：

```text
方案 A：主 Agent 加载 Skill，并把必要规则放入委派任务
方案 B：主 Agent 决定委派和 Skill，Subagent 加载获准的 Skill
方案 C：角色型 Subagent 固定拥有一小组与职责匹配的 Skill
```

更合理的生产默认值不是“所有 Subagent 拥有所有 Skill”，而是：

> 执行任务的 Agent 获得完成任务所需、且角色和权限允许的 Skill。

主 Agent 可以负责较高层路由；Subagent 可以使用范围受限的执行知识；最终工具权限仍由 Harness 或 Policy 强制执行。

## 五、当前代码的对象与职责

| 对象 | 当前职责 | 模型是否直接看见 |
| --- | --- | --- |
| `SKILLS_DIR` | 指定本地 Skill 根目录 | 否 |
| `_parse_frontmatter()` | 把 frontmatter 解析为元信息字典 | 否 |
| `_scan_skills()` | 启动时扫描并读取完整 `SKILL.md` | 否 |
| `SKILL_REGISTRY` | 在进程内缓存名称、描述和正文 | 否 |
| `list_skills()` | 把名称和描述格式化为轻量目录 | 间接可见 |
| `build_system()` / `SYSTEM` | 把 Skill 目录放进每轮 System Prompt | 是 |
| `load_skill` Tool Schema | 让模型知道可以按名称请求完整 Skill | 是 |
| `load_skill()` Handler | 从注册表查找并返回缓存正文 | 否，返回结果可见 |
| `TOOL_HANDLERS` | 把 Tool 名称分发到 Python Handler | 否 |
| `messages` 中的 `tool_result` | 保存已经加载的 Skill 正文 | 是，直到被压缩、截断或会话结束 |
| `SUB_TOOLS` | 定义教学版 Subagent 的基础工具 | 只对 Subagent 可见 |

## 六、关键流程伪代码

```text
应用启动：
  创建空 SKILL_REGISTRY
  遍历 skills/ 下的每个子目录
  读取 SKILL.md
  解析 name 和 description
  把 name、description、完整 content 缓存到注册表

  catalog = 只枚举 name + description
  SYSTEM = 基础指令 + catalog + load_skill 使用提示

收到用户任务：
  调用模型：system = SYSTEM，messages = 当前历史，tools = TOOLS

  if 模型不需要 Skill：
      正常回答或调用其他 Tool

  if 模型调用 load_skill(name)：
      Harness 从 TOOL_HANDLERS 找到 load_skill
      从 SKILL_REGISTRY 查询 name
      返回缓存的完整 SKILL.md
      把正文作为 tool_result 追加到 messages
      再次调用模型
      模型根据 Skill 正文继续执行
```

## 七、真实运行验证

已使用 DeepSeek 的 Anthropic 兼容接口运行 `s07_skill_loading/code.py`，测试提示要求模型加载 `code-review` Skill 并回答其中的前三项审查重点。

观察到的关键轨迹：

```text
[HOOK] UserPromptSubmit
[HOOK] load_skill
[HOOK] Stop: session used 1 tool calls
```

模型正确返回了 Skill 中的 Security、Correctness 和 Performance 三项内容。这证明当前链路已经跑通：

```text
SYSTEM 中发现 Skill
  → 模型选择 load_skill
  → Harness 执行 Handler
  → tool_result 返回正文
  → 模型基于正文生成最终答案
```

本地 `.env` 和 `.venv` 均被 Git 忽略；学习笔记不记录 API Key。

## 八、待完成的本章验收

1. 不看代码，独立解释 Skill Catalog 与 Skill Content 分别解决什么问题。
2. 独立写出 `_scan_skills → build_system → load_skill → tool_result` 的伪代码。
3. 解释为什么完整正文已经在 `SKILL_REGISTRY` 中，却仍然不算模型上下文。
4. 区分 State、Context、Memory 和磁盘文件，不把它们统称为“Agent 状态”。
5. 说明 Skill 与 Tool 的边界，以及加载 Skill 为什么不会自动获得工具权限。
6. 设计一个 Subagent 使用 Skill 的方案，说明 Skill 过滤、工具权限和任务委派分别由谁负责。
7. 分析 Skill 不存在、frontmatter 损坏、重名和恶意指令时应该怎样处理。

## 九、当前掌握状态

- 已掌握：Skill Catalog 与完整正文的两级加载目的。
- 已掌握：Skill 与 Tool 的基本区别。
- 已掌握：`SKILL_REGISTRY`、`SYSTEM`、`messages` 三个数据位置的可见性边界。
- 已校准：按需加载的是模型上下文，不是磁盘读取。
- 已校准：Context 是当前模型输入，不等于系统拥有的全部 State。
- 已校准：Skill 元信息参与决策，正文与资源参与执行。
- 已校准：主 Agent 负责路由不等于只有主 Agent 可以使用 Skill。
- 已验证：DeepSeek Anthropic 兼容接口能够完成一次真实 `load_skill` Tool Calling。
- 待验收：独立伪代码、错误路径、安全边界和 Subagent Skill 方案。

## 十、与完整 Agent 工程的对应位置

本章主要对应 Agent 工程能力域中的 **Tool 与 Skill**，并直接连接：

- **Context Engineering**：决定每轮模型到底看到目录还是完整正文；
- **Agent 控制流**：由模型判断是否以及何时调用 `load_skill`；
- **安全与治理**：Skill 说明不能绕过 Tool 权限，Skill 来源和内容需要信任边界；
- **多 Agent 编排**：决定由主 Agent 传递 Skill，还是由 Subagent 加载获准的 Skill；
- **可观测性与 Eval**：验证模型是否选择正确 Skill、是否遵守正文以及加载成本是否合理。
