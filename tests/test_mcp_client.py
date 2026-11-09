import pytest

from codefixer.agent.mcp_client import workspace_session

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_tools_list_exposes_the_five_workspace_tools(tmp_path):
    async with workspace_session(str(tmp_path)) as session:
        result = await session.list_tools()

    names = {tool.name for tool in result.tools}
    assert names == {"list_files", "read_file", "search_code", "edit_file", "run_tests"}
