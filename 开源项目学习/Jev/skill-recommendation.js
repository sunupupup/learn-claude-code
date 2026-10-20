// Node.js 22+；运行：node 开源项目学习/Jev/skill-recommendation.js
const { join } = require('node:path');
const { loadEnvFile, constrainedMemory } = require('node:process');
loadEnvFile(join(__dirname, '.env'));

// 直接在这里修改需求；每条需求发送一次请求。
const requests = [
  '把这份产品介绍整理成一份 5 页 PPT，交付 PPTX 文件。',
  '读取 sales.csv，清洗缺失值并按月汇总销售额，再制作可悬停和筛选的交互趋势图。',
  '不用查资料，也不要操作网页或文件，只用几句话解释 HTTP 和 HTTPS 的区别。',
];

// 教学候选：Jev 只根据这些描述评分，不会加载或执行技能。
const skills = {
  spreadsheet: {
    name: '表格分析',
    description:
      '读取 Excel/CSV，清洗数据、计算统计指标、输出汇总表和基础静态图表。',
  },
  visualization: {
    name: '交互可视化',
    description:
      '将已准备的数据制作成交互图表，支持悬停、筛选和联动；不负责读取或清洗 Excel。',
  },
  presentation: {
    name: 'PPT制作',
    description: '创建和编辑演示文稿，包括页面排版、图文组织与 PPTX 导出。',
  },
  pdf: {
    name: 'PDF处理',
    description:
      '提取 PDF 内容，合并、拆分和生成 PDF；不负责制作 PPT 或实时信息查询。',
  },
  browser: {
    name: '网页操作',
    description:
      '打开并操作网页中的按钮、表单和页面元素；不负责本地文件分析或通用知识问答。',
  },
};

// 数组下标就是评分等级：0～3，分数可以是小数，不是成功率。
const criteria = [
  '不适用：没有对应需求，或该技能不具备所需能力。',
  '间接相关：可能提供辅助，但没有直接完成用户明确要求的子任务。',
  '直接适用：能够完成用户明确要求的一个实质子任务，但不能独立完成全部需求。',
  '高度适用：能够独立完成全部明确需求，无需其他专门技能。',
];

async function main() {
  for (const input of requests) {
    // 每个技能独立问一个 Score 问题，五个问题合在同一次请求里。
    const request = {
      model: 'jev-latest',
      state: { user_request: input, skills },
      questions: Object.fromEntries(
        Object.keys(skills).map((id) => [
          id,
          {
            type: 'score',
            instructions: `只依据 state.skills.${id} 的描述，评价该技能对 state.user_request 的适配程度。不要假设未声明的能力，也不要推荐用户没有要求的附加产物。`,
            criteria,
          },
        ])
      ),
    };

    console.log('\n用户需求：', input);
    console.log('实际请求：', JSON.stringify(request, null, 2));
    const response = await fetch('https://api.zhizengzeng.com/v1/systemone', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${process.env.ZHIZENGZENG_API_KEY}`,
      },
      body: JSON.stringify(request),
    });
    const data = await response.json();
    console.log('HTTP 状态：', response.status);
    console.log('实际响应：', JSON.stringify(data, null, 2));

    // 程序只按适配分从高到低排序，直接观察分数，不加入推荐阈值或复核策略。
    const rows = Object.entries(skills)
      .map(([id, skill]) => ({
        技能: skill.name,
        // score	Skill 对当前需求的适配程度	我们定义的 0～3
        // jev不会给出整数，只会给出区间内的一个值
        // criteria: [
        //   '不适用',       // 0
        //   '间接相关',     // 1
        //   '完成部分需求', // 2
        //   '完成全部需求', // 3
        // ]
        // 2 级的概率：40%
        // 3 级的概率：60%
        // score = 2 × 0.4 + 3 × 0.6 = 2.6
        适配分: data.answers[id].score,
        // confidence	模型给出的等级概率有多集中，越集中表示判断越明确	0～1
        // 先找到概率最大的等级：0 级，概率 0.95，再计算其他概率离它有多远。
        置信度: data.answers[id].confidence,
      }))
      .sort((a, b) => b.适配分 - a.适配分);
    console.table(rows);
  }
}

main();

// 真实 response 示例：制作 5 页 PPT（2026-10-21 实测）
// result = confidence > threshold? argmax(probabilities): '不确定';
// 如果最终必须选一个等级，就取 probabilities 中概率最大的那个枚举；再用 confidence 判断是否接受这个选择。
const result = {
  answers: {
    browser: {
      confidence: 0.94,
      legend: {
        0: '不适用：没有对应需求，或该技能不具备所需能力。',
        1: '间接相关：可能提供辅助，但没有直接完成用户明确要求的子任务。',
        2: '直接适用：能够完成用户明确要求的一个实质子任务，但不能独立完成全部需求。',
        3: '高度适用：能够独立完成全部明确需求，无需其他专门技能。',
      },
      probabilities: {
        0: 0.95,
        1: 0.04,
        2: 0.01,
        3: 0,
      },
      score: 0.05,
      type: 'score',
    },
    pdf: {
      confidence: 0.93,
      legend: {
        0: '不适用：没有对应需求，或该技能不具备所需能力。',
        1: '间接相关：可能提供辅助，但没有直接完成用户明确要求的子任务。',
        2: '直接适用：能够完成用户明确要求的一个实质子任务，但不能独立完成全部需求。',
        3: '高度适用：能够独立完成全部明确需求，无需其他专门技能。',
      },
      probabilities: {
        0: 0.94,
        1: 0.05,
        2: 0.01,
        3: 0,
      },
      score: 0.08,
      type: 'score',
    },
    presentation: {
      confidence: 0.62,
      legend: {
        0: '不适用：没有对应需求，或该技能不具备所需能力。',
        1: '间接相关：可能提供辅助，但没有直接完成用户明确要求的子任务。',
        2: '直接适用：能够完成用户明确要求的一个实质子任务，但不能独立完成全部需求。',
        3: '高度适用：能够独立完成全部明确需求，无需其他专门技能。',
      },
      probabilities: {
        0: 0,
        1: 0,
        2: 0.38,
        3: 0.62,
      },
      score: 2.6,
      type: 'score',
    },
    spreadsheet: {
      confidence: 0.96,
      legend: {
        0: '不适用：没有对应需求，或该技能不具备所需能力。',
        1: '间接相关：可能提供辅助，但没有直接完成用户明确要求的子任务。',
        2: '直接适用：能够完成用户明确要求的一个实质子任务，但不能独立完成全部需求。',
        3: '高度适用：能够独立完成全部明确需求，无需其他专门技能。',
      },
      probabilities: {
        0: 0.96,
        1: 0.04,
        2: 0,
        3: 0,
      },
      score: 0.04,
      type: 'score',
    },
    visualization: {
      confidence: 0.96,
      legend: {
        0: '不适用：没有对应需求，或该技能不具备所需能力。',
        1: '间接相关：可能提供辅助，但没有直接完成用户明确要求的子任务。',
        2: '直接适用：能够完成用户明确要求的一个实质子任务，但不能独立完成全部需求。',
        3: '高度适用：能够独立完成全部明确需求，无需其他专门技能。',
      },
      probabilities: {
        0: 0.96,
        1: 0.04,
        2: 0,
        3: 0,
      },
      score: 0.04,
      type: 'score',
    },
  },
  model: 'jev-latest',
  usage: {
    input_tokens: 1617,
    output_tokens: 74,
  },
};
