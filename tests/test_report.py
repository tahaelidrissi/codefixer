import os

import pytest

from codefixer.agent.graph import build_graph
from codefixer.agent.mcp_client import load_workspace_tools, workspace_session
from codefixer.agent.report import build_report

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
async def test_report_reflects_the_real_fix(tmp_path, model):
    """files_modified and tests_passed must come from the real trace (shop.py
    edited, final run_tests green) - cause is the only field left to the LLM."""
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
        graph = build_graph(tools, model=model)

        result = await graph.ainvoke(
            {"messages": [("user", "There's a failing test in this repository. Fix it.")]}
        )
        report = build_report(result["messages"], model=model)

    assert report.files_modified == ["shop.py"]
    assert report.tests_passed is True
    assert report.cause
