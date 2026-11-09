import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool, ToolException
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from pydantic import Field, create_model


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
