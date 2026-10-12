
这个是 pi 里面压缩上下文的system prompt
```js
const SUMMARIZATION_PROMPT = `The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.

Use this EXACT format:

## Goal
[What is the user trying to accomplish? Can be multiple items if the session covers different tasks.]

## Constraints & Preferences
- [Any constraints, preferences, or requirements mentioned by user]
- [Or "(none)" if none were mentioned]

## Progress
### Done
- [x] [Completed tasks/changes]

### In Progress
- [ ] [Current work]

### Blocked
- [Issues preventing progress, if any]

## Key Decisions
- **[Decision]**: [Brief rationale]

## Next Steps
1. [Ordered list of what should happen next]

## Critical Context
- [Any data, examples, or references needed to continue]
- [Or "(none)" if not applicable]

Keep each section concise. Preserve exact file paths, function names, and error messages.`;
```

其实目的就是压缩完之后生成这样一份 

```md
## Goal
修复订单查询接口。

## Constraints & Preferences
- 不修改数据库结构。

## Progress
### Done
- 已定位缓存失效问题。
### In Progress
- 正在修改查询逻辑。
### Blocked
- 暂无。

## Key Decisions
- 查询失败时不写入缓存，避免缓存错误结果。

## Next Steps
1. 完成修改。
2. 验证失败后可以重新查询。

## Critical Context
- 关键函数：getOrder()
- 原错误：Order not found
```