from dataclasses import dataclass
from pathlib import Path

import yaml

TASKS_DIR = Path(__file__).resolve().parents[3] / "evals" / "tasks"


@dataclass(frozen=True)
class Task:
    name: str
    problem: str
    category: str
    repo_dir: Path
    hidden_test_path: Path


def load_tasks(tasks_dir: Path = TASKS_DIR) -> list[Task]:
    """Reads every eval task under `tasks_dir`. Each task's `repo_dir` is
    what gets handed to the agent; `hidden_test_path` lives outside it and
    is only ever run afterward by the eval harness, never given to the
    agent - a structural separation, not just a naming convention.
    """
    tasks = []
    for task_dir in sorted(p for p in tasks_dir.iterdir() if p.is_dir()):
        metadata = yaml.safe_load((task_dir / "task.yaml").read_text(encoding="utf-8"))
        tasks.append(
            Task(
                name=task_dir.name,
                problem=metadata["problem"],
                category=metadata["category"],
                repo_dir=task_dir / "repo",
                hidden_test_path=task_dir / "hidden_test.py",
            )
        )
    return tasks
