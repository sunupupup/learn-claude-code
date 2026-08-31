"""Deterministic tests for the s07 enhanced Skill resource loader."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "s07_skill_loading" / "code_skill_enhance.py"
spec = importlib.util.spec_from_file_location("s07_skill_enhance", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_agent_builder_resource_index_is_cached_without_resource_contents():
    skill = module.SKILL_REGISTRY["agent-builder"]
    paths = {item["path"] for item in skill["resources"]}
    assert "references/minimal-agent.py" in paths
    assert "scripts/init_agent.py" in paths
    assert all("content" not in item for item in skill["resources"])


def test_enhance_skill_returns_skill_and_resource_catalog():
    enhanced = module.enhance_skill("agent-builder")
    assert "# Agent Builder" in enhanced
    assert "references/minimal-agent.py" in enhanced
    assert "scripts/init_agent.py" in enhanced


def test_advance_skill_reads_indexed_resource_with_line_limit():
    result = module.advance_skill(
        "agent-builder", "references/minimal-agent.py", limit=3
    )
    assert result.startswith("[Advanced Skill resource: agent-builder/")
    assert "... (" in result


def test_advance_skill_rejects_undeclared_and_traversal_paths():
    assert "not declared" in module.advance_skill("agent-builder", "SKILL.md")
    assert "relative path" in module.advance_skill("agent-builder", "../README.md")
    assert "relative path" in module.advance_skill("agent-builder", "C:/secret.txt")


def test_advance_skill_reports_missing_resource_and_unknown_skill():
    skill = module.SKILL_REGISTRY["agent-builder"]
    missing = {"path": "references/does-not-exist.md", "description": ""}
    skill["resources"].append(missing)
    try:
        assert "does not exist" in module.advance_skill(
            "agent-builder", "references/does-not-exist.md"
        )
    finally:
        skill["resources"].remove(missing)
    assert "Skill not found" in module.advance_skill("missing", "x.md")


def test_skill_without_index_remains_compatible():
    result = module.load_skill("code-review")
    assert "# Code Review Skill" in result
    assert "No indexed supporting resources" in result
