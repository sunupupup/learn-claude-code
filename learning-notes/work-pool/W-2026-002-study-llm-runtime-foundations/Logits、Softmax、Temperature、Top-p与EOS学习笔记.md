# Logits、Softmax、Temperature、Top-p 与 EOS 学习笔记

本实验观察：拿到候选 Token 的分数后，程序怎样选择下一个 Token，以及什么时候停止生成。

使用四个人工候选：猫 `2.0`、狗 `1.0`、鱼 `0.0`、`<EOS>` `0.5`。只用 Python 标准库，不加载真实模型。

脚本：[sampling_demo.py](./experiments/logits-sampling-basic/sampling_demo.py)。

在原仓库根目录运行：

```powershell
python .\learning-notes\work-pool\W-2026-002-study-llm-runtime-foundations\experiments\logits-sampling-basic\sampling_demo.py --strategy greedy
```

只有两种选择策略：`--strategy greedy` 直接选最高分；`--strategy sample` 随机采样。旧的 `--stage` 已移除。

采样分支按顺序执行：**温度调节 → Softmax 转概率 → Top-p 筛选并归一化 → 按概率抽取**。每一步都会打印结果。

```powershell
python .\learning-notes\work-pool\W-2026-002-study-llm-runtime-foundations\experiments\logits-sampling-basic\sampling_demo.py --strategy sample --temperature 1 --top-p 0.8 --seed 7
```

改变 `--temperature` 观察分布变化；`--top-p 1` 保留全部候选。温度 0 在本 Demo 中改走 Greedy，不进行除法。Greedy 不使用温度、Top-p 或随机种子。

两种策略选完后都检查 EOS。默认只选一次；观察循环停止可用 `--strategy sample --top-p 1 --seed 7 --max-tokens 30`。每轮复用固定分数，仅模拟选择与停止，不是真实模型生成。

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


## 从一句话到下一个 Token 的生成流程

再重新梳理下 整体的 流程

用户Query
    ↓ 分词器
["我"，"喜欢"，"你"]
    ↓ token映射
[2,12,33] Token ID
    ↓ 向量化 N维度，通常好几千， Embedding 查向量
[[0.,0..],[0.,0..],[0.,0..]] 输入向量矩阵
    ↓
进入 Transformer 第 1 层
    ├─ Attention：融合前文信息 （这边已经在Transformer了，会进行信息的叠加）
    └─ 前馈网络：继续加工各位置的向量
    ↓
进入 Transformer 第 2 层
    ├─ Attention
    └─ 前馈网络
    ↓
……重复多层，结合前文信息，不断加工各个 Token 的向量，得到用来预测下一个 Token 的最终向量。
    ↓
输出层 → 候选 Token 分数

到了最后一层，假如 得到 2 × 4096 的矩阵：
第 1 行：[4096 个数字]
第 2 行：[4096 个数字] ← 取这一行，已结合前文信息

取最后一行，输出层把这 4096 个数字转换成整个词表的分数。

关系到一个 输出投影矩阵（Output Projection Matrix），也常叫 LM Head 权重。

每一个token都有一个权重向量，每个向量都是 4096 维度 （和上面一样）
假如该模型 有 100 个 token （词表中）

就会 第 2 行：[4096 个数字] * 100*4096 这个矩阵
得到 100 个 token 的 每个分数
然后一般取top k 或者 其他 策略
按 Greedy（贪心） 或随机采样等策略，选择下一个 Token ID

贪心，追求稳定，但不代表准确性最好

## 影响下一个token的因素

程序怎么选择
- Greedy	直接选最高分候选
- Temperature（温度）	调整概率分布，让抽样更集中或更分散
- Top-p	按累计概率筛选参与抽样的候选
- 随机数／种子	抽样时影响具体抽中哪个候选

greedy和sample，都称之为解码策略，得到最终的tokenid，，，感觉通俗点理解就是pick策略，挑一个符合要求的token

--strategy greedy
    → 直接选最高分

--strategy sample
    → 温度调节， 进行  分数 / 温度 ， 温度小于1，会使得分数的差距变大，影响softmax函数，将分数转为概率
    → Softmax 转概率
    → Top-p/Top-k 筛选并归一化
    → 按概率抽取

两条路径选完后，都检查 EOS

温度	 调整后分数	         Softmax 后概率
T=0.5	[4, 2]，差距变大	   88% / 12%
T=1	  [2, 1]	            73% / 27%
T=2	  [1, 0.5]，差距变小	 62% / 38%

Top-p/Top-k 互为平替
Top-k：按数量，保留概率最高的 k 个候选。
Top-p：按累计概率阈值，从高到低累加，保留到累计概率达到 p。
注意 Top-p 不是要求每个候选的概率超过 p。
而是前n个最大概率的和，超过p，取那n个值
比如候选概率是：
猫：50%
狗：30%
鱼：15%
鸟： 5%
设置 Top-p = 0.8（80%），从高到低累加：
先保留猫：      累计 50%，还没到 80%
再保留狗：      累计 80%，达到，停止

还有一个策略，除了 Greedy 和 Sampling，还有一个典型策略：Beam Search（束搜索）。
- Greedy：每步选一个最高分候选，一条路走下去。
- Sampling：每步按概率抽一个，一条路走下去。
- Beam Search：同时保留几条候选续写，继续扩展、比较序列得分，最后选出结果。官方说明
比如 Greedy 第一步选了“猫”就继续；Beam Search 可以暂时同时保留“猫……”和“狗……”两条路线，接着比较。

## 生成了一个token后，再生成一个token的不同之处

少算很多，都是因为模型的“因果自注意力（Causal Self-Attention）。” 结合、汇总前面 Token 的信息

核心流程不变：把刚选出的 Token ID 追加到前文，再计算分数、选出下一个 Token。模型权重不变，前文变了。

以常见的开启 KV Cache（键值缓存）的推理为例，假设开始时没有已有缓存：

- **生成第一个 Token**：处理整段输入，在每层保存各位置的 K、V，用最后位置的隐藏向量计算候选分数并选出 Token。这叫 Prefill（预填充）。
- **生成后续 Token**：只把刚选出的 Token 作为新增位置送进模型，在每层读取前文缓存，计算新位置的注意力并补入它的 K、V，再用这个新位置的最终隐藏向量预测下一个 Token。这叫 Decode（逐步解码）。

为什么旧位置不用重算？因为因果注意力只允许看自己和前文，后面新增 Token 不会改变旧位置的结果。

**可以理解成每层只新增计算“最后一行”，但这一行仍要对全部可见前文计算注意力；并不是只看新 Token 自己。** 没有 KV Cache 时，也可以把增长后的整段序列重新计算，只是重复工作更多。
