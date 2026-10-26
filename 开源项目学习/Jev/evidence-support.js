// 从仓库根目录运行：node 开源项目学习/Jev/evidence-support.js
// 添加 --dry-run 只预览请求；Node.js 22+，无需安装依赖。
const { existsSync } = require('node:fs');
const { join } = require('node:path');
const { loadEnvFile } = require('node:process');
const { performance } = require('node:perf_hooks');

const envPath = join(__dirname, '.env');
if (existsSync(envPath)) loadEnvFile(envPath);

// 原样保留待测证据和回答，方便直接替换样例继续实验。
const evidence = 'version=3.2.1\nrelease_date=2026-10-20';
const answer =
  'AgentX最新版本是3.2.1，\n发布于2026-10-20，\n并修复了严重安全漏洞。';
const endpoint = 'https://api.zhizengzeng.com/v1/systemone';
const request = {
  model: 'jev-latest',
  state: { evidence, answer },
  questions: {
    answer_supported: {
      // Noul 是是非判断的概率：0 倾向否，1 倾向是，0.5 附近表示不确定。
      // 判断整段是否成立，不将“部分事实匹配”当成“所有声明都有依据”。
      type: 'noul',
      instructions:
        '只依据 state.evidence，不使用外部知识或自行补充事实：从这些证据推断出 state.answer 的整段回答，是否合理且有充分证据支持？',
      criteria: {
        true: '回答中的所有事实声明都能由给定证据支持。',
        false: '回答中存在与证据矛盾，或给定证据不足以支持的事实声明。',
      },
    },
  },
};

async function main() {
  console.log('请求地址：', endpoint);
  console.log('实际请求：', JSON.stringify(request, null, 2));
  if (process.argv.includes('--dry-run')) return;

  // 仅使用本目录已有渠道凭证；不把密钥放进请求展示或日志。
  const apiKey = process.env.ZHIZENGZENG_API_KEY;
  if (!apiKey)
    throw new Error('请设置 ZHIZENGZENG_API_KEY，或填写本目录 .env。');
  const started = performance.now();
  // 一次运行只发一次请求；超时不自动重试，避免重复消耗额度。
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
  console.log(
    `HTTP ${response.status}；端到端耗时 ${Math.round(
      performance.now() - started
    )} ms`
  );
  console.log('实际响应：', body.replaceAll(apiKey, '[REDACTED]'));
  if (!response.ok) throw new Error(`接口调用失败：HTTP ${response.status}`);

  const data = JSON.parse(body);
  const result = data.answers?.answer_supported;
  // HTTP 成功后仍需确认问题名称、响应类型和数值范围，避免把缺失结果当低分。
  if (
    result?.type !== 'noul' ||
    !Number.isFinite(result.noul) ||
    result.noul < 0 ||
    result.noul > 1
  ) {
    throw new Error(
      '响应应包含 answers.answer_supported.type=noul 和 0～1 的 noul 数值。'
    );
  }
  console.log('响应模型：', data.model);
  console.log(`整段回答有充分证据支持：${result.noul}`);
  console.log(
    '分数越接近 1，越倾向合理；越接近 0，越倾向不合理；0.5 附近表示不确定。'
  );
  console.log(
    '这是模型对“是”的概率判断，不是答对了多少事实，也不是实测准确率。'
  );
}

main().catch((error) => {
  const message =
    error.name === 'TimeoutError'
      ? '等待超过 30 秒，未确认上游结果；未自动重试。'
      : error.message;
  console.error(
    '失败：',
    message.replaceAll(process.env.ZHIZENGZENG_API_KEY || '\0', '[REDACTED]')
  );
  process.exitCode = 1;
});

// 测试结果
const result = {
  answers: {
    answer_supported: {
      // 0 倾向否，1 倾向是
      noul: 0.04,
      type: 'noul',
    },
  },
  model: 'jev-latest',
  usage: {
    input_tokens: 459,
    output_tokens: 21,
  },
};
