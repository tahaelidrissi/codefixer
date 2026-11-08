import pytest

from codefixer.servers import workspace


@pytest.fixture(autouse=True)
def workspace_root(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE", tmp_path)
    return tmp_path


def test_run_tests_reports_passing_test(workspace_root):
    (workspace_root / "test_ok.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8"
    )

    output = workspace.run_tests("test_ok.py")

    assert "1 passed" in output


def test_run_tests_reports_failing_test_without_raising(workspace_root):
    (workspace_root / "test_fail.py").write_text(
        "def test_fail():\n    assert 1 + 1 == 3\n", encoding="utf-8"
    )

    output = workspace.run_tests("test_fail.py")

    assert "1 failed" in output
    assert "assert" in output


def test_run_tests_supports_pytest_node_id(workspace_root):
    (workspace_root / "test_multi.py").write_text(
        "def test_a():\n    assert True\n\ndef test_b():\n    assert False\n", encoding="utf-8"
    )

    output = workspace.run_tests("test_multi.py::test_a")

    assert "1 passed" in output


def test_run_tests_rejects_escape_attempt(workspace_root):
    with pytest.raises(ValueError, match="sort du dépôt"):
        workspace.run_tests("../../../Windows")


def test_run_tests_times_out(workspace_root, monkeypatch):
    monkeypatch.setattr(workspace, "TEST_TIMEOUT", 1)
    (workspace_root / "test_hang.py").write_text(
        "import time\n\ndef test_hang():\n    time.sleep(30)\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="dépassé"):
        workspace.run_tests("test_hang.py")


def test_run_tests_truncates_long_output(workspace_root, monkeypatch):
    monkeypatch.setattr(workspace, "MAX_OUTPUT_LINES", 5)
    many_failing_tests = "\n\n".join(f"def test_{i}():\n    assert False" for i in range(30))
    (workspace_root / "test_verbose.py").write_text(many_failing_tests, encoding="utf-8")

    output = workspace.run_tests("test_verbose.py")

    assert "tronquée" in output
    assert len(output.splitlines()) == 6
