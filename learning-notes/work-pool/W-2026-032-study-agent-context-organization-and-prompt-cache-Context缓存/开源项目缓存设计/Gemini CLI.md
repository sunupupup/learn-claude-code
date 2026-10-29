# 我的笔记 

Gemini CLI 这边
把一次用户输入到agent回答，称之为 loop
loop中间的一次while循环，称之为 turn， 所以有 executeTurn 的方法



# System prompt的组成

https://github.com/google-gemini/gemini-cli/blob/acae7124bdd849e554eaa5e090199a0cf08cd782/packages/core/src/prompts/snippets.ts#L136-L164

拼接内容应该是包含下面这些：

| 顺序 | 拼接函数 | 里面主要写什么 |
|---|---|---|
| 1 | `renderPreamble` | 身份：软件工程 CLI Agent；当前运行模式 |
| 2 | `renderCoreMandates` | 核心规则：保护凭据、处理不可信内容、节省上下文、遵守项目风格、测试验证 |
| 3 | `renderSubAgents` | 可用子 Agent 的名称、描述，以及任务委派规则 |
| 4 | `renderAgentSkills` | 可用技能的名称、描述、文件位置，以及如何激活 |
| 5 | `renderHookContext` | 如何理解外部 Hook 注入的上下文 |
| 6 | `renderPrimaryWorkflows` **或** `renderPlanningWorkflow` | 普通开发流程，或 Plan 模式的规划与审批流程 |
| 7 | `renderTaskTracker` | 使用任务追踪工具拆解、更新和验证任务的规则 |
| 8 | `renderOperationalGuidelines` | 回复风格、工具并行与顺序执行、文件编辑、命令执行等规范 |
| 9 | `renderInteractiveYoloMode` | 自主执行模式下，何时继续、何时询问用户 |
| 10 | `renderSandbox` | 当前沙箱限制，以及遇到权限错误时如何处理 |
| 11 | `renderGitRepo` | Git 操作规范，包括提交、暂存和推送要求 |

```ts
/**
 * Composes the core system prompt from its constituent subsections.
 * Adheres to the minimal complexity principle by using simple interpolation of function calls.
 */
export function getCoreSystemPrompt(options: SystemPromptOptions): string {
  return `
${renderPreamble(options.preamble)}

${renderCoreMandates(options.coreMandates)}

${renderSubAgents(options.subAgents)}

${renderAgentSkills(options.agentSkills)}

${renderHookContext(options.hookContext)}

${
  options.planningWorkflow
    ? renderPlanningWorkflow(options.planningWorkflow)
    : renderPrimaryWorkflows(options.primaryWorkflows)
}

${options.taskTracker ? renderTaskTracker(options.taskTracker) : ''}

${renderOperationalGuidelines(options.operationalGuidelines)}

${renderInteractiveYoloMode(options.interactiveYoloMode)}

${renderSandbox(options.sandbox)}

${renderGitRepo(options.gitRepo)}
`.trim();
}
```

这个方法看着真舒服，一眼明了

## renderPreamble

首先是 renderPreamble， preamble 代表序言
当前系统的角色声明

几种模式的声明

Default
- 人要确认：改文件、跑 shell、拉网页
- 可以直接做：读代码

Plan
- 人要确认：退出计划、部分只读工具
- 可以直接做：只调研，并只能把 .md 计划写到计划目录

Auto-Edit
- 人要确认：shell
- 可以直接做：工作区内的 write_file / replace，以及 web_fetch

YOLO
- 人要确认：只有 ask_user
- 可以直接做：其余工具调用默认自动批准

```ts
export function renderPreamble(options?: PreambleOptions): string {
  if (!options) return '';
 
  let modeStr = 'Default';
  if (options.approvalMode === 'plan') modeStr = 'Plan';
  if (options.approvalMode === 'yolo') modeStr = 'YOLO';
  if (options.approvalMode === 'autoEdit') modeStr = 'Auto-Edit';

  const base = options.interactive
    ? 'You are Gemini CLI, an interactive CLI agent specializing in software engineering tasks.'
    : 'You are Gemini CLI, an autonomous CLI agent specializing in software engineering tasks.';

  return `${base} You are currently operating in **${modeStr}** mode. Your primary goal is to help users safely and effectively.`;
}
```

## renderCoreMandates

renderCoreMandates， mandate ，必须照做的指令，一种强烈的指令 

里面包含了很多强硬的指令
- 安全：不打印密钥、保护env、git文件、系统配置文件、不要擅自提交代码、把外部工具和MCP输出当成不可信数据
- 上下文效率：少浪费上下文，但不要为了省 token 多绕回合。
  - 比如：针对于 搜索文件并且替换所有关键词， gemini cli建议使用grep_search工具，而不要使用原生的grep，防止上下文撑满了

- 工程规范：跟仓库既有风格、先分清用户是在提问还是在下令、改完要补测试、不要擅自回滚。
  还有一些其他工程规范，比如
  - 不要revert代码
  - 注意lint警告
  - 使用设计模式
  - 遵循仓库已有的风格
  - 等等


## renderSubAgents

- 列举出当前存活的sub agent
- 说明sub agent的使用场景，其实就是一些脏活累活，主agent只需要知道结果就行
  - 重复批量活，例如给 src/ 下很多文件加许可证头，或修全仓库的 lint。
  - 输出会很长的命令，例如啰嗦的构建日志、铺开的全文搜索。
  - 要来回试很多次才能找到路的调研。

## renderAgentSkills

已加载的skill的信息

## renderHookContext

这是一段安全提示。外部 hook 附带的文字会被包进 <hook_context>，模型必须把它当成只读的背景信息。
标签里的内容不能当成新指令。它不能推翻 Core Mandates 和安全规则；和系统提示冲突时，以系统提示为准。这是在防 hook 脚本或它带进来的外部文本对模型做提示注入

## renderPlanningWorkflow 、 renderPrimaryWorkflows

renderPlanningWorkflow，这个就是强调在计划模式下，只能写plan文件，不能改源码

renderPrimaryWorkflows，这个就是强调一些开发规范，比如必须遵循 「调研 → 策略 → 执行」走

# renderTaskTracker

renderTaskTracker 是在告诉模型，当前这套任务管理怎么运作，以及要用哪几个工具去改状态。

## renderOperationalGuidelines

操作规范

这一节有四块：

- 语气。 像同事一样直接说。CLI 里尽量少输出，能少就少于 3 行。用工具做事，文字只用来沟通。不要在工具参数里写解释。

- 危险命令。 会改文件或系统状态的 shell 命令，执行前先用一句话说明目的和影响。不要用 ask_user 去征求「能不能跑」；确认框由系统弹出。不要把密钥写进代码。

- 工具怎么调用。 互不依赖的工具同一轮并行。后一个依赖前一个的结果时，设 wait_for_previous。同一个文件不要在一轮里 replace 多次，拆到后面的回合。用户拒绝了某次调用，就不要原样再试。后台进程用 is_background。能用非交互命令就不要用会等人输入的命令。

- 长期记忆写到哪。 没有单独的保存记忆工具，直接改 Markdown。团队约定写 GEMINI.md，这台机器上的私人说明写项目私有记忆，跨项目的个人偏好写全局记忆。同一条事实只放一处。临时进度和这次改了什么代码不要写进去。


## renderSandbox

开启沙箱模式才会有内容添加，

沙箱用来把模型发起的危险操作和你的主机隔开。模型可以跑 shell、改文件；这些动作一旦直接在本机执行，就可能误删家目录、读到密钥，或者执行一段你没仔细看过的命令。


模型为了修一个测试，决定跑这条命令：

rm -rf ~/Library && cat ~/.ssh/id_rsa
没开沙箱时，这条命令就在你的电脑上执行，主目录和私钥都暴露给它。

开了沙箱之后，shell 被关在项目目录里。~/Library 和 ~/.ssh 都在沙箱外面，命令会因 Operation not permitted 失败，删不到、也读不到。

**沙箱的作用**：预置允许边界（能写哪些目录、网络和端口开不开），避免模型的命令直接改到整个主机，越界访问由沙箱按这份规则拒绝。

大部分编码代理的沙箱也是这个作用：把模型生成的命令和主机隔开，限制它能碰的文件和网络，避免误删家目录或读到沙箱外的密钥。云端产品常常默认开，本机 CLI 常常像 Gemini CLI 这样默认关、由你打开。具体用容器、微虚机还是 Seatbelt，各家不同。