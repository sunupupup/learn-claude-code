# s09 Memory 学习笔记

> 学习主题：跨压缩、跨会话保存有长期价值的信息，并在需要时按相关性召回。
>
> 当前状态：s09 基础机制已掌握，可以开始 s10；生产级 Memory 治理暂存于 W-2026-008，尚未启动。

## 一、本章要解决的问题

s08 的上下文压缩是有损的：压缩可能保留目标和大意，但丢失用户的具体偏好、项目背景或历史反馈。新会话还不会自动继承上一会话的上下文。

Memory 增加了一层不参与普通上下文压缩、可以跨会话保留的存储。但 Memory 不是完整聊天记录，也不是权威业务数据库，而是“未来可能仍然有用的用户偏好、反馈、项目事实和参考入口”。

核心问题可以概括为：

~~~
什么值得记住？
什么时候写入？
什么时候召回？
什么时候更新、合并、过期或删除？
如何证明记忆没有制造更多噪声？
~~~

## 二、我的原始理解与校准

### 2.1 索引与正文的位置

我的原始理解：记忆文件会放进 SYSTEM prompt。

🔴 **已验证理解**：MEMORY.md 的索引进入 SYSTEM prompt，具体选中的记忆正文会注入当前 user message。

准确的数据流是：

~~~
MEMORY.md 索引
    → build_system()
    → system prompt

相关记忆正文
    → load_memories()
    → 当前 user message 的 content 前面
~~~

这样设计是为了让索引相对稳定，而把每次动态变化的正文放在当前请求中。当前代码中，记忆正文不是更高优先级的系统指令，而是 user message 中的普通文本，因此不能天然当作可信指令。

### 2.2 三个函数的边界

最初把“扫描文件、选择记忆、读取正文”都写进了 load_memories()，这是本章最主要的函数边界错误。

校准后：

| 函数 | 输入 | 输出 | 职责 |
| --- | --- | --- | --- |
| list_memory_files() | .memory/ 目录 | 记忆对象列表 | 扫描文件、解析 frontmatter 和正文 |
| select_relevant_memories(messages) | 当前消息历史 | filename 列表 | 根据最近用户消息选择相关文件 |
| load_memories(messages) | 当前消息历史 | 一段字符串 | 读取选中文件正文并包装成待注入文本 |

select_relevant_memories() 内部会调用 list_memory_files()；load_memories() 再调用选择函数和 read_memory_file()。这里没有暴露给模型使用的 memory tool，都是 Harness 内部的 Python 函数；选择阶段额外调用一次 LLM，称为 side-query。

### 2.3 选择范围与注入位置

🔴 **已验证理解**：一次新的 CLI query 会启动一个顶层 agent_loop()，在进入主模型调用前选择相关 Memory。

需要区分两个“最近”：

- 选择依据：最近最多 3 条 user message，并截取最多 2000 个字符；
- 注入位置：当前这次请求对应的最后一条 user message。

当前代码不是每个工具调用轮次都重新选择 Memory；一次顶层 agent_loop() 内，load_memories() 只在内部 while 循环开始前执行一次。

## 三、Memory 文件模型

每条记忆是一个 Markdown 文件，包含 YAML frontmatter：

~~~
---
name: user-preference-tabs
description: User prefers tabs for indentation
type: user
---

User prefers using tabs, not spaces, for indentation.
~~~

四种教学分类：

| 类型 | 含义 | 示例 |
| --- | --- | --- |
| user | 用户偏好或个人事实 | 使用 tab，不使用空格 |
| feedback | 用户对 Agent 行为的纠正 | 不要 mock 数据库 |
| project | 当前项目背景或事实 | auth 重写由合规需求驱动 |
| reference | 外部资料或排查入口 | bug 在某个工单系统中 |

MEMORY.md 是目录索引，通常只有：

~~~
- [user-preference-tabs](user-preference-tabs.md) — User prefers tabs for indentation
~~~

索引行不保存完整正文，也不保存全部 frontmatter。正文和类型仍在单独文件中。

slug 是适合放进文件名的短标识，例如：

~~~
User Preference Tabs → user-preference-tabs.md
~~~

当前实现只做了基础替换，不等于完整的文件名安全校验；相同 slug 会导致后一次 write_text() 覆盖前一个文件。

.transcripts 与 Memory 不同：它是上下文压缩前的会话记录，供调试、审计或人工恢复参考。transcript 可以理解为“会话流水记录”。

## 四、加载流程

### 4.1 列出记忆

list_memory_files() 扫描 .memory/*.md，跳过 MEMORY.md，读取每个文件并返回：

~~~
{
    "filename": "user-preference-tabs.md",
    "name": "user-preference-tabs",
    "description": "...",
    "type": "user",
    "body": "...",
}
~~~

### 4.2 选择相关记忆

选择阶段只把 name + description 组成 catalog，不把所有正文发送给选择 LLM：

~~~
最近的用户消息 + Memory catalog
    → side-query LLM
    → JSON 数组，例如 [0, 2]
    → 根据数组位置映射为 filename
~~~

位置索引容易让模型返回结构化结果，但它不是稳定 ID；文件增删后位置可能变化。生产实现更适合使用稳定的 memory_id 或经过校验的 filename。

如果 side-query 抛异常或没有找到数组，教学代码会降级为关键词匹配。关键词策略只是：按空白切分、保留长度大于 3 的片段，再对 name + description 做子字符串匹配；它不是 Embedding 检索，中文召回能力较弱。

还要注意：合法的空数组 [] 表示“没有相关记忆”，当前代码不会继续使用关键词 fallback；越界索引也可能直接得到空结果。

### 4.3 读取并注入正文

load_memories() 根据选择结果读取完整文件内容，拼成带有：

~~~
<relevant_memories>
...
</relevant_memories>
~~~

的 XML-like 普通文本。它不是经过 XML 解析的真正 XML。之后 agent_loop() 会把这段文本拼到当前 user message 前面，再调用主 LLM。

## 五、写入、去重与整理

### 5.1 记忆提取

当前代码只有在模型结束本轮、不再请求工具时才调用 extract_memories()：

~~~
if response.stop_reason != "tool_use":
    extract_memories(pre_compress)
~~~

因此：

- 中间工具调用轮次不会提取；
- API 失败、JSON 解析失败或空数组通常不会新增记忆；
- 写入过程中出错，仍可能出现部分更新；
- 提取使用的是压缩前快照，不一定包含刚生成的最后一条 assistant 回复。

messages[-10:] 表示最近 10 个 Message 对象，不是 10 个完整对话轮次。这个数字是控制 side-query 输入长度和成本的教学启发式，不是固定技术标准。

### 5.2 去重与更新

existing_desc 只把已有记忆的名称和描述交给 LLM，属于软性去重提示，不是程序级的确定性去重。

当前写入行为：

~~~
相同 slug → 覆盖原文件
不同 slug → 新增文件
~~~

代码没有独立的 update_memory()、delete_memory() 或正文冲突检测接口；是否输出相同名称，主要依赖 LLM 的判断。

### 5.3 Consolidation / Dream

consolidate_memories() 会让 LLM 返回一个整理后的新集合，目标包括：

- 合并重复记忆；
- 删除过期或冲突记忆；
- 控制总数量；
- 优先保留重要用户偏好。

这里的 Dream 是对“低频整理记忆”过程的称呼，不是一个新的存储类型。

当前教学实现的实际流程是：

~~~
LLM 返回新集合
    → 用 Path.unlink() 删除旧记忆文件
    → 写入新文件
    → 由 write_memory_file() 重建索引
~~~

Path.unlink() 的作用就是删除文件。旧文件在新文件完全写成功前就被删除，因此可能出现数据丢失、部分写入或索引不一致。若 LLM 返回空数组，旧文件会被删除，但当前代码可能不会重新构建 MEMORY.md。

## 六、与 s08 上下文压缩的关系

Memory 和 Session/Context 不是同一个东西：

| 机制 | 主要作用 | 生命周期 |
| --- | --- | --- |
| s08 Context Compact | 缩短当前请求的历史 | 当前 Session |
| Session memory | 帮助当前会话跨 compact 继续 | 单个 Session |
| s09 Memory | 保存未来会话仍可能有用的信息 | 跨 Session |
| Transcript | 保存压缩前记录 | 磁盘记录，不自动注入 |

s08 的压缩骨架仍在 s09 中：

- snip_compact()：按 Message 粒度裁掉中间历史；
- micro_compact()：保留最近 3 个 tool_result block，更早且超过 120 字符的结果变成不可自动恢复的占位符；
- persist_large()：将超大的 Tool Result 保存到 .task_outputs/tool-results/<tool_use_id>.txt，保留路径和预览；
- compact_history()：先写 transcript，再用一条摘要消息替换活跃历史；
- reactive_compact()：API 报上下文过长后，摘要旧历史并保留最近几条消息，最多重试一次。

CONTEXT_LIMIT = 50000 是字符数阈值，estimate_size() 使用 len(str(msgs))，不是精确 Token 计数。因此 API 实际报错后的 reactive compact 仍然必要。

## 七、这次学习中犯过的错误

1. 把 MEMORY.md 索引和完整 Memory 正文都理解成 SYSTEM prompt 内容；校准为“索引进 SYSTEM，正文进当前 user message”。
2. 把 list_memory_files() 的扫描逻辑写进 load_memories()；校准为“扫描、选择、读取”三个阶段。
3. 把最近 3 条 user message 简化成 message[-3:0]；实际需要筛选 user role，并且最多收集 3 条用户消息。
4. 认为选择阶段可能提供 memory tool；实际上是内部 Python 函数和一次 LLM side-query，不在 TOOLS 中。
5. 认为关键词 fallback 可以理解“web 项目”等语义；实际只是空白切分后的简单子字符串匹配，中文效果较弱。
6. 认为 existing_desc 能完成去重；实际只是给 LLM 的软性提示。
7. 认为示例只会新增记忆；实际相同 slug 会覆盖文件，但没有可靠的显式更新语义。
8. 没有一开始看到 unlink()；它会直接删除旧文件，而当前 consolidation 不是原子替换。
9. 把 messages[-10:] 理解成 10 个对话轮次；实际是 10 个 Message 对象。
10. 把每个内部工具轮次都理解成会重新匹配 Memory；实际一次顶层 agent_loop() 只在开始时选择一次。

## 八、修正后的核心伪代码

~~~
list_memory_files():
  扫描 .memory/*.md，跳过 MEMORY.md
  读取文件内容，解析 frontmatter 和正文
  返回 memory 对象列表

select_relevant_memories(messages):
  files = list_memory_files()
  recent = 最近最多 3 条 user message
  catalog = 每个文件的 name + description
  让 side-query LLM 返回相关文件的索引数组
  如果调用或解析失败，使用简单关键词 fallback
  把合法索引映射成 filename 列表

load_memories(messages):
  selected = select_relevant_memories(messages)
  读取 selected 中每个 filename 的完整正文
  返回带 relevant_memories 边界的文本

agent_loop(messages):
  memory_text = load_memories(messages)
  system = build_system()  # 只把 MEMORY.md 索引放进 SYSTEM
  将 memory_text 拼到当前 user message 前面
  调用主 LLM
~~~

## 九、已补充的生产级考量

详细学习任务见 W-2026-008：Memory 生产实践与生命周期治理。本章目前先记录入口和关键意识。

### 写入和整理门控

文件数达到阈值只是教学简化。生产系统还应考虑：

- 时间间隔和冷却时间；
- 最近修改过的会话数量；
- 扫描节流；
- 并发整理任务；
- 失败退避和后台执行。

### 评测指标

10 条消息是启发式参数，需要通过 Eval 验证。至少关注：

- 重要记忆召回率；
- 记忆精确率；
- 重复记忆率；
- 过期记忆率；
- 冲突率；
- Token、成本、延迟和 side-query 失败率。

评测不能只看最终回答，还要检查提取、选择、注入和后续工具轨迹。

### 一致性、恢复和安全

生产实现需要考虑：

- 文件锁或单写者队列；
- 临时目录完整写入后再原子替换；
- 备份、版本号和内容 Hash；
- unlink() 后崩溃的恢复；
- 空结果、非法 JSON 和部分写入；
- TTL、过期、用户更正和删除；
- 隐私、敏感信息脱敏、租户隔离和审计；
- Memory 正文中的 Prompt Injection；
- Memory 读取权限不能由 LLM 的相关性选择代替。

## 十、掌握状态与第十章准备度

### 已掌握

- 能解释索引和正文的不同注入位置；
- 能区分 list_memory_files()、select_relevant_memories() 和 load_memories()；
- 理解最近 3 条用户消息用于选择，当前 user message 用于注入；
- 理解 side-query、关键词 fallback 和返回 filename 的关系；
- 理解提取只在最终工具轮结束后尝试；
- 理解同 slug 覆盖、unlink() 删除和 consolidation 的批量替换风险；
- 能把 Memory 与 Context Compact、Transcript 区分开。

### 尚待验证

- 构造超过上下文阈值的长历史，验证 memory_turn 在压缩后是否可能失效；
- 运行多轮实验，观察 Memory 文件、索引、召回和提取结果；
- 独立写出 selection/load 的 5 行伪代码；
- 启动 W-2026-008，系统学习 Memory 的生产治理。

### 是否可以开始 s10

可以开始 s10。理由是 s09 的基础机制和代码主链路已经理解，剩余内容属于生产级扩展，不阻塞下一章。W-2026-008 保持 ready，以后可以单独启动，不需要把它混入 s10 的基础学习。
