import pytest

from codefixer.servers import workspace


@pytest.fixture(autouse=True)
def workspace_root(tmp_path, monkeypatch):
    """Toutes les fonctions du serveur lisent workspace.WORKSPACE : on le pointe
    vers un dossier temporaire propre pour chaque test."""
    monkeypatch.setattr(workspace, "WORKSPACE", tmp_path)
    return tmp_path


def test_read_file_numbers_every_line(workspace_root):
    (workspace_root / "app.py").write_text("one\ntwo\nthree\n", encoding="utf-8")

    result = workspace.read_file("app.py")

    assert result == "1: one\n2: two\n3: three"


def test_read_file_partial_range(workspace_root):
    (workspace_root / "app.py").write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

    result = workspace.read_file("app.py", start_line=2, end_line=3)

    assert result == "2: two\n3: three"


def test_read_file_end_line_beyond_file_is_clamped(workspace_root):
    (workspace_root / "app.py").write_text("one\ntwo\n", encoding="utf-8")

    result = workspace.read_file("app.py", start_line=1, end_line=100)

    assert result == "1: one\n2: two"


def test_read_file_start_line_beyond_file_raises(workspace_root):
    (workspace_root / "app.py").write_text("one\ntwo\n", encoding="utf-8")

    with pytest.raises(ValueError, match="2 lignes"):
        workspace.read_file("app.py", start_line=5)


def test_read_file_empty_file_returns_empty_string(workspace_root):
    (workspace_root / "empty.py").write_text("", encoding="utf-8")

    assert workspace.read_file("empty.py") == ""


def test_read_file_missing_file_raises(workspace_root):
    with pytest.raises(ValueError, match="n'existe pas"):
        workspace.read_file("missing.py")


def test_read_file_on_directory_raises(workspace_root):
    (workspace_root / "pkg").mkdir()

    with pytest.raises(ValueError, match="dossier"):
        workspace.read_file("pkg")


def test_read_file_binary_file_raises(workspace_root):
    (workspace_root / "image.png").write_bytes(bytes([0xFF, 0xFE, 0x00, 0x80, 0x81]))

    with pytest.raises(ValueError, match="binaire"):
        workspace.read_file("image.png")


def test_read_file_too_large_without_range_raises(workspace_root, monkeypatch):
    monkeypatch.setattr(workspace, "MAX_LINES", 3)
    (workspace_root / "big.py").write_text("\n".join(f"line{i}" for i in range(10)), encoding="utf-8")

    with pytest.raises(ValueError, match="trop pour être lu en entier"):
        workspace.read_file("big.py")


def test_read_file_too_large_with_range_is_allowed(workspace_root, monkeypatch):
    monkeypatch.setattr(workspace, "MAX_LINES", 3)
    (workspace_root / "big.py").write_text("\n".join(f"line{i}" for i in range(10)), encoding="utf-8")

    result = workspace.read_file("big.py", start_line=1, end_line=2)

    assert result == "1: line0\n2: line1"


def test_search_code_finds_matches_across_files(workspace_root):
    (workspace_root / "pricing.py").write_text(
        "def calculate_discount(price, rate):\n    return price * rate / 10\n", encoding="utf-8"
    )
    (workspace_root / "cart.py").write_text("items = []\n", encoding="utf-8")

    result = workspace.search_code("discount")

    assert result == "pricing.py:1: def calculate_discount(price, rate):"


def test_search_code_supports_regex(workspace_root):
    (workspace_root / "pricing.py").write_text("def calculate_discount():\n    pass\n", encoding="utf-8")

    result = workspace.search_code(r"def \w+_discount")

    assert result == "pricing.py:1: def calculate_discount():"


def test_search_code_invalid_regex_raises(workspace_root):
    with pytest.raises(ValueError, match="expression régulière"):
        workspace.search_code("(unclosed")


def test_search_code_no_match_returns_message(workspace_root):
    (workspace_root / "cart.py").write_text("items = []\n", encoding="utf-8")

    result = workspace.search_code("discount")

    assert result == "Aucune correspondance pour 'discount'."


def test_search_code_ignores_ignored_dirs(workspace_root):
    (workspace_root / ".git").mkdir()
    (workspace_root / ".git" / "config").write_text("discount\n", encoding="utf-8")
    (workspace_root / "app.py").write_text("discount = 10\n", encoding="utf-8")

    result = workspace.search_code("discount")

    assert result == "app.py:1: discount = 10"


def test_search_code_skips_binary_files(workspace_root):
    (workspace_root / "image.png").write_bytes(bytes([0xFF, 0xFE, 0x00, 0x80, 0x81]))
    (workspace_root / "app.py").write_text("discount = 10\n", encoding="utf-8")

    result = workspace.search_code("discount")

    assert result == "app.py:1: discount = 10"


def test_search_code_missing_path_raises(workspace_root):
    with pytest.raises(ValueError, match="n'existe pas"):
        workspace.search_code("discount", path="missing")


def test_search_code_path_is_a_file_raises(workspace_root):
    (workspace_root / "app.py").write_text("discount = 10\n", encoding="utf-8")

    with pytest.raises(ValueError, match="dossier"):
        workspace.search_code("discount", path="app.py")


def test_search_code_truncates_results(workspace_root, monkeypatch):
    monkeypatch.setattr(workspace, "MAX_MATCHES", 2)
    (workspace_root / "app.py").write_text("\n".join("discount" for _ in range(5)), encoding="utf-8")

    result = workspace.search_code("discount")

    assert result.count("discount") == 2
    assert "tronqué" in result
