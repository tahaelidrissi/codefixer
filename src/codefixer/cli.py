import argparse
import asyncio
import sys
from pathlib import Path

from langgraph.errors import GraphRecursionError

from codefixer.agent.github_client import cloned_repo, fetch_issue, push_fix_branch
from codefixer.agent.graph import DEFAULT_MAX_TURNS, DEFAULT_MODEL, build_graph
from codefixer.agent.mcp_client import load_workspace_tools, workspace_session
from codefixer.agent.report import Report, build_report
from codefixer.agent.trace import format_step
from codefixer.skills.loader import SKILLS_DIR


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

    fix_issue = subparsers.add_parser("fix-issue", help="Fix the bug described by a GitHub issue.")
    fix_issue.add_argument("issue_url", help="URL of the GitHub issue, e.g. https://github.com/owner/repo/issues/42")
    fix_issue.add_argument(
        "--model", default=DEFAULT_MODEL, help='Model to use, as "provider:name" (default: %(default)s).'
    )
    fix_issue.add_argument(
        "--max-turns", type=int, default=DEFAULT_MAX_TURNS, help="Turn limit before giving up."
    )

    return parser.parse_args(argv)


def _resolve_skills_dirs(repo: str) -> list[Path]:
    """Built-in skills, plus the target repo's own .codefixer/skills/ if it
    has one - added automatically, no CLI flag needed."""
    skills_dirs = [SKILLS_DIR]
    repo_skills_dir = Path(repo) / ".codefixer" / "skills"
    if repo_skills_dir.is_dir():
        skills_dirs.append(repo_skills_dir)
    return skills_dirs


async def _run_fix(repo: str, problem: str, model: str, max_turns: int) -> Report:
    hit_limit = False
    final_state = None

    skills_dirs = _resolve_skills_dirs(repo)

    async with workspace_session(repo) as session:
        tools = await load_workspace_tools(session)
        graph = build_graph(tools, model=model, max_turns=max_turns, skills_dirs=skills_dirs)

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

    return report


async def _run_fix_issue(issue_url: str, model: str, max_turns: int) -> None:
    issue = await fetch_issue(issue_url)
    print(f"Issue #{issue.number}: {issue.title}")
    print()

    with cloned_repo(issue.clone_url) as workdir:
        report = await _run_fix(str(workdir), issue.body, model, max_turns)

        print()
        if report.tests_passed and report.files_modified:
            branch = push_fix_branch(workdir, issue.number)
            print(f"Pushed to branch: {branch}")
        else:
            print("Not pushing: tests are not passing or nothing was changed.")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    if args.command == "fix":
        coro = _run_fix(args.repo, args.problem, args.model, args.max_turns)
    else:
        coro = _run_fix_issue(args.issue_url, args.model, args.max_turns)

    try:
        asyncio.run(coro)
    except GraphRecursionError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
