import subprocess

import pytest

from codefixer.sandbox.container import copy_repo_out, diff_repos, sandboxed_repo
from conftest import requires_docker

pytestmark = requires_docker


def test_sandboxed_repo_copies_the_repo_in_and_runs_commands(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")

    with sandboxed_repo(repo) as container_id:
        result = subprocess.run(
            ["docker", "exec", container_id, "cat", "/repo/app.py"],
            capture_output=True,
            text=True,
            check=True,
        )

    assert result.stdout == "value = 1\n"


def test_sandboxed_repo_destroys_the_container_on_exit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")

    with sandboxed_repo(repo) as container_id:
        pass

    inspect = subprocess.run(["docker", "inspect", container_id], capture_output=True)
    assert inspect.returncode != 0


def test_sandboxed_repo_destroys_the_container_even_if_the_caller_raises(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")

    with pytest.raises(ValueError):
        with sandboxed_repo(repo) as container_id:
            saved_id = container_id
            raise ValueError("boom")

    inspect = subprocess.run(["docker", "inspect", saved_id], capture_output=True)
    assert inspect.returncode != 0


def test_diff_repos_reports_an_edited_file(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    (original / "app.py").write_text("value = 1\n", encoding="utf-8")

    with sandboxed_repo(original) as container_id:
        subprocess.run(
            ["docker", "exec", container_id, "sh", "-c", "echo 'value = 2' > /repo/app.py"],
            check=True,
        )
        modified = tmp_path / "modified"
        modified.mkdir()
        copy_repo_out(container_id, modified)

    diff = diff_repos(original, modified)

    assert "-value = 1" in diff
    assert "+value = 2" in diff
