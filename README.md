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
- **Sandbox** (`src/codefixer/sandbox/`) — the `workspace` server actually runs
  *inside* a disposable Docker container, not on the host: no network access,
  capped CPU/memory, a read-only filesystem except the repo itself, and any
  command killed if it runs too long. The repo is copied in and the final
  result copied back out — the host's real filesystem is never mounted.
- **Agent** (`src/codefixer/agent/`) — a client that launches the sandboxed
  `workspace` server, converts its tools into a format an LLM can call, and
  drives a LangGraph loop: an agent node calls the model (with a system prompt
  giving it its method and a turn limit so it can't loop forever), a tools node
  executes whatever it asked for against the real server, and the cycle repeats
  until the model is done or the tests pass. A structured final report (cause,
  files modified, tests passed) is built from the real tool-call trace, not
  from the model's own summary.
- **CLI** (`src/codefixer/cli.py`) — `codefixer fix <repo> "<problem>"` ties all
  of the above into one command: it streams each step live as the agent works,
  then prints the final report.
- **Skills** (`skills/`, `src/codefixer/skills/loader.py`) — small Markdown
  files with specialized know-how (writing a regression test, debugging an
  import error, following a repo's conventions). Only each skill's name and
  description are injected into the system prompt (progressive disclosure);
  the agent loads a skill's full instructions on demand through a
  `load_skill` tool. Skills are also exposed as MCP resources
  (`src/codefixer/servers/skills.py`), and a target repo can add its own
  under `.codefixer/skills/`, overriding a built-in skill of the same name.
- **Evals** (`evals/`, `src/codefixer/evals/`) — a small benchmark: a set of
  buggy repos, each with a test the agent can see and a *hidden* test it
  never does, so a superficial fix (hardcoding the one visible assertion)
  gets caught. The harness runs the agent on every task and reports
  resolution rate, regressions, cheating, turns, tokens, and diff size —
  objective numbers instead of eyeballing individual runs.

Models are chosen per run as a `"provider:name"` string (e.g.
`"anthropic:claude-opus-5-5"` or `"groq:openai/gpt-oss-120b"`), so the same code
runs against any supported provider — currently Anthropic and Groq.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- [Docker](https://www.docker.com/), running, with the `codefixer-sandbox` image
  built (see below) — only needed to run the agent loop or the CLI
- An API key for at least one provider, only needed to run the agent loop or
  the CLI — the MCP server and its tools work without one:
  - `ANTHROPIC_API_KEY` from [console.anthropic.com](https://console.anthropic.com)
  - `GROQ_API_KEY` from [console.groq.com](https://console.groq.com) (free, no
    card required — a good way to try the agent without spending anything)

## Setup

```bash
uv sync
cp .env.example .env
docker build -t codefixer-sandbox src/codefixer/sandbox
```

Then edit `.env` and fill in whichever key(s) you have. It's loaded
automatically and gitignored, so a key never ends up committed.

## Running the tests

```bash
uv run pytest tests/ -q
```

Most of the suite (the MCP server, the path confinement, the tool adapter) runs
entirely offline. Tests that call a real LLM are skipped automatically when the
matching API key isn't set, and sandbox tests are skipped automatically if
Docker isn't available.

## Using the CLI

```bash
uv run codefixer fix examples/buggy_shop "There's a failing test in this repository. Fix it."
```

Defaults to `anthropic:claude-opus-5-5`; pass `--model` to use another
provider or model (e.g. `--model groq:openai/gpt-oss-120b`), and `--max-turns`
to change the turn limit (default 25).

## Trying the MCP servers by hand

```bash
set CODEFIXER_WORKSPACE=path\to\a\repo
uv run mcp dev src/codefixer/servers/workspace.py
```

This opens the MCP Inspector, where each of the five tools can be called
directly to see its schema and output. This runs the server directly on the
host, for quick inspection — the real `codefixer fix` CLI always runs it
inside the sandboxed container instead.

```bash
uv run mcp dev src/codefixer/servers/skills.py
```

Same Inspector, but the Resources tab: one `skill://<name>` entry per
built-in skill, each showing its full `SKILL.md` content.

## Skills

Three skills ship in `skills/`: `write-pytest-test`, `debug-import-error`,
and `repo-conventions`. A target repo can add its own under
`.codefixer/skills/` — picked up automatically by the CLI, with a repo skill
overriding a built-in one of the same name.

## Evals

```bash
uv run python evals/run_evals.py --model groq:openai/gpt-oss-120b
```

Runs the agent on every task under `evals/tasks/` and prints, per task,
whether it resolved the real (hidden) bug, whether it regressed or cheated
(edited a test file), and its turns/tokens/diff size - plus averages across
the run. Add `--compare-skills` to run every task twice, once with the
built-in skills and once without, to see whether they actually change the
outcome rather than just assuming they help.

Each task lives in `evals/tasks/<name>/`: `repo/` is what the agent sees,
`hidden_test.py` is kept structurally outside it and is only run afterward
against the agent's final result.

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
│   ├── workspace.py       MCP server: file tools and test runner
│   └── skills.py          MCP server: skills exposed as resources
├── agent/
│   ├── mcp_client.py       launches the sandboxed workspace server, adapts its tools for an LLM
│   ├── graph.py            the LangGraph agent loop, the load_skill tool
│   ├── prompts.py          the agent's system prompt (method, constraints)
│   ├── report.py           builds the structured final report
│   └── trace.py            formats one agent-loop message into a readable line
├── skills/
│   └── loader.py           reads SKILL.md headers and bodies, built-in and per-repo
├── sandbox/
│   ├── Dockerfile          the sandbox image: python:3.12-slim + pytest + mcp, non-root
│   └── container.py        container lifecycle: copy in, restrict, run, diff out, destroy
└── evals/
    ├── tasks.py            reads a task's repo, hidden test, problem, and category
    └── runner.py           runs the agent on a task, checks the hidden test, computes metrics
skills/                    the 3 built-in skills shipped with CodeFixer
evals/tasks/               buggy repos + hidden tests, one per bug category
examples/buggy_shop/       a small buggy repo used to exercise the tools and the agent
tests/                     Pytest suite for the server, the sandbox, the adapter, and the agent loop
```

## Status

Steps 1 (the `workspace` MCP server), 2 (the agent loop and CLI), 3 (agent
skills), and 4 (the Docker sandbox) are complete. Step 5 (evals) is mostly
done: six tasks across five bug categories, a harness that reports
resolution rate, regressions, cheating, turns, tokens, and diff size, and a
with/without-skills comparison — a two-model/two-prompt comparison is still
pending a second provider's API key. Next up: step 6, GitHub integration
and human validation before any pull request.
