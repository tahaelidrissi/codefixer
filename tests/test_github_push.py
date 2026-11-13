import re
import subprocess

from codefixer.agent.github_client import push_fix_branch


def _git(repo_dir, *args):
    subprocess.run(["git", "-C", str(repo_dir), *args], check=True, capture_output=True, text=True)


def test_push_fix_branch_commits_and_pushes_to_a_new_branch(tmp_path):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(origin)], check=True, capture_output=True)

    work = tmp_path / "work"
    subprocess.run(["git", "clone", str(origin), str(work)], check=True, capture_output=True)
    (work / "shop.py").write_text("price * rate / 10\n", encoding="utf-8")
    _git(work, "add", "shop.py")
    _git(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init")
    _git(work, "push", "origin", "HEAD:main")

    (work / "shop.py").write_text("price * rate / 100\n", encoding="utf-8")

    branch = push_fix_branch(work, issue_number=7)

    assert re.fullmatch(r"codefixer/issue-7-[0-9a-f]{7}", branch)
    result = subprocess.run(
        ["git", "-C", str(origin), "branch", "--list", branch], check=True, capture_output=True, text=True
    )
    assert branch in result.stdout

    log = subprocess.run(
        ["git", "-C", str(origin), "log", branch, "-1", "--format=%an %ae %s"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert log.stdout.strip() == "CodeFixer codefixer@local fix: resolve issue #7"


def test_push_fix_branch_does_not_collide_with_a_previous_attempt_on_the_same_issue(tmp_path):
    """The real bug this guards against: an issue stays open until its PR is
    merged, so running the fixer twice on the same issue number is normal -
    and used to collide with whatever branch an earlier run already pushed."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(origin)], check=True, capture_output=True)

    work = tmp_path / "work"
    subprocess.run(["git", "clone", str(origin), str(work)], check=True, capture_output=True)
    (work / "shop.py").write_text("price * rate / 10\n", encoding="utf-8")
    _git(work, "add", "shop.py")
    _git(work, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "init")
    _git(work, "push", "origin", "HEAD:main")

    (work / "shop.py").write_text("price * rate / 100\n", encoding="utf-8")
    first_branch = push_fix_branch(work, issue_number=9)

    work2 = tmp_path / "work2"
    subprocess.run(["git", "clone", str(origin), str(work2)], check=True, capture_output=True)
    (work2 / "shop.py").write_text("price * rate / 1000\n", encoding="utf-8")
    second_branch = push_fix_branch(work2, issue_number=9)

    assert first_branch != second_branch
