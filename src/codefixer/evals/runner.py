import argparse
import asyncio
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from langgraph.errors import GraphRecursionError

from codefixer.agent.graph import DEFAULT_MAX_TURNS, DEFAULT_MODEL, build_graph
from codefixer.agent.mcp_client import load_workspace_tools, workspace_session
from codefixer.agent.report import build_report
from codefixer.evals.tasks import Task, load_tasks


@dataclass(frozen=True)
class TaskResult:
    task_name: str
    category: str
    resolved: bool
    cheated: bool
    hit_turn_limit: bool


def _looks_like_a_test_file(path: str) -> bool:
    name = Path(path).name
    return name.startswith("test_") or name.endswith("_test.py")


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


async def run_task(task: Task, model: str = DEFAULT_MODEL, max_turns: int = DEFAULT_MAX_TURNS) -> TaskResult:
    """Runs the agent on one eval task, in a throwaway copy of its repo -
    never the committed fixture itself, since workspace_session overwrites
    whatever directory it's given with the agent's final result."""
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "repo"
        shutil.copytree(task.repo_dir, workspace)

        hit_limit = False
        final_state = None
        async with workspace_session(str(workspace)) as session:
            tools = await load_workspace_tools(session)
            graph = build_graph(tools, model=model, max_turns=max_turns)

            try:
                async for state in graph.astream({"messages": [("user", task.problem)]}, stream_mode="values"):
                    final_state = state
            except GraphRecursionError:
                hit_limit = True

            report = None if hit_limit else build_report(final_state["messages"], model=model)

        cheated = bool(report and any(_looks_like_a_test_file(path) for path in report.files_modified))
        resolved = not hit_limit and _hidden_test_passes(workspace, task.hidden_test_path)

        return TaskResult(
            task_name=task.name,
            category=task.category,
            resolved=resolved,
            cheated=cheated,
            hit_turn_limit=hit_limit,
        )


async def run_evals(
    tasks: list[Task] | None = None, model: str = DEFAULT_MODEL, max_turns: int = DEFAULT_MAX_TURNS
) -> list[TaskResult]:
    """Runs the agent on every task, one at a time, with the same model and
    turn limit throughout - a fixed configuration, so results are
    comparable across runs."""
    if tasks is None:
        tasks = load_tasks()
    return [await run_task(task, model=model, max_turns=max_turns) for task in tasks]


def print_results(results: list[TaskResult]) -> None:
    for result in results:
        status = "RESOLVED" if result.resolved else "FAILED"
        flags = []
        if result.cheated:
            flags.append("cheated")
        if result.hit_turn_limit:
            flags.append("hit turn limit")
        suffix = f" ({', '.join(flags)})" if flags else ""
        print(f"[{status}] {result.task_name} ({result.category}){suffix}")

    resolved_count = sum(result.resolved for result in results)
    print(f"\n{resolved_count}/{len(results)} tasks resolved")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="run_evals")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help='Model to use, as "provider:name" (default: %(default)s).'
    )
    parser.add_argument("--max-turns", type=int, default=DEFAULT_MAX_TURNS, help="Turn limit per task.")
    args = parser.parse_args(argv)

    results = asyncio.run(run_evals(model=args.model, max_turns=args.max_turns))
    print_results(results)


if __name__ == "__main__":
    main()
