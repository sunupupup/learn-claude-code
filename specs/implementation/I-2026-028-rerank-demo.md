# Rerank 排序反转实验实现

- 日期：2026-10-25
- Change：[C-2026-029](../changes/C-2026-029-rerank-demo.md)
- 使用与设计主要来源：[Demo README](../../practice/rerank-demo/README.md)
- 验收主要来源：[真实运行记录](../../practice/rerank-demo/VERIFICATION.md)

在 `practice/rerank-demo/` 实现固定 revision 的中文 BGE embedding、Qdrant 本地内存查询、
BGE cross-encoder 重排与严格反转检查。只有检索 top-k 进入重排，分数由模型计算，
预期文档对仅用于检查结果；提供自定义 query/候选输入及可选 JSON 结果导出。

真实 CPU 验证：默认问题 A > B 变为 B > A；top-k=1 无法找回 B，反转检查按预期失败；
改问功能定义时 A 在两阶段均第一。缓存完成后已在离线模式运行。
验收文档保留退票案例未反转的分数，明确单个正例不代表整体质量提升。

2026-10-25 按用户要求清理依赖与原始 JSON，Demo 目录仅保留 README、源码和验收文档。
默认样例并入源码，安装版本写入 README；虚拟环境、运行缓存及本次下载的两个模型缓存删除。

本例未验证生产检索性能或通用准确率。改动范围为 Demo、必要 Spec 与实践索引。
