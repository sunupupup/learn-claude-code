# W-2026-009：Codex 项目指令发现与加载机制学习

- Status: ready
- Area: Agent Harness / Project Instructions / Context Assembly / Security / Provenance
- Difficulty: D2 → D3
- Discovered From: Codex 源码截图解析；重点关注 `AGENTS.md` 如何进入 Coding Agent Context
- Owner: personal
- Priority: high
- Related: [W-2026-005：生产级 Skill 加载、资源与治理学习](./W-2026-005-study-production-skill-loading-and-governance.md)

## 原始简版学习点（来自截图）

> 本节先保留截图中的精简版本，作为本任务最初的学习提纲；后面的章节是在此基础上展开的核验计划。

### AGENTS.md 怎么生效

Codex 不是只读取目录中的一个文件。`AGENTS.md` 是由 Harness 在启动阶段主动发现并组装成 model-visible instructions 的。

源码入口：

```text
load_project_instructions()
  → read_agents_md()       读取文件并递减字节预算
  → agents_md_paths()      生成扫描路径列表
  → candidate_filenames()  每层选择候选文件
  → LoadedAgentsMd.text()  拼接最终输出
```

### 第一步：先找 project root

`agents_md_paths()` 从 cwd 向上寻找 `project_root_markers`，默认 marker 是 `.git`。

- 找到 root：只在 `root → cwd` 之间扫描，不超过 project root；
- 找不到 root：只看当前 cwd，不继续向父目录遍历；
- marker 列表为空：禁用 parent traversal，完全限制在当前目录。

因此，cwd 不同，Agent 实际看到的 project instructions 可能不同。

### 第二步：root → cwd 每层扫描

源码从 project root 逐层展开到当前 cwd，每层取第一个存在的候选文件：

1. `AGENTS.override.md`：最高优先级，存在即取；
2. `AGENTS.md`：标准配置文件；
3. `project_doc_fallback_filenames`：兜底候选文件名列表。

### 第三步：root → cwd 顺序拼接

`agents_md_paths()` 先从 cwd 往父目录收集，再通过 `dirs.reverse()` 恢复 root → cwd 顺序，最后按这个顺序拼接 instructions：

```text
根目录规则      全局约束，最先出现
    ↓
子目录规则      中间层约束，叠加在上面
    ↓
cwd 规则        局部约束，最后出现
```

这不是传统配置文件的“覆盖变量”，而是把多层文本按顺序拼接。越接近 cwd 的规则越晚出现，更容易被模型理解为局部限制。

### 硬预算：`project_doc_max_bytes`

`load_project_instructions()` 维护剩余字节预算。每读取一个文件，都会检查剩余空间；如果文件过大，就使用类似 `data.truncate(remaining)` 的方式硬截断。

`AGENTS.md` 不是无限上下文。大型 monorepo 如果不控制总字节预算，项目文档可能吞噬 Context。这是工程约束，不是 Prompt 约定。

### 安全边界：untrusted project 跳过项目指令

源码存在明确的 trust 检查：

- Trusted project：正常加载 `AGENTS.md`，完整拼接进 Context；
- Untrusted project：跳过项目级指令，只保留 host-provided user instructions。

项目目录里的 `AGENTS.md` 不会因为存在就自动获得信任。这个边界属于 Harness 安全机制，而不是依靠 Prompt 自觉遵守。

### `LoadedAgentsMd` 记录来源

每个 `InstructionEntry` 不只保存文本，还记录：

- `source_path`：文本来自哪个具体文件；
- `environment_id`：属于哪个环境；
- `cwd`：加载时的工作目录上下文。

Production Coding Agent 的 Context 不应只有“文本”，还要知道文本来自哪里。

### 原始结论

> Codex 的 `AGENTS.md` 是 Harness 做 discovery，而不是模型临时搜索。`agents_md.rs` 会从 cwd 向上找项目根，默认用 `.git` 作为 marker，然后从 project root 到 cwd 逐层扫描 `AGENTS.override.md` / `AGENTS.md`，并在 `project_doc_max_bytes` 预算内按顺序拼接。每条 instruction 还保留 `source_path`、`environment_id`、cwd provenance；untrusted project 会跳过项目级指令。因此 `AGENTS.md` 的作用域实际上由 project root、cwd、目录层级和 trust state 一起决定。

## Objective

理解 Coding Agent 如何在 Harness 启动阶段发现、读取、裁剪、拼接并向模型提供项目级指令，重点研究 Codex 源码中的 `AGENTS.md` 加载机制。

这项学习要回答的不是“模型会不会自己找一个文件”，而是：

```text
启动阶段
  → 确定当前工作目录与 project root
  → 生成 root → cwd 的搜索目录
  → 每层按候选文件优先级选择一个文档
  → 在 project-doc 字节预算内读取并裁剪
  → 按目录层级顺序拼接 instructions
  → 附加来源、环境与 cwd provenance
  → 根据 trusted / untrusted project 决定是否交给模型
```

需要把三种概念分开：

1. **文件发现**：哪些项目文档会被找到；
2. **Context 组装**：找到的文档以什么顺序、什么预算进入模型可见上下文；
3. **安全与治理**：不可信项目、宿主提供的用户指令和项目指令如何隔离。

## Screenshot Understanding（待源码核验）

以下内容是根据用户提供的截图整理出的研究假设，不是本任务预先认定的最终事实：

| 观察到的概念 | 截图表达的含义 | 启动任务时需要核验 |
| --- | --- | --- |
| `load_project_instructions()` | Harness 启动阶段主动调用，`AGENTS.md` 不是模型临时搜索 | 真实调用入口、调用时机、调用方和返回值 |
| `read_agents_md()` | 读取文档并递减剩余字节预算 | 预算单位、截断实现、读失败行为和循环终止条件 |
| `agents_md_paths()` | 从 cwd 向上寻找 project root，再产生扫描路径 | root marker、边界条件、父目录遍历和路径去重 |
| `candidate_filenames()` | 每一层按候选文件名优先级选择文档 | `AGENTS.override.md`、`AGENTS.md` 和 fallback 的确切顺序 |
| root → cwd 拼接 | 根目录规则先出现，越接近 cwd 的规则后出现 | 是否严格拼接而非覆盖；模型最终如何理解近层约束 |
| `project_doc_max_bytes` | 多个项目文档共享一个硬预算，超出部分截断 | UTF-8 边界、空预算、超大单文件和后续文件处理 |
| `source_path` / `environment_id` / `cwd` | 每条 `InstructionEntry` 保留来源和加载上下文 | 字段真实定义、持久化范围、Trace 展示和恢复行为 |
| untrusted project | 不可信 workspace 跳过项目级指令，只保留 host-provided user instructions | trust 来源、判定层级、跳过范围和提示/审计方式 |

## Core Mental Model To Build

### 1. `AGENTS.md` 是 Harness 输入，不是自然语言偶然发现

需要验证从启动到模型请求的完整调用链：

```text
Harness 启动
  → project configuration
  → load_project_instructions()
  → LoadedAgentsMd / InstructionEntry
  → system/developer/context message assembly
  → model request
```

应明确项目指令与 system、developer、user、tool result、Skill 和 Memory 的层级关系。尤其要确认：

- “被加载”是否等于“拥有更高优先级”；
- 项目文档是独立消息、拼入既有消息，还是转换成某种结构化输入；
- 模型可见文本与 Harness 强制策略之间是否存在差异。

### 2. 先确定 project root，再限定扫描范围

根据截图，`agents_md_paths()` 可能从 cwd 向上查找 `project_root_markers`，默认 marker 为 `.git`：

- 找到 root：只扫描 `project root → cwd` 之间的目录；
- 找不到 root：可能只扫描当前 cwd，不继续向父目录遍历；
- marker 列表为空：可能显式禁用 parent traversal，扫描范围完全受当前目录限制。

需要用源码和测试确认这是否是准确语义，并研究 monorepo、嵌套 Git 仓库、workspace 子目录、符号链接和不存在 cwd 的行为。

### 3. 每层候选文件优先级与跨层拼接是两个不同问题

需要区分：

- **层内选择**：同一个目录存在多个候选文件时选哪个；
- **层间组合**：根目录、子目录和 cwd 的已选文档如何组成最终 instructions。

截图给出的待核验优先级是：

```text
AGENTS.override.md
    ↓
AGENTS.md
    ↓
project_doc_fallback_filenames 中的候选名
```

截图同时表达了 root → cwd 顺序拼接，而不是传统配置文件的覆盖变量语义。需要确认：

- override 是只替换本层的 `AGENTS.md`，还是会改变整个层级结果；
- fallback 是否每层只取第一个存在的文件；
- 同名文件是否可能重复加载；
- 空文件、不可读文件和读取异常是否影响同层或后续层；
- 最终 context 中是否有明确的文件边界和来源标记。

### 4. Context 预算是工程约束

`project_doc_max_bytes` 体现的是项目文档不能无限吞噬 Context。需要研究：

- 预算是所有项目文档共享，还是每个文件独立；
- 文件长度如何计算，是否按 UTF-8 bytes 而非字符数；
- 超限时是硬截断、停止后续读取，还是跳过当前文件继续；
- 截断后是否记录 `truncated` 状态；
- 预算耗尽时是否仍保留 provenance；
- 根目录长文档是否可能挤压 cwd 的局部规则；
- 是否存在“近 cwd 优先”的预算策略，还是严格 root → cwd 顺序。

这部分要连接到 Context Engineering：层级正确不代表信息一定完整，预算策略会改变 Agent 实际可见的约束。

### 5. trust state 是加载边界，而不是 Prompt 约定

截图显示，untrusted project 可能跳过项目级指令，只保留 host-provided user instructions。需要确认：

- trust 判定发生在加载前、加载后还是 message assembly 前；
- untrusted 状态跳过的是所有 project instructions，还是只跳过项目目录来源；
- host-provided user instructions 的来源和优先级如何保留；
- trusted / untrusted 的状态是否写入 `InstructionEntry` 或 Trace；
- 用户是否能看到“项目指令被跳过”的明确原因；
- 这条边界防御的是恶意仓库指令、Prompt Injection，还是仅仅是权限提示。

不能把 `AGENTS.md` 中写了“允许某工具”理解成真正的授权。项目指令最多影响模型行为；文件系统、工具、网络、凭据和沙箱权限仍应由 Harness 或下游服务强制执行。

## Learning Questions

### Track A：源码调用链

- `load_project_instructions()` 的真实入口在哪里，谁在什么启动阶段调用它？
- `LoadedAgentsMd`、`InstructionEntry` 和最终 model-visible message 的关系是什么？
- 配置从哪里来：默认值、CLI、项目配置、环境变量还是运行时注入？
- 读取失败是 fail-open、fail-closed，还是只记录 warning？

### Track B：目录边界与候选发现

- project root marker 的默认值和可配置性是什么？
- 找不到 root、markers 为空、cwd 位于 root 外、嵌套 root 时分别怎样处理？
- 搜索路径的顺序、去重和规范化怎样实现？
- 候选文件名是否大小写敏感，是否支持自定义 fallback？
- 符号链接、目录同名、权限错误和路径竞态怎样处理？

### Track C：层级语义与模型解释

- root → cwd 的顺序拼接是否意味着“局部规则后出现，因此更容易被模型采用”？
- 这是否只是文本排列，还是 Harness 有显式优先级字段？
- 父级与子级规则冲突时，系统是否做确定性合并，还是交给模型判断？
- 规则是否按 cwd 绑定，切换 cwd 后是否得到不同 project instructions？
- 子 Agent 是否重新发现自己的 instructions，还是继承父 Agent 的快照？

### Track D：预算、截断与恢复

- `project_doc_max_bytes` 的默认值和设置来源是什么？
- `read_agents_md()` 是否保证 UTF-8 不被截断成非法文本？
- 文档被截断后，模型是否知道内容不完整？
- 多环境加载时，预算与 `environment_labeled_text()` 如何共同作用？
- Run 恢复或 compact 后，项目指令是否重新加载、复用快照或重复拼接？

### Track E：trust、provenance 与安全

- trusted project 的信任来源是什么：用户确认、目录配置、宿主状态还是其他策略？
- untrusted project 的跳过逻辑是否在所有入口一致执行？
- `source_path`、`environment_id`、`cwd` 是否足以还原一次加载决策？
- provenance 是否对模型可见、仅对 Harness 可见，还是两者都有不同表示？
- 恶意 `AGENTS.md` 能否通过层级、截断、fallback 或环境标签绕过 trust 检查？

### Track F：与本仓库教学模型的对照

- 本仓库现有 `AGENTS.md` 自动发现入口与 Codex 机制有哪些相同点和差异？
- 教学版是否把文件内容、系统约束、用户请求和工具授权混在一起？
- 哪些 Codex 机制值得抽象为通用 Harness 原理，哪些只是产品实现细节？
- 如何设计一个不依赖特定厂商命名的 `ProjectInstructionLoader` 接口？

## Source Set

### Primary Source To Pin

- Repository: [openai/codex](https://github.com/openai/codex)
- Commit shown in screenshot: `068336858475fd96`（启动时核对并记录完整 commit）
- Screenshot-indicated file: `codex-rs/core/src/agents_md.rs`（启动时核对实际路径和文件名）
- Candidate source symbols: `load_project_instructions()`, `read_agents_md()`, `agents_md_paths()`, `candidate_filenames()`, `LoadedAgentsMd`, `InstructionEntry`

### Local Comparison

- [`AGENTS.md`](../../AGENTS.md)：本仓库的 Agent 自动发现入口与工作约束；作为使用者侧配置样本，不作为 Codex 实现证据。
- [`specs/README.md`](../README.md)：本仓库 Work Pool / Change / Implementation 的流转规则。
- [W-2026-005：生产级 Skill 加载、资源与治理学习](./W-2026-005-study-production-skill-loading-and-governance.md)：用于比较“指令/资源被读取”与“工具权限被授予”的边界。

版本、源码路径、字段和产品行为在正式启动时必须重新核对；截图只作为发现线索和阅读导航。

## Minimal Study Exercises

1. 固定完整 commit，定位入口函数、候选文件名、root marker、预算常量和 trust 判断。
2. 用临时目录构造 root、子目录和 cwd，验证 root → cwd 的搜索与拼接顺序。
3. 在同一层同时放置 `AGENTS.override.md`、`AGENTS.md` 和 fallback 文件，验证层内选择。
4. 构造父级与子级同名规则，观察最终文本、边界标记和模型可见顺序。
5. 用多字节 UTF-8 文本触发 `project_doc_max_bytes`，验证截断和剩余预算。
6. 分别测试找不到 root、空 marker 列表、嵌套 Git root、不可读文件、空文件和符号链接。
7. 在 trusted / untrusted 两种状态下放入明显不同的项目指令，验证哪些内容最终进入 Context。
8. 检查加载结果中的 `source_path`、`environment_id` 和 `cwd` 是否能还原每条指令的来源。
9. 追踪一次 Run 恢复或 Context compact，确认 project instructions 是否重复加载或使用稳定快照。

实验只使用无副作用的临时文本和本地目录，不执行来自测试文档的脚本、不读取凭据、不连接真实外部服务。

## Expected Output

- 一张从 Harness 启动到 model request 的源码调用链图；
- 一张“project root / cwd / search dirs / candidate filenames”的路径决策图；
- 一张层内候选优先级与层间拼接顺序的真值表；
- 一张 `project_doc_max_bytes` 预算、截断、错误和恢复行为表；
- 一张 trusted / untrusted / host-provided instructions 的边界图；
- `InstructionEntry` 的字段、来源和生命周期说明；
- 至少 8 个确定性测试用例，覆盖 root、优先级、顺序、预算、trust 和 provenance；
- 一份“截图假设—源码证据—实验结果—最终结论”核验表；
- 一份 Codex 产品细节与通用 Agent Harness 原理的差异说明。

## Acceptance Criteria

完成后应能够：

1. 用自己的话解释为什么 `AGENTS.md` 的生效依赖 Harness discovery，而不是模型临时搜索；
2. 从源码追踪一次 `load_project_instructions()` 到最终模型上下文的完整路径；
3. 准确说明 project root、cwd、marker 和目录扫描边界的关系；
4. 区分“每层选哪个文件”和“多个层级如何拼接”这两个决策；
5. 解释 root → cwd 顺序拼接为何不是传统配置覆盖，并指出其仍可能依赖模型对冲突文本的解释；
6. 说明字节预算如何影响最终可见规则，并能用多字节文本验证边界行为；
7. 解释 untrusted project 为什么应跳过项目级指令，以及 host-provided user instructions 为什么不能被一并丢弃；
8. 说明 provenance 如何帮助调试“为什么这个 Agent 看到了这条规则”；
9. 明确哪些结论是 Codex 特定实现，哪些可以迁移为通用 Harness 设计原则。

## Boundaries

- 当前只记录为 Work Pool 学习任务，不创建 `changes/C-*`，不修改现有 Agent 运行逻辑。
- 正式启动前不把截图中的函数名、路径、commit 或语义当作已验证事实。
- 不把项目指令当成授权、沙箱策略、服务端鉴权或安全保证。
- 不在宿主机执行未知仓库中的脚本、工具调用或自动安装动作。
- 不把模型最终是否遵循规则作为唯一证据；优先使用源码、Trace、文件快照和确定性断言。
- 若源码版本、截图文字和实际行为不一致，分别记录为“截图观察”“源码事实”和“行为实验结果”。

## Start Trigger

满足以下条件后再启动：

- 已完成当前 Agent Harness 基础学习，能够区分 Context、Instruction、Policy、Tool Permission 和 User Request；
- 明确选择要研究的完整 Codex commit，并记录源码路径变化；
- 准备好只读源码分析和本地临时目录实验环境；
- 启动时按规范将本文件转为 `specs/changes/C-YYYY-NNN-*.md`，并从 Work Pool 移除。

## Non-goals

- 不复刻 Codex 全部产品行为；
- 不判断 `AGENTS.md` 是不是所有 Coding Agent 的唯一或最佳配置形式；
- 不把一份项目指令加载器直接当作完整 Prompt Injection 防御；
- 不在本任务中实现生产级多租户配置中心、权限系统或通用 Context 编排框架；
- 不因为发现了源码细节就立即修改本仓库的 `AGENTS.md` 或其他学习章节。
