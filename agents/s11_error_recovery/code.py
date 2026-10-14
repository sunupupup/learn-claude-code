#!/usr/bin/env python3
"""
s11: Error Recovery — three recovery paths + exponential backoff.

Run:  python s11_error_recovery/code.py
Need: pip install anthropic python-dotenv + .env with ANTHROPIC_API_KEY

Changes from s10:
  - LLM call wrapped in try/except with three recovery paths
  1. max_tokens 是正常响应的停止原因，不是异常；首次触发时把输出预算从 8K 提升到 64K，保持原 messages 重新生成
  - Path 1: max_tokens -> escalate 8K->64K (no append on first escalation),
            then continuation prompt (max 3)
  2. prompt_too_long 是请求异常；先执行一次紧急压缩，再用压缩后的上下文重试
  - Path 2: prompt_too_long -> reactive compact -> retry (once)
  3. 429 表示限流、529 表示服务过载；等待一段递增且带随机抖动的时间后重试
  - Path 3: 429/529 -> exponential backoff with jitter (max 10),
            fallback model on consecutive 529
  - with_retry is a plain Python wrapper around the model call; it resembles
    LangChain wrap-style middleware conceptually, but is not a LangChain hook
  - RecoveryState tracks escalation / compact / 529 / model

ASCII flow:
  messages -> prompt assembly -> compress+load -> [try] LLM [except] -> tools -> loop
                                                    |          |
                                              stop_reason   error type
                                              max_tokens?   prompt_too_long? -> compact
                                              escalate /    429/529? -> backoff
                                              continue      other? -> log + exit
"""

import os, subprocess, time, random, json
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
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
PRIMARY_MODEL = os.environ["MODEL_ID"]
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL_ID")

# ── Constants ──

ESCALATED_MAX_TOKENS = 64000
DEFAULT_MAX_TOKENS = 8000
MAX_RECOVERY_RETRIES = 3
MAX_RETRIES = 10
BASE_DELAY_MS = 500
MAX_CONSECUTIVE_529 = 3
CONTINUATION_PROMPT = (
    "Output token limit hit. Resume directly — "
    "no apology, no recap. Pick up mid-thought."
)

# ── Prompt Assembly (from s10, synced) ──

PROMPT_SECTIONS = {
    "identity": "You are a coding agent. Act, don't explain.",
    "tools": "Available tools: bash, read_file, write_file.",
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
        print("  \033[90m[cache hit] system prompt unchanged\033[0m")
        return _last_prompt
    _last_context_key = key
    _last_prompt = assemble_system_prompt(context)

    loaded = ["identity", "tools", "workspace"]
    if context.get("memories"):
        loaded.append("memory")
    print(f"  \033[32m[assembled] sections: {', '.join(loaded)}\033[0m")
    return _last_prompt


# ── Tools (unchanged) ──


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


# ── Error Recovery (s11 new) ──


class RecoveryState:
    """集中记录一次 agent_loop 内跨轮次共享的恢复状态。"""

    def __init__(self):
        # 输出预算在一次 agent_loop 中最多只升级一次。
        self.has_escalated = False
        # 64K 仍被截断后，最多追加三次续写提示。
        self.recovery_count = 0
        # 记录连续的 529，用于达到阈值后选择备用模型。
        self.consecutive_529 = 0
        # 紧急压缩最多执行一次，避免无收益地反复裁剪上下文。
        self.has_attempted_reactive_compact = False
        self.current_model = PRIMARY_MODEL


def retry_delay(attempt, retry_after=None):
    """计算指数退避延迟；调用方传入 Retry-After 时优先采用服务端建议。"""
    if retry_after:
        return retry_after
    # 基础延迟按 0.5、1、2、4……秒增长，并封顶在 32 秒。
    base = min(BASE_DELAY_MS * (2**attempt), 32000) / 1000
    # 随机抖动把并发请求的重试时刻打散，避免它们再次同时冲击服务端。
    jitter = random.uniform(0, base * 0.25)
    return base + jitter


def with_retry(fn, state: RecoveryState):
    """Exponential backoff for transient errors (429/529).
    Non-transient errors are re-raised for the outer handler."""
    for attempt in range(MAX_RETRIES):
        try:
            result = fn()
            state.consecutive_529 = 0
            return result
        except Exception as e:
            name = type(e).__name__
            msg = str(e).lower()

            # 429 rate limit -> exponential backoff
            if "ratelimit" in name.lower() or "429" in msg:
                delay = retry_delay(attempt)
                print(
                    f"  \033[33m[429 rate limit] retry {attempt+1}/{MAX_RETRIES},"
                    f" wait {delay:.1f}s\033[0m"
                )
                time.sleep(delay)
                # 等待结束后进入 for 循环的下一次调用。
                continue

            # 529 overloaded -> exponential backoff + fallback model
            # 529 表示供应商服务暂时过载；它与请求触发限流的 429 不同。
            if "overloaded" in name.lower() or "529" in msg or "overloaded" in msg:
                state.consecutive_529 += 1
                # 设计意图：当前模型连续三次 529 后，更新状态并选择备用模型。
                if state.consecutive_529 >= MAX_CONSECUTIVE_529:
                    # 教学实现尚未判断当前是否已经使用备用模型，后续 529 可能重复执行同一次“切换”。
                    if FALLBACK_MODEL:
                        state.current_model = FALLBACK_MODEL
                        state.consecutive_529 = 0
                        print(
                            f"  \033[31m[529 x{MAX_CONSECUTIVE_529}]"
                            f" switching to {FALLBACK_MODEL}\033[0m"
                        )
                    else:
                        state.consecutive_529 = 0
                        print(
                            f"  \033[31m[529 x{MAX_CONSECUTIVE_529}]"
                            f" no FALLBACK_MODEL_ID configured, continuing retry\033[0m"
                        )
                delay = retry_delay(attempt)
                print(
                    f"  \033[33m[529 overloaded] retry {attempt+1}/{MAX_RETRIES},"
                    f" wait {delay:.1f}s\033[0m"
                )
                time.sleep(delay)
                continue

            # Not transient -> re-raise for outer try/except
            raise
    raise RuntimeError(f"Max retries ({MAX_RETRIES}) exceeded")


def is_prompt_too_long_error(e: Exception) -> bool:
    """Check whether an API error indicates prompt/context too long."""
    msg = str(e).lower()
    return (
        ("prompt" in msg and "long" in msg)
        or "prompt_is_too_long" in msg
        or "context_length_exceeded" in msg
        or "max_context_window" in msg
    )


# 教学版紧急压缩只保留最后五条消息，并在前面增加一条恢复提示，不会生成摘要。
# 直接按数量截取可能破坏 assistant tool_use 与 user tool_result 的配对；生产实现需要
# 选择协议安全的切点，并保留目标、关键状态、未完成副作用和可恢复的结果引用。
def reactive_compact(messages: list) -> list:
    """Emergency compact — teaching version keeps last N messages.
    Real CC generates a compact summary via LLM, then retries with
    the compacted message list. Teaching version simplifies to tail
    retention since s08/s09 already cover LLM-based compact."""
    print("  \033[31m[reactive compact] trimming to last 5 messages\033[0m")
    tail = messages[-5:]
    return [
        {
            "role": "user",
            "content": "[Reactive compact] Earlier conversation trimmed. "
            "Continue from where you left off.",
        },
        *tail,
    ]


# ── Context ──


def update_context(context: dict, messages: list) -> dict:
    """Derive context from real state: which tools exist, whether memory files exist."""
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


# ── Agent Loop ──


def agent_loop(messages: list, context: dict):
    """Main loop with error recovery wrapping LLM calls."""
    system = get_system_prompt(context)
    state = RecoveryState()
    max_tokens = DEFAULT_MAX_TOKENS

    while True:
        # ── LLM call: with_retry handles 429/529, outer handles rest ──
        try:
            # 应用层只把 429/529 视为可原样重试的瞬时错误；需要改变请求或无法自愈的
            # 错误交给外层分类。生产实现还需与 SDK 自带重试统一预算，避免叠加重试。
            response = with_retry(
                lambda mt=max_tokens, mdl=state.current_model: client.messages.create(
                    model=mdl,
                    system=system,
                    messages=messages,
                    tools=TOOLS,
                    max_tokens=mt,
                ),
                state,
            )
        except Exception as e:
            # Path 2: prompt_too_long -> reactive compact (once)
            # 输入上下文超过模型或服务限制时，请求会在生成正常响应前被拒绝；具体由
            # 网关、路由层还是模型服务校验取决于供应商实现，应用层只依赖错误契约。
            if is_prompt_too_long_error(e):
                if not state.has_attempted_reactive_compact:
                    messages[:] = reactive_compact(messages)
                    state.has_attempted_reactive_compact = True
                    # 回到 while 循环开头，用压缩后的 messages 重新调用模型。
                    continue
                print("  \033[31m[unrecoverable] still too long after compact\033[0m")
                messages.append(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "text",
                                "text": "[Error] Context too large, cannot continue.",
                            }
                        ],
                    }
                )
                return

            # 教学版对其他错误没有分类，因此停止当前循环；“未分类”不代表它们天然不可恢复。
            name = type(e).__name__
            print(f"  \033[31m[unrecoverable] {name}: {str(e)[:100]}\033[0m")
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": f"[Error] {name}: {str(e)[:200]}"}
                    ],
                }
            )
            return

        # ── Path 1: max_tokens -> escalate or continue ──
        # max_tokens 是正常响应中的停止原因，不是 API 异常；是否恢复取决于业务是否接受
        # 截断结果。本章把它视为未完成，并尝试提高输出预算或续写。
        if response.stop_reason == "max_tokens":
            # First escalation: don't append truncated output, retry same request
            # escalate 表示提高输出额度：不保存首次截断内容，用更大的 max_tokens 重新生成。
            if not state.has_escalated:
                max_tokens = ESCALATED_MAX_TOKENS
                state.has_escalated = True
                print(
                    f"  \033[33m[max_tokens] escalating"
                    f" {DEFAULT_MAX_TOKENS} -> {ESCALATED_MAX_TOKENS}\033[0m"
                )
                continue
            # 64K still truncated: save truncated output + continuation prompt
            messages.append({"role": "assistant", "content": response.content})
            if state.recovery_count < MAX_RECOVERY_RETRIES:
                messages.append({"role": "user", "content": CONTINUATION_PROMPT})
                state.recovery_count += 1
                print(
                    f"  \033[33m[max_tokens] continuation"
                    f" {state.recovery_count}/{MAX_RECOVERY_RETRIES}\033[0m"
                )
                continue
            print("  \033[31m[max_tokens] recovery limit reached\033[0m")
            return

        # Normal completion: append assistant response
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return

        # ── Tool execution ──
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

        context = update_context(context, messages)
        system = get_system_prompt(context)


if __name__ == "__main__":
    print("s11: error recovery")
    print("Enter a question, press Enter to send. Type q to quit.\n")
    history = []
    context = update_context({}, [])
    while True:
        try:
            query = input("\033[36ms11 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        turn_start = len(history)
        history.append({"role": "user", "content": query})
        agent_loop(history, context)
        context = update_context(context, history)
        for msg in history[turn_start:]:
            if msg.get("role") != "assistant":
                continue
            for block in msg["content"]:
                if getattr(block, "type", None) == "text":
                    print(block.text)
        print()
