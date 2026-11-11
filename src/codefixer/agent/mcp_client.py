import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool, ToolException
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from pydantic import Field, create_model

from codefixer.sandbox.container import copy_repo_out, sandboxed_repo, volume_from

_CODEFIXER_SRC = Path(__file__).resolve().parents[1]
_SANDBOX_SERVER_PATH = "/opt/codefixer-server"


def _stage_workspace_server() -> Path:
    """Builds a throwaway copy of just the files workspace.py needs to run
    (itself plus its package __init__.py stubs) - not skills.py or anything
    else under servers/, which isn't needed and wouldn't even import inside
    the sandbox (no yaml, no codefixer.skills there)."""
    staging = Path(tempfile.mkdtemp())
    (staging / "codefixer" / "servers").mkdir(parents=True)
    shutil.copy2(_CODEFIXER_SRC / "__init__.py", staging / "codefixer" / "__init__.py")
    shutil.copy2(_CODEFIXER_SRC / "servers" / "__init__.py", staging / "codefixer" / "servers" / "__init__.py")
    shutil.copy2(_CODEFIXER_SRC / "servers" / "workspace.py", staging / "codefixer" / "servers" / "workspace.py")
    return staging


@asynccontextmanager
async def workspace_session(workspace: str):
    """Opens an MCP client session connected to the workspace server,
    running INSIDE a sandboxed container (no network, capped CPU/memory,
    read-only filesystem except /repo and /tmp) instead of as a plain host
    subprocess. workspace.py itself needs no changes for this: the
    container's WORKDIR is already /repo, matching its default
    CODEFIXER_WORKSPACE. Its own code is mounted read-only from a separate
    volume, built once from a throwaway local copy (not committed anywhere,
    just enough to run the server - see _stage_workspace_server).

    On exit, the container's final /repo state is copied back onto
    `workspace` on the host - the same net effect as before (the repo on
    disk ends up fixed), just computed safely inside the sandbox first.
    """
    staging = _stage_workspace_server()
    try:
        with (
            volume_from(staging) as server_volume,
            sandboxed_repo(
                Path(workspace).resolve(),
                extra_mounts=[(server_volume, _SANDBOX_SERVER_PATH)],
            ) as container_id,
        ):
            params = StdioServerParameters(
                command="docker",
                args=[
                    "exec",
                    "-i",
                    "--env",
                    f"PYTHONPATH={_SANDBOX_SERVER_PATH}",
                    container_id,
                    "python",
                    "-m",
                    "codefixer.servers.workspace",
                ],
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session

            copy_repo_out(container_id, Path(workspace).resolve())
    finally:
        shutil.rmtree(staging)


_JSON_TYPE_TO_PYTHON: dict[str, type] = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
}


def _python_type(schema: dict[str, Any]) -> type:
    """Maps one JSON Schema property, as our tools' Annotated[..., Field(...)]
    params produce it, to a Python type. Covers only what workspace.py emits:
    plain types, or "anyOf" with "null" for an optional parameter.
    """
    if "anyOf" in schema:
        non_null = next(s for s in schema["anyOf"] if s.get("type") != "null")
        return _python_type(non_null) | None
    return _JSON_TYPE_TO_PYTHON[schema["type"]]


def _args_model(tool: types.Tool) -> type:
    """Builds a Pydantic model for a tool's arguments from its MCP input schema,
    so LangChain can validate and describe them to the LLM."""
    properties = tool.input_schema.get("properties", {})
    required = set(tool.input_schema.get("required", []))
    fields = {
        name: (
            _python_type(prop),
            Field(... if name in required else prop.get("default"), description=prop.get("description")),
        )
        for name, prop in properties.items()
    }
    return create_model(f"{tool.name}_args", **fields)


def _as_langchain_tool(session: ClientSession, tool: types.Tool) -> StructuredTool:
    """Wraps one MCP tool as a StructuredTool whose execution calls it for real
    over the session, instead of running any logic locally."""

    async def call(**kwargs: Any) -> str:
        result = await session.call_tool(tool.name, kwargs)
        text = "\n".join(block.text for block in result.content if isinstance(block, types.TextContent))
        if result.is_error:
            raise ToolException(text)
        return text

    return StructuredTool.from_function(
        coroutine=call,
        name=tool.name,
        description=tool.description or "",
        args_schema=_args_model(tool),
        infer_schema=False,
    )


async def load_workspace_tools(session: ClientSession) -> list[StructuredTool]:
    """Discovers the tools exposed by an MCP session and converts each one into
    a LangChain StructuredTool, ready to be given to an LLM."""
    result = await session.list_tools()
    return [_as_langchain_tool(session, tool) for tool in result.tools]
