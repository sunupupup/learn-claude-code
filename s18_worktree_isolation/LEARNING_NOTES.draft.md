# s18 Worktree Isolation — 前置问题存档

> 本文件保留学习前的原始疑问与当时的猜想，不代表最终结论。
> 术语、纠正、代码证据与掌握状态统一维护在 [正式学习笔记](LEARNING_NOTES.md)，原先重复的结论已归并到该文件。

## 1. 我的前置问题

### 1.1 同任务、同文件，为什么要多个 worktree？

我在 `code.py` 开头写下：

> 从上一章可知，很多 **teammate**（持久队友）可以领取任务干活，但是会出现 A 和 B 同时修改同一个文件的情况，这就会用到 **git worktree**（Git 工作树）来进行 **Isolation**（隔离）。
>
> 但我总感觉有点不合理：如果在同一个任务中，就算是多个 teammate 在修改同一个文件，那也不可能拆分多个 worktree 啊。worktree 的目的，不应该是多个 agent 开发多个不相干的功能才有意义么？同一个 agent 在开发任务的时候，同个文件还得开多个 worktree，合理么？

### 1.2 日常里从没见过「每个 subagent 各开一个 worktree」

README 举例是 Alice 重构认证、Bob 重构 UI 登录页——但我实际用主 agent 派 **subagent**（一次性子 Agent，s06）时，顶多主 agent 自己开一个 worktree 开发，子 agent 并不会各自专门搞 worktree。这是不是常态？

### 1.3 并行队友的 worktree 是不是对用户无感、偷偷合并？

如果真发生「并行 **teammate** 各开 worktree」这种极端情况，是不是 **harness**（Agent 运行框架）在后台构造对用户无感的 worktree，干完再偷偷 **merge**（合并分支）？这和主 agent 的 worktree（**session** 级持久、不默认删除）是不是不一样？

### 1.4 如果让我设计：多 worktree 完成后怎么合并？

我设想若 teammate A 和 teammate B 都改了同一份文件，流程可以是：

```text
Teammate A (worktree A) → task done
Teammate B (worktree B) → task done
Lead（协调者）: check_temp_worktree_task
Lead: merge_worktree（合并现存的几个 worktree）
```

在这个例子里，合并似乎就是 **两次 `read_file` + 一次 `write_file`**（LLM 读两份再写一份）。这样设计合理么？

### 1.5 临时 worktree 与「一般只有一个 worktree」

综合前面讨论，我现在的理解是：

- teammate 开 worktree **是允许的**，但需要有专门的 **merge task**（集成任务）来保证 **Integration**（集成）；
- 临时 worktree 好理解了——它是并行「执行车道」，不是终点；
- 我之前看到的 worktree，一次 **session** 或任务 **一般只有一个**，除非用户特殊强调要多开。

---

## 校准入口

- 同一目标是否可以有多个 worktree、集成是否必须叫 merge task：见正式笔记第 2 节。
- “两个 read 加一个 write”、合并成功与业务正确：见正式笔记第 6 节。
- 产品默认行为及“通常只有一个”的经验猜测：见正式笔记第 7 节，尚未逐产品核验。
