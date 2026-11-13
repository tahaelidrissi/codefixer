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

    assert branch == "codefixer/issue-7"
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
