# Agent Context 组织与缓存命中知识图谱

## 1. 完整技术链路

```text
用户目标 / 项目指令 / System Prompt / Tool Schema / Memory / Skill / 文件 / 对话历史
  → Harness 读取、筛选、权限检查并确定各自版本
  → 按变化频率与作用域编排 Context，确定消息与 Tool 顺序
  → 序列化为 Provider 请求（模型、设置、消息、Tools 等）
  → Provider 的 Prompt Cache 依据可复用前缀、断点和缓存策略尝试复用
  → Usage 返回 cache read / cache write / 普通 input 等统计
  → Agent 记录成本、延迟、命中比率与失效/诊断信息
  → 下一轮追加、更新、压缩或重建 Context
```

**核心直觉：**Context 组织决定请求中哪些内容重复、排列是否稳定；Provider 只按自己的规则识别可复用内容。语义相似不等于前缀相同，静态内容的存在也不保证命中。

## 2. 问题与扩展方案

| 面对什么问题 | 改变哪个环节、怎么改 | 概念或方案 | 深入入口 |
| --- | --- | --- | --- |
| 每轮重发大量相同指令和工具说明 | 固定 system prompt 与 tool catalog，让 history 只追加；按已声明原因才重建前缀 | Pinned prefix、Prompt/Prefix Cache | [CodeWhale CACHE 设计](https://github.com/Hmbown/CodeWhale/blob/main/docs/CACHE.md)；DeepSeek 官方缓存文档 |
| 工作区或用户元数据每轮小幅变更 | 识别静态/会话/请求级片段，改变装配顺序前评估语义与权限 | Context 分块、动态后缀、作用域 | [W-2026-009](../../../specs/work-pool/W-2026-009-study-system-prompt-production-context-governance.md) |
| 工具定义变化导致无法复用 | 保持 schema 和顺序稳定，明确新增/移除工具的影响 | Tool Schema 稳定性、cache breakpoint | [Goose Provider 文档](https://github.com/aaif-goose/goose/blob/main/documentation/docs/getting-started/providers.md)；Anthropic/OpenAI 官方文档 |
| 显示“缓存开启”但不知道是否命中 | 记录 Provider Usage 的 cached/write/input token 和统计分母 | 命中率口径、成本账本 | [OpenAI Usage 与诊断](https://developers.openai.com/api/docs/guides/prompt-caching/diagnostics)；[Aider 缓存统计限制](https://aider.chat/docs/usage/caching.html) |
| 长时间空闲后缓存消失 | 比较缓存 TTL、请求频率、保活代价和节省金额 | TTL、keepalive、缓存重建 | [Aider 缓存保活](https://aider.chat/docs/usage/caching.html)；Provider 文档 |
| 更高命中与权限/新鲜度冲突 | 先保证身份、租户、权限和内容版本正确，再限定可共享作用域 | 缓存隔离、版本/失效策略 | [W-2026-009](../../../specs/work-pool/W-2026-009-study-system-prompt-production-context-governance.md) |

## 3. 概念之间的关系

- **Harness Context 组装 → Provider Prompt Cache**：前者控制请求内容及顺序，后者由模型服务或兼容层决定是否复用其内部计算。
- **应用层 Prompt 组装缓存 ≠ Provider Prompt Cache**：应用缓存保存/复用本地拼好的字符串或消息；Provider 缓存复用模型侧前缀计算结果。前者可帮助稳定输入，但不能证明后者命中。
- **Provider Prompt Cache ≠ KV Cache（推理 Runtime）**：常见 Prompt Cache 可能复用 Prefix 对应的 KV 状态；KV Cache 也可能只服务单次生成中的历史 Token。对外可见名称相似，不代表生命周期和可见指标相同。
- **Token Usage ≠ 延迟测量**：cached token 可用于分析复用和输入成本；端到端延迟还受排队、网络、Prefill、输出长度与工具等待影响。
- **CodeWhale、Aider 与 Goose 是实现样本，不是产品间性能排行榜**：缓存功能说明与源码路径可以比较；只有固定 Provider、模型、输入和测量口径的对照实验才能比较运行结果。
- **Context 复用优化不改变授权责任**：缓存命中不能绕过当前用户的权限判定、Context 刷新和租户隔离。

## 4. 主线与选学扩展

### 必学主线

1. Prompt Cache 缓存什么，和本地组装缓存、Runtime KV Cache 如何区分。
2. Agent 一轮模型请求由哪些 Context 部分组成；哪些通常稳定、哪些按回合变化。
3. 请求顺序、Tool Schema、模型/设置和前缀插入如何影响可复用范围。
4. 在 CodeWhale 中沿 pinned-prefix、Context drift、Usage 和 `/cache stats` 链路找源码证据；用 Aider 对照 Context 组成，用 Goose 窄对照 Provider-specific 请求适配。
5. 用实际指标而不是“缓存功能已开启”判断命中，并能说明一个 miss、TTL 或安全隔离场景。

### 选学扩展

- 多实例路由、负载分布和 Provider 内部缓存拓扑：仅当跨请求命中不稳定且需要解释时深入。
- Context compaction 与 Prefix Cache 的权衡：压缩可降低总输入，即使命中率下降，整体成本仍可能更低；结合 [W-2026-024](../../../specs/changes/C-2026-014-study-production-reactive-context-compaction.md) 另行学习。
- Prompt Cache 的跨用户计时侧信道和共享缓存隔离：作为安全专题，不影响主线学习。
- OpenHands SDK 多 Provider 能力表：前面项目无法说明 Provider 能力判定时再读。

## 5. 子笔记、Demo 与资料索引

- [LEARNING_NOTES.md](LEARNING_NOTES.md)：学习过程、模块索引、状态和下一步。
- [名词清单.md](名词清单.md)：按知识块查术语；词条不代表已掌握。
- 子模块笔记与 Demo：尚未创建，等对应问题实际开始后按需补充。
- [CodeWhale CACHE 设计](https://github.com/Hmbown/CodeWhale/blob/main/docs/CACHE.md)；[CodeWhale releases](https://github.com/Hmbown/CodeWhale/releases)；[DeepSeek Context Caching](https://api-docs.deepseek.com/guides/kv_cache/)。
- [Aider Prompt Caching](https://aider.chat/docs/usage/caching.html)；[Aider Options](https://aider.chat/docs/config/options.html)。
- [Goose Provider docs](https://github.com/aaif-goose/goose/blob/main/documentation/docs/getting-started/providers.md)；[Goose provider source](https://github.com/aaif-goose/goose/tree/main/crates/goose/src/providers)。
- [Anthropic Prompt Caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)；[OpenAI Prompt Caching](https://developers.openai.com/api/docs/guides/prompt-caching)；[OpenAI Diagnostics](https://developers.openai.com/api/docs/guides/prompt-caching/diagnostics)。

> 以上项目资料是学习入口。每条源码结论都要补固定仓库版本、Commit、文件/行号和证据等级；Provider 行为随版本变化时以重新核验为准。
