"""图检索最小实验；笔记：../../RAG扩展-GraphRAG.md。仅标准库，无模型调用。"""

start_entity = "订单服务"  # 从问题中选出的起点；本实验手工指定，不做实体识别
max_hops = 2              # 沿关系最多走几条边；改为 1 对比缺少哪些证据

# 1. 每条关系保留原文来源；这里手工整理，替代尚未学习的自动抽取步骤。
documents = {
    "D1": "订单服务依赖订单数据库。",
    "D2": "订单数据库由李明负责。",
    "D3": "邮件服务由王芳负责。",
}
edges = [
    ("订单服务", "依赖", "订单数据库", "D1"),
    ("订单数据库", "负责人", "李明", "D2"),
    ("邮件服务", "负责人", "王芳", "D3"),
]
question = f"{start_entity}依赖的数据库由谁负责？"
if not isinstance(max_hops, int) or max_hops < 0:
    raise ValueError("max_hops 需要是非负整数。")

# 2. 做一个简单的文字匹配对照；这不是向量检索性能对比。
direct_hits = [key for key, body in documents.items() if start_entity in body]
print("问题：", question)
print("只匹配起点文字：", direct_hits)

# 3. 广度优先遍历：每一轮只从上一轮新到达的节点继续走。
frontier = [start_entity]
visited = {start_entity}
evidence_ids = []
paths = {start_entity: []}
found_paths = []
for hop in range(1, max_hops + 1):
    next_frontier = []
    for node in frontier:
        for source, relation, target, doc_id in edges:
            if source != node:
                continue  # 有向关系只沿 source → target 走
            print(f"第 {hop} 跳：{source} --{relation}--> {target} [{doc_id}]")
            if doc_id not in evidence_ids:
                evidence_ids.append(doc_id)
            path = paths[node] + [(source, relation, target, doc_id)]
            # 只接受这个问题对应的关系模式，不把任意相邻人名当答案。
            if [edge[1] for edge in path] == ["依赖", "负责人"]:
                found_paths.append(path)
            if target not in visited:
                visited.add(target)  # 防止有环时反复扩展同一节点
                paths[target] = path
                next_frontier.append(target)
    frontier = next_frontier
    if not frontier:
        break

# 4. 找到关系后仍取回原文，让后续生成可以引用证据。
context = "\n".join(f"[{key}] {documents[key]}" for key in evidence_ids)
print("\n取回的原文：\n" + (context or "没有证据"))
if found_paths:
    for path in found_paths:
        citations = " ".join(f"[{edge[3]}]" for edge in path)
        print(f"规则得到的结果（不是 LLM 生成）：{path[-1][2]} {citations}")
else:
    print("当前图与跳数内，没有找到完整的‘依赖 → 负责人’证据链。")
print("\n交给 LLM 的输入示意：\n仅根据证据回答，缺少证据则说明不知道。")
print(f"问题：{question}\n证据：\n{context}")
