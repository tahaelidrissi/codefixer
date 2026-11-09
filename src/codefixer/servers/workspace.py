from pathlib import Path
from typing import Annotated
import os
import re
import subprocess
import sys
from pydantic import Field

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

mcp = MCPServer("workspace")

WORKSPACE = Path(os.environ.get("CODEFIXER_WORKSPACE", ".")).resolve()
IGNORED = {".git", ".venv", "__pycache__"}
MAX_LINES = 2000
MAX_MATCHES = 200
MAX_OUTPUT_LINES = 200
TEST_TIMEOUT = 60


def resolve_path(path: str) -> Path:
    """Converts a relative path given by the LLM into a safe absolute path, inside WORKSPACE.

    Rejects absolute paths before even joining them to WORKSPACE (otherwise pathlib silently
    ignores WORKSPACE), then resolves the result (which eliminates ".." and symbolic links)
    and checks that it stays within the repo.
    """
    if Path(path).is_absolute():
        raise ToolError(
            f"'{path}' est un chemin absolu, interdit. Utilise un chemin relatif à la racine du dépôt."
        )

    resolved = (WORKSPACE / path).resolve()

    if not resolved.is_relative_to(WORKSPACE):
        raise ToolError(f"'{path}' sort du dépôt, ce qui n'est pas autorisé.")

    return resolved


@mcp.tool()
def list_files(
    path: Annotated[str, Field(description="Directory to explore, relative to the repo root.")] = ".",
) -> list[str]:
    """Recursively lists the files in a directory of the repo.

    Returns paths relative to the repo root, separated by "/" and sorted,
    directly usable in the other tools.
    The .git, .venv and __pycache__ directories are ignored.
    """
    root = resolve_path(path)

    if not root.exists():
        raise ToolError(
            f"Le dossier '{path}' n'existe pas. Appelle list_files('.') pour voir la structure du dépôt."
        )
    if not root.is_dir():
        raise ToolError(f"'{path}' est un fichier, pas un dossier. Utilise read_file pour le lire.")

    result = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in IGNORED for part in p.parts):
            continue
        result.append(p.relative_to(WORKSPACE).as_posix())

    return sorted(result)


@mcp.tool()
def read_file(
    path: Annotated[str, Field(description="File to read, relative to the repo root.")],
    start_line: Annotated[
        int | None,
        Field(description="First line to read (1-indexed, inclusive). Omitted = from the start."),
    ] = None,
    end_line: Annotated[
        int | None,
        Field(description="Last line to read (1-indexed, inclusive). Omitted = until the end."),
    ] = None,
) -> str:
    """Reads a file from the repo and numbers each line ("12: content").

    Use start_line / end_line to read an excerpt instead of the whole file.
    """
    target = resolve_path(path)

    if not target.exists():
        raise ToolError(
            f"Le fichier '{path}' n'existe pas. Appelle list_files pour voir les fichiers disponibles."
        )
    if not target.is_file():
        raise ToolError(f"'{path}' est un dossier, pas un fichier. Utilise list_files pour l'explorer.")

    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        raise ToolError(f"'{path}' n'est pas un fichier texte lisible (probablement binaire).")

    total = len(lines)
    if total == 0:
        return ""

    if start_line is None and end_line is None and total > MAX_LINES:
        raise ToolError(
            f"'{path}' contient {total} lignes, trop pour être lu en entier. "
            "Précise start_line et end_line pour lire un extrait."
        )

    start = start_line if start_line is not None else 1
    if start < 1:
        raise ToolError("start_line doit être >= 1.")
    if start > total:
        raise ToolError(f"'{path}' ne contient que {total} lignes, start_line={start} est hors limites.")

    end = total if end_line is None else min(end_line, total)
    if end < start:
        raise ToolError(f"end_line ({end_line}) doit être >= start_line ({start}).")

    selected = lines[start - 1 : end]
    return "\n".join(f"{i}: {line}" for i, line in enumerate(selected, start=start))


@mcp.tool()
def search_code(
    pattern: Annotated[str, Field(description="Regular expression to search for (like grep).")],
    path: Annotated[str, Field(description="Directory to search in, relative to the repo root.")] = ".",
) -> str:
    """Searches for a pattern in the files of the repo.

    Returns each matching line in the format "file:line: content".
    The .git, .venv and __pycache__ directories are ignored, as are binary files.
    """
    root = resolve_path(path)

    if not root.exists():
        raise ToolError(
            f"Le dossier '{path}' n'existe pas. Appelle list_files('.') pour voir la structure du dépôt."
        )
    if not root.is_dir():
        raise ToolError(f"'{path}' est un fichier, pas un dossier. Utilise read_file pour le lire.")

    try:
        regex = re.compile(pattern)
    except re.error as e:
        raise ToolError(f"'{pattern}' n'est pas une expression régulière valide : {e}")

    files = sorted(root.rglob("*"), key=lambda p: p.relative_to(WORKSPACE).as_posix())

    results = []
    truncated = False
    for file_path in files:
        if not file_path.is_file():
            continue
        if any(part in IGNORED for part in file_path.parts):
            continue

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue

        rel = file_path.relative_to(WORKSPACE).as_posix()
        for i, line in enumerate(lines, start=1):
            if regex.search(line):
                results.append(f"{rel}:{i}: {line}")
                if len(results) >= MAX_MATCHES:
                    truncated = True
                    break
        if truncated:
            break

    if not results:
        return f"Aucune correspondance pour '{pattern}'."

    output = "\n".join(results)
    if truncated:
        output += f"\n... résultat tronqué à {MAX_MATCHES} correspondances, précise pattern ou path."
    return output


@mcp.tool()
def edit_file(
    path: Annotated[str, Field(description="File to modify, relative to the repo root.")],
    old_str: Annotated[
        str,
        Field(description="Exact text to replace, copied from read_file (without the line numbers). "
                           "Must appear exactly once in the file."),
    ],
    new_str: Annotated[str, Field(description="Replacement text.")],
) -> str:
    """Replaces old_str with new_str in a file of the repo.

    old_str must appear exactly once (otherwise error: not found or ambiguous).
    Only that passage is changed, the rest of the file stays untouched.
    """
    target = resolve_path(path)

    if not target.exists():
        raise ToolError(
            f"Le fichier '{path}' n'existe pas. Appelle list_files pour voir les fichiers disponibles."
        )
    if not target.is_file():
        raise ToolError(f"'{path}' est un dossier, pas un fichier. Utilise list_files pour l'explorer.")

    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ToolError(f"'{path}' n'est pas un fichier texte lisible (probablement binaire).")

    count = content.count(old_str)
    if count == 0:
        raise ToolError(
            f"Le texte donné n'apparaît pas dans '{path}'. Vérifie-le avec read_file avant de réessayer."
        )
    if count > 1:
        raise ToolError(
            f"Le texte donné apparaît {count} fois dans '{path}', c'est ambigu. "
            "Ajoute plus de contexte à old_str pour cibler un seul passage."
        )

    line_number = content[: content.index(old_str)].count("\n") + 1
    target.write_text(content.replace(old_str, new_str, 1), encoding="utf-8")

    return f"'{path}' modifié, ligne {line_number}."


@mcp.tool()
def run_tests(
    target: Annotated[
        str,
        Field(description="File, directory, or specific test to run (pytest syntax, e.g. "
                           "'tests/test_x.py::test_y'), relative to the repo root. Defaults to the whole repo."),
    ] = ".",
) -> str:
    """Runs pytest on the repo and returns its output (raw text, results included).

    A failing test is not a tool error: the output shows it, it's up to the caller
    to interpret it. The output is truncated keeping the end if it's too long
    (that's where the summary and errors are). The process is killed after
    TEST_TIMEOUT seconds if it hasn't finished.
    """
    file_part = target.split("::", 1)[0]
    resolve_path(file_part)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", target],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise ToolError(f"Les tests ont dépassé {TEST_TIMEOUT} secondes et ont été arrêtés.")

    lines = (result.stdout + result.stderr).splitlines()
    if len(lines) > MAX_OUTPUT_LINES:
        omitted = len(lines) - MAX_OUTPUT_LINES
        lines = [f"... sortie tronquée, {omitted} lignes initiales omises ..."] + lines[-MAX_OUTPUT_LINES:]

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
