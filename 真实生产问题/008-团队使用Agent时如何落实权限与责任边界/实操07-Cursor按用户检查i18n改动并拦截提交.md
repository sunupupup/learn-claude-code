# 实操 07：Cursor 按用户检查 i18n 改动并拦截提交

> **具体防护场景：** 防止 bbb@qq.com 在提交翻译修改时，把组件或业务代码的改动一起提交。通过 Cursor 的 beforeShellExecution Hook 检查本次暂存文件，超出 i18n/ 翻译资源范围就拒绝 git commit 并显示警告；PR comment 告警和服务端合并拦截由实操 04 实现。

## 场景

`bbb@qq.com` 属于国际化团队，只允许提交 `i18n/` 下的翻译资源。Cursor 发起提交时，如果暂存区还有组件、后端等其他文件，就拒绝命令并显示越界警告。

## 配置代码

需要 Node.js 和 Git。直接使用 Cursor 原生 Hook，不需要搭插件工程。

**文件一：[`cursor-i18n-scope-guard.cjs`](./cursor-i18n-scope-guard.cjs)**。这是已放在当前 008 目录中的完整脚本。修改脚本顶部 `restrictedEmail` 可替换受限用户；`allowedFile()` 定义允许路径和扩展名。

脚本完整代码：

```javascript
'use strict';

const { spawnSync } = require('node:child_process');

// 只有这个用户受本示例的 i18n 提交范围限制；不使用可修改的 Git name。
const restrictedEmail = 'bbb@qq.com';
const warning = '警告！非专业开发者正在修改实际代码文件，已越界，请注意是否合理！';

function reply(permission, message) {
  const output = { permission };
  if (message) {
    output.user_message = message;
    output.agent_message = message;
  }
  process.stdout.write(JSON.stringify(output) + '\n');
}

function allowedFile(filename) {
  // i18n/ 包含子目录；只接受明确的翻译资源，不放行目录内的任意代码。
  return filename.startsWith('i18n/') &&
    !filename.split('/').includes('..') &&
    /\.(json|ya?ml|po|properties)$/i.test(filename);
}

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  try {
    const event = JSON.parse(input.replace(/^\uFEFF/, ''));
    const command = event.command;
    if (typeof command !== 'string') {
      return reply('deny', '无法取得待执行命令，拒绝执行。');
    }

    // 这里只治理 git commit；不宣称覆盖所有 shell、MCP 或人工操作。
    const mentionsCommit = /\bgit(?:\.exe)?\b[\s\S]*\bcommit\b/i.test(command);
    if (!mentionsCommit) return reply('allow');

    const email = typeof event.user_email === 'string'
      ? event.user_email.trim().toLowerCase() : '';
    if (!email) return reply('deny', '未取得 Cursor 登录邮箱，无法确认提交范围。');
    if (email !== restrictedEmail) return reply('allow');

    // 只支持单条 git commit -m "说明"，避免 -a、--only、--amend 等改变被检查范围。
    // 复合命令、变量、重定向和其他提交写法直接拒绝，不能先改暂存区再执行提交。
    const simpleCommit = /^\s*git(?:\.exe)?\s+commit\s+-m\s+(?:"[^"\r\n]*"|'[^'\r\n]*')\s*$/i;
    if (!simpleCommit.test(command) || /[\r\n;&|<>`$]/.test(command)) {
      return reply('deny', '受限用户请先暂存文件，再单独执行 git commit -m "说明"；本 Hook 不放行其他提交写法。');
    }
    if (typeof event.cwd !== 'string' || !event.cwd) {
      return reply('deny', '缺少命令工作目录，无法检查本次暂存内容。');
    }

    // 只读暂存区：检查本次 commit 的文件，而不是把无关的未暂存修改一起算进去。
    // NUL 分隔兼容带空格/换行的文件名；关闭重命名识别，让原路径和新路径都被检查。
    const result = spawnSync('git', [
      '-C', event.cwd, '--no-optional-locks', '-c', 'core.fsmonitor=false',
      'diff', '--cached', '--name-only', '--no-renames',
      '--no-ext-diff', '--no-textconv', '-z', '--',
    ], { encoding: 'utf8', timeout: 3000, maxBuffer: 8 * 1024 * 1024, windowsHide: true });
    if (result.error || result.status !== 0) {
      return reply('deny', '暂存区读取失败，未放行提交。');
    }
    const files = result.stdout.split('\0').filter(Boolean);
    if (!files.length) return reply('deny', '没有暂存文件，请先暂存本次翻译修改。');
    const outside = files.filter(filename => !allowedFile(filename));
    if (outside.length) {
      const list = outside.map(filename => JSON.stringify(filename)).join('\n');
      return reply('deny', `${warning}\n允许范围：i18n/ 下的 JSON、YAML、PO、properties。\n越界文件：\n${list}`);
    }
    reply('allow');
  } catch {
    // 解析或检查异常不能被当作合规；Cursor 仍负责真正停止原命令。
    reply('deny', '提交范围检查异常，未放行本次命令。');
  }
});
```

**文件二：`.cursor/hooks.json`**。已有 Hook 时合并 `beforeShellExecution` 数组，不覆盖原有 `sessionStart`。完整 JSON 副本也在本目录的 [`cursor-i18n-scope-guard.hooks.json`](./cursor-i18n-scope-guard.hooks.json)。

```json
{
  "version": 1,
  "hooks": {
    "beforeShellExecution": [
      {
        "command": "node \"D:/code/third-party-labs/agent/learn-claude-code/真实生产问题/008-团队使用Agent时如何落实权限与责任边界/cursor-i18n-scope-guard.cjs\"",
        "timeout": 5,
        "failClosed": true
      }
    ]
  }
}
```

让 Cursor 先正常暂存本次翻译文件，再单独执行以下形式的提交：

```bash
git commit -m "更新前端翻译"
```

程序读取宿主的 `user_email` 和命令 `cwd`，使用下面的只读命令取得本次暂存列表，再逐个调用 `allowedFile()` 判断：

```bash
git diff --cached --name-only --no-renames --no-ext-diff --no-textconv -z --
```

越界时返回给 Cursor 的完整对象示例：

```json
{
  "permission": "deny",
  "user_message": "警告！非专业开发者正在修改实际代码文件，已越界，请注意是否合理！\n越界文件：src/components/Login.tsx",
  "agent_message": "警告！非专业开发者正在修改实际代码文件，已越界，请注意是否合理！\n越界文件：src/components/Login.tsx"
}
```

## 能起到的作用

- `bbb@qq.com` 暂存了范围外文件：阻止 Cursor 执行该提交，同时把警告交给用户和 Agent。
- 只暂存 `i18n/` 及子目录的 `.json`、`.yaml`、`.yml`、`.po`、`.properties`：放行，Git 自身仍可能因其他原因拒绝提交。
- 其他已识别邮箱不受此示例限制；无法识别邮箱时不放行被识别出的提交。
- 为确保检查对应本次提交，受限用户仅支持单条 `git commit -m "说明"`，其他提交形式或复合命令拒绝。
- 这是 Cursor 提交检查点，不是文件写入隔离；其他工具、手工终端或未被识别的封装入口不在覆盖范围。服务端合并关口见[实操 04](./实操04-让Agent提PR并由人批准合并.md)。
- 未运行、未新增测试、未修改你的真实 Hook 配置。接口依据：[Cursor beforeShellExecution](https://cursor.com/docs/hooks#beforeshellexecution--beforemcpexecution)、[Git diff](https://git-scm.com/docs/git-diff)。

## 我的笔记

