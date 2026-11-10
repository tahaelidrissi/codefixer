import os

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from codefixer.agent.graph import build_graph
from codefixer.agent.mcp_client import load_workspace_tools, workspace_session
from codefixer.agent.trace import format_step


def test_format_step_renders_a_tool_call():
    message = AIMessage(
        content="",
        tool_calls=[{"name": "run_tests", "args": {"target": "."}, "id": "1"}],
    )

    assert format_step(message) == "[tool] run_tests(target=.)"


def test_format_step_renders_multiple_tool_calls_on_separate_lines():
    message = AIMessage(
        content="",
        tool_calls=[
            {"name": "read_file", "args": {"path": "a.py"}, "id": "1"},
            {"name": "read_file", "args": {"path": "b.py"}, "id": "2"},
        ],
    )

    assert format_step(message) == "[tool] read_file(path=a.py)\n[tool] read_file(path=b.py)"


def test_format_step_truncates_long_argument_values():
    message = AIMessage(
        content="",
        tool_calls=[{"name": "edit_file", "args": {"old_str": "x" * 200}, "id": "1"}],
    )

    result = format_step(message)

    assert result.startswith("[tool] edit_file(old_str=")
    assert len(result) < 120


def test_format_step_renders_a_tool_result():
    message = ToolMessage(content="1 passed", name="run_tests", tool_call_id="1")

    assert format_step(message) == "[result] 1 passed"


def test_format_step_truncates_long_tool_results():
    message = ToolMessage(content="y" * 500, name="search_code", tool_call_id="1")

    result = format_step(message)

    assert result.startswith("[result] ")
    assert len(result) < 220


def test_format_step_renders_the_final_answer():
    message = AIMessage(content="The bug is fixed.")

    assert format_step(message) == "[answer] The bug is fixed."


def test_format_step_ignores_human_and_system_messages():
    assert format_step(HumanMessage(content="Fix the bug.")) is None
    assert format_step(SystemMessage(content="You are a coding agent.")) is None


@pytest.mark.anyio
@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="no GROQ_API_KEY")
async def test_format_step_handles_real_agent_messages(tmp_path):
    """format_step must also make sense of what a real run actually produces,
    not just the synthetic messages above."""
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")

    async with workspace_session(str(tmp_path)) as session:
        tools = await load_workspace_tools(session)
        graph = build_graph(tools, model="groq:openai/gpt-oss-120b")

        steps = []
        async for state in graph.astream(
            {"messages": [("user", "List the files in the repo, using the tools you have.")]},
            stream_mode="values",
        ):
            step = format_step(state["messages"][-1])
            if step is not None:
                steps.append(step)

    assert any(step.startswith("[tool] list_files") for step in steps)
    assert any(step.startswith("[result]") for step in steps)


@pytest.fixture
def anyio_backend():
    return "asyncio"
