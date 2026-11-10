import os

import pytest
from langgraph.errors import GraphRecursionError

from codefixer.agent.graph import build_graph
from codefixer.agent.mcp_client import load_workspace_tools, workspace_session

pytestmark = pytest.mark.anyio

_MODELS = [
    pytest.param(
        "groq:openai/gpt-oss-120b",
        marks=pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="no GROQ_API_KEY"),
    ),
    pytest.param(
        "anthropic:claude-haiku-5-5",
        marks=pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY"),
    ),
]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize("model", _MODELS)
async def test_agent_calls_a_tool_and_stops(tmp_path, model):
    """Proves the loop works end to end: the LLM must pick list_files on its
    own, observe the result, and stop - checked against two different
    providers to confirm nothing is hardcoded."""
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")

    async with workspace_session(str(tmp_path)) as session:
        tools = await load_workspace_tools(session)
        graph = build_graph(tools, model=model)

        result = await graph.ainvoke(
            {"messages": [("user", "List the files in the repo, using the tools you have.")]}
        )

    tool_messages = [message for message in result["messages"] if message.type == "tool"]
    assert tool_messages
    assert "app.py" in tool_messages[0].content


@pytest.mark.parametrize("model", _MODELS)
async def test_agent_fixes_the_buggy_shop_bug_without_touching_the_test(tmp_path, model):
    """End-to-end check of the system prompt's method and constraints, on the
    same bug as examples/buggy_shop: the agent must reproduce it, fix the code
    (not the test), and verify by re-running the tests - not just stop."""
    test_shop_source = (
        "from shop import calculate_discount\n\n\n"
        "def test_calculate_discount():\n"
        "    assert calculate_discount(100, 10) == 10\n"
    )
    (tmp_path / "shop.py").write_text(
        "def calculate_discount(price, rate):\n    return price * rate / 10\n", encoding="utf-8"
    )
    (tmp_path / "test_shop.py").write_text(test_shop_source, encoding="utf-8")

    async with workspace_session(str(tmp_path)) as session:
        tools = await load_workspace_tools(session)
        graph = build_graph(tools, model=model)

        await graph.ainvoke(
            {"messages": [("user", "There's a failing test in this repository. Fix it.")]}
        )

    assert (tmp_path / "test_shop.py").read_text(encoding="utf-8") == test_shop_source
    assert "price * rate / 100" in (tmp_path / "shop.py").read_text(encoding="utf-8")


@pytest.mark.parametrize("model", _MODELS)
async def test_agent_stops_cleanly_at_the_turn_limit(tmp_path, model):
    """A max_turns too low for the task must raise GraphRecursionError, not
    loop forever or silently return a half-finished result."""
    (tmp_path / "shop.py").write_text(
        "def calculate_discount(price, rate):\n    return price * rate / 10\n", encoding="utf-8"
    )
    (tmp_path / "test_shop.py").write_text(
        "from shop import calculate_discount\n\n\n"
        "def test_calculate_discount():\n"
        "    assert calculate_discount(100, 10) == 10\n",
        encoding="utf-8",
    )

    async with workspace_session(str(tmp_path)) as session:
        tools = await load_workspace_tools(session)
        graph = build_graph(tools, model=model, max_turns=1)

        with pytest.raises(GraphRecursionError):
            await graph.ainvoke(
                {"messages": [("user", "There's a failing test in this repository. Fix it.")]}
            )
