# Rerank 排序反转实验

- 状态：done
- 日期：2026-10-25
- 用户授权：在 `practice/` 创建可运行 Demo，展示向量检索 A > B、重排 B > A。

采用本地中文 BGE embedding、Qdrant 本地内存模式与 BGE cross-encoder。
固定模型 revision；只把检索 top-k 交给重排；输出两类真实分数，允许反转未出现。
人工选择用于教学的样例，不把一个案例当成整体质量评估。

验收：真实模型运行得到严格反转；缩小 top-k 后无法找回未召回文档；
保留运行证据、运行命令、关键中文注释。设计和使用主要来源为
[Demo README](../../practice/rerank-demo/README.md)。不自动提交或 push。

已完成实现及真实模型验收，见 [I-2026-028](../implementation/I-2026-028-rerank-demo.md)。
