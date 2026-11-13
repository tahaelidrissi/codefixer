import os
import subprocess

import pytest
from langgraph.types import Command

from codefixer.agent.approval import build_approval_graph
from codefixer.agent.github_client import diff_of

pytestmark = pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="no GROQ_API_KEY")

_MODEL = "groq:openai/gpt-oss-120b"
_PROBLEM = "The test test_calculate_discount is failing; calculate_discount returns the wrong result."


def _git(repo_dir, *args):
    subprocess.run(["git", "-C", str(repo_dir), *args], check=True, capture_output=True, text=True)


def _fixed_clone(tmp_path):
    """A real local clone (bare "origin" + working copy) with the fix already
    applied but not yet committed - diff_of() can read it, push_fix_branch()
    can push it, and no real GitHub push happens during the test."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(origin)], check=True, capture_output=True)

    work = tmp_path / "work"
    subprocess.run(["git", "clone", str(origin), str(work)], check=True, capture_output=True)
    (work / "shop.py").write_text("def calculate_discount(price, rate):\n    return price * rate / 10\n")
    _git(work, "add", "shop.py")
    _git(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init")
    _git(work, "push", "origin", "HEAD:main")

    (work / "shop.py").write_text("def calculate_discount(price, rate):\n    return price * rate / 100\n")
    return origin, work


def test_approval_pushes_the_branch_when_a_human_approves(tmp_path):
    origin, work = _fixed_clone(tmp_path)
    graph = build_approval_graph()
    config = {"configurable": {"thread_id": "approve-test"}}

    state = graph.invoke(
        {"problem": _PROBLEM, "diff": diff_of(work), "model": _MODEL, "repo_dir": str(work), "issue_number": 1},
        config,
    )
    payload = state["__interrupt__"][0].value
    assert payload["summary"]
    assert "diff" in payload

    state = graph.invoke(Command(resume=True), config)

    assert state["branch"] == "codefixer/issue-1"
    result = subprocess.run(
        ["git", "-C", str(origin), "branch", "--list", state["branch"]], check=True, capture_output=True, text=True
    )
    assert state["branch"] in result.stdout


def test_approval_does_not_push_when_a_human_rejects(tmp_path):
    origin, work = _fixed_clone(tmp_path)
    graph = build_approval_graph()
    config = {"configurable": {"thread_id": "reject-test"}}

    graph.invoke(
        {"problem": _PROBLEM, "diff": diff_of(work), "model": _MODEL, "repo_dir": str(work), "issue_number": 2},
        config,
    )
    state = graph.invoke(Command(resume=False), config)

    assert state["branch"] is None
    result = subprocess.run(["git", "-C", str(origin), "branch"], check=True, capture_output=True, text=True)
    assert "codefixer/issue-2" not in result.stdout
