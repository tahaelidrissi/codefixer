import argparse
import asyncio
import sys

from langgraph.errors import GraphRecursionError

from codefixer.agent.graph import DEFAULT_MAX_TURNS, DEFAULT_MODEL, build_graph
from codefixer.agent.mcp_client import load_workspace_tools, workspace_session
from codefixer.agent.report import build_report
from codefixer.agent.trace import format_step


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="codefixer")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fix = subparsers.add_parser("fix", help="Fix a bug in a repository.")
    fix.add_argument("repo", help="Path to the repository to fix.")
    fix.add_argument("problem", help="Description of the bug to fix.")
    fix.add_argument(
        "--model", default=DEFAULT_MODEL, help='Model to use, as "provider:name" (default: %(default)s).'
    )
    fix.add_argument(
        "--max-turns", type=int, default=DEFAULT_MAX_TURNS, help="Turn limit before giving up."
    )

    return parser.parse_args(argv)


async def _run_fix(repo: str, problem: str, model: str, max_turns: int) -> None:
    hit_limit = False
    final_state = None

    async with workspace_session(repo) as session:
        tools = await load_workspace_tools(session)
        graph = build_graph(tools, model=model, max_turns=max_turns)

        # Caught here, inside the session's `async with`, not in main(): an
        # exception still propagating when this block exits gets wrapped in
        # an ExceptionGroup by the MCP session's own task group teardown, so
        # `except GraphRecursionError` in main() would never match it.
        try:
            async for state in graph.astream({"messages": [("user", problem)]}, stream_mode="values"):
                final_state = state
                step = format_step(state["messages"][-1])
                if step is not None:
                    print(step)
        except GraphRecursionError:
            hit_limit = True

        report = None if hit_limit else build_report(final_state["messages"], model=model)

    if hit_limit:
        raise GraphRecursionError(f"Gave up after {max_turns} turns without fixing the bug.")

    print()
    print(f"Cause: {report.cause}")
    print(f"Files modified: {', '.join(report.files_modified) or '(none)'}")
    print(f"Tests passed: {report.tests_passed}")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    try:
        asyncio.run(_run_fix(args.repo, args.problem, args.model, args.max_turns))
    except GraphRecursionError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
