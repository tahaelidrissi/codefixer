import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@asynccontextmanager
async def workspace_session(workspace: str):
    """Opens an MCP client session connected to the workspace server, running
    as a stdio subprocess with its CODEFIXER_WORKSPACE pointed at `workspace`.
    """
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "codefixer.servers.workspace"],
        env={"CODEFIXER_WORKSPACE": str(Path(workspace).resolve())},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
