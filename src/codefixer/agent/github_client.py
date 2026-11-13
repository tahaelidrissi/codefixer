import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

GITHUB_MCP_IMAGE = "ghcr.io/github/github-mcp-server"


@asynccontextmanager
async def github_session():
    """Opens an MCP client session connected to GitHub's official MCP
    server - not something we wrote ourselves, the same tool any other
    MCP-compatible agent can use. Run locally via Docker over stdio (not
    GitHub's remote HTTP endpoint), to reuse the exact same stdio client
    code already used for the workspace server.

    Needs GITHUB_TOKEN in the environment (loaded from .env): a
    fine-grained personal access token, scoped to only what the current
    increment needs - least privilege from the very first connection, not
    just before opening a pull request.
    """
    params = StdioServerParameters(
        command="docker",
        args=["run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", GITHUB_MCP_IMAGE, "stdio"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": os.environ["GITHUB_TOKEN"]},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        yield session
