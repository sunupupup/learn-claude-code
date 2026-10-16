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
