from codefixer.evals.tasks import load_tasks


def test_load_tasks_finds_the_five_eval_tasks():
    tasks = load_tasks()

    names = {task.name for task in tasks}
    assert names == {
        "calc_discount_divisor",
        "budget_edge_case",
        "import_error_typo",
        "wrong_type_concat",
        "multi_file_tax",
    }

    categories = {task.category for task in tasks}
    assert categories == {"calculation", "edge_case", "import_error", "wrong_type", "multi_file"}

    for task in tasks:
        assert task.problem
        assert task.repo_dir.is_dir()
        assert task.hidden_test_path.exists()
        assert not (task.repo_dir / "hidden_test.py").exists()


def test_load_tasks_reads_a_custom_directory(tmp_path):
    task_dir = tmp_path / "example_task"
    (task_dir / "repo").mkdir(parents=True)
    (task_dir / "repo" / "app.py").write_text("value = 1\n", encoding="utf-8")
    (task_dir / "task.yaml").write_text("problem: Fix the bug.\ncategory: calculation\n", encoding="utf-8")
    (task_dir / "hidden_test.py").write_text("def test_hidden():\n    assert True\n", encoding="utf-8")

    tasks = load_tasks(tmp_path)

    assert len(tasks) == 1
    assert tasks[0].name == "example_task"
    assert tasks[0].problem == "Fix the bug."
