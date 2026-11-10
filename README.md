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
  drives a LangGraph loop: an agent node calls the model (with a system prompt
  giving it its method and a turn limit so it can't loop forever), a tools node
  executes whatever it asked for against the real server, and the cycle repeats
  until the model is done or the tests pass. A structured final report (cause,
  files modified, tests passed) is built from the real tool-call trace, not
  from the model's own summary.
- **CLI** (`src/codefixer/cli.py`) — `codefixer fix <repo> "<problem>"` ties all
  of the above into one command: it streams each step live as the agent works,
  then prints the final report.

Models are chosen per run as a `"provider:name"` string (e.g.
`"anthropic:claude-opus-5-5"` or `"groq:openai/gpt-oss-120b"`), so the same code
runs against any supported provider — currently Anthropic and Groq.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An API key for at least one provider, only needed to run the agent loop or
  the CLI — the MCP server and its tools work without one:
  - `ANTHROPIC_API_KEY` from [console.anthropic.com](https://console.anthropic.com)
  - `GROQ_API_KEY` from [console.groq.com](https://console.groq.com) (free, no
    card required — a good way to try the agent without spending anything)

## Setup

```bash
uv sync
cp .env.example .env
```

Then edit `.env` and fill in whichever key(s) you have. It's loaded
automatically and gitignored, so a key never ends up committed.

## Running the tests

```bash
uv run pytest tests/ -q
```

Most of the suite (the MCP server, the path confinement, the tool adapter) runs
entirely offline. Tests that call a real LLM are skipped automatically when the
matching API key isn't set.

## Using the CLI

```bash
uv run codefixer fix examples/buggy_shop "There's a failing test in this repository. Fix it."
```

Defaults to `anthropic:claude-opus-5-5`; pass `--model` to use another
provider or model (e.g. `--model groq:openai/gpt-oss-120b`), and `--max-turns`
to change the turn limit (default 25).

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
├── cli.py                 `codefixer fix <repo> "<problem>"`
├── servers/
│   └── workspace.py       MCP server: file tools and test runner
└── agent/
    ├── mcp_client.py       connects to the workspace server, adapts its tools for an LLM
    ├── graph.py            the LangGraph agent loop
    ├── prompts.py          the agent's system prompt (method, constraints)
    ├── report.py           builds the structured final report
    └── trace.py            formats one agent-loop message into a readable line
examples/buggy_shop/       a small buggy repo used to exercise the tools and the agent
tests/                     Pytest suite for the server, the adapter, and the agent loop
```

## Status

Steps 1 (the `workspace` MCP server) and 2 (the agent loop and CLI) are
complete: five tested tools, a LangGraph ReAct loop with a system prompt, a
turn limit, a structured report, and a working `codefixer fix` command. Next
up: step 3, agent skills.
