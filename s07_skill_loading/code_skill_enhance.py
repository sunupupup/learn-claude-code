#!/usr/bin/env python3
"""
s07 Skill Loading — enhanced resource-aware variant.

This file is intentionally separate from code.py.  It demonstrates a
progressive Skill workflow:

  1. Catalog: SYSTEM contains only Skill names and descriptions.
  2. Enhance: load_skill(name) / enhance_skill(name) returns SKILL.md plus
     an indexed resource catalog.
  3. Advance: advance_skill(name, path) reads one explicitly indexed file
     under that Skill directory.

The terms "enhance" and "advance" are teaching-demo names, not Anthropic
SDK features.  The program never executes scripts and never lets a model
choose an arbitrary path outside an indexed Skill resource.

Run from the repository root:

    .venv\\Scripts\\python.exe s07_skill_loading\\code_skill_enhance.py
"""

import ast
import json
import os
import subprocess
from pathlib import Path

import yaml

try:
    import readline

    readline.parse_and_bind("set bind-tty-special-chars off")
except ImportError:
    pass

from anthropic import Anthropic
from dotenv import load_dotenv


load_dotenv(override=True)
if os.getenv("ANTHROPIC_BASE_URL"):
    # Prefer ANTHROPIC_API_KEY for Anthropic-compatible providers when a
    # host environment also happens to contain ANTHROPIC_AUTH_TOKEN.
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKDIR = PROJECT_ROOT
SKILLS_DIR = PROJECT_ROOT / "skills"
MODEL = os.environ["MODEL_ID"]
client = Anthropic(base_url=os.getenv("ANTHROPIC_BASE_URL"))
CURRENT_TODOS: list[dict] = []


# ---------------------------------------------------------------------------
# Skill manifest and progressive resource loading
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (YAML metadata, full text body) for a SKILL.md file."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return meta if isinstance(meta, dict) else {}, parts[2].strip()


def _normalize_resource_path(value: object) -> str | None:
    """Normalize a manifest path, rejecting absolute and parent traversal."""
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip().replace("\\", "/")
    # Reject POSIX roots, Windows drive paths and UNC paths before Path parses
    # the value.  The explicit '..' check is needed before resolve().
    if raw.startswith(("/", "\\")) or (len(raw) >= 2 and raw[1] == ":"):
        return None
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        return None
    normalized = path.as_posix()
    return normalized if normalized not in ("", ".") else None


def _normalize_resources(meta: dict) -> list[dict]:
    """Convert optional frontmatter resources into a safe, small index."""
    raw_resources = meta.get("resources", [])
    if not isinstance(raw_resources, list):
        return []

    resources: list[dict] = []
    seen: set[str] = set()
    for item in raw_resources:
        if isinstance(item, str):
            raw_path, description = item, ""
        elif isinstance(item, dict):
            raw_path = item.get("path")
            description = item.get("description", "")
        else:
            continue
        path = _normalize_resource_path(raw_path)
        if path is None or path in seen:
            continue
        seen.add(path)
        resources.append(
            {
                "path": path,
                "description": description if isinstance(description, str) else "",
            }
        )
    return resources


SKILL_REGISTRY: dict[str, dict] = {}


def _scan_skills() -> None:
    """Cache Skill metadata and indexes, but not auxiliary file contents."""
    if not SKILLS_DIR.exists():
        return
    for directory in sorted(SKILLS_DIR.iterdir()):
        if not directory.is_dir():
            continue
        manifest = directory / "SKILL.md"
        if not manifest.exists():
            continue
        raw = manifest.read_text(encoding="utf-8")
        meta, _body = _parse_frontmatter(raw)
        name = meta.get("name", directory.name)
        if not isinstance(name, str) or not name.strip():
            name = directory.name
        description = meta.get("description", "")
        if not isinstance(description, str) or not description.strip():
            description = raw.split("\n")[0].lstrip("#").strip()
        SKILL_REGISTRY[name] = {
            "name": name,
            "description": description,
            "content": raw,
            "directory": directory,
            "resources": _normalize_resources(meta),
        }


_scan_skills()


def list_skills() -> str:
    """Return the cheap catalog shown to the model in SYSTEM."""
    if not SKILL_REGISTRY:
        return "(no skills found)"
    return "\n".join(
        f"- **{skill['name']}**: {skill['description']}"
        for skill in SKILL_REGISTRY.values()
    )


def _format_resource_index(skill: dict) -> str:
    resources = skill.get("resources", [])
    if not resources:
        return (
            "\n\n## Supporting resources\n"
            "No indexed supporting resources."
        )
    lines = [
        "\n\n## Supporting resources (advance with advance_skill)",
        "These files are indexed but are not loaded until needed:",
    ]
    for resource in resources:
        suffix = f" — {resource['description']}" if resource["description"] else ""
        lines.append(f"- `{resource['path']}`{suffix}")
    return "\n".join(lines)


def enhance_skill(name: str) -> str:
    """Load SKILL.md and enhance it with its on-demand resource index."""
    skill = SKILL_REGISTRY.get(name)
    if not skill:
        return f"Skill not found: {name}"
    return skill["content"] + _format_resource_index(skill)


def _read_indexed_resource(
    name: str, resource_path: str, limit: int | None = None
) -> str:
    """Read one allowlisted resource while enforcing the Skill root boundary."""
    skill = SKILL_REGISTRY.get(name)
    if not skill:
        return f"Skill not found: {name}"

    normalized = _normalize_resource_path(resource_path)
    if normalized is None:
        return "Error: resource path must be a relative path without '..'"

    indexed = {item["path"]: item for item in skill.get("resources", [])}
    if normalized not in indexed:
        return f"Error: resource not declared for skill '{name}': {resource_path}"

    skill_root = Path(skill["directory"]).resolve()
    target = (skill_root / Path(normalized)).resolve()
    if not target.is_relative_to(skill_root):
        return "Error: resource path escapes the Skill directory"
    if not target.exists():
        return f"Error: indexed resource does not exist: {normalized}"
    if not target.is_file():
        return f"Error: indexed resource is not a file: {normalized}"

    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return f"Error: cannot read resource {normalized}: {exc}"

    # Keep a single resource result bounded even when no limit is supplied.
    max_lines = 400 if limit is None else max(1, min(limit, 400))
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [
            f"... ({len(lines) - max_lines} more lines; request a smaller slice if needed)"
        ]
    return "\n".join(lines)


def advance_skill(name: str, path: str, limit: int | None = None) -> str:
    """Advance from a Skill index into one explicitly declared resource."""
    content = _read_indexed_resource(name, path, limit)
    if content.startswith("Error:") or content.startswith("Skill not found:"):
        return content
    return f"[Advanced Skill resource: {name}/{path}]\n{content}"


# Compatibility alias for the original chapter's conceptual API.
load_skill = enhance_skill


# ---------------------------------------------------------------------------
# Basic tools retained from s02-s07
# ---------------------------------------------------------------------------


def safe_path(path_text: str) -> Path:
    path = (WORKDIR / path_text).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {path_text}")
    return path


def run_bash(command: str) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=WORKDIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = (result.stdout + result.stderr).strip()
        return output[:50000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


def run_read(path: str, limit: int | None = None) -> str:
    try:
        lines = safe_path(path).read_text(encoding="utf-8").splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more lines)"]
        return "\n".join(lines)
    except Exception as exc:
        return f"Error: {exc}"


def run_write(path: str, content: str) -> str:
    try:
        target = safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as exc:
        return f"Error: {exc}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        target = safe_path(path)
        text = target.read_text(encoding="utf-8")
        if old_text not in text:
            return f"Error: text not found in {path}"
        target.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return f"Edited {path}"
    except Exception as exc:
        return f"Error: {exc}"


def run_glob(pattern: str) -> str:
    import glob

    try:
        results = []
        for match in glob.glob(pattern, root_dir=WORKDIR):
            if (WORKDIR / match).resolve().is_relative_to(WORKDIR):
                results.append(match)
        return "\n".join(results) if results else "(no matches)"
    except Exception as exc:
        return f"Error: {exc}"


def _normalize_todos(todos):
    if isinstance(todos, str):
        try:
            todos = json.loads(todos)
        except json.JSONDecodeError:
            try:
                todos = ast.literal_eval(todos)
            except (SyntaxError, ValueError):
                return None, "Error: todos must be a list or JSON array string"
    if not isinstance(todos, list):
        return None, "Error: todos must be a list"
    for index, item in enumerate(todos):
        if not isinstance(item, dict):
            return None, f"Error: todos[{index}] must be an object"
        if "content" not in item or "status" not in item:
            return None, f"Error: todos[{index}] missing 'content' or 'status'"
        if item["status"] not in ("pending", "in_progress", "completed"):
            return None, f"Error: todos[{index}] has invalid status"
    return todos, None


def run_todo_write(todos: list) -> str:
    global CURRENT_TODOS
    todos, error = _normalize_todos(todos)
    if error:
        return error
    CURRENT_TODOS = todos
    print("\n## Current Tasks")
    for item in CURRENT_TODOS:
        print(f"  [{item['status']}] {item['content']}")
    return f"Updated {len(CURRENT_TODOS)} tasks"


def extract_text(content) -> str:
    if not isinstance(content, list):
        return str(content)
    return "\n".join(
        getattr(block, "text", "")
        for block in content
        if getattr(block, "type", None) == "text"
    )


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
        "description": "Read a workspace file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write a workspace file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in a workspace file once.",
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
        "description": "Find workspace files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    },
    {
        "name": "todo_write",
        "description": "Create and manage a task list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {"type": "string"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                            },
                        },
                        "required": ["content", "status"],
                    },
                }
            },
            "required": ["todos"],
        },
    },
    {
        "name": "load_skill",
        "description": (
            "Enhance a Skill: load its SKILL.md and the indexed supporting "
            "resource catalog. Do not load resource files yet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "advance_skill",
        "description": (
            "Advance into one explicitly indexed Skill resource. Read-only; "
            "does not execute scripts or permit arbitrary paths."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "path": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["name", "path"],
        },
    },
]


TOOL_HANDLERS = {
    "bash": run_bash,
    "read_file": run_read,
    "write_file": run_write,
    "edit_file": run_edit,
    "glob": run_glob,
    "todo_write": run_todo_write,
    "load_skill": enhance_skill,
    "advance_skill": advance_skill,
}


# ---------------------------------------------------------------------------
# Hooks and Agent Loop
# ---------------------------------------------------------------------------


SYSTEM = (
    f"You are a coding agent at {WORKDIR}.\n"
    f"Skills available:\n{list_skills()}\n"
    "Progressive Skill workflow:\n"
    "1. load_skill(name) enhances the context with SKILL.md and a resource index.\n"
    "2. If a listed resource is needed, advance_skill(name, path) loads only that file.\n"
    "3. Never invent a resource path, execute scripts, or treat a Skill as permission."
)

HOOKS = {"UserPromptSubmit": [], "PreToolUse": [], "PostToolUse": [], "Stop": []}


def register_hook(event: str, callback) -> None:
    HOOKS[event].append(callback)


def trigger_hooks(event: str, *args):
    for callback in HOOKS[event]:
        result = callback(*args)
        if result is not None:
            return result
    return None


DENY_LIST = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if="]


def permission_hook(block):
    if block.name == "bash":
        command = block.input.get("command", "")
        for denied in DENY_LIST:
            if denied in command:
                print(f"Blocked dangerous command: {denied}")
                return "Permission denied"
    return None


def log_hook(block):
    print(f"[HOOK] {block.name}")


def context_inject_hook(_query: str):
    print(f"[HOOK] UserPromptSubmit: working in {WORKDIR}")


def summary_hook(messages: list):
    tool_count = sum(
        1
        for message in messages
        for block in (
            message.get("content", [])
            if isinstance(message.get("content"), list)
            else []
        )
        if isinstance(block, dict) and block.get("type") == "tool_result"
    )
    print(f"[HOOK] Stop: session used {tool_count} tool calls")


register_hook("UserPromptSubmit", context_inject_hook)
register_hook("PreToolUse", permission_hook)
register_hook("PreToolUse", log_hook)
register_hook("Stop", summary_hook)


def agent_loop(messages: list) -> None:
    for _round in range(30):
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM,
            messages=messages,
            tools=TOOLS,
            max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            trigger_hooks("Stop", messages)
            return

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            blocked = trigger_hooks("PreToolUse", block)
            if blocked:
                output = str(blocked)
            else:
                handler = TOOL_HANDLERS.get(block.name)
                output = handler(**block.input) if handler else f"Unknown: {block.name}"
                trigger_hooks("PostToolUse", block, output)
            results.append(
                {"type": "tool_result", "tool_use_id": block.id, "content": output}
            )
        messages.append({"role": "user", "content": results})
    print("[STOP] reached 30 rounds")


if __name__ == "__main__":
    print("s07 enhanced: Skill enhance + advance resource loading")
    print("Type a question, press Enter. Type q to quit.\n")
    history = []
    while True:
        try:
            query = input("s07-enhance >> ")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        trigger_hooks("UserPromptSubmit", query)
        history.append({"role": "user", "content": query})
        agent_loop(history)
        if history and isinstance(history[-1].get("content"), list):
            print(extract_text(history[-1]["content"]))
        print()
