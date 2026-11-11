# 1. OpenClaw

这边比较全的一个Memory模块

[](./openClaw的记忆.md)

# 2. Claude Code 的 Auto Memory

`https://code.claude.com/docs/en/memory#how-it-works`

就是换了种memory的加载方式和存储方式 ， 渐进式加载的方式

Claude Code 的 MEMORY.md 是一份带摘要的目录。
每条通常是一行「标题 + 文件链接 + 一句话摘要」，详细记忆放在同目录的其他 .md 文件里。
因为摘要也会随目录加载，有些偏好看这一行就知道了，需要细节时才打开对应文件

在harness中需要额外多提示一些内容就
告诉Agent让他自行对记忆进行分类、自行按需要加载需要的记忆、每个记忆文件需要有头部的name和desc等信息

具体例子在 [claude的memory示范](./claude的memory示范/)：
索引是 [MEMORY.md](./claude的memory示范/MEMORY.md)
其中一条正文是 [user_role.md](./claude的memory示范/user_role.md)。

# 3. Codex 的 rg 检索方式

找某个文件、某个目录里面有关键词的行

某个输出
```bash
`rg -n -g '*.md' 'pnpm' .`

memory\preferences.md:12:新项目默认使用 pnpm。
```

# 4. Codex 的记忆补救措施

每个会话都有自己的子memory，存在 rollout_summaries/ 里
既参与主Memory的补偿机制，也参与当前session的记忆检索

解决的问题是， 对话A中，相关的记忆Agent没记下来
所以需要一定的补救措施

Codex的行为是，在新开一个对话进行对话的时候，
会检查所有不活跃（超过6小时）的session，然后对session的关键数据进行一次LLM检查并且和记忆进行对比

当然还需要去重，检查过的就不检查了，可以对比 session update time 和 session compare time

然后分为两阶段

1. 第一阶段重看会话 A。 
Harness 把筛选后的用户消息、助手回复等记录交给模型，生成 A 的会话摘要。这一步主要回答「这次发生了什么，哪些信息以后可能有用？」

2. 第二阶段对照旧记忆
Harness 先把选中的会话摘要写入 rollout_summaries/，每条会话对应一个 Markdown 文件。整理 Agent 先看哪些摘要文件发生了变化，再按需读现有的 MEMORY.md 和相关会话摘要，判断该保留、补充还是更正哪些内容，最后更新供新会话加载的 MEMORY.md。


# 5. Codex 的跨对话记忆兜底机制

openclaw有些记忆，记了，但是太散，分散在 主memory 和 各个daily记忆

针对于这种分散的情况，跨对话的也有兜底机制

先逐会话提取，再跨会话整理。 Codex 在同一轮后台任务里等第一阶段处理完这一批会话，才尝试启动第二阶段。

上面的记忆补救措施，拿到了每个会话的滚动记忆
但是并不是单个子记忆就更新总记忆
汇总在一起在更新 memory md

# 6. Tencent 的多层记忆模型

有个独特的点，甚至没有write memory 工具了
