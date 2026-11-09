import pytest

from codefixer.agent.mcp_client import load_workspace_tools, workspace_session

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_tools_list_exposes_the_five_workspace_tools(tmp_path):
    async with workspace_session(str(tmp_path)) as session:
        result = await session.list_tools()

    names = {tool.name for tool in result.tools}
    assert names == {"list_files", "read_file", "search_code", "edit_file", "run_tests"}


async def test_load_workspace_tools_returns_five_langchain_tools(tmp_path):
    async with workspace_session(str(tmp_path)) as session:
        tools = await load_workspace_tools(session)

    names = {tool.name for tool in tools}
    assert names == {"list_files", "read_file", "search_code", "edit_file", "run_tests"}


async def test_langchain_tool_actually_calls_the_mcp_server(tmp_path):
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")

    async with workspace_session(str(tmp_path)) as session:
        tools = await load_workspace_tools(session)
        list_files = next(tool for tool in tools if tool.name == "list_files")

        output = await list_files.ainvoke({"path": "."})

    assert output == "app.py"


async def test_langchain_tool_surfaces_tool_error(tmp_path):
    async with workspace_session(str(tmp_path)) as session:
        tools = await load_workspace_tools(session)
        read_file = next(tool for tool in tools if tool.name == "read_file")

        with pytest.raises(Exception, match="n'existe pas"):
            await read_file.ainvoke({"path": "missing.py"})
