import json
import subprocess
import time

import pytest

from codefixer.sandbox.container import copy_repo_out, diff_repos, exec_in_container, sandboxed_repo
from conftest import requires_docker

pytestmark = requires_docker


def _inspect(container_id: str) -> dict:
    result = subprocess.run(["docker", "inspect", container_id], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)[0]


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


def test_sandboxed_repo_has_no_network_access(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with sandboxed_repo(repo) as container_id:
        config = _inspect(container_id)["HostConfig"]

    assert config["NetworkMode"] == "none"


def test_sandboxed_repo_sets_cpu_and_memory_limits(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with sandboxed_repo(repo, cpus="1", memory="512m") as container_id:
        config = _inspect(container_id)["HostConfig"]

    assert config["Memory"] == 512 * 1024 * 1024
    assert config["NanoCpus"] == 1_000_000_000


def test_sandboxed_repo_is_read_only_outside_repo_and_tmp(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with sandboxed_repo(repo) as container_id:
        result = subprocess.run(
            ["docker", "exec", container_id, "sh", "-c", "echo x > /etc/codefixer-write-test"],
            capture_output=True,
        )

    assert result.returncode != 0


def test_exec_in_container_kills_a_command_that_hangs(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with sandboxed_repo(repo) as container_id:
        start = time.monotonic()
        result = exec_in_container(container_id, "sleep", "30", timeout_seconds=2)
        elapsed = time.monotonic() - start

    assert result.returncode != 0
    assert elapsed < 10
