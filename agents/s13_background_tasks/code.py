#!/usr/bin/env python3
"""
s13: Background Tasks — thread-based async execution + notification injection.
中文概括：基于线程的后台执行与完成通知注入。

Run:  python s13_background_tasks/code.py
Need: pip install anthropic python-dotenv + .env with ANTHROPIC_API_KEY

Changes from s12:
  - threading.Thread for background execution
  - background_tasks dict for lifecycle tracking (bg_id, command, status) 后台任务生命周期状态
  - background_results dict + threading.Lock for thread-safe storage 共享状态同步
  - should_run_background: model explicit request via run_in_background param
  - is_slow_operation: fallback heuristic when model doesn't specify
  - start_background_task: dispatch to daemon thread, return bg task id
  - collect_background_results: gather completed, return as notifications 收集完成结果并生成通知
  - agent_loop: slow ops → background + placeholder, inject notifications
  - Notifications use <task_notification> format, not reused tool_use_id

Note: Teaching code keeps a basic agent loop to stay focused on background
tasks. S11's full error recovery (RecoveryState, backoff, escalation,
reactive compact, fallback model) is omitted.
"""

import os, subprocess, json, time, random, threading
from pathlib import Path
from dataclasses import dataclass, asdict

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
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
MODEL = os.environ["MODEL_ID"]

# ── Task System (from s12, synced) ──
# 复用 s12 的文件型任务状态；它与本章新增的进程内后台任务状态不是同一套生命周期。
TASKS_DIR = WORKDIR / ".tasks"
TASKS_DIR.mkdir(exist_ok=True)


@dataclass
class Task:
    id: str
    subject: str
    description: str
    status: str  # pending | in_progress | completed
    owner: str | None
    blockedBy: list[str]


def _task_path(task_id: str) -> Path:
    return TASKS_DIR / f"{task_id}.json"


def create_task(
    subject: str, description: str = "", blockedBy: list[str] | None = None
) -> Task:
    task = Task(
        id=f"task_{int(time.time())}_{random.randint(0, 9999):04d}",
        subject=subject,
        description=description,
        status="pending",
        owner=None,
        blockedBy=blockedBy or [],
    )
    save_task(task)
    return task


def save_task(task: Task):
    _task_path(task.id).write_text(json.dumps(asdict(task), indent=2))


def load_task(task_id: str) -> Task:
    return Task(**json.loads(_task_path(task_id).read_text()))


def list_tasks() -> list[Task]:
    return [
        Task(**json.loads(p.read_text())) for p in sorted(TASKS_DIR.glob("task_*.json"))
    ]


def get_task(task_id: str) -> str:
    """Return full task details as JSON."""
    task = load_task(task_id)
    return json.dumps(asdict(task), indent=2)


def can_start(task_id: str) -> bool:
    """Check if all blockedBy dependencies are completed.
    Missing dependencies are treated as blocked."""
    task = load_task(task_id)
    for dep_id in task.blockedBy:
        if not _task_path(dep_id).exists():
            return False
        if load_task(dep_id).status != "completed":
            return False
    return True


def claim_task(task_id: str, owner: str = "agent") -> str:
    task = load_task(task_id)
    if task.status != "pending":
        return f"Task {task_id} is {task.status}, cannot claim"
    if not can_start(task_id):
        deps = [
            d
            for d in task.blockedBy
            if not _task_path(d).exists() or load_task(d).status != "completed"
        ]
        return f"Blocked by: {deps}"
    task.owner = owner
    task.status = "in_progress"
    save_task(task)
    print(f"  \033[36m[claim] {task.subject} → in_progress (owner: {owner})\033[0m")
    return f"Claimed {task.id} ({task.subject})"


def complete_task(task_id: str) -> str:
    task = load_task(task_id)
    if task.status != "in_progress":
        return f"Task {task_id} is {task.status}, cannot complete"
    task.status = "completed"
    save_task(task)
    unblocked = [
        t.subject
        for t in list_tasks()
        if t.status == "pending" and t.blockedBy and can_start(t.id)
    ]
    print(f"  \033[32m[complete] {task.subject} ✓\033[0m")
    msg = f"Completed {task.id} ({task.subject})"
    if unblocked:
        msg += f"\nUnblocked: {', '.join(unblocked)}"
        print(f"  \033[33m[unblocked] {', '.join(unblocked)}\033[0m")
    return msg


# ── Prompt Assembly (from s10, synced) ──

PROMPT_SECTIONS = {
    "identity": "You are a coding agent. Act, don't explain.",
    "tools": "Available tools: bash, read_file, write_file, "
    "create_task, list_tasks, get_task, claim_task, complete_task.",
    "workspace": f"Working directory: {WORKDIR}",
    "memory": "Relevant memories are injected below when available.",
}


def assemble_system_prompt(context: dict) -> str:
    sections = [
        PROMPT_SECTIONS["identity"],
        PROMPT_SECTIONS["tools"],
        PROMPT_SECTIONS["workspace"],
    ]
    memories = context.get("memories", "")
    if memories:
        sections.append(f"Relevant memories:\n{memories}")
    return "\n\n".join(sections)


_last_context_key, _last_prompt = None, None


def get_system_prompt(context: dict) -> str:
    global _last_context_key, _last_prompt
    key = json.dumps(context, sort_keys=True, ensure_ascii=False, default=str)
    if key == _last_context_key and _last_prompt:
        return _last_prompt
    _last_context_key = key
    _last_prompt = assemble_system_prompt(context)
    return _last_prompt


# ── Tools ──


def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str, run_in_background: bool = False) -> str:
    # run_in_background is handled by agent_loop dispatch, not here
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
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


# Task tools


def run_create_task(
    subject: str, description: str = "", blockedBy: list[str] | None = None
) -> str:
    task = create_task(subject, description, blockedBy)
    deps = f" (blockedBy: {', '.join(blockedBy)})" if blockedBy else ""
    print(f"  \033[34m[create] {task.subject}{deps}\033[0m")
    return f"Created {task.id}: {task.subject}{deps}"


def run_list_tasks() -> str:
    tasks = list_tasks()
    if not tasks:
        return "No tasks. Use create_task to add some."
    lines = []
    for t in tasks:
        icon = {"pending": "○", "in_progress": "●", "completed": "✓"}.get(t.status, "?")
        deps = f" (blockedBy: {', '.join(t.blockedBy)})" if t.blockedBy else ""
        owner = f" [{t.owner}]" if t.owner else ""
        lines.append(f"  {icon} {t.id}: {t.subject} " f"[{t.status}]{owner}{deps}")
    return "\n".join(lines)


def run_get_task(task_id: str) -> str:
    try:
        return get_task(task_id)
    except FileNotFoundError:
        return f"Error: Task {task_id} not found"


def run_claim_task(task_id: str) -> str:
    return claim_task(task_id, owner="agent")


def run_complete_task(task_id: str) -> str:
    return complete_task(task_id)


TOOLS = [
    {
        "name": "bash",
        "description": "Run a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                # 模型可在 bash Tool Call 中显式请求后台执行；最终仍由 Harness 执行分派策略。
                # 当前教学实现只为 bash Tool 暴露该参数。
                "run_in_background": {"type": "boolean"},
            },
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
    {
        "name": "create_task",
        "description": "Create a new task with optional blockedBy dependencies.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "blockedBy": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["subject"],
        },
    },
    {
        "name": "list_tasks",
        "description": "List all tasks with status, owner, and dependencies.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_task",
        "description": "Get full details of a specific task by ID.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "claim_task",
        "description": "Claim a pending task. Sets owner, changes status to in_progress.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
    {
        "name": "complete_task",
        "description": "Complete an in-progress task. Reports unblocked downstream tasks.",
        "input_schema": {
            "type": "object",
            "properties": {"task_id": {"type": "string"}},
            "required": ["task_id"],
        },
    },
]

TOOL_HANDLERS = {
    "bash": run_bash,
    "read_file": run_read,
    "write_file": run_write,
    "create_task": run_create_task,
    "list_tasks": run_list_tasks,
    "get_task": run_get_task,
    "claim_task": run_claim_task,
    "complete_task": run_complete_task,
}


# ── Background Tasks (s13 new) ──
# s13 新增：进程内后台任务注册表、结果缓存与共享状态同步锁。
_bg_counter = 0
background_tasks: dict[str, dict] = {}  # bg_id → {tool_use_id, command, status}
background_results: dict[str, str] = {}  # bg_id → output
background_lock = threading.Lock()


# Harness 的启发式兜底：仅将命中慢命令关键词的 bash 调用判为后台候选。
def is_slow_operation(tool_name: str, tool_input: dict) -> bool:
    """Fallback heuristic: commands likely to take > 30s."""
    if tool_name != "bash":
        return False
    cmd = tool_input.get("command", "").lower()
    slow_keywords = [
        "install",
        "build",
        "test",
        "deploy",
        "compile",
        "docker build",
        "pip install",
        "npm install",
        "cargo build",
        "pytest",
        "make",
    ]
    return any(kw in cmd for kw in slow_keywords)


# 后台路由策略：true 直接后台；字段缺失或为 false 时仍执行 Harness 启发式判断。
def should_run_background(tool_name: str, tool_input: dict) -> bool:
    """Model explicit request takes priority; fallback to heuristic."""
    if tool_input.get("run_in_background"):
        return True
    return is_slow_operation(tool_name, tool_input)


def execute_tool(block) -> str:
    """Execute a tool call block, return output."""
    handler = TOOL_HANDLERS.get(block.name)
    if handler:
        return handler(**block.input)
    return f"Unknown tool: {block.name}"


def start_background_task(block) -> str:
    """Run tool in a daemon thread. Returns background task ID."""
    global _bg_counter
    _bg_counter += 1
    # 以至少 4 位十进制数格式化进程内 ID，便于日志阅读；不提供跨进程唯一性。
    bg_id = f"bg_{_bg_counter:04d}"
    cmd = block.input.get("command", block.name)

    def worker():
        result = execute_tool(block)
        with background_lock:
            background_tasks[bg_id]["status"] = "completed"
            background_results[bg_id] = result

    # 先注册 running 状态再启动线程，保证 worker 更新时对应任务记录已经存在。
    # 与 worker、collector 使用同一把锁同步共享状态；计数器当前由单一主循环串行更新。
    with background_lock:
        background_tasks[bg_id] = {
            "tool_use_id": block.id,
            "command": cmd,
            "status": "running",
        }
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    print(f"  \033[33m[background] dispatched {bg_id}: {cmd[:40]}\033[0m")
    return bg_id


# 在 Agent Loop 的 Tool 批次结束处轮询完成结果；这不是持续监听或主动唤醒。
def collect_background_results() -> list[str]:
    """Collect completed background results as task_notification messages."""
    with background_lock:
        ready_ids = [
            bid
            for bid, task in background_tasks.items()
            if task["status"] == "completed"
        ]
    notifications = []
    for bg_id in ready_ids:
        # 在同一临界区移除任务元数据和结果，保持两张共享表的对应关系。
        with background_lock:
            task = background_tasks.pop(bg_id)
            output = background_results.pop(bg_id, "")
        # 教学版仅做 200 字符前缀截断；这不是语义摘要，也没有完整输出的恢复引用。
        summary = output[:200] if len(output) > 200 else output
        notifications.append(
            f"<task_notification>\n"
            f"  <task_id>{bg_id}</task_id>\n"
            f"  <status>completed</status>\n"
            f"  <command>{task['command']}</command>\n"
            f"  <summary>{summary}</summary>\n"
            f"</task_notification>"
        )
        print(
            f"  \033[32m[background done] {bg_id}: "
            f"{task['command'][:40]} ({len(output)} chars)\033[0m"
        )
    return notifications


# ── Context ──


def update_context(context: dict, messages: list) -> dict:
    """Derive context from real state."""
    memories = ""
    if MEMORY_INDEX.exists():
        content = MEMORY_INDEX.read_text().strip()
        if content:
            memories = content
    return {
        "enabled_tools": list(TOOL_HANDLERS.keys()),
        "workspace": str(WORKDIR),
        "memories": memories,
    }


# ── Agent Loop (simplified, focused on background tasks) ──


def agent_loop(messages: list, context: dict):
    system = get_system_prompt(context)
    while True:
        try:
            response = client.messages.create(
                model=MODEL,
                system=system,
                messages=messages,
                tools=TOOLS,
                max_tokens=8000,
            )
        except Exception as e:
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": f"[Error] {type(e).__name__}: {e}"}
                    ],
                }
            )
            return

        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            return

        # 收集本次 assistant 响应中所有 tool_use 对应的 tool_result，组成下一条 user 消息。
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            print(f"\033[36m> {block.name}\033[0m")

            # 当前 Schema 仅允许 bash 提供 run_in_background；显式分支本身未再次校验工具名。
            if should_run_background(block.name, block.input):
                bg_id = start_background_task(block)
                # 后台分派后立即返回占位 tool_result，先完成原 tool_use 的消息协议配对。
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        # 占位结果携带 bg_id；完成通知再用同一 ID 关联后台生命周期。
                        "content": f"[Background task {bg_id} started] "
                        f"Command: {block.input.get('command', '')}. "
                        f"Result will be available when complete.",
                    }
                )
            else:
                # 未命中后台路由的 Tool Call 在主循环中同步执行。
                output = execute_tool(block)
                print(str(output)[:300])
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": output}
                )

        # Inject tool results + background notifications in one user message
        user_content = list(results)
        # Tool 批次结束后轮询完成结果，并作为独立 text block 追加到下一条 user 消息。
        bg_notifications = collect_background_results()
        if bg_notifications:
            for notif in bg_notifications:
                user_content.append({"type": "text", "text": notif})
            print(
                f"  \033[32m[inject] {len(bg_notifications)} background "
                f"notification(s)\033[0m"
            )
        messages.append({"role": "user", "content": user_content})
        context = update_context(context, messages)
        system = get_system_prompt(context)


if __name__ == "__main__":
    print("s13: background tasks")
    print("Enter a question, press Enter to send. Type q to quit.\n")
    history = []
    context = update_context({}, [])
    while True:
        try:
            query = input("\033[36ms13 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history, context)
        context = update_context(context, history)
        for block in history[-1]["content"]:
            if getattr(block, "type", None) == "text":
                print(block.text)
        print()
