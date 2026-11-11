from codefixer.evals.tasks import load_tasks


def test_load_tasks_finds_the_first_eval_task():
    tasks = load_tasks()

    assert len(tasks) == 1
    task = tasks[0]
    assert task.name == "calc_discount_divisor"
    assert task.category == "calculation"
    assert task.problem
    assert (task.repo_dir / "shop.py").exists()
    assert (task.repo_dir / "test_shop.py").exists()
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
