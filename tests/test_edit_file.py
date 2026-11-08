import pytest

from codefixer.servers import workspace


@pytest.fixture(autouse=True)
def workspace_root(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE", tmp_path)
    return tmp_path


def test_edit_file_replaces_unique_match(workspace_root):
    (workspace_root / "pricing.py").write_text(
        "def calculate_discount(price, rate):\n    return price * rate / 10\n", encoding="utf-8"
    )

    result = workspace.edit_file("pricing.py", "price * rate / 10", "price * rate / 100")

    assert result == "'pricing.py' modifié, ligne 2."
    assert (workspace_root / "pricing.py").read_text(encoding="utf-8") == (
        "def calculate_discount(price, rate):\n    return price * rate / 100\n"
    )


def test_edit_file_leaves_rest_of_file_untouched(workspace_root):
    (workspace_root / "app.py").write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")

    workspace.edit_file("app.py", "b = 2", "b = 20")

    assert (workspace_root / "app.py").read_text(encoding="utf-8") == "a = 1\nb = 20\nc = 3\n"


def test_edit_file_not_found_raises(workspace_root):
    (workspace_root / "app.py").write_text("a = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="n'apparaît pas"):
        workspace.edit_file("app.py", "x = 99", "x = 100")


def test_edit_file_ambiguous_match_raises(workspace_root):
    (workspace_root / "app.py").write_text("a = 1\na = 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="ambigu"):
        workspace.edit_file("app.py", "a = 1", "a = 2")


def test_edit_file_missing_file_raises(workspace_root):
    with pytest.raises(ValueError, match="n'existe pas"):
        workspace.edit_file("missing.py", "a", "b")


def test_edit_file_on_directory_raises(workspace_root):
    (workspace_root / "pkg").mkdir()

    with pytest.raises(ValueError, match="dossier"):
        workspace.edit_file("pkg", "a", "b")


def test_edit_file_binary_file_raises(workspace_root):
    (workspace_root / "image.png").write_bytes(bytes([0xFF, 0xFE, 0x00, 0x80, 0x81]))

    with pytest.raises(ValueError, match="binaire"):
        workspace.edit_file("image.png", "a", "b")


def test_edit_file_rejects_escape_attempt(workspace_root):
    with pytest.raises(ValueError, match="sort du dépôt"):
        workspace.edit_file("../../../Windows/win.ini", "a", "b")
