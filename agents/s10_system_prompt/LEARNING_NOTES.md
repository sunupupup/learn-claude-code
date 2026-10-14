# s10 System Prompt 学习笔记

> 学习主题：根据运行时状态动态组装 System Prompt，而不是把所有内容硬编码成一段固定字符串。
>
> 当前状态：已经掌握 Prompt Section、context 快照、条件加载和教学版缓存的基本关系；真实项目中的 Prompt Cache、动态指令加载和并发失效机制尚待继续学习。

## 一、本章要解决的问题

Agent 的能力增加后，System Prompt 不再只是固定身份描述，还可能包含：

- 可用工具；
- 工作目录和运行环境；
- Memory；
- 项目指令，例如 `AGENTS.md`；
- 已激活的 Skill 或其他运行时能力。

如果把它们全部写在一个硬编码字符串中，会导致维护困难、无关内容浪费 Token、动态状态无法及时反映，以及不同指令之间更容易发生冲突。

本章的核心结论是：

> System Prompt 是根据当前运行状态组装出来的结果，不是永远不变的一段字符串。

## 二、我的原始理解与校准

### 2.1 Prompt Section 与 context

我的原始理解：本章重点是 Prompt Section 和 context 的内容。

🔴 **已验证理解**：Prompt Section 是可独立维护的 Prompt 片段；context 是描述当前运行状态的数据，组装函数根据 context 决定加载哪些 section，并填充哪些动态内容。

```text
context
  → 选择 section、填充动态内容
  → assemble_system_prompt()
  → 最终 System Prompt
```

`context` 不是最终 Prompt，也不是完整的对话历史。它更像是组装 Prompt 时使用的运行状态快照。

### 2.2 Memory、AGENTS.md 与 Skill

我的原始理解：Memory 可以这样拼接，Skill 和 `AGENTS.md` 也可以理解成动态加载的外部文件或外部状态。

🔴 **已验证理解**：从抽象层看，它们都可以作为运行时上下文来源，经过读取、解析和筛选后进入 context，再参与 Prompt 组装。

统一的数据流可以表示为：

```text
外部来源
  → loader / parser / filter
  → context
  → assemble_system_prompt()
  → System Prompt
```

但它们不能完全用同一种规则处理：

| 来源 | 主要内容 | 需要特别考虑的加载规则 |
| --- | --- | --- |
| Memory | 过去的事实、偏好、经验 | 相关性、作用域、隐私和大小限制 |
| `AGENTS.md` | 项目或目录范围内的行为规则 | 目录层级、覆盖关系、信任和优先级 |
| Skill | 完成某类任务的方法、资源或脚本 | 发现、激活、版本、权限和渐进加载 |

因此，“动态外部状态”是共同的上层抽象，但不代表它们可以无条件地全部塞入 System Prompt。

### 2.3 `update_context()` 是更新还是重建

我的原始理解：代码中的 `update_context()` 看起来没有直接修改 context；后来理解为它每次读取当前状态并进行全量重建。

🔴 **已验证理解**：在当前教学代码中，`update_context()` 不修改传入的旧字典，而是重新读取当前状态并返回一个新的 context 字典。

当前实现返回：

```python
{
    "enabled_tools": list(TOOL_HANDLERS.keys()),
    "workspace": str(WORKDIR),
    "memories": memories,
}
```

例如工具刚刚创建了 `.memory/MEMORY.md`，下一次执行 `update_context()` 时才会读到新的 Memory 内容。

这不是唯一实现方式。生产系统也可以使用增量更新、版本号、文件监听或事件通知；但本例选择了简单的“重新生成状态快照”。

### 2.4 `get_system_prompt()` 是否每次都重新组装

我的原始理解：每次 loop 都会调用 `get_system_prompt()`。

校准后：

🔴 每次都会调用 `get_system_prompt()`，但不代表每次都会重新组装 Prompt。

```text
调用 get_system_prompt(context)
  → 生成确定性 context key
  → key 相同：cache hit，返回旧 Prompt
  → key 不同：重新执行 assemble_system_prompt()
```

所以更准确的说法是：

> 每次工具轮次后都重新检查 context；只有 context 变化时才重新组装 System Prompt。

## 三、两类缓存的边界

### 3.1 教学代码中的应用层缓存

`get_system_prompt()` 使用 `json.dumps(context, sort_keys=True, ...)` 生成确定性 key。

它的作用是：

- 避免当前进程内重复拼接字符串；
- 在 context 不变时返回同一个 Prompt；
- 让 section 顺序和 Prompt 内容保持稳定。

它不能保证模型服务商的 API 层 Prompt Cache 命中。

### 3.2 API 层 Prompt Cache

API 层缓存是否命中，还取决于：

- 服务商是否支持 Prompt Cache；
- 请求前缀是否完全稳定；
- 缓存边界或动态区间配置；
- 模型、接口和缓存生命周期；
- 动态内容是否被放在稳定前缀之后。

因此，应用层缓存是“减少本地重复组装并帮助保持稳定”，不是“严格保证 API 缓存生效”。

### 3.3 缓存失效边界

如果外部文件已经变化，但程序没有重新调用 `update_context()`，本地缓存不会自动知道，可能继续返回过期 Prompt。

```text
外部状态变化
  + 没有重新采集 context
  → context key 不变
  → 继续命中旧缓存
```

## 四、当前代码的调用链

```text
启动或工具轮次结束
    ↓
update_context()
    ↓
get_system_prompt(context)
    ↓
assemble_system_prompt(context)
    ↓
client.messages.create(system=system, ...)
    ↓
模型可能请求工具
    ↓
执行工具并写入 tool_result
    ↓
重新采集 context
```

需要区分三个循环层次：

1. 外层交互循环：不断接收用户的新问题；
2. `agent_loop()`：处理当前一个用户请求；
3. 内部 `while True`：可能经历多轮“模型调用 → 工具执行 → 继续调用”。

`history` 保存 user、assistant 和 tool result 消息；System Prompt 通过 `system` 参数单独传给模型，不放入 `history`。

## 五、当前教学代码的简化点

这些是代码阅读时发现的简化，不是本章已经完成的生产实现：

1. `context` 中虽然有 `enabled_tools` 和 `workspace`，但当前 `assemble_system_prompt()` 仍然使用固定的 tools 和 workspace 文本，没有真正根据这两个字段动态渲染。
2. `update_context(context, messages)` 当前没有读取 `messages`，所以消息历史不会影响本例的 context。
3. `PROMPT_SECTIONS["memory"]` 是概念性 section 标识，实际 Memory 内容直接通过 `Relevant memories:` 拼接。
4. 本例直接读取 `MEMORY.md` 的全部非空内容，没有做相关性检索、大小限制、隐私过滤或权限判断。
5. 本例每次重新读取文件，但没有处理并发写入、文件监听、版本号、原子发布和失效竞态。

## 六、修正后的核心伪代码

```text
update_context():
  读取当前工作目录
  读取当前已注册工具
  读取存在且非空的 Memory 内容
  返回新的 context 快照

get_system_prompt(context):
  key = 对 context 做确定性序列化
  如果 key 与上次相同：
    返回上次组装的 Prompt
  否则：
    prompt = assemble_system_prompt(context)
    保存 key 和 prompt
    返回 prompt

agent_loop(messages, context):
  system = get_system_prompt(context)
  循环：
    调用模型
    如果不需要工具：结束
    执行工具并追加 tool_result
    context = update_context(context, messages)
    system = get_system_prompt(context)
```

## 七、当前掌握状态

### 已掌握

- 能说明 Prompt Section 与 context 的关系；
- 能理解 Memory 是条件加载，而不是无条件注入空内容；
- 能理解 `update_context()` 在本例中是全量重建新的状态快照；
- 能区分“调用 `get_system_prompt()`”和“重新执行 Prompt 组装”；
- 能区分应用层 Prompt 组装缓存和 API 层 Prompt Cache；
- 能说明工具执行后为什么要重新采集 context；
- 能把 Memory、`AGENTS.md` 和 Skill 统一理解为上下文来源，同时意识到三者需要不同的加载规则；
- 能区分外层交互循环、`agent_loop()` 和内部工具调用轮次。

### 尚待验证

- 独立解释 `PROMPT_SECTIONS`、`assemble_system_prompt()` 和 `get_system_prompt()` 的具体代码关系；
- 通过实验验证创建或修改 `.memory/MEMORY.md` 后 Prompt section 的变化；
- 设计真正根据 `enabled_tools`、`workspace` 和 Skill 状态渲染 Prompt 的实现；
- 继续学习动态上下文的权限、注入防护、并发一致性和失效策略；
- 进一步区分真实 Agent Runtime 中的系统指令、用户上下文、Skill 内容和 API Prompt Cache。

## 八、动态文件加载与 mtime 缓存

为了观察“外部文件作为 context 来源”的最小实现，代码增加了两个显式加载器：

```python
{
    "instructions": load_agents_in_scope(),
    "active_skills": load_selected_skills(),
}
```

当前实现有意不自动扫描或读取仓库的 `AGENTS.md`：

- `load_agents_in_scope()` 只读取显式配置的 `AGENT_INSTRUCTION_FILES`；
- `load_selected_skills()` 只读取显式选择的 `ACTIVE_SKILL_NAMES` 对应的 `skills/<name>/SKILL.md`；
- 没有被配置或选中的来源，不会进入 context，也不会进入 System Prompt。

文件读取通过 `_read_cached_text()` 统一处理：

```text
每次 update_context()
  → 调用 Path.stat() 检查 mtime_ns + size
  → 签名未变化：返回进程内缓存
  → 签名变化或首次读取：重新 read_text()
  → 文件删除：缓存为空内容
```

这里的 `mtime_ns + size` 是教学版失效判断。它可以避免每轮重复读取未变化的文件，但不是并发一致性方案，也不能严格保证 API 层 Prompt Cache 命中。生产系统还可能需要版本号、文件锁、事件通知、原子发布或内容 Hash。

## 九、下一步验收问题

1. 如果工具没有修改任何外部状态，下一次调用 `get_system_prompt(context)` 会发生什么？
2. 如果工具修改了 `.memory/MEMORY.md`，但没有再次调用 `update_context()`，会发生什么？
3. 为什么不能把所有 Skill 文件一次性加载进 System Prompt？
4. 当前代码中 `enabled_tools` 发生变化时，为什么 tools section 还不会自动变化？
