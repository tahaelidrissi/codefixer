import argparse
import asyncio
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from langchain_core.messages import AIMessage
from langgraph.errors import GraphRecursionError

from codefixer.agent.graph import DEFAULT_MAX_TURNS, DEFAULT_MODEL, build_graph
from codefixer.agent.mcp_client import load_workspace_tools, workspace_session
from codefixer.agent.report import build_report
from codefixer.evals.tasks import Task, load_tasks
from codefixer.sandbox.container import diff_repos


@dataclass(frozen=True)
class TaskResult:
    task_name: str
    category: str
    resolved: bool
    regressed: bool
    cheated: bool
    hit_turn_limit: bool
    turns: int
    total_tokens: int
    diff_lines: int
    error: str | None = None


def _describe_exception(exc: BaseException) -> str:
    """Unwraps an ExceptionGroup down to its real cause. MCP's session
    teardown wraps whatever failed during workspace_session's own setup
    (e.g. the server crashing before run_task's try/except even starts) in
    one of these, and str() on the group itself just says "unhandled
    errors in a TaskGroup", hiding the actual error message.
    """
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return str(exc)


def _looks_like_a_test_file(path: str) -> bool:
    name = Path(path).name
    return name.startswith("test_") or name.endswith("_test.py")


def _test_suite_passes(repo_dir: Path) -> bool:
    result = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=repo_dir, capture_output=True, text=True)
    return result.returncode == 0


def _hidden_test_passes(workspace: Path, hidden_test_path: Path) -> bool:
    """Copies the hidden test alongside the agent's final files and runs it
    on its own - never given to the agent itself, only used here to check
    the real fix, not just the one assertion the agent could see."""
    destination = workspace / hidden_test_path.name
    shutil.copy2(hidden_test_path, destination)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", destination.name],
            cwd=workspace,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    finally:
        destination.unlink()


def _count_turns_and_tokens(final_state: dict | None) -> tuple[int, int]:
    """One AIMessage is one ReAct turn (one LLM call). usage_metadata is a
    standard LangChain field both Anthropic and Groq fill in - no provider
    API call needed to get token counts after the fact."""
    if final_state is None:
        return 0, 0
    ai_messages = [m for m in final_state["messages"] if isinstance(m, AIMessage)]
    total_tokens = sum((m.usage_metadata or {}).get("total_tokens", 0) for m in ai_messages)
    return len(ai_messages), total_tokens


def _count_diff_lines(original: Path, modified: Path) -> int:
    diff = diff_repos(original, modified)
    return sum(
        1 for line in diff.splitlines() if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    )


async def run_task(
    task: Task,
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    skills_dirs: list[Path] | None = None,
) -> TaskResult:
    """Runs the agent on one eval task, in a throwaway copy of its repo -
    never the committed fixture itself, since workspace_session overwrites
    whatever directory it's given with the agent's final result.

    `skills_dirs` is forwarded as-is to build_graph: None keeps its default
    (the built-in skills), while an empty list disables skills entirely -
    this is how the with/without-skills experiment below works, with no
    extra logic needed here.
    """
    with tempfile.TemporaryDirectory() as tmp:
        # A separate throwaway copy just for the baseline check: running
        # pytest directly on task.repo_dir would litter the committed
        # fixture with __pycache__/.pytest_cache on disk.
        baseline = Path(tmp) / "baseline"
        shutil.copytree(task.repo_dir, baseline)
        baseline_passed = _test_suite_passes(baseline)

        workspace = Path(tmp) / "repo"
        shutil.copytree(task.repo_dir, workspace)

        hit_limit = False
        error: str | None = None
        final_state = None
        # Caught here, inside workspace_session's `async with` (same reason
        # as cli.py's _run_fix): an exception still propagating when that
        # block exits gets wrapped in an ExceptionGroup by the MCP
        # session's own task group teardown. A broad except here is
        # deliberate - one task's unexpected crash (a provider error, a
        # model hallucinating a tool, ...) must not take down the whole
        # eval run, it should just be reported as this task's result.
        async with workspace_session(str(workspace)) as session:
            tools = await load_workspace_tools(session)
            graph = build_graph(tools, model=model, max_turns=max_turns, skills_dirs=skills_dirs)

            try:
                async for state in graph.astream({"messages": [("user", task.problem)]}, stream_mode="values"):
                    final_state = state
            except GraphRecursionError:
                hit_limit = True
            except Exception as exc:  # noqa: BLE001 - see comment above
                error = _describe_exception(exc)

            report = None
            if not (hit_limit or error):
                try:
                    report = build_report(final_state["messages"], model=model)
                except Exception as exc:  # noqa: BLE001 - see comment above
                    # The agent's own loop already succeeded here - only
                    # this separate "summarize the cause" call failed.
                    # Losing a real resolved/regressed/diff_lines signal
                    # over that alone would be a worse outcome than just
                    # reporting cheated as unknown (False).
                    print(f"[WARN] {task.name}: build_report failed - {_describe_exception(exc)}")

        cheated = bool(report and any(_looks_like_a_test_file(path) for path in report.files_modified))
        regressed = baseline_passed and not _test_suite_passes(workspace)
        resolved = not (hit_limit or error) and _hidden_test_passes(workspace, task.hidden_test_path)
        turns, total_tokens = _count_turns_and_tokens(final_state)
        diff_lines = _count_diff_lines(task.repo_dir, workspace)

        return TaskResult(
            task_name=task.name,
            category=task.category,
            resolved=resolved,
            regressed=regressed,
            cheated=cheated,
            hit_turn_limit=hit_limit,
            turns=turns,
            total_tokens=total_tokens,
            diff_lines=diff_lines,
            error=error,
        )


def _error_result(task: Task, message: str) -> TaskResult:
    return TaskResult(
        task_name=task.name,
        category=task.category,
        resolved=False,
        regressed=False,
        cheated=False,
        hit_turn_limit=False,
        turns=0,
        total_tokens=0,
        diff_lines=0,
        error=message,
    )


async def run_evals(
    tasks: list[Task] | None = None,
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    skills_dirs: list[Path] | None = None,
) -> list[TaskResult]:
    """Runs the agent on every task, one at a time, with the same model,
    turn limit, and skills throughout - a fixed configuration, so results
    are comparable across runs. A second safety net around run_task itself
    (which already handles crashes during the agent's own run): if
    something fails before that - e.g. the sandbox never starts - the
    batch still continues instead of losing every other task's result.
    """
    if tasks is None:
        tasks = load_tasks()

    results = []
    for task in tasks:
        try:
            results.append(await run_task(task, model=model, max_turns=max_turns, skills_dirs=skills_dirs))
        except Exception as exc:  # noqa: BLE001 - see docstring
            results.append(_error_result(task, _describe_exception(exc)))
    return results


async def compare_with_and_without_skills(
    tasks: list[Task] | None = None, model: str = DEFAULT_MODEL, max_turns: int = DEFAULT_MAX_TURNS
) -> tuple[list[TaskResult], list[TaskResult]]:
    """Runs the same tasks twice, same model both times - once with the
    built-in skills (the default), once with skills_dirs=[] (none at all) -
    the only variable that changes, so any difference in the results comes
    from the skills themselves."""
    if tasks is None:
        tasks = load_tasks()
    with_skills = await run_evals(tasks=tasks, model=model, max_turns=max_turns)
    without_skills = await run_evals(tasks=tasks, model=model, max_turns=max_turns, skills_dirs=[])
    return with_skills, without_skills


def print_results(results: list[TaskResult]) -> None:
    for result in results:
        if result.error:
            print(f"[ERROR] {result.task_name} ({result.category}) - {result.error}")
            continue

        status = "RESOLVED" if result.resolved else "FAILED"
        flags = []
        if result.regressed:
            flags.append("regressed")
        if result.cheated:
            flags.append("cheated")
        if result.hit_turn_limit:
            flags.append("hit turn limit")
        suffix = f" ({', '.join(flags)})" if flags else ""
        print(
            f"[{status}] {result.task_name} ({result.category}) - "
            f"{result.turns} turns, {result.total_tokens} tokens, {result.diff_lines} diff lines{suffix}"
        )

    count = len(results)
    resolved_count = sum(result.resolved for result in results)
    print(f"\n{resolved_count}/{count} tasks resolved")
    if count:
        print(f"avg turns: {sum(r.turns for r in results) / count:.1f}")
        print(f"avg tokens: {sum(r.total_tokens for r in results) / count:.0f}")
        print(f"avg diff lines: {sum(r.diff_lines for r in results) / count:.1f}")


def print_comparison(with_skills: list[TaskResult], without_skills: list[TaskResult]) -> None:
    print("=== With skills ===")
    print_results(with_skills)
    print("\n=== Without skills ===")
    print_results(without_skills)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="run_evals")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help='Model to use, as "provider:name" (default: %(default)s).'
    )
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS, help="Turn limit per task.")
    parser.add_argument(
        "--compare-skills",
        action="store_true",
        help="Run every task once with the built-in skills and once without, same model, and compare.",
    )
    args = parser.parse_args(argv)

    if args.compare_skills:
        with_skills, without_skills = asyncio.run(
            compare_with_and_without_skills(model=args.model, max_turns=args.max_turns)
        )
        print_comparison(with_skills, without_skills)
    else:
        results = asyncio.run(run_evals(model=args.model, max_turns=args.max_turns))
        print_results(results)


if __name__ == "__main__":
    main()
