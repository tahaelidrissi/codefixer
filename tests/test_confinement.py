import pytest
from mcp.server.mcpserver.exceptions import ToolError

from codefixer.servers import workspace


@pytest.fixture(autouse=True)
def workspace_root(tmp_path, monkeypatch):
    monkeypatch.setattr(workspace, "WORKSPACE", tmp_path)
    return tmp_path


def test_resolve_path_allows_relative_path_inside_workspace(workspace_root):
    (workspace_root / "src").mkdir()

    resolved = workspace.resolve_path("src")

    assert resolved == workspace_root / "src"


def test_resolve_path_rejects_absolute_path(workspace_root):
    with pytest.raises(ToolError, match="absolu"):
        workspace.resolve_path("C:/Windows/System32")


def test_resolve_path_rejects_absolute_posix_style_path(workspace_root):
    """Sur Windows, '/etc/passwd' n'a pas de lettre de lecteur donc pathlib ne le considère pas
    "absolu" : c'est le deuxième filtre (resolve + comparaison à WORKSPACE) qui le bloque."""
    with pytest.raises(ToolError, match="sort du dépôt"):
        workspace.resolve_path("/etc/passwd")


def test_resolve_path_rejects_dotdot_escape(workspace_root):
    with pytest.raises(ToolError, match="sort du dépôt"):
        workspace.resolve_path("../../../Windows")


def test_resolve_path_allows_dotdot_that_stays_inside(workspace_root):
    (workspace_root / "a" / "b").mkdir(parents=True)

    resolved = workspace.resolve_path("a/b/../b")

    assert resolved == workspace_root / "a" / "b"


def test_list_files_rejects_escape_attempt(workspace_root):
    with pytest.raises(ToolError, match="sort du dépôt"):
        workspace.list_files("../../../Windows")


def test_read_file_rejects_absolute_path(workspace_root):
    with pytest.raises(ToolError, match="absolu"):
        workspace.read_file("C:/Windows/System32/config/SAM")


def test_search_code_rejects_escape_attempt(workspace_root):
    with pytest.raises(ToolError, match="sort du dépôt"):
        workspace.search_code("password", path="../../..")
