# CodeFixer

CodeFixer is a coding agent that fixes bugs in a code repository: it explores the
code, reproduces a failing test, edits the files, reruns the tests, and repeats
until everything passes. It is built incrementally as a learning project covering
three subjects: **coding agents**, **MCP** (Model Context Protocol), and **agent
skills**.

## How it works

The project is split into two layers that talk to each other over the real MCP
protocol, not through direct function calls:

- **`workspace` MCP server** (`src/codefixer/servers/workspace.py`) — exposes five
  tools for working on a repository, with no AI involved: `list_files`,
  `read_file`, `search_code`, `edit_file`, and `run_tests`. All file access is
  confined to a single configurable repo root; tests run in an isolated
  subprocess with a timeout.
- **Agent** (`src/codefixer/agent/`) — a client that launches the `workspace`
  server as a subprocess, converts its tools into a format an LLM can call, and
  drives a LangGraph loop: the model decides which tool to call, the tool runs
  for real against the server, the result goes back to the model, and the cycle
  repeats until the model is done.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An `ANTHROPIC_API_KEY` (only needed to run the agent loop itself; the MCP
  server and its tools work without one)

## Setup

```bash
uv sync
```

## Running the tests

```bash
uv run pytest tests/ -q
```

Most of the suite (the MCP server, the path confinement, the tool adapter) runs
entirely offline. The tests in `tests/test_graph.py` call a real LLM and require
`ANTHROPIC_API_KEY` to be set.

## Trying the `workspace` server by hand

```bash
set CODEFIXER_WORKSPACE=path\to\a\repo
uv run mcp dev src/codefixer/servers/workspace.py
```

This opens the MCP Inspector, where each of the five tools can be called
directly to see its schema and output.

## The example bug

`examples/buggy_shop/` is a minimal fixture: a `calculate_discount` function with
a one-line bug, and a test that fails because of it.
`examples/buggy_shop/fix_cycle.py` drives the five workspace tools by hand (no
LLM) through the full cycle — run the tests, find the bug, read it, fix it,
rerun the tests — to prove the tools alone are enough to fix it:

```bash
uv run python examples/buggy_shop/fix_cycle.py
```

## Project layout

```
src/codefixer/
├── servers/
│   └── workspace.py      MCP server: file tools and test runner
└── agent/
    ├── mcp_client.py      connects to the workspace server, adapts its tools for an LLM
    └── graph.py           the LangGraph agent loop
examples/buggy_shop/       a small buggy repo used to exercise the tools and the agent
tests/                     Pytest suite for the server, the adapter, and the agent loop
```

## Status

The `workspace` MCP server and its five tools are complete and tested. The agent
side currently has a minimal MCP client, a hand-written MCP-to-LangChain tool
adapter, and a bare LangGraph loop (no system prompt or turn limit yet) — work
in progress.
