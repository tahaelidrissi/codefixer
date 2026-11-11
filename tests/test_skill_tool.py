import pytest
from langchain_core.tools import ToolException

from codefixer.agent.graph import _build_skill_tool


def test_skill_tool_loads_a_real_skills_body():
    tool = _build_skill_tool()

    result = tool.invoke({"name": "write-pytest-test"})

    assert "test" in result.lower()


def test_skill_tool_raises_tool_exception_for_an_unknown_name():
    tool = _build_skill_tool()

    with pytest.raises(ToolException):
        tool.invoke({"name": "does-not-exist"})
