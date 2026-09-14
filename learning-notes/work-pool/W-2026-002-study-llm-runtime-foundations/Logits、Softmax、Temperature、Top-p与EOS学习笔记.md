# Logits、Softmax、Temperature、Top-p 与 EOS 学习笔记

本实验观察：拿到候选 Token 的分数后，程序怎样选择下一个 Token，以及什么时候停止生成。

使用四个人工候选：猫 `2.0`、狗 `1.0`、鱼 `0.0`、`<EOS>` `0.5`。只用 Python 标准库，不加载真实模型。

脚本：[sampling_demo.py](./experiments/logits-sampling-basic/sampling_demo.py)。

在原仓库根目录运行：

```powershell
python .\learning-notes\work-pool\W-2026-002-study-llm-runtime-foundations\experiments\logits-sampling-basic\sampling_demo.py --stage greedy
```

替换 `--stage` 后的值，观察不同环节：

| 参数 | 实验内容 |
| --- | --- |
| `greedy` | 选择分数最高的候选 |
| `softmax` | 将原始分数转换成概率 |
| `temperature` | 比较不同温度下的概率分布 |
| `top-p` | 筛选候选、重新归一化并抽样 |
| `eos` | 重复抽样，选中 EOS 后停止 |

采样默认使用固定种子 `7`，可用 `--seed 其他整数` 改变。EOS 实验每步复用固定分数，仅模拟停止过程。

# 我自己的笔记

这个案例的意思是：大模型如何预测下一个模型、怎么打分，啥时候停止

你输入 Token A、Token B，模型根据它们预测下一个 Token，但中间有一个“打分再选择”的过程

概念	这章要弄明白的事
Logits（原始分数）	模型给词表中每个候选打的分，为什么它还不是概率？
Softmax（概率转换）	怎样把这些分数变成总和为 1 的概率？
Greedy（贪心选择）	每次直接选概率最高的 Token。
Temperature（温度）	怎样让概率更集中或更平均，从而影响随机抽样？
Top-p（核采样）	怎样保留累计概率达到阈值的候选，再重新归一化、抽样？
EOS（End of Sequence，序列结束符）	选中这个特殊 Token 后，推理程序怎样结束生成？
