"""设计师账号只允许改 CSS。

preToolUse 会在工具真正执行前把参数从标准输入送进来。
脚本只往标准输出写一份 JSON：permission 为 allow 或 deny。
退出码保持 0，Cursor 才会采用这份 JSON；退出码 2 会被当成直接拒绝。
"""

import json
import subprocess
import sys
from pathlib import Path

# 给人看的提示和回给 Agent 的错误使用同一句话，方便对上这条团队规范。
DENY_MESSAGE = "设计师不允许修改非 CSS 文件"

# 只读工具的参数里也会有 path，但不能把它当成一次修改。
READ_TOOLS = {"Read", "Grep", "Glob"}
# 会改仓库文件的工具。StrReplace 与 search_replace 都列上，避免版本拼写不同。
EDIT_TOOLS = {"Write", "StrReplace", "search_replace", "Delete", "EditNotebook"}

# 脚本在 .cursor/hooks/ 下，往上两级才是仓库根。用这个目录读 git name，
# 不依赖 Cursor 当时的工作目录，避免读到别的仓库或只读到全局配置。
REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_input():
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def _tool_input(payload):
    """tool_input 文档里是对象，个别版本会先变成 JSON 字符串，两种都解开。"""
    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, str):
        tool_input = json.loads(tool_input)
    return tool_input if isinstance(tool_input, dict) else {}


def _target_path(tool_input):
    # Write / StrReplace / Delete 用 path。EditNotebook 用 target_notebook。
    for key in ("path", "file_path", "target_file", "target_notebook"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _git_user_name():
    """读取 git config user.name。读不到时返回空字符串，调用方据此放行。"""
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def _is_designer(git_name):
    # 「包含 designer」按子串判断，大小写不敏感，这样 Designer、ui-designer 都会命中。
    return "designer" in git_name.casefold()


def _is_css(path):
    return path.casefold().endswith(".css")


def _deny(path):
    message = DENY_MESSAGE if not path else f"{DENY_MESSAGE}（{path}）"
    return {
        "permission": "deny",
        "user_message": message,
        "agent_message": message,
    }


def _classify_tool(tool_name):
    """脚本内部的第二轮工具名判断。

    hooks.json 的 matcher 是第一轮，决定这个脚本启不启动。
    启动之后，Cursor 仍会在 JSON 里带上 tool_name，这里再认一次。
    """
    if tool_name in READ_TOOLS:
        return "read"
    if tool_name in EDIT_TOOLS:
        return "edit"
    # Shell、Task、MCP 等不在上面两组里，这条 CSS 规范不处理。
    return "other"


def _decide(payload, git_name):
    # 规范只约束设计师。其他身份、以及暂时读不到 git name 的情况都放行。
    # 读不到名字就放行，是为了避免 git 故障时把全团队的改文件都拦住。
    if not _is_designer(git_name):
        return {"permission": "allow"}

    # 先看工具名，再看路径。Read 即使指向 .py，也只是读取，应当放行。
    tool_name = str(payload.get("tool_name") or "")
    if _classify_tool(tool_name) != "edit":
        return {"permission": "allow"}

    path = _target_path(_tool_input(payload))
    # 没有路径时无法证明这是 CSS。设计师这一侧收紧：认不出来就拒绝。
    if not _is_css(path):
        return _deny(path)
    return {"permission": "allow"}


def main():
    try:
        payload = _load_input()
    except json.JSONDecodeError:
        # 输入坏了就无法判断是谁在改什么。这不是权限字段错误，放行并让工具自己失败。
        payload = {}

    # 输出保持纯 ASCII（中文变成 \uXXXX）。Windows 下 hook 由 PowerShell 拉起，
    # 控制台代码页不一定是 UTF-8，转义后 Cursor 仍能还原成中文，也不会把 JSON 弄坏。
    json.dump(_decide(payload, _git_user_name()), sys.stdout, ensure_ascii=True)


if __name__ == "__main__":
    main()
