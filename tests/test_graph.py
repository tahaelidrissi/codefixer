import os

import pytest

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
    """Proves the loop works end to end, with no system prompt or turn limit yet:
    the LLM must pick list_files on its own, observe the result, and stop -
    checked against two different providers to confirm nothing is hardcoded."""
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
