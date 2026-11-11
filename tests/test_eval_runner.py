import os

import pytest

from codefixer.evals.runner import _hidden_test_passes, _looks_like_a_test_file, run_task
from codefixer.evals.tasks import load_tasks


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


@pytest.mark.anyio
@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="no GROQ_API_KEY")
async def test_run_task_resolves_the_calculation_task():
    task = next(task for task in load_tasks() if task.name == "calc_discount_divisor")

    result = await run_task(task, model="groq:openai/gpt-oss-120b")

    assert result.resolved is True
    assert result.cheated is False
    assert result.hit_turn_limit is False


@pytest.fixture
def anyio_backend():
    return "asyncio"
