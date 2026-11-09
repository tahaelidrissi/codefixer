from codefixer.servers import workspace


def test_full_fix_cycle(tmp_path, monkeypatch):
    """Reproduces the examples/buggy_shop bug end to end: run_tests -> search_code ->
    read_file -> edit_file -> run_tests, with no LLM involved."""
    monkeypatch.setattr(workspace, "WORKSPACE", tmp_path)
    (tmp_path / "shop.py").write_text(
        "def calculate_discount(price, rate):\n    return price * rate / 10\n", encoding="utf-8"
    )
    (tmp_path / "test_shop.py").write_text(
        "from shop import calculate_discount\n\n\n"
        "def test_calculate_discount():\n"
        "    assert calculate_discount(100, 10) == 10\n",
        encoding="utf-8",
    )

    assert "1 failed" in workspace.run_tests(".")

    matches = workspace.search_code("calculate_discount")
    assert "shop.py" in matches

    content = workspace.read_file("shop.py")
    assert "price * rate / 10" in content

    workspace.edit_file("shop.py", "price * rate / 10", "price * rate / 100")

    assert "1 passed" in workspace.run_tests(".")
