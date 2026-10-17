// 从仓库根目录运行：node 开源项目学习/Jev/basic.js
// Node.js 22+；仅使用内置模块，不需要安装 npm 依赖。
const { existsSync } = require('node:fs');
const { join } = require('node:path');
const { loadEnvFile } = require('node:process');
const { performance } = require('node:perf_hooks');

// 只读取本 Demo 旁的配置，不混用仓库根目录其他模型的凭证。
const envPath = join(__dirname, '.env');
if (existsSync(envPath)) loadEnvFile(envPath);

const endpoint = 'https://api.zhizengzeng.com/v1/systemone';
const request = {
  model: 'jev-latest',
  state: process.argv[2] && process.argv[2] !== '--dry-run'
    ? process.argv[2]
    : 'Help! My payouts have been failing for 3 days.',
  questions: {
    is_urgent: {
      type: 'noul',
      instructions: 'Does this convey urgency?',
    },
  },
};

async function main() {
  console.log('请求地址：', endpoint);
  console.log('请求正文：', JSON.stringify(request, null, 2));
  // 预览只展示正文，不发请求，也不消耗 API 额度。
  if (process.argv.includes('--dry-run')) return;

  const apiKey = process.env.ZHIZENGZENG_API_KEY;
  if (!apiKey) throw new Error('请设置 ZHIZENGZENG_API_KEY，或填写本目录 .env。');
  const started = performance.now();
  // 单次请求不自动重试；超时只说明本地停止等待，上游执行结果可能未知。
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(request),
    signal: AbortSignal.timeout(30_000),
    redirect: 'error',
  });
  const body = await response.text();
  console.log(`HTTP ${response.status}；端到端耗时 ${Math.round(performance.now() - started)} ms`);
  // 如果服务端意外回显密钥，也不把原值输出到日志。
  console.log('实际响应：', body.replaceAll(apiKey, '[REDACTED]'));
  if (!response.ok) throw new Error(`接口调用失败：HTTP ${response.status}`);

  const data = JSON.parse(body);
  const answer = data.answers?.is_urgent;
  // HTTP 成功还不够：确认返回了本次问题对应的合法数值。
  if (answer?.type !== 'noul' || !Number.isFinite(answer.noul)
      || answer.noul < 0 || answer.noul > 1) {
    throw new Error('响应不符合预期：应包含 answers.is_urgent.type=noul 和 0～1 的 noul 数值。');
  }
  console.log(`是否紧急：${answer.noul}（越接近 1，越倾向“是”）`);
}

main().catch((error) => {
  const message = error.name === 'TimeoutError'
    ? '等待超过 30 秒，未确认上游结果；未自动重试。'
    : error.message;
  console.error('失败：', message.replaceAll(process.env.ZHIZENGZENG_API_KEY || '\0', '[REDACTED]'));
  process.exitCode = 1;
});
