import os
from pathlib import Path

import pytest

from langchain_core.messages import AIMessage, HumanMessage

from codefixer.evals import runner as runner_module
from codefixer.evals.runner import (
    TaskResult,
    _count_diff_lines,
    _count_turns_and_tokens,
    _describe_exception,
    _error_result,
    _hidden_test_passes,
    _looks_like_a_test_file,
    compare_with_and_without_skills,
    run_evals,
    run_task,
)
from codefixer.evals.tasks import Task, load_tasks


def test_describe_exception_returns_the_plain_message_for_a_normal_exception():
    assert _describe_exception(ValueError("boom")) == "boom"


def test_describe_exception_unwraps_a_nested_exception_group():
    inner = ValueError("the real cause")
    group = ExceptionGroup("outer", [ExceptionGroup("inner", [inner])])

    assert _describe_exception(group) == "the real cause"


def test_looks_like_a_test_file():
    assert _looks_like_a_test_file("test_shop.py")
    assert _looks_like_a_test_file("shop_test.py")
    assert not _looks_like_a_test_file("shop.py")


def test_hidden_test_passes_when_the_fix_is_correct(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "shop.py").write_text(
        "def calculate_discount(price, rate):\n    return price * rate / 100\n", encoding="utf-8"
    )
    hidden_test_path = tmp_path / "hidden_test.py"
    hidden_test_path.write_text(
        "from shop import calculate_discount\n\n\ndef test_hidden():\n    assert calculate_discount(100, 10) == 10\n",
        encoding="utf-8",
    )

    assert _hidden_test_passes(workspace, hidden_test_path) is True
    assert not (workspace / "hidden_test.py").exists()


def test_hidden_test_fails_when_the_bug_is_still_there(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "shop.py").write_text(
        "def calculate_discount(price, rate):\n    return price * rate / 10\n", encoding="utf-8"
    )
    hidden_test_path = tmp_path / "hidden_test.py"
    hidden_test_path.write_text(
        "from shop import calculate_discount\n\n\ndef test_hidden():\n    assert calculate_discount(100, 10) == 10\n",
        encoding="utf-8",
    )

    assert _hidden_test_passes(workspace, hidden_test_path) is False


def test_count_turns_and_tokens_sums_only_ai_messages():
    final_state = {
        "messages": [
            HumanMessage(content="Fix it."),
            AIMessage(content="", usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}),
            AIMessage(content="Done.", usage_metadata={"input_tokens": 20, "output_tokens": 8, "total_tokens": 28}),
        ]
    }

    turns, total_tokens = _count_turns_and_tokens(final_state)

    assert turns == 2
    assert total_tokens == 43


def test_count_turns_and_tokens_handles_no_state():
    assert _count_turns_and_tokens(None) == (0, 0)


def test_count_diff_lines_counts_changed_lines_only(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    (original / "app.py").write_text("value = 1\n", encoding="utf-8")
    modified = tmp_path / "modified"
    modified.mkdir()
    (modified / "app.py").write_text("value = 2\n", encoding="utf-8")

    assert _count_diff_lines(original, modified) == 2


def test_error_result_marks_the_task_as_not_resolved():
    task = Task(
        name="example",
        problem="Fix it.",
        category="calculation",
        repo_dir=Path("/tmp/example/repo"),
        hidden_test_path=Path("/tmp/example/hidden_test.py"),
    )

    result = _error_result(task, "boom")

    assert result.task_name == "example"
    assert result.error == "boom"
    assert result.resolved is False


@pytest.mark.anyio
async def test_run_evals_continues_after_one_task_crashes(monkeypatch):
    tasks = [
        Task(name="ok_task", problem="p", category="calculation", repo_dir=Path("/tmp/ok"), hidden_test_path=Path("/tmp/ok/h.py")),
        Task(
            name="crashing_task",
            problem="p",
            category="calculation",
            repo_dir=Path("/tmp/bad"),
            hidden_test_path=Path("/tmp/bad/h.py"),
        ),
    ]

    async def fake_run_task(task, model=None, max_turns=None, skills_dirs=None):
        if task.name == "crashing_task":
            raise RuntimeError("simulated crash")
        return TaskResult(
            task_name=task.name,
            category=task.category,
            resolved=True,
            regressed=False,
            cheated=False,
            hit_turn_limit=False,
            turns=1,
            total_tokens=10,
            diff_lines=1,
        )

    monkeypatch.setattr(runner_module, "run_task", fake_run_task)

    results = await run_evals(tasks=tasks)

    assert len(results) == 2
    assert results[0].resolved is True
    assert results[0].error is None
    assert results[1].error == "simulated crash"
    assert results[1].resolved is False


@pytest.mark.anyio
async def test_compare_with_and_without_skills_toggles_only_that(monkeypatch):
    calls = []

    async def fake_run_evals(tasks=None, model=None, max_turns=None, skills_dirs=None):
        calls.append(skills_dirs)
        return []

    monkeypatch.setattr(runner_module, "run_evals", fake_run_evals)

    await compare_with_and_without_skills(tasks=[])

    assert calls == [None, []]


@pytest.mark.anyio
@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="no GROQ_API_KEY")
async def test_run_task_resolves_the_calculation_task():
    task = next(task for task in load_tasks() if task.name == "calc_discount_divisor")

    result = await run_task(task, model="groq:openai/gpt-oss-120b")

    assert result.resolved is True
    assert result.regressed is False
    assert result.cheated is False
    assert result.hit_turn_limit is False
    assert result.turns > 0
    assert result.total_tokens > 0
    assert result.diff_lines > 0


@pytest.fixture
def anyio_backend():
    return "asyncio"
