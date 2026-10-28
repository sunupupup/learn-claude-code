# 1. 关键 SDK 

用到了一些关键函数

1. observe, 这个方法能同时观察 单个tool、整次Agent执行的链路

- observer run
- observer tool

runSupportConversationInner 这个是 一次turn 的执行
能观测到 时间开销、中途错误、入参、返回结果
```js
observe(runSupportConversationInner, {
  name: "dad-it-support-chat-turn",
  asType: "agent"
});
```

工具的观测，把原有工具 observe 包装一下， 能够自然记录 tool 的调用时间、入参、输入结果等
```js
const getSupportContextTool = observe(
  async () => {
    const context = getSupportContext();

    return {
      ok: true,
      context: {
        id: context.id,
        label: context.label,
        ... 工具返回的内容
      }
    };
  },
  {
    name: "get_support_context",
    asType: "tool"
  }
);
```

2. observeOpenAI

观察每个llm的客户端，进行封装


```js
const openai = observeOpenAI(
  new OpenAI({ apiKey: env.openaiApiKey }),
  langfusePrompt ? { langfusePrompt } : undefined
);
```

3. updateActiveObservation 

给span补充一些额外信息

```js
import { observe, updateActiveObservation } from "@langfuse/tracing";

const getSupportContextTool = observe(
  async () => {
    const context = getSupportContext();

    // 给当前工具 Span 补充业务信息
    updateActiveObservation({
      metadata: {
        contextId: context.id,
        deviceCount: context.devices.length,
        source: "local"
      }
    });

    return {
      ok: true,
      context: {
        id: context.id,
        label: context.label
      }
    };
  },
  {
    name: "get_support_context",
    asType: "tool"
  }
);
```


4. propagateAttributes

propagate 传播

绑定更多的上下文内容 
| 上下文 | 用途 |
|---|---|
| `traceId`、当前 `spanId` | **串执行关系**：属于哪条链、父步骤是谁 |
| `userId`、`sessionId`、标签等 | **补业务归属**：哪个用户、哪段会话、哪类任务 |

```js
async function runSupportConversationInner(request: ChatRequest): Promise<ChatResponse> {
  。。。一堆内容

  return propagateAttributes(
    {
      userId,
      sessionId: request.sessionId,
      traceName: "dad-it-support-chat-turn",
      tags: ["langfuse-workshop", "dad-it-support"]
    },
    ...具体的执行函数
  )
}
```

# 2. 实际测试观察

一般会使用 三种id 来查看相关数据

session id 、trace id、user id

一次trace提供 tree、graph、timeline 等多种方式来进行预览

tree更讲究父子关系
timeline看重各个时间段的执行时间
graph的方式更讲究循环、状态流转



# 3. System Prompt 版本号

提示词版本由发布 Prompt 创建，不是 observe 自动根据内容变化创建；观测记录负责关联已发布的版本。


先把 System Prompt 以固定的 Prompt 名称（如 dad-it-support-agent）发布到 Langfuse。

每次创建新版本时，Langfuse 自动分配递增的版本号。

Agent 执行时，从 Langfuse 读取提示词正文及版本信息，将正文发送给模型，并通过 observeOpenAI 把模型调用记录关联到该版本。

后续就能按版本分析执行记录，并通过评测实验比较不同版本的效果。

```
prompt.create({ name, prompt })       → 创建提示词版本
observeOpenAI(..., { langfusePrompt }) → 关联本次模型调用与提示词版本
```

[不同版本的prompt的调用记录展示页面](./refer/langfuse_prompt_version.png)

[不同版本的prompt的Metrics统计信息](./refer/langfuse_prompt_metrics.png)

# 4. 线上质量监控

| 要了解什么 | 用当前例子说明 |
|---|---|
| **1. 监控目标** | 检测“用户反对回答”，而不是笼统判断“Agent 好不好” |
| **2. 检查哪些记录** | 选整轮 Agent 记录，因为需要看到对话历史 |
| **3. 怎样判断** | 代码规则检查明确模式；模型评委判断语义；人工复核复杂案例 |
| **4. 何时触发** | 配置筛选条件和采样比例，让新记录符合条件时自动执行 |
| **5. 结果怎样使用** | 保存评分 → 筛选可疑对话 → 查看原始证据 → 分类问题 |

需要专门造一些 评估器 

langfuse的评估器，LLM-as-a-Judge 模式，用LLM当评委来判断某个标准

作用可以看纯粹点

他们是 能够利用 trace 数据，筛选出 我们系统的某些测试集、bad case用于迭代

Langfuse 评测器利用 Trace 数据，按指定标准打分或标记，帮助发现 bad case，作为后续测试集与迭代的素材。

langfuse的评估器负责利用观测trace数据找出有价值的数据

!!!
后续需要评测执行框架、数据整理和 CI/CD 配合；Langfuse 本身也提供 Dataset、Experiment 和评分能力。
!!!


langfuse的评估器，三种模式
1. LLM-as-a-Judge， 判断，比如 回答是否有依据？
2. Code Evaluator，用代码的方式评估，工具参数合法性、markdown格式合法性
3. Decision Model ， 分类场景


如何触发评估
不用人天天去手点

1. 新纪录自动运行，只需要配置一些Rules，设置采样率：测试时设为 100%
2. 批量检查，选择时间范围和条件，批量运行
3. MCP的方式

# 5. 测试集和离线评测

建测试集：场景、输入、预期结果；运行 Agent，用规则与模型评委评分（05–06）。

**离线回归测评**

本地修改 Agent 后，跑固定测试用例，把执行记录和评分传到 Langfuse 查看、比较。 这叫离线回归评测。

[测试数据](./langfuse-workshop/data/seed-dataset.json)

[测试代码](./langfuse-workshop/scripts/run-dataset.ts)
这个测试代码，其实就是在调用 实际的Agent业务代码的方法
本地运行Agent测试 -> 本地模型评分 -> 将执行记录上唇Langfuse -> 在Langfuse上查看结果

测试过程中的内容，也会一并上传到 Langfuse 上 `dataset.runExperiment` 方法


# 6. 离线评测实操

运行完之后，Langfuse上有测试集的记录和实验结果记录
[测试数据集和结果展示](./refer/langfuse_dataset_eval.png)

# 7. 评估一次改动

改一个因素 → 重跑同一数据集 → 比较逐例结果 → 判断是否改善
用旧实验作基线，判断新改动带来了什么变化。

[对比实验](./refer/langfuse_exp_compare.png)

Compare 负责展示差异，关键是我们怎样定义“什么算通过”。

**这边对于业务代码的需要评估的内容，需要好好设计，对，这才是业务 Eval 的核心设计工作！！**
每个 case 至少想清楚：
1. 预期行为：应该做什么、不应该做什么。
2. 判断证据：看回复、工具调用，还是最终业务状态。
3. 评测方法：代码能确定判断，还是需要模型／人工。
4. 通过条件：哪些必须满足，哪些只是参考指标。

每个 case 可以根据业务要求，使用不同的评估维度。

| Case | 适用维度 |
|---|---|
| A：查询订单 | A 参数正确、B 必需工具调用、C 回答有依据 |
| B：拒绝越权操作 | B 工具调用符合要求、D 正确拒答、F 无越权副作用 |

```js
// 示意：每道题声明自己需要哪些检查
caseA.checks = ["A", "B", "C"];
caseB.checks = ["B", "D", "F"];
```



# 8. 评测粒度和范围

有三种粒度，单一span、单轮turn、整个session长任务

| 范围 | 一次测试执行什么 |
|---|---|
| **单个 LLM Span 快照** | 恢复模型输入，再调用一次模型 |
| **单 Turn 快照** | 恢复轮次开始前的历史和状态，执行这一轮模型→工具→回复 |
| **完整任务** | 从任务初始状态出发，走完可能跨多轮的流程 |


留存：倒下来的数据是啥样子 ？ 又怎么给agent后续评估、测试使用 ？？ 