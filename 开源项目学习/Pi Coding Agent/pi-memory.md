# pi-memory：基础文件读写与注入

## 项目简介

pi-memory 是 jayzeng 维护的 Pi 社区扩展，用 Markdown 保存长期记忆、每日记录和临时清单，并将记忆内容提供给 Agent。可选的 qmd 检索留到下一模块学习。

- 项目：[jayzeng/pi-memory](https://github.com/jayzeng/pi-memory)。
- 宿主：[Pi Coding Agent](https://github.com/earendil-works/pi/tree/main/packages/coding-agent)；插件能力不等于 Pi 默认能力。

## 学习问题与范围

- 当前问题：用户说“这个项目用 pnpm”之后，谁决定写入、保存在哪里，后续请求怎样看到它？
- 范围：文件分类、`memory_write` / `memory_read`、上下文注入与刷新时机；暂不展开语义检索。
- 顺序与进度：先学本模块；已初始化，尚未验收。
- 后续：[pi-qmd：记忆检索](pi-qmd.md)；关联：[W-2026-013](../../learning-notes/work-pool/W-2026-013-study-memory-production-practices-Memory/LEARNING_NOTES.md)。

## 源码与证据

- 本地源码：[pi-memory/](pi-memory/)；与已有 `pi-long-task/` 同级，按用户指定保存在当前学习目录，仅本地阅读。
- 版本：`0.4.2`；Commit：`1e276a762a666a7031459fdf7af018cc7966663e`；读取日期：2026-10-21。
- [固定版本 README](https://github.com/jayzeng/pi-memory/blob/1e276a762a666a7031459fdf7af018cc7966663e/README.md)、[扩展入口 index.ts](https://github.com/jayzeng/pi-memory/blob/1e276a762a666a7031459fdf7af018cc7966663e/index.ts)。
- 许可证：MIT，已核对本地 LICENSE。
- 证据状态：已核对项目说明、版本与许可证；完整调用链、宿主兼容性及运行效果待验证。

# 我的笔记

## Hook 机制

### before_agent_start

将记忆插入系统提示词

记忆相关工具简介 + memory 文件介绍 + daily memory 文件介绍 + 待办 文件介绍

```js
"Use memory_read / memory_search for the authoritative latest state;  " 
"- Decisions, preferences, and durable facts → MEMORY.md",
"- Day-to-day notes and running context → daily/<YYYY-MM-DD>.md",
"- Things to fix later or keep in mind → scratchpad tool",
"- Use memory_search to find past context across all memory files (keyword, semantic, or deep search).",
```

主要分为三块内容

| 部分 | 具体内容 |
|---|---|
| **快照提示** | 当前记忆是之前加载的快照；要看最新内容，调用 `memory_read` / `memory_search` |
| **使用说明** | 长期事实存 `MEMORY.md`；日常记录存 `daily/<日期>.md`；待办用 `scratchpad`；用户说“记住”时立即写入；建议使用标签和链接 |
| **`memoryContext`** | **真正的记忆正文**，不只是文件地址 |


### session_before_compact

在压缩前干点事, 最重要的是 **刷新 memory 快照**
其他的操作似乎我们暂时看不到明显的收益 

```
收集未完成待办
    ＋
今天 daily 文件的最后 15 行
    ↓
加上时间、会话短 ID 和 Session Handoff 标题
    ↓
追加到今天 daily 文件末尾
    ↓
刷新 memory 快照
```

## Tool 机制

### memory_write

三个核心参数
- target 写到哪 enum
  - long_term 长期记忆，写到全局的memory md
  - daily 短期记忆，写到当日的md

- content 需要写的内容 string

- mode 写入的模式
  - append 追加
  - overwrite 覆写

写入的内容，如果是追加模式，直接文件末尾追加
```js 
const stamped = `<!-- ${ts} [${session_id}] -->\n${content}`;
```

因为在写入的时候，每次还得buildPreview， 看起来还有个很重要的这个
在读取的时候， 
如果是 MEMORY.md 文件， 采用 middle 模式，如果内容太长，会对中间内容用 ... 代替
如果是 daily md  文件，采用 end 模式 ，前缀用 ...， 只取末尾的max chars

这个 memory_tool 工具，工具结果是这样的
```js
{
  "content": [{ type: "text", text: `Appended to MEMORY.md${existingSnippet}` }],
}
```
新的 content 都在 tool call参数里面了，所以这边只需要加 existingSnippet 已有记忆的快照就行


!! 这个工具通过 type 的 append 和 overwrite 来减少的工具的数量，不需要专门的update


### memory_read

读取三种记忆内容
```js
"- 'long_term': Read MEMORY.md",
"- 'scratchpad': Read SCRATCHPAD.md",
"- 'daily': Read a specific day's log (default: today). Pass date as YYYY-MM-DD.",
```

### memory_forget

把一整串内容，从记忆文件中删除

memory_forget
    ↓
先把待删除内容保存到 recovery/<恢复ID>.json
    ↓
再从 MEMORY.md 或指定 daily 文件中删除
    ↓
刷新记忆快照，并返回恢复 ID

### memory_restore

恢复记忆

memory_restore({ recoveryId: "刚才的恢复ID" })
    ↓
读取恢复记录
    ↓
把缺失的内容追加回原来的文件
    ↓
刷新记忆快照

### memory_search

检索记忆，避免所有内容都塞入上下文

三个参数
| 参数 | 含义 | 示例／默认值 |
|---|---|---|
| `query` | **想找什么**，必填 | `"之前为什么选择 pnpm"` |
| `mode` | **怎么找**，可选 | 默认 `"keyword"` |
| `limit` | **最多返回多少条结果**，可选 | 默认 `5`，不是字符数或 Token 数 |

其中 mode 有三种：
- keyword：按关键词找，适合具体名称、日期、错误码。
- semantic：按意思找，措辞不同也可能找到。
- deep：结合关键词和语义检索，再重新排序候选结果。


### scratchpad

记录、更新一些待办事项
因为这个包含了很多种行为，所以tool的名字直接就是 scratchpad

参数
- action
  - ["add", "done", "undo", "clear_done", "list"]
  - add 添加一个待办事项 [ ] text
  - done 完成一个待办事项 [x] text
  - undo 重新打开一个待办
  - clear_done 把完成的事都删掉
  - list 列出所有
- text


## Memory 加载的内容

MEMORY.md   `用户的一些长期记忆，可通过 “帮我记住xxx” 来触发`
  默认用 pnpm

SCRATCHPAD.md  `用户的一些延后的事项，可通过“先把xxx记成后续待办事项” 来触发`
  [ ] 排查登录失败

daily/当天日期.md  `用户当天干的事，会经常性触发用户做的事，有点类似于audit log，和用户query强相关`
  今天调整了登录接口


SCRATCHPAD.md 是 代办
这个内容还挺格式化的， 会被解析成格式化的内存数据，代表一个个待办是否做好了

| 操作 | 作用 |
|---|---|
| `add` | 添加一项 |
| `done` | 标记完成 |
| `undo` | 改回未完成 |
| `clear_done` | 清除已完成项 |
| `list` | 查看清单 |


```markdown
- [ ] 排查登录失败
- [ ] 修复后补一个测试
- [x] 确认数据库连接正常
```


## QMD 

源码是 @tobilu/qmd 这个库

QMD 是这里的搜索引擎。记忆文件发生变化后，要同步索引，搜索才能跟上最新内容

QMD 是搜索引擎，BM25 是它在关键词搜索中使用的相关性评分算法。 两者属于不同层次：

两条基础检索路线是 BM25 关键词检索和向量语义检索；deep 再把它们结合并重排。
QMD 通过 node-llama-cpp 加载一个较小的 Embedding（向量化）模型，在本地把记忆文本和查询转换成向量，用于查找语义相近的内容。
你这份源码默认用的是 EmbeddingGemma 300M，约 3 亿参数


经常看到这三个内容 

| 操作 | 作用 |
|---|---|
| `detectQmd()` | 检查 QMD 是否可调用，**不建立索引** |
| `qmd update` | 扫描文件变化，更新文档与全文检索索引 |
| `qmd embed` | 为新增或变化的内容生成向量，供语义检索使用 |

memory_search
    ↓ 调用
QMD 搜索引擎
    ├─ keyword  → BM25 关键词检索
    ├─ semantic → 向量语义检索
    └─ deep     → 混合检索，再重排


| `mode` | 调用 QMD |
|---|---|
| `keyword` | `qmd search` |
| `semantic` | `qmd vsearch` |
| `deep` | `qmd query` |


### deep 混合检索、重排序

关于重排序

用的是 QMD 内部的行为

默认使用另一个小模型：Qwen3-Reranker 0.6B，约 6 亿参数，同样通过 node-llama-cpp 在本地运行。

```py
from sentence_transformers import CrossEncoder

model = CrossEncoder("Qwen/Qwen3-Reranker-0.6B")

query = "What is the capital of China?"
documents = [
    "The capital of China is Beijing.",
    "Gravity is a force that attracts two bodies towards each other. It gives weight to physical objects and is responsible for the movement of planets around the sun.",
]

pairs = [(query, doc) for doc in documents]
scores = model.predict(pairs)
print(scores)
# [ 7.625 -11.375]

rankings = model.rank(query, documents)
print(rankings)
# [{'corpus_id': 0, 'score': 7.625}, {'corpus_id': 1, 'score': -11.375}]

```

https://qwenlm.github.io/blog/qwen3-embedding/ 

Qwen3-Reranker 是在 Qwen3 基础模型上，针对“相关性判断”专门训练出来的模型。
官方说明它使用 LoRA 微调，并直接用高质量标注数据进行监督训练。LoRA 就是主要训练一小部分新增参数，让已有模型适应新任务

## QMD 专栏学习 

| 顺序 | 核心问题 | 学习价值 |
|---|---|---|
| 1 | **文件怎么变成索引？** 扫描哪些文件、保存什么数据、存在哪里？ | 理解“文件存在”为什么不等于“可以搜到” |
| 2 | **文件修改、删除后，索引怎样同步？** | 理解旧内容为何可能继续被搜到、新内容为何暂时搜不到 |
| 3 | **BM25 怎样处理查询并找到结果？** 中文怎样分词？ | 理解关键词检索擅长和容易遗漏的情况 |
| 4 | **长文件怎样切块、生成向量？** 查询怎样向量化？ | 理解检索粒度，以及为什么同一句话换个切法可能影响结果 |
| 5 | **关键词与向量结果怎样融合？** | 理解两路结果怎样去重、合成一个候选列表 |
| 6 | **重排拿哪些片段评分，怎样决定最终顺序？** | 理解重排的成本、候选限制和实际作用 |
| 7 | **返回的是片段还是完整正文？** 路径、分数和来源怎样保留？ | 看清搜索结果怎样回到 Agent，是否还需要继续读取原文 |
| 8 | **怎样验证真的搜得更好？** | 用同一批记忆对比命中、误匹配、延迟，避免只相信功能介绍 |

TODO 。。。 有兴趣再研究吧