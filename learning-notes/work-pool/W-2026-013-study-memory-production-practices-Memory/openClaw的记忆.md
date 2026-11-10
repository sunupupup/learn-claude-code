# 概览

| 环节 | 要查清楚的实际问题 |
|---|---|
| **1. 存储** | 哪些文件保存记忆正文？会话日志、SQLite 索引和缓存分别存什么？如果使用远程嵌入服务，哪些内容会发出去，哪些数据能确认保存在外部？ |
| **2. 写入与更新** | 用户说「以后默认用 pnpm」时，是模型决定写文件，还是程序自动提取？接近上下文压缩时，谁触发记忆保存，谁实际落盘？写的是一条新记录，还是会修订旧记录？ |
| **3. 索引与同步** | Markdown 写完后什么时候能搜到？文件修改或删除后，索引怎么跟上？如果索引坏了，能不能根据原文件重建？ |
| **4. 注入与检索** | 哪些内容在首轮就进入上下文？哪些只在模型调用记忆工具后返回？提示词怎么引导模型决定何时查，工具又返回整份文件还是带路径和行号的片段？ |
| **5. 冲突与遗忘** | 「默认 pnpm」和「项目甲那天临时用了 npm」可以同时成立。如果后来明确说「以后改用 npm」，系统会改写旧偏好、保留两条让模型判断，还是有程序规则处理？删除一条记忆后，旧日志或索引还能不能找到它？ |

# 1. 存储

1. 长期记忆：~/.openclaw/workspace/MEMORY.md

2. 每日记忆：~/.openclaw/workspace/memory/YYYY-MM-DD.md

3. 搜索索引：~/.openclaw/memory/<agentId>.sqlite

4. 会话记录：~/.openclaw/agents/<agentId>/sessions/<SessionId>.jsonl

## 1.1 长期记忆

既可以放入 MEMORY.md 的正文，也有一段单独的 Memory Recall，告诉模型什么时候主动查记忆

下面是真实OpenClaw的 system-prompt.ts 文件的内容
有个单独的memory call模块
告诉Agent在干某些事（涉及到工作、决定、日期、人物）之前，必须先调用 memory_search 搜索 MEMORY.md 和 memory/*.md
再用 memory_get 只读取需要的几行。如果查过之后仍然没有把握，就告诉用户你已经查过了。

```
## Memory Recall
Before answering anything about prior work, decisions, dates, people, preferences, or todos: rumemory_search on MEMORY.md + memory/*.md; then use memory_get to pull only the needed lines. If loconfidence after search, say you checked.
```

这个是系统提示词藜麦对于 Memory 功能的说明

初次之外，memory的内容也会被注入到system prompt中
一组约定好的工作区 Markdown 文件，比如 SOUL.md、`USER.md`、`IDENTITY.md`、`MEMORY.md`，拼进系统提示词的 Project Context
（防止字符太长，会设置 20000 chars 的字数上限，进行截断处理）

那这么看来
还没启动 system prompt 可能就 接近 10w chars 了
大概 2-3w token

# 2. 写入部分


写记忆，其实就是写工作区的markdown

模型判断要记什么、写到哪个文件，再调用普通的 write 或 edit

`写入规则`: 
OpenClaw作为本地Agent，有个独立的Agent.md 所以模型从工作区的 AGENTS.md 知道「什么时候记、记到哪」
如果是云端的，那就只能写在system prompt了

关于两种记忆的描述 agent md 里面也有
Daily notes: memory/YYYY-MM-DD.md (create memory/ if needed) — raw logs of what happened
每日笔记：memory/YYYY-MM-DD.md（创建内存/ 如需要）——发生事情的原始日志
Long-term: MEMORY.md — your curated memories, like a human's long-term memory
长期：MEMORY.md——你精心策划的记忆，就像人类的长期记忆一样


记忆正文用通用的 write / edit 写入，SQLite 搜索索引由记忆管理器另行同步。

记忆的写入会同时更新相关的数据库索引数据
1. 文件工具改 Markdown。 edit 完成后，磁盘上的正文已经更新。人手动改这个文件，也可以触发后面的索引同步。 文件工具注册
2. 记忆管理器更新 SQLite。 启用文件监听时，它会检测索引范围内文件的新增、修改和删除，并在短暂延迟后触发同步。普通工作区文件如果不在记忆索引范围内，就不会因此进入记忆库。 监听逻辑 · 同步触发

其实就是写完了，不管了，然后记忆管理器，先准备好新片段和向量，再删旧索引、写新索引，只改一行也会替换这份文件的整组索引片段

有个问题，在记忆管理器那边 如果删除了之后，写新索引失败了怎么办 ？

会有兜底机制

其实每次写的时候，都会对比全量的 sqlite files 表

这里补充一下 
sqlite 一般会有两张表 

1. files 表：一份文件一条记录，存路径、来源类型、内容哈希、修改时间和大小。同步时用这里的哈希判断这份文件是否需要重新索引。
2. chunks 表：一个片段一条记录，存片段正文、向量、文件路径和起止行号。`memory_search` 返回的就是这类片段。 SQLite 表结构

每次都会将 files 对比 全量的本地的 md 文件

这时候，会再次刷一遍脏数据

# 3. 索引和同步

就是在 write edit 的时候完成的 


# 4. 检索部分

俩memory的工具
| 工具 | 模型传什么 | Harness 做什么 |
|---|---|---|
| `memory_search` | `query`，可选 `maxResults`、`minScore` | 在配置好的记忆来源里搜索，返回相关片段、路径、行号和分数。内置后端走 SQLite，按配置可结合向量与关键词搜索。 |
| `memory_get` | `path`，可选 `from`、`lines` | 读取指定记忆文件的正文，可以只取某个行段。适合核对命中片段的原文和上下文。 |

## memory_search

memory_search搜的是本地 SQLite 里的索引 （SQLite 是关系型数据库，同时可以通过扩展支持向量搜索）

search部分的代码

可以看到分为关键词检索和向量检索

- 关键词检索主要看重 关键词的匹配，SQLite FTS5 的 MATCH，用 BM25 排序

- 向量检索，查询和记忆片段像不像，可以理解为语义

```ts
    const keywordResults = hybrid.enabled
      ? await this.searchKeyword(cleaned, candidates).catch(() => [])
      : [];

    const queryVec = await this.embedQueryWithTimeout(cleaned);
    const hasVector = queryVec.some((v) => v !== 0);
    const vectorResults = hasVector
      ? await this.searchVector(queryVec, candidates).catch(() => [])
      : [];

    if (!hybrid.enabled) {
      return vectorResults.filter((entry) => entry.score >= minScore).slice(0, maxResults);
    }

    const merged = this.mergeHybridResults({
      vector: vectorResults,
      keyword: keywordResults,
      vectorWeight: hybrid.vectorWeight,
      textWeight: hybrid.textWeight,
    });
```

每条结果里有什么
数据库里先取出这些列，再收成统一结构：

id：这段记忆的编号，合并时用来对上同一条
path：来自哪个文件
startLine / endLine：片段在文件里的行号范围
source：来源，例如记忆文件或会话记录
snippet：片段正文，超长会被截断
score：这一路自己的匹配分，越高越好

然后重排序 mergeHybridResults

因为涉及到两类分数，一种是 vectorScore  还有 textScore

然后通过一个公式统统一起来

```ts
const DEFAULT_HYBRID_VECTOR_WEIGHT = 0.7;
const DEFAULT_HYBRID_TEXT_WEIGHT = 0.3;
const score = 0.7 * entry.vectorScore + 0.3 * entry.textScore;
```


# 5. 冲突与遗忘

记忆冲突主要由模型或人通过编辑 Markdown 处理，删除后的搜索索引由程序同步清理。


- 遗忘：让某条信息不再被当作记忆使用。

这边比较简单，直接调用 edit 工具即可

- 冲突：用户记忆内容冲突了

这边分为两种冲突 

1. 同一个 memory.md 内部自己冲突了，前后记录着 "用npm" 和 "用pnpm"

一般会根据用户的query检索出来俩内容 ，比如用户说 “帮我初始化下这个前端项目”，然后上面俩都搜出来了
这边确实会存在不确定性
所以需要和用户确认下事实，然后根据用户确认的内容，更新下记忆

2. 不同 memory 和 daily memory 冲突了

假如 memory.md 记录用户喜欢npm ，但是 daily 的记录用户喜欢pnpm
两份文件正常存下来了，单问题在于 Agent下次以哪个为准
此时，需要看

- 如果daily里面的内容，真的是长期的，那就更新 memory md
- 如果daily里面的内容，短期的，比如“临时使用npm”，那以长期记忆为准

有些零星的提示词，Agent会自行决定，怎么去更新文件、更新的内容是啥
`默认 AGENTS.md 模板建议回顾 daily、更新 MEMORY.md、移除过时内容。`

# 补：Agent md 的内容

https://github.com/openclaw/openclaw/blob/v2026.2.9/docs/reference/templates/AGENTS.md 

里面有不少内容

1. 安全性考虑：不要泄露个人隐私、不要直接执行破坏性命令、不懂就问
2. React Like a Human! 像人类一样，可以使用一些小表情和人对话
3. 定时机制，告诉llm定期来读取下最近的 daily文件和 memory 文件，并且删除相关过时的信息
4. 两种记忆文件的介绍

# 补：其他全局文件 

| 文件 | 它回答的问题 | 例子 |
|---|---|---|
| `SOUL.md` | Agent 应该**怎么说话、怎么做事**？ | 直接一点，证据不足就说明不确定。 |
| `IDENTITY.md` | Agent **是谁**？ | 名字叫「知微」，标志是 🧭。 |
| `USER.md` | Agent 在跟**谁**合作？ | 用户希望怎么称呼、如何沟通，有什么背景。 |
| `MEMORY.md` | 从过去的交互里，**哪些结论值得以后复用**？ | 用户明确确认「新前端项目默认用 pnpm」。 |
| `memory/YYYY-MM-DD.md` | **当时发生了什么**？ | 某天用户确认了 pnpm 默认值，同日排查项目甲时临时用了 npm。 |


不过说实话
这些内容，其实都可以打散，然后放到memory 或者 agent md里面

和用户强相关的内容，放memory md
和agent规范、约束，放在agent md

# 剩下来的问题

1. 写入环节

模型判断错了记忆的适用范围，将临时的记忆变成了长期记忆

2. 同步环节

有记忆数据，同步失败了，但是此时新开了个session

这边可以在新开session之前，也进行一些 脏数据 的对比，倒是还好

3. 读取环节

相关性不等于有效性

4. 遗忘环节

删除了一处，还可能有很多残留的相关记忆
下次检索还是能检索到