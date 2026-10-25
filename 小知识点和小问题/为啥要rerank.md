# 为啥要 rerank

- 向量检索本身能处理语义，通常可以找到同义词、不同措辞但含义相近的内容。
- 它的不足是：对语义相关性的打分可能不够准确，导致候选文档排序不理想。
- “语义相似度不够”可以作为口语概括；这里指判断精度不足，不是分数数值太低。

## 为什么可能打分不准
- 表示瓶颈（Representation Bottleneck）：整段文档压缩成固定维度向量，细节可能表达不充分。
- 双编码器（Bi-encoder）分别编码问题和文档；本例 rerank 用交叉编码器（Cross-encoder）联合读取两者，补充细粒度交互。
- 字面匹配偏置（Literal Bias）：一些向量模型偏爱相同措辞，可能高估关键词重合多的内容、低估同义改写；ACL 2025 论文 [Collapse of Dense Retrievers: Short, Early, and Literal Biases Outranking Factual Evidence](https://aclanthology.org/2025.acl-long.447/) 在 Dragon+、Contriever 等模型中观察到此倾向，不代表所有模型必然如此。

## 实测例子
- 问题：怎么关闭苹果手机的自动续费？
- A 是功能介绍：向量分数 0.762836，重排分数 1.998149。
- B 是取消订阅步骤：向量分数 0.589417，重排分数 2.900497。
- 顺序从 A > B 变成 B > A；本例中 B 更能回答“怎么关闭”，两列分数不能跨列比较。

## 使用边界
- rerank 只能重排已召回的候选，也可能排错；检索效果已足够时，不必增加这一层。
- 参考：[官方检索与重排说明](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html)、[固定长度表示的局限](https://arxiv.org/abs/2005.00181)。
