# 实操 08：Cursor 按角色注入会话提示词

> **具体防护场景：** 同一个项目同时有 UI 设计师和国际化人员使用 Agent，防止 Agent 不知道当前开发者的职责，默认按全栈开发权限接任务。通过 sessionStart 按登录邮箱选择提示词，只向当前会话注入该开发者的角色和允许编辑范围，不让其他人的角色规则占用上下文。

## 场景

- `aaa@qq.com`：UI 设计师，只做前端 UI/UX 修改。
- `bbb@qq.com`：国际化团队，只改前端多语言资源文件。
- 其他用户：不添加这两种角色的提示词。

## 配置代码

使用 **Cursor 原生 sessionStart Hook**，需要 Node.js。脚本已经在当前 008 目录的 [`cursor-role-rules.cjs`](./cursor-role-rules.cjs)，下面保留完整代码。

**文件一：`cursor-role-rules.cjs`**。

```javascript
'use strict';

// 邮箱匹配由程序完成，全员角色表不会进入模型上下文。
const rulesByEmail = {
  'aaa@qq.com': [
    '当前用户的角色是 UI 设计师。',
    '只允许修改前端 UI/UX：布局、样式、视觉资源、响应式、可访问性和纯界面交互。',
    '先只读确认项目真实的前端目录；不得修改业务逻辑、后端、数据库、API、鉴权、部署、依赖及构建配置。',
    '不得修改多语言翻译资源。使用命令或 MCP 等工具时也必须遵守相同范围。',
    '需要范围外修改时，停止该部分修改并说明原因，不得自行扩大范围。',
  ].join('\n'),
  'bbb@qq.com': [
    '当前用户的角色是国际化团队。',
    '只允许修改前端多语言翻译资源文件。先只读确认实际的翻译目录及文件用途，不得把任意 JSON 或 TS 文件当作翻译资源。',
    '保持资源结构、插值变量及消息语法正确。不得修改组件、样式、业务代码、国际化加载逻辑、后端、依赖及构建配置。',
    '使用命令或 MCP 等工具时也必须遵守相同范围。',
    '需要范围外修改时，停止该部分修改并说明原因，不得自行扩大范围。',
  ].join('\n'),
};

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  try {
    const event = JSON.parse(input.replace(/^\uFEFF/, ''));
    // 只匹配 Cursor 传入的登录邮箱，不读取 Git name 或让模型判断用户身份。
    const email = typeof event?.user_email === 'string'
      ? event.user_email.trim().toLowerCase()
      : '';
    const rule = Object.hasOwn(rulesByEmail, email) ? rulesByEmail[email] : null;
    // 未匹配用户不添加上下文；匹配用户只收到自己的规则正文。
    const output = rule ? { additional_context: rule } : {};
    process.stdout.write(JSON.stringify(output) + '\n');
  } catch {
    process.stdout.write('{}\n');
    process.stderr.write('角色规则脚本：输入无效，未注入规则。\n');
    process.exitCode = 1;
  }
});
```

**文件二：业务项目的 `.cursor/hooks.json`**。希望对所有项目生效时，放到用户级 `~/.cursor/hooks.json`。已有配置就合并 `sessionStart` 数组，不覆盖其他 Hook。

```json
{
  "version": 1,
  "hooks": {
    "sessionStart": [
      {
        "command": "node \"D:/code/third-party-labs/agent/learn-claude-code/真实生产问题/008-团队使用Agent时如何落实权限与责任边界/cursor-role-rules.cjs\""
      }
    ]
  }
}
```

保存配置后，新建 Agent 对话。Cursor 将登录邮箱作为 Hook 输入传给脚本；程序匹配用户，再通过 `additional_context` 返回该角色的正文，由 Cursor 加入会话上下文。切换账号或修改规则后，新建会话使用新的匹配结果。

## 能起到的作用

- 在会话开始时，向 Agent 说明当前开发者的角色和允许编辑范围；不需要每次手工重复提示。
- 全员映射留在程序里，模型只接收匹配角色；未匹配用户输出空对象，不注入无关内容。
- 与实操 07 可以同时注册：本例负责提前告知角色，07 负责在提交检查点拒绝越界文件。
- 这是提示词层面的职责约束，不会自动建立文件权限；sessionStart 非阻塞，不能据此保证首轮时序或强制防越界。本次只整理已有脚本，没有运行或新增测试。

依据：[Cursor sessionStart 与 additional_context](https://cursor.com/docs/hooks#sessionstart)。

## 我的笔记

