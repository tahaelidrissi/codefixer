import pytest
from langchain_core.tools import ToolException

from codefixer.agent.graph import _build_skill_tool
from codefixer.skills.loader import SKILLS_DIR


def test_skill_tool_loads_a_real_skills_body():
    tool = _build_skill_tool([SKILLS_DIR])

    result = tool.invoke({"name": "write-pytest-test"})

    assert "test" in result.lower()


def test_skill_tool_raises_tool_exception_for_an_unknown_name():
    tool = _build_skill_tool([SKILLS_DIR])

    with pytest.raises(ToolException):
        tool.invoke({"name": "does-not-exist"})


def test_skill_tool_loads_a_repo_specific_skill(tmp_path):
    repo_skill_dir = tmp_path / "custom-skill"
    repo_skill_dir.mkdir()
    (repo_skill_dir / "SKILL.md").write_text(
        "---\nname: custom-skill\ndescription: d\n---\nRepo-specific instructions.\n", encoding="utf-8"
    )
    tool = _build_skill_tool([SKILLS_DIR, tmp_path])

    result = tool.invoke({"name": "custom-skill"})

    assert result == "Repo-specific instructions."
