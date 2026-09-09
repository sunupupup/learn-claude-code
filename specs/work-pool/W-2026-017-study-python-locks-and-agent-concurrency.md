# W-2026-017：Python 锁与 Agent 并发状态治理

- Status: ready
- Area: Python / Concurrency / Agent Runtime / Shared State / Reliability
- Difficulty: D1 → D3（从 `threading.Lock` 基础进入多 Agent 共享状态、文件一致性和恢复边界）
- Discovered From: [`s14_cron_scheduler`](../../s14_cron_scheduler/README.md) 学习中对 `cron_lock`、`agent_lock`、`background_lock` 的观察，以及 [`s15_agent_teams`](../../s15_agent_teams/README.md) 学习中对 MessageBus、队友状态和共享工作区竞态的讨论
- Owner: personal
- Priority: medium

## Objective

建立一套面向 Agent Runtime 的 Python 并发控制心智模型：能够解释 `threading.Lock` 保护什么、不保护什么，判断一个共享状态应该使用线程锁、文件锁、原子状态转移、队列、数据库事务、租约还是单写者设计。

本 Work Pool 不只是学习 Python API，而是结合 s14 和 s15 回答：

- 哪些状态在多个线程或 Agent 之间共享；
- 临界区应该覆盖哪些读改写步骤；
- 如何区分线程内、进程间和跨机器的锁；
- 加锁后仍可能出现哪些消息丢失、重复执行、死锁、饥饿和崩溃恢复问题；
- Agent 的工具副作用为什么还需要幂等键、状态查询和验收证据，而不能只靠锁。

## Confirmed Starting Cases

### s14：调度和后台状态

当前教学代码中已经出现多种 `threading.Lock` 使用：

- `background_lock`：保护后台任务状态和结果字典；
- `cron_lock`：保护 `scheduled_jobs`、`cron_queue` 等调度状态；
- `agent_lock`：让 Queue Processor 同一时刻只启动一个 Agent Turn。

这些锁解决的是进程内线程之间的并发访问和 Agent Turn 串行化，不等于持久队列、分布式锁、执行租约或 Durable Execution。

同时需要观察：持久化 JSON 的读写、进程崩溃、重启去重和错过触发等问题，不能仅靠当前的线程锁解决。

### s15：团队通信和共享工作区

当前教学代码中的 `MessageBus` 使用文件追加发送消息，并通过读取后删除来消费收件箱。`read + unlink` 不是一个原子操作；多个读取者、读取与写入并发、以及进程在消费中途崩溃，都可能产生丢失或重复语义。

当前教学代码还使用 `active_teammates` 跟踪队友，并允许多个队友访问同一工作区。队友状态、任务文件和工作区文件之间的并发一致性没有由同一个锁自动解决。

README 对真实 Claude Code 文件锁的描述属于版本相关的进一步映射；启动本 Work Pool 时需重新固定版本和源码后核验，不把教程说明直接当作当前生产事实。

## Recommended Learning Order

1. **Python 线程基础**：线程、共享可变对象、竞态、临界区、`Lock`、`RLock`、`with lock`、阻塞和非阻塞获取。
2. **回到 s14**：逐个标出 `background_lock`、`cron_lock`、`agent_lock` 的保护对象、持锁范围和释放路径。
3. **状态机与原子性**：分析 `check → modify → save` 为什么不是原子操作，并用任务认领或 Cron 状态举例。
4. **回到 s15**：分析 `MessageBus.send()`、`read_inbox()`、`active_teammates` 和共享工作区的不同竞态。
5. **锁的边界**：比较线程锁、文件锁、数据库事务/CAS、单写者队列、租约和分布式锁。
6. **可靠性扩展**：加入重复投递、消息确认、崩溃恢复、幂等和副作用状态未知等场景。
7. **确定性实验**：先用 Fake Agent/Fake Tool，不接真实 LLM，验证顺序、重复、丢失、阻塞和恢复行为。

## Core Questions

- `cron_lock` 为什么可以保护进程内的 `list`，但不能保护另一个进程中的同名 `list`？
- `agent_lock` 串行化的是 Agent Turn，是否也能取消或回滚正在执行的 Tool？
- `read_inbox()` 的 `read + unlink` 临界区应该如何定义？加锁后，进程在删除前崩溃和删除后未确认分别会怎样？
- `active_teammates` 的“检查名称不存在 → 创建 → 登记”如何避免重复创建？
- 两个队友同时写同一个工作区文件时，为什么 MessageBus 的锁没有帮助？
- 什么时候应减少共享状态、指定单一 Owner，而不是继续增加锁？
- 什么时候需要 CAS、幂等键、状态查询或人工审批，而不仅是互斥锁？
- 如何区分“消息只消费一次”和“业务副作用只发生一次”？

## Expected Output

- 一张 s14/s15 共享状态、Owner、并发访问者和保护机制对照表；
- 一份 Python `threading.Lock` 最小实验，覆盖正确临界区、错误临界区和异常释放；
- 一张锁类型选择表：线程锁、文件锁、数据库事务/CAS、队列、租约、单写者；
- 一个 `MessageBus` 消费语义实验，明确 at-most-once、at-least-once 和业务幂等的差别；
- 一组确定性测试，覆盖重复认领、重复读取、消息丢失、进程崩溃和共享文件冲突；
- 一份“锁无法解决的问题”清单，连接到 W-2026-004、W-2026-006、W-2026-007、W-2026-013 和 W-2026-015。

## Success Criteria

完成后应能够：

1. 用自己的话解释锁、临界区、竞态和原子性；
2. 从 s14 和 s15 代码中准确指出至少三个共享状态及其访问者；
3. 判断当前锁的保护范围是否覆盖完整的不变量，而不是只看某一行是否加锁；
4. 解释线程锁、文件锁和分布式协调的边界；
5. 设计一个不会因重复消息或重试而重复产生业务副作用的处理流程；
6. 通过实验区分“代码静态上看起来安全”和“运行时已经被验证”。

## Why Deferred

当前先继续 s15 的 Agent Team 主线，避免把章节学习立即扩展成完整 Python 并发课程。该主题需要同时回看 s14、s15，并加入故障注入、文件系统和副作用语义，适合作为独立学习单元。

## Start Trigger

- 用户明确说“开始 W-2026-017”；
- 或明确说“开始学 Python 锁/并发 Work Pool”；
- 启动后先建立 s14/s15 的共享状态清单，再决定是否编写独立实验文件；
- 未启动前不修改 s14/s15 教学逻辑，不把当前静态风险描述成已运行验证的结论。

## Boundaries

- 当前只登记学习任务，不修改教学代码，不安装并发框架；
- 优先学习 Python 标准库和当前仓库中的真实案例；
- 明确区分线程级互斥、进程级文件协调和跨服务分布式一致性；
- 不把加锁视为权限控制、幂等、持久化、消息确认或业务验收；
- 不把教程 README 中的真实项目映射直接当成当前版本源码证据。

## Non-goals

- 不在本任务中构建通用分布式锁服务；
- 不把所有 Agent 协作问题归结为 Python GIL 或线程锁；
- 不重复承担完整 Subagent Runtime、消息注入治理或副作用安全 Work Pool 的全部内容；
- 不在没有确定性实验和证据的情况下宣称实现具备生产级并发安全。

## Related

- [`s14 Cron Scheduler`](../../s14_cron_scheduler/README.md)
- [`s14 学习笔记`](../../s14_cron_scheduler/LEARNING_NOTES.md)
- [`s15 Agent Teams`](../../s15_agent_teams/README.md)
- [`W-2026-004：生产级 Subagent Runtime`](./W-2026-004-study-production-subagent-runtime.md)
- [`W-2026-006：Tool Result 压缩、恢复与副作用安全`](./W-2026-006-study-tool-result-compaction-and-recovery.md)
- [`W-2026-007：副作用 Tool 的分层安全`](./W-2026-007-study-side-effect-tool-security.md)
- [`W-2026-013：Task Completion Verification`](./W-2026-013-study-task-completion-verification.md)
- [`W-2026-015：Agent 消息注入、插队与运行时事件交付`](./W-2026-015-study-agent-message-injection-steering.md)
