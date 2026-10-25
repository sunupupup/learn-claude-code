# 真实运行验收

日期：2026-10-25。Windows、Python 3.11.14、CPU，4 个计算线程。
依赖：torch 2.14.1、sentence-transformers 5.1.2、transformers 4.57.3、qdrant-client 1.15.1。
模型 ID、固定 revision 与默认候选原文保存在 [demo.py](./demo.py) 中，关键实测分数保留在本文。
依赖、模型缓存与原始 JSON 已按用户要求删除；以下命令记录当时的验收过程，重新运行需先按 README 安装。

## 1. 默认样例：严格反转，通过

```powershell
$env:HF_HUB_OFFLINE='1'
practice/rerank-demo/.venv/Scripts/python.exe practice/rerank-demo/demo.py --check --output practice/rerank-demo/result.json
```

模型完整缓存后，在 `HF_HUB_OFFLINE=1` 下完成真实计算，退出码 **0**。
结果汇总如下。

Query：**怎么关闭苹果手机的自动续费？**

| 文档 | 内容作用 | 向量分数 | 向量名次 | 重排分数 | 重排名次 |
|---|---|---:|---:|---:|---:|
| A | 介绍自动续费是什么 | 0.762836 | 1 | 1.998149 | 2 |
| B | 说明如何取消订阅 | 0.589417 | 2 | 2.900497 | 1 |
| C | 屏幕亮度 | 0.486033 | 3 | -4.808917 | 3 |
| D | 耳机电量 | 0.390899 | 4 | -5.829095 | 4 |

程序检查得到 `inversions = [["A", "B"]]`，且 `check_passed = true`。
两个分数列各自排序，不跨列比较数值；重排分数不是概率。

## 2. 只召回一篇：不能找回 B，通过边界验证

```powershell
practice/rerank-demo/.venv/Scripts/python.exe practice/rerank-demo/demo.py --top-k 1 --check --output practice/rerank-demo/evidence/top1.json
```

向量检索只有 A，rerank 后也只有 A。`inversions = []`，退出码 **1**，符合预期。
这证明验收不会为了显示“成功”而添加未召回的 B 或伪造排序。

## 3. 换成定义问题：A 应当排前面

```powershell
practice/rerank-demo/.venv/Scripts/python.exe practice/rerank-demo/demo.py --query "苹果手机的自动续费功能是什么？" --output practice/rerank-demo/evidence/definition-query.json
```

退出码 **0**。A 向量分数 **0.792865**、重排分数 **7.254363**，两个阶段均第一。
这不是要求 rerank 总把 B 提升；应看当前问题究竟在问“是什么”还是“怎么关闭”。

## 4. 保留未反转的案例

最初尝试“因公司取消出差产生的退票手续费能否报销”：A 讨论个人原因取消，B 讨论公司调整公务行程。
向量检索 A **0.853336** > B **0.746258**；重排仍为 A **7.873811** > B **5.437149**。
其 `--check` 返回 **1**，没有复现预期反转。
这个失败案例说明：对本次模型与这些文本，reranker 没有正确区分适用条件。
不能从成功例子推出 rerank 总会理解否定、主体或业务规则。

其他检查：`--help`、输入格式检查、Python 语法编译及 Qdrant 本地余弦查询通过。
上述证据只验证小样本教学行为，不验证通用准确率、吞吐量或远程数据库部署。

清理前已确认源码内置样例与原 JSON 一致，并重新运行 `--check` 通过，默认样例分数与上表一致。
