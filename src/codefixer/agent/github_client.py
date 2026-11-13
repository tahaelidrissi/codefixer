import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

GITHUB_MCP_IMAGE = "ghcr.io/github/github-mcp-server"

_ISSUE_URL_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/issues/(\d+)/?$")


@dataclass
class Issue:
    owner: str
    repo: str
    number: int
    title: str
    body: str
    clone_url: str


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


def parse_issue_url(url: str) -> tuple[str, str, int]:
    """Pulls (owner, repo, issue_number) out of a GitHub issue URL. Only the
    one URL shape we actually need to support - issue URLs always look like
    this, there's no alternate form to account for."""
    match = _ISSUE_URL_RE.match(url)
    if match is None:
        raise ValueError(f"Not a GitHub issue URL: {url}")
    owner, repo, number = match.groups()
    return owner, repo, int(number)


async def fetch_issue(url: str) -> Issue:
    """Reads an issue's title and body through the GitHub MCP server, given
    its URL. The body is what becomes the agent's problem description -
    `clone_url` is derived from the same owner/repo, not read from the API,
    since it's always the same predictable HTTPS form for a public repo."""
    owner, repo, number = parse_issue_url(url)
    async with github_session() as session:
        result = await session.call_tool(
            "issue_read", {"method": "get", "owner": owner, "repo": repo, "issue_number": number}
        )
    text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
    if result.is_error:
        raise RuntimeError(text)
    payload = json.loads(text)
    return Issue(
        owner=owner,
        repo=repo,
        number=number,
        title=payload["title"],
        body=payload.get("body") or "",
        clone_url=f"https://github.com/{owner}/{repo}.git",
    )


@contextmanager
def cloned_repo(clone_url: str):
    """Clones a repo into a throwaway temp directory for the agent to fix,
    cleaned up once the caller is done with it - same lifecycle as the
    staging directory in mcp_client.py's _stage_workspace_server.

    Plain `git clone`, no authentication: the GITHUB_TOKEN used for
    `github_session` is scoped to Issues + Metadata only, not repo
    contents, so it wouldn't grant access anyway. This only reaches public
    repos until that scope is deliberately widened for a private one.
    """
    workdir = Path(tempfile.mkdtemp())
    try:
        subprocess.run(["git", "clone", clone_url, str(workdir)], check=True, capture_output=True, text=True)
        yield workdir
    finally:
        # git marks some files inside .git read-only on Windows; shutil.rmtree
        # can't delete those without being told to clear that flag first.
        shutil.rmtree(workdir, onerror=lambda func, path, _exc: (os.chmod(path, stat.S_IWRITE), func(path)))
