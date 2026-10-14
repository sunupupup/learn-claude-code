from __future__ import annotations

from pathlib import Path
import py_compile

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = ROOT / "agents"
# 扫描新版章节及其补充脚本，避免只扫描旧版 agents/*.py 而漏掉全部课程。
AGENT_FILES = sorted(
    path for path in AGENTS_DIR.glob("s[0-9][0-9]_*/**/*.py")
)
AGENT_IDS = [str(path.relative_to(AGENTS_DIR)) for path in AGENT_FILES]


@pytest.mark.parametrize("agent_path", AGENT_FILES, ids=AGENT_IDS)
def test_agent_scripts_compile(agent_path: Path) -> None:
    _ = py_compile.compile(str(agent_path), doraise=True)


def test_agent_scripts_exist() -> None:
    # 目录迁移后仍需保留完整 s01-s20 主线，补充脚本不计入章节数量。
    chapters = sorted(path.parent.name[:3] for path in AGENTS_DIR.glob("s[0-9][0-9]_*/code.py"))
    assert chapters == [f"s{index:02d}" for index in range(1, 21)]
