import json
import os

import pytest

from codefixer.agent.github_client import github_session
from conftest import requires_docker

pytestmark = [pytest.mark.anyio, requires_docker, pytest.mark.skipif(not os.environ.get("GITHUB_TOKEN"), reason="no GITHUB_TOKEN")]


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_tools_list_exposes_known_github_tools():
    async with github_session() as session:
        result = await session.list_tools()

    names = {tool.name for tool in result.tools}
    assert "get_me" in names
    assert "create_pull_request" in names


async def test_get_me_returns_the_authenticated_account():
    async with github_session() as session:
        result = await session.call_tool("get_me", {})

    text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
    payload = json.loads(text)
    assert "login" in payload
