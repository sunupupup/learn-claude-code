#!/usr/bin/env python3
"""
s09_memory.py - Memory System

一种可以跨会话持久保存的记忆系统。
Persistent, cross-session knowledge for the coding agent.

Storage:
    .memory/
      MEMORY.md          ← index (one line per memory, ≤200 lines)  只保存记忆名称、文件链接和描述，不保存完整正文
      feedback_tabs.md    ← individual memory files (Markdown + YAML frontmatter)
      user_profile.md
      project_facts.md

Flow in agent_loop:
    1. Load MEMORY.md index into SYSTEM prompt (cheap, always present)   索引进入 SYSTEM；具体正文按需注入当前 user turn
    2. Select relevant memories by filename/description → inject content  不通过 memory tool；程序先用 side-query 选择文件，再读取正文
    3. Run compression pipeline from s08
    4. After each turn ends → extract new memories from original messages  顶层 user turn 结束且模型不再调用工具时，从压缩前快照提取候选记忆
    5. Periodically consolidate (Dream)  达到简化阈值后，批量合并重复、冲突或过期记忆

Builds on s08 (context compact). Usage:

    python s09_memory/code.py
    Needs: pip install anthropic python-dotenv + ANTHROPIC_API_KEY in .env
"""

import os, subprocess, json, time, re
from pathlib import Path

try:
    import readline

    readline.parse_and_bind("set bind-tty-special-chars off")
except ImportError:
    pass

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(override=True)
if os.getenv("ANTHROPIC_BASE_URL"):
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

WORKDIR = Path.cwd()

# 创建 .memory 目录；MEMORY.md 会在首次重建索引时生成
MEMORY_DIR = WORKDIR / ".memory"
MEMORY_DIR.mkdir(exist_ok=True)
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"

SKILLS_DIR = WORKDIR / "skills"
TRANSCRIPT_DIR = WORKDIR / ".transcripts"  # 保存压缩前的会话记录，供调试、审计或恢复参考
TOOL_RESULTS_DIR = WORKDIR / ".task_outputs" / "tool-results"
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]


# ═══════════════════════════════════════════════════════════
#  NEW in s09: Memory System
# ═══════════════════════════════════════════════════════════

MEMORY_TYPES = ["user", "feedback", "project", "reference"]


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, parts[2].strip()

# mem_type 是记忆分类：user、feedback、project 或 reference；当前教学代码未做运行时校验
def write_memory_file(name: str, mem_type: str, description: str, body: str):
    """Write a single memory file with YAML frontmatter."""
    # slug 是适合放进文件名的短标识；这里仅做基础规范化，不等于完整的文件名安全校验
    slug = name.lower().replace(" ", "-").replace("/", "-")
    filename = f"{slug}.md"
    filepath = MEMORY_DIR / filename
    filepath.write_text(
        f"---\nname: {name}\ndescription: {description}\ntype: {mem_type}\n---\n\n{body}\n"
    )
    # 更新记忆的索引文件
    _rebuild_index()
    return filepath


def _rebuild_index():
    """Rebuild MEMORY.md index from all memory files."""
    lines = []
    for f in sorted(MEMORY_DIR.glob("*.md")):
        if f.name == "MEMORY.md":
            continue
        raw = f.read_text()
        meta, body = _parse_frontmatter(raw)
        name = meta.get("name", f.stem)
        desc = meta.get("description", body.split("\n")[0][:80])
        # 索引行格式：- [记忆名称](实际文件名) — 一行描述；type 和正文仍在单独文件中
        lines.append(f"- [{name}]({f.name}) — {desc}")
    MEMORY_INDEX.write_text("\n".join(lines) + "\n" if lines else "")


def read_memory_index() -> str:
    """Read MEMORY.md index (injected into SYSTEM every turn)."""
    if not MEMORY_INDEX.exists():
        return ""
    text = MEMORY_INDEX.read_text().strip()
    return text if text else ""


def read_memory_file(filename: str) -> str | None:
    """Read a single memory file's full content."""
    path = MEMORY_DIR / filename
    if not path.exists():
        return None
    return path.read_text()


# 扫描所有记忆文件，解析并返回 filename、name、description、type、body 等信息
def list_memory_files() -> list[dict]:
    """List all memory files with metadata."""
    result = []
    for f in sorted(MEMORY_DIR.glob("*.md")):
        if f.name == "MEMORY.md":
            continue
        raw = f.read_text()
        meta, body = _parse_frontmatter(raw)
        result.append(
            {
                "filename": f.name,
                "name": meta.get("name", f.stem),
                "description": meta.get("description", ""),
                "type": meta.get("type", "user"),
                "body": body,
            }
        )
    return result

# 根据当前会话最近的用户消息，选择本次需要加载的记忆；选择阶段只发送目录，不发送正文
def select_relevant_memories(messages: list, max_items: int = 5) -> list[str]:
    """Select relevant memory filenames by matching recent conversation against
    memory names/descriptions. Uses a simple LLM call (or falls back to keyword
    matching on name+description)."""
    files = list_memory_files()
    if not files:
        return []

    # Collect recent user text for context
    recent_texts = []
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    str(getattr(b, "text", ""))
                    for b in content
                    if getattr(b, "type", None) == "text"
                )
            if isinstance(content, str):
                recent_texts.append(content)
            if len(recent_texts) >= 3:
                break
    # 最多收集最近 3 条 user message，再截取最多 2000 个字符；这是成本与相关性的教学启发式
    recent = " ".join(reversed(recent_texts))[:2000]

    if not recent.strip():
        return []

    # Build catalog of name + description for LLM to choose from
    catalog_lines = []
    for i, f in enumerate(files):
        catalog_lines.append(f"{i}: {f['name']} — {f['description']}")
    catalog = "\n".join(catalog_lines)

    # 让 LLM 根据 recent 用户内容和 memory catalog 选择相关文件；返回位置索引便于解析，之后再映射为 filename
    prompt = (
        "Given the recent conversation and the memory catalog below, "
        "select the indices of memories that are clearly relevant. "
        "Return ONLY a JSON array of integers, e.g. [0, 3]. "
        "If none are relevant, return [].\n\n"
        f"Recent conversation:\n{recent}\n\n"
        f"Memory catalog:\n{catalog}"
    )

    try:
        response = client.messages.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        text = extract_text(response.content).strip()
        # Extract JSON array from response
        match = re.search(r"\[.*?\]", text, re.DOTALL)
        # 先提取 JSON 数组，再逐项验证元素是否为整数且位于合法文件索引范围
        if match:
            indices = json.loads(match.group())
            selected = []
            for idx in indices:
                if isinstance(idx, int) and 0 <= idx < len(files):
                    selected.append(files[idx]["filename"])
                    if len(selected) >= max_items:
                        break
            # 输出文件名数组，供 load_memories() 读取对应正文
            return selected
    except Exception:
        pass

    # 只有 side-query 抛异常或没有找到数组时才会走这里；合法但无效的索引不会再次 fallback
    # Fallback: keyword matching on name + description
    # 按空白切分，并保留长度大于 3 个字符的片段；这不是真正的分词或语义检索
    keywords = [w.lower() for w in recent.split() if len(w) > 3]
    selected = []
    # 对每个 memory 的 name+description 做子字符串匹配；这是简单降级策略，中文召回能力较弱
    for f in files:
        text = (f["name"] + " " + f["description"]).lower()
        if any(kw in text for kw in keywords):
            selected.append(f["filename"])
            if len(selected) >= max_items:
                break
    return selected


def load_memories(messages: list) -> str:
    """Load relevant memory content for injection into context."""
    # 在本次顶层 agent loop 进入模型调用前，先准备相关 memory 正文
    selected_files = select_relevant_memories(messages)
    if not selected_files:
        return ""

    parts = ["<relevant_memories>"]
    for filename in selected_files:
        content = read_memory_file(filename)
        if content:
            parts.append(content)
    parts.append("</relevant_memories>")

    # 拼成带 XML-like 边界的普通文本，不是真正经过 XML 解析的 XML
    return "\n\n".join(parts)


def extract_memories(messages: list):
    """Extract new memories from recent dialogue. Runs after each turn."""
    # 顶层 loop 结束后尝试提取候选记忆；是否写入还取决于 stop_reason、解析结果和内容校验
    # Collect recent conversation text
    dialogue_parts = []
    # 只取最近 10 个 Message 对象，不是 10 个完整对话轮次；这是控制 side-query 成本的教学启发式
    # 生产环境应评测重要记忆召回率、重复率、过期率，以及 Token、成本和延迟
    for msg in messages[-10:]:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                str(getattr(b, "text", ""))
                for b in content
                if getattr(b, "type", None) == "text"
            )
        if isinstance(content, str) and content.strip():
            dialogue_parts.append(f"{role}: {content}")
    dialogue = "\n".join(dialogue_parts)

    if not dialogue.strip():
        return

    # 仅把已有记忆的 name+description 作为 LLM 的去重提示，不是确定性去重
    existing = list_memory_files()
    existing_desc = (
        "\n".join(f"- {m['name']}: {m['description']}" for m in existing)
        if existing
        else "(none)"
    )

    prompt = (
        "Extract user preferences, constraints, or project facts from this dialogue.\n"
        "Return a JSON array. Each item: {name, type, description, body}.\n"
        "- name: short kebab-case identifier (e.g. 'user-preference-tabs')\n"
        "- type: one of 'user' (user preference), 'feedback' (guidance), "
        "'project' (project fact), 'reference' (external pointer)\n"
        "- description: one-line summary for index lookup\n"
        "- body: full detail in markdown\n"
        "If nothing new or already covered by existing memories, return [].\n\n"
        f"Existing memories:\n{existing_desc}\n\n"
        f"Dialogue:\n{dialogue[:4000]}"
    )

    try:
        response = client.messages.create(
            model=MODEL, messages=[{"role": "user", "content": prompt}], max_tokens=800
        )
        text = extract_text(response.content).strip()
        # Extract JSON array from response
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return
        items = json.loads(match.group())
        if not items:
            return
        count = 0
        for mem in items:
            name = mem.get("name", f"memory_{int(time.time())}")
            mem_type = mem.get("type", "user")
            desc = mem.get("description", "")
            body = mem.get("body", "")
            if desc and body:
                # 相同 slug 会覆盖原文件，不同 slug 会新增文件；是否重复主要依赖 LLM 取名和描述
                # 当前没有显式 update/delete 接口，也没有程序级的正文相似度或冲突检测
                write_memory_file(name, mem_type, desc, body)
                count += 1
        if count:
            print(f"\n\033[33m[Memory: extracted {count} new memories]\033[0m")
    except Exception:
        pass


CONSOLIDATE_THRESHOLD = 10


def consolidate_memories():
    """Merge duplicate/stale memories. Triggered when file count ≥ threshold."""
    files = list_memory_files()
    if len(files) < CONSOLIDATE_THRESHOLD:
        return

    catalog = "\n\n".join(
        f"## {f['filename']}\nname: {f['name']}\ndescription: {f['description']}\n{f['body']}"
        for f in files
    )

    # LLM 返回整理后的新集合；应只合并同一规则或同一事实，不能为了减少文件任意泛化
    prompt = (
        "Consolidate the following memory files. Rules:\n"
        "1. Merge duplicates into one\n"
        "2. Remove outdated/contradicted memories\n"
        "3. Keep the total under 30 memories\n"
        "4. Preserve important user preferences above all\n"
        "Return a JSON array. Each item: {name, type, description, body}.\n\n"
        f"{catalog[:16000]}"
    )

    try:
        response = client.messages.create(
            model=MODEL, messages=[{"role": "user", "content": prompt}], max_tokens=3000
        )
        text = extract_text(response.content).strip()
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            return
        items = json.loads(match.group())

        # 批量替换旧集合：先删除旧记忆文件，保留 MEMORY.md；unlink() 会删除文件，当前实现不可回滚
        # 教学实现没有锁、备份或原子替换，写入中途失败可能造成部分结果或索引不一致
        # 如果 items 为空，旧文件会被删除，但下面不会调用 write_memory_file() 重建索引
        for f in MEMORY_DIR.glob("*.md"):
            if f.name != "MEMORY.md":
                f.unlink()

        for mem in items:
            name = mem.get("name", f"memory_{int(time.time())}")
            mem_type = mem.get("type", "user")
            desc = mem.get("description", "")
            body = mem.get("body", "")
            if desc and body:
                # 旧文件已在上面用 unlink() 删除；这里开始写入整理后的新文件
                write_memory_file(name, mem_type, desc, body)

        print(
            f"\n\033[33m[Memory: consolidated {len(files)} → {len(items)} memories]\033[0m"
        )
    except Exception:
        pass


# Build SYSTEM with memory index
def build_system() -> str:
    index = read_memory_index()
    memories_section = f"\n\nMemories available:\n{index}" if index else ""
    return (
        f"You are a coding agent at {WORKDIR}."
        f"{memories_section}\n"
        "Relevant memories are injected below. Respect user preferences from memory.\n"
        "When the user says 'remember' or expresses a clear preference, extract it as a memory."
    )


SUB_SYSTEM = (
    f"You are a coding agent at {WORKDIR}. "
    "Complete the task you were given, then return a concise summary. "
    "Do not delegate further."
)


# ═══════════════════════════════════════════════════════════
#  FROM s02-s08 (skeleton): Basic tools
# ═══════════════════════════════════════════════════════════


def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=WORKDIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    try:
        file_path = safe_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        file_path = safe_path(path)
        text = file_path.read_text()
        if old_text not in text:
            return f"Error: text not found in {path}"
        file_path.write_text(text.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


def run_glob(pattern: str) -> str:
    import glob as g

    try:
        results = []
        for match in g.glob(pattern, root_dir=WORKDIR):
            if (WORKDIR / match).resolve().is_relative_to(WORKDIR):
                results.append(match)
        return "\n".join(results) if results else "(no matches)"
    except Exception as e:
        return f"Error: {e}"


def extract_text(content) -> str:
    if not isinstance(content, list):
        return str(content)
    return "\n".join(
        getattr(b, "text", "") for b in content if getattr(b, "type", None) == "text"
    )


# Subagent (simplified from s06-s07)
SUB_TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
]
SUB_HANDLERS = {"bash": run_bash, "read_file": run_read, "write_file": run_write}


def spawn_subagent(task: str) -> str:
    print(f"\n\033[35m[Subagent spawned]\033[0m")
    messages = [{"role": "user", "content": task}]
    for _ in range(30):
        response = client.messages.create(
            model=MODEL,
            system=SUB_SYSTEM,
            messages=messages,
            tools=SUB_TOOLS,
            max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = SUB_HANDLERS.get(block.name)
                output = handler(**block.input) if handler else f"Unknown: {block.name}"
                print(f"  \033[90m[sub] {block.name}: {str(output)[:100]}\033[0m")
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": output}
                )
        messages.append({"role": "user", "content": results})
    result = extract_text(messages[-1]["content"])
    if not result:
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                result = extract_text(msg["content"])
                if result:
                    break
        if not result:
            result = "Subagent stopped after 30 turns without final answer."
    print(f"\033[35m[Subagent done]\033[0m")
    return result


# ═══════════════════════════════════════════════════════════
#  FROM s08 (skeleton): Compaction pipeline
# ═══════════════════════════════════════════════════════════

CONTEXT_LIMIT = 50000
KEEP_RECENT = 3
PERSIST_THRESHOLD = 30000


def estimate_size(msgs):
    return len(str(msgs))


def _block_type(block):
    return (
        block.get("type") if isinstance(block, dict) else getattr(block, "type", None)
    )


def _message_has_tool_use(msg):
    if msg.get("role") != "assistant":
        return False
    content = msg.get("content")
    if not isinstance(content, list):
        return False
    return any(_block_type(block) == "tool_use" for block in content)


def _is_tool_result_message(msg):
    if msg.get("role") != "user":
        return False
    content = msg.get("content")
    if not isinstance(content, list):
        return False
    return any(
        isinstance(block, dict) and block.get("type") == "tool_result"
        for block in content
    )


# Message 级上下文裁剪：删除中间历史，保留头部和尾部，并尽量保护相邻的工具调用结果配对
def snip_compact(msgs, mx=50):
    if len(msgs) <= mx:
        return msgs
    head_end, tail_start = 3, len(msgs) - (mx - 3)
    if head_end > 0 and _message_has_tool_use(msgs[head_end - 1]):
        while head_end < len(msgs) and _is_tool_result_message(msgs[head_end]):
            head_end += 1
    if (
        tail_start > 0
        and tail_start < len(msgs)
        and _is_tool_result_message(msgs[tail_start])
        and _message_has_tool_use(msgs[tail_start - 1])
    ):
        tail_start -= 1
    if head_end >= tail_start:
        return msgs
    return (
        msgs[:head_end]
        + [{"role": "user", "content": f"[snipped {tail_start - head_end} msgs]"}]
        + msgs[tail_start:]
    )


def collect_tool_results(msgs):
    blocks = []
    for mi, msg in enumerate(msgs):
        if msg.get("role") != "user" or not isinstance(msg.get("content"), list):
            continue
        for bi, block in enumerate(msg["content"]):
            if isinstance(block, dict) and block.get("type") == "tool_result":
                blocks.append((mi, bi, block))
    return blocks

# 保留最近 3 个 tool_result block；更早且超过 120 个字符的正文替换为不可自动恢复的占位符
def micro_compact(msgs):
    tr = collect_tool_results(msgs)
    if len(tr) <= KEEP_RECENT:
        return msgs
    for _, _, b in tr[:-KEEP_RECENT]:
        if len(b.get("content", "")) > 120:
            b["content"] = "[Earlier tool result compacted.]"
    return msgs


# 将超大的 tool result 落盘到 .task_outputs/tool-results/<tool_use_id>.txt，向上下文返回路径和预览
def persist_large(tid, out):
    if len(out) <= PERSIST_THRESHOLD:
        return out
    TOOL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    p = TOOL_RESULTS_DIR / f"{tid}.txt"
    if not p.exists():
        p.write_text(out)
    return f"<persisted-output>\nFull: {p}\nPreview:\n{out[:2000]}\n</persisted-output>"


def tool_result_budget(msgs, mx=200_000):
    last = msgs[-1] if msgs else None
    if (
        not last
        or last.get("role") != "user"
        or not isinstance(last.get("content"), list)
    ):
        return msgs
    blocks = [
        (i, b)
        for i, b in enumerate(last["content"])
        if isinstance(b, dict) and b.get("type") == "tool_result"
    ]
    total = sum(len(str(b.get("content", ""))) for _, b in blocks)
    if total <= mx:
        return msgs
    for _, block in sorted(
        blocks, key=lambda p: len(str(p[1].get("content", ""))), reverse=True
    ):
        if total <= mx:
            break
        c = str(block.get("content", ""))
        if len(c) <= PERSIST_THRESHOLD:
            continue
        block["content"] = persist_large(block.get("tool_use_id", "?"), c)
        total = sum(len(str(b.get("content", ""))) for _, b in blocks)
    return msgs


def write_transcript(msgs):
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    p = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"
    with p.open("w") as f:
        for m in msgs:
            f.write(json.dumps(m, default=str) + "\n")
    return p


def summarize_history(msgs):
    conv = json.dumps(msgs, default=str)[:80000]
    r = client.messages.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": "Summarize this coding-agent conversation so work can continue.\n"
                "Preserve: 1. current goal, 2. key findings, 3. files changed, 4. remaining work, 5. user constraints.\n\n"
                + conv,
            }
        ],
        max_tokens=2000,
    )
    return extract_text(r.content).strip()


def compact_history(msgs):
    # 压缩前把完整 messages 写入 JSONL transcript，供后续调试、审计或人工恢复参考
    write_transcript(msgs)
    summary = summarize_history(msgs)
    # 用一条摘要消息替换活跃 messages；原始 transcript 不会自动重新注入模型
    return [{"role": "user", "content": f"[Compacted]\n\n{summary}"}]


def reactive_compact(msgs):
    write_transcript(msgs)
    summary = summarize_history(msgs)
    # 应急压缩：摘要旧历史并保留最近 5 条；必要时向前多保留一条以保护工具调用配对
    tail_start = max(0, len(msgs) - 5)
    if (
        tail_start > 0
        and tail_start < len(msgs)
        and _is_tool_result_message(msgs[tail_start])
        and _message_has_tool_use(msgs[tail_start - 1])
    ):
        tail_start -= 1
    return [
        {"role": "user", "content": f"[Reactive compact]\n\n{summary}"},
        *msgs[tail_start:],
    ]


# ═══════════════════════════════════════════════════════════
#  Tool Definitions (skeleton — fewer tools to focus on memory)
# ═══════════════════════════════════════════════════════════

TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in a file once.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "glob",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
    {
        "name": "task",
        "description": "Launch a subagent to handle a subtask.",
        "input_schema": {
            "type": "object",
            "properties": {"description": {"type": "string"}},
            "required": ["description"],
        },
    },
]

TOOL_HANDLERS = {
    "bash": run_bash,
    "read_file": run_read,
    "write_file": run_write,
    "edit_file": run_edit,
    "glob": run_glob,
    "task": spawn_subagent,
}


# ═══════════════════════════════════════════════════════════
#  agent_loop — s09: inject memories + extract after each turn
# ═══════════════════════════════════════════════════════════

MAX_REACTIVE_RETRIES = 1


def agent_loop(messages: list):
    reactive_retries = 0
    # s09: inject relevant memory content into the current user turn
    memories_content = load_memories(messages)
    memory_turn = (
        len(messages) - 1
        if messages and isinstance(messages[-1].get("content"), str)
        else None
    )
    # s09: build system once per user turn; memory is updated after the loop returns
    system = build_system()

    while True:
        # s09: save pre-compression snapshot for accurate memory extraction
        pre_compress = [
            (
                m
                if isinstance(m, dict)
                else {"role": m.get("role", ""), "content": str(m.get("content", ""))}
            )
            for m in messages
        ]

        # s08: compression pipeline (budget → snip → micro)
        messages[:] = tool_result_budget(messages)
        messages[:] = snip_compact(messages)
        messages[:] = micro_compact(messages)

        # 如果粗略估算超过教学阈值，则进行一次历史摘要；CONTEXT_LIMIT 是字符数，不是真实 Token 上限
        if estimate_size(messages) > CONTEXT_LIMIT:
            print("[auto compact]")
            messages[:] = compact_history(messages)

        try:
            request_messages = messages
            if (
                memories_content
                and memory_turn is not None
                and memory_turn < len(messages)
            ):
                request_messages = messages.copy()
                request_messages[memory_turn] = {
                    **messages[memory_turn],
                    "content": memories_content
                    + "\n\n"
                    + messages[memory_turn]["content"],
                }
            response = client.messages.create(
                model=MODEL,
                system=system,
                messages=request_messages,
                tools=TOOLS,
                max_tokens=8000,
            )
            reactive_retries = 0
        except Exception as e:
            # API 实际返回 prompt_too_long 或 too many tokens 后触发 reactive compact，当前最多重试一次
            if (
                "prompt_too_long" in str(e).lower()
                or "too many tokens" in str(e).lower()
            ) and reactive_retries < MAX_REACTIVE_RETRIES:
                print("[reactive compact]")
                messages[:] = reactive_compact(messages)
                reactive_retries += 1
                continue
            raise

        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            # 只有模型结束本轮、不再请求工具时才提取；中间工具轮次不提取，API 失败或空数组通常不新增
            # 写入过程中若发生异常，仍需防止已经写入部分记忆后留下不一致状态
            # s09: extract from pre-compression snapshot for full fidelity
            extract_memories(pre_compress)
            consolidate_memories()
            return

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            print(f"\033[36m> {block.name}\033[0m")
            handler = TOOL_HANDLERS.get(block.name)
            output = handler(**block.input) if handler else f"Unknown: {block.name}"
            print(str(output)[:200])
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": output}
            )
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    print("s09: Memory — persistent cross-session knowledge")
    print("输入问题，回车发送。输入 q 退出。\n")
    history = []
    # 每个新的 CLI query 启动一个顶层 agent_loop；相关 memory 在该 loop 开始时选择一次，
    # 不会在同一 loop 的每个工具调用轮次重新选择
    while True:
        try:
            query = input("\033[36ms09 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        for block in history[-1]["content"]:
            if getattr(block, "type", None) == "text":
                print(block.text)
        print()
