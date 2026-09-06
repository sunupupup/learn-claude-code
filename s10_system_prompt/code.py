#!/usr/bin/env python3
"""
s10: System Prompt — Runtime prompt assembly with caching.

Run:  python s10_system_prompt/code.py
Need: pip install anthropic python-dotenv + .env with ANTHROPIC_API_KEY

Changes from s09:
  - PROMPT_SECTIONS: topic-keyed dict of prompt fragments
  - assemble_system_prompt(context): select + join sections by real state
  - get_system_prompt(context): deterministic cache via json.dumps
  - agent_loop uses get_system_prompt(context) instead of hardcoded SYSTEM

Memory section loads when .memory/MEMORY.md exists (real state, not keywords).
"""

import os, subprocess, json
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
MEMORY_DIR = WORKDIR / ".memory"
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"

# 这两个配置故意保持显式：本章只演示“加载哪些来源”，
# 不自动扫描任何未配置的指令文件或 Skill。
AGENT_INSTRUCTION_FILES: tuple[Path, ...] = ()
# 例如：("agent-builder",)；留空表示本次运行不加载 Skill。
ACTIVE_SKILL_NAMES: tuple[str, ...] = ()
SKILLS_DIR = WORKDIR / "skills"

client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]


# ── Prompt Sections ──

PROMPT_SECTIONS = {
    "identity": "You are a coding agent. Act, don't explain.",
    "tools": "Available tools: bash, read_file, write_file.",
    "workspace": f"Working directory: {WORKDIR}",
    "memory": "Relevant memories are injected below when available.",
}


def assemble_system_prompt(context: dict) -> str:
    """Select and join prompt sections based on current context."""
    sections = []

    # Always loaded — identity, tools, workspace
    sections.append(PROMPT_SECTIONS["identity"])
    sections.append(PROMPT_SECTIONS["tools"])
    sections.append(PROMPT_SECTIONS["workspace"])

    # 条件加载：只有 context 中存在非空 Memory 内容时才注入。
    # 同样的模式也可以扩展到其他运行时指令文件、已激活的 Skill 等外部来源；
    # 但不同来源仍需要各自的加载、作用域、信任和优先级规则。
    memories = context.get("memories", "")
    if memories:
        sections.append(f"Relevant memories:\n{memories}")

    instructions = context.get("instructions", "")
    if instructions:
        # 只有加载到非空运行时指令时，才把这一段加入 System Prompt。
        sections.append(f"Runtime instructions:\n{instructions}")

    active_skills = context.get("active_skills", "")
    if active_skills:
        # Skill 必须先被显式选中并成功读取，才会进入当前 Prompt。
        sections.append(f"Active skills:\n{active_skills}")

    return "\n\n".join(sections)


_last_context_key = None
_last_prompt = None


# 这里的缓存只避免当前进程内重复拼接 System Prompt，
# 不保证模型服务商的 API 层 Prompt Cache 一定命中。
# 是否重新组装，取决于 context 是否发生变化。
def get_system_prompt(context: dict) -> str:
    """Cache wrapper — reassemble only when context changes.

    Uses json.dumps for deterministic serialization, not Python's hash()
    which has process randomization and fails on nested dicts/lists.
    This cache only avoids redundant string assembly within a process.
    Real Claude Code additionally protects API-level prompt cache via
    stable section ordering and SYSTEM_PROMPT_DYNAMIC_BOUNDARY.
    """
    global _last_context_key, _last_prompt
    key = json.dumps(context, sort_keys=True, ensure_ascii=False, default=str)
    if key == _last_context_key and _last_prompt:
        print("  \033[90m[cache hit] system prompt unchanged\033[0m")
        return _last_prompt
    _last_context_key = key
    # context 的来源需要沿 update_context() 继续追踪：
    # 它是根据当前运行状态重新生成的快照。
    _last_prompt = assemble_system_prompt(context)

    loaded = ["identity", "tools", "workspace"]
    if context.get("memories"):
        loaded.append("memory")
    if context.get("instructions"):
        loaded.append("instructions")
    if context.get("active_skills"):
        loaded.append("active_skills")
    print(f"  \033[32m[assembled] sections: {', '.join(loaded)}\033[0m")
    return _last_prompt


# ── Tools ──


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
            "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}},
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

TOOL_HANDLERS = {"bash": run_bash, "read_file": run_read, "write_file": run_write}


# ── Context ──


# 文件缓存的结构：
#   绝对路径 -> ((最后修改时间纳秒, 文件大小), 文件文本)
# signature 为 None 表示文件当前不存在，这样文件后来创建时也能触发重新读取。
_file_text_cache: dict[str, tuple[tuple[int, int] | None, str]] = {}


def _read_cached_text(path: Path) -> str:
    """只有文件状态变化时才重新读取文本文件。"""
    # 统一使用绝对路径作为缓存 key，避免同一个文件通过相对路径和绝对路径
    # 访问时产生两份缓存。
    cache_key = str(path.resolve())

    # 每次调用仍然需要检查文件元数据，但这里只是 stat，不会读取文件正文。
    # mtime_ns 比普通 mtime 精度更高；再配合 size，可以覆盖大多数教学场景。
    try:
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        # 文件被删除时，把当前状态记为“缺失”，避免继续使用旧内容。
        signature = None

    cached = _file_text_cache.get(cache_key)
    if cached and cached[0] == signature:
        # 文件的修改时间和大小都没有变化，直接复用上一次读取的正文。
        return cached[1]

    # 首次读取、文件发生变化，或文件从不存在变为存在时，才读取正文。
    content = path.read_text().strip() if signature is not None else ""
    _file_text_cache[cache_key] = (signature, content)
    return content


def _join_cached_files(paths: tuple[Path, ...]) -> str:
    """读取一组已配置文件，并拼接其中非空的正文。"""
    # 每个文件分别经过 _read_cached_text()，因此不会因为批量加载而绕过缓存。
    contents = [_read_cached_text(path) for path in paths]
    # 空文件和不存在的文件不进入最终 context，避免给 Prompt 增加无效内容。
    return "\n\n".join(content for content in contents if content)


def load_agents_in_scope() -> str:
    """加载显式配置的运行时指令，不自动扫描未知文件。"""
    # AGENT_INSTRUCTION_FILES 是外部配置入口；本例不在函数内部猜测文件位置。
    return _join_cached_files(AGENT_INSTRUCTION_FILES)


def load_selected_skills() -> str:
    """根据显式选择的 Skill 名称，加载对应的 SKILL.md。"""
    # ACTIVE_SKILL_NAMES 只保存 Skill 名称，真正的文件路径由统一目录规则拼出。
    # 没有被选中的 Skill 不会读取，也不会进入 context。
    paths = tuple(SKILLS_DIR / name / "SKILL.md" for name in ACTIVE_SKILL_NAMES)
    return _join_cached_files(paths)


# context 是运行时状态快照，不是完整的对话历史。
# 本例每次重新读取 Memory、工具注册表和工作目录，并返回一个新的 dict。
# 如果 MEMORY.md 不存在或为空，就不把空的 memory 内容放进 System Prompt。
# 其他动态来源也可以采用相同模式，但需要分别处理作用域、信任和加载策略。
def update_context(context: dict, messages: list) -> dict:
    """根据当前运行状态重新生成一份 context 快照。"""
    # 教学实现直接读取 MEMORY.md 的全部非空内容；
    # 生产实现通常还需要按相关性、大小和权限进行筛选。
    memories = _read_cached_text(MEMORY_INDEX)
    return {
        # 工具注册表是当前实际可执行的工具集合。
        "enabled_tools": list(TOOL_HANDLERS.keys()),
        # 工作目录是本次 Agent 执行环境的一部分。
        "workspace": str(WORKDIR),
        # Memory、运行时指令和 Skill 都是按需加载的动态文本。
        "memories": memories,
        "instructions": load_agents_in_scope(),
        "active_skills": load_selected_skills(),
    }


# ── Agent Loop ──


def agent_loop(messages: list, context: dict):
    """Main loop — uses assembled system prompt instead of hardcoded SYSTEM."""
    system = get_system_prompt(context)
    while True:
        response = client.messages.create(
            model=MODEL, system=system, messages=messages, tools=TOOLS, max_tokens=8000
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
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

        # 工具执行可能改变外部状态，因此工具轮次结束后重新生成 context 快照。
        # 本例采用全量重建，而不是修改原有 dict。
        context = update_context(context, messages)
        # 每次都会调用 get_system_prompt()，但 context 不变时只是 cache hit，
        # 不会重新执行 assemble_system_prompt()。
        system = get_system_prompt(context)


if __name__ == "__main__":
    print("s10: system prompt — runtime assembly")
    print("Enter a question, press Enter to send. Type q to quit.\n")
    history = []
    # 初始 context 是当前运行状态的快照：工作目录、已注册工具和 Memory 索引内容。
    context = update_context({}, [])
    while True:
        try:
            query = input("\033[36ms10 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        # history 保存当前会话的消息，包括 user、assistant 和 tool_result；
        # System Prompt 通过 system 参数单独传给模型，不放在 history 中。
        history.append({"role": "user", "content": query})
        # agent_loop() 处理当前用户请求；内部 while True 可能经历多轮
        # “模型调用 → 工具执行 → 继续调用”。
        agent_loop(history, context)
        # 当前请求结束后刷新一次 context，为下一轮用户输入准备最新状态。
        context = update_context(context, history)
        for block in history[-1]["content"]:
            if getattr(block, "type", None) == "text":
                print(block.text)
        print()
