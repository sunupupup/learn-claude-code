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
