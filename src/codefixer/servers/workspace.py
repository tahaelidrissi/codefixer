from pathlib import Path
from typing import Annotated
import os
import re
from pydantic import Field

from mcp.server import MCPServer

mcp = MCPServer("workspace")

WORKSPACE = Path(os.environ.get("CODEFIXER_WORKSPACE", ".")).resolve()
IGNORED = {".git", ".venv", "__pycache__"}
MAX_LINES = 2000
MAX_MATCHES = 200


@mcp.tool()
def list_files(
    path: Annotated[str, Field(description="Dossier à explorer, relatif à la racine du dépôt.")] = ".",
) -> list[str]:
    """Liste récursivement les fichiers d'un dossier du dépôt.

    Renvoie les chemins relatifs à la racine du dépôt, séparés par "/" et triés,
    directement utilisables dans les autres outils.
    Les dossiers .git, .venv et __pycache__ sont ignorés.
    """
    root = WORKSPACE / path

    if not root.exists():
        raise ValueError(
            f"Le dossier '{path}' n'existe pas. Appelle list_files('.') pour voir la structure du dépôt."
        )
    if not root.is_dir():
        raise ValueError(f"'{path}' est un fichier, pas un dossier. Utilise read_file pour le lire.")

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
    path: Annotated[str, Field(description="Fichier à lire, relatif à la racine du dépôt.")],
    start_line: Annotated[
        int | None,
        Field(description="Première ligne à lire (1-indexée, incluse). Omis = depuis le début."),
    ] = None,
    end_line: Annotated[
        int | None,
        Field(description="Dernière ligne à lire (1-indexée, incluse). Omis = jusqu'à la fin."),
    ] = None,
) -> str:
    """Lit un fichier du dépôt et numérote chaque ligne ("12: contenu").

    Utilise start_line / end_line pour lire un extrait plutôt que tout le fichier.
    """
    target = WORKSPACE / path

    if not target.exists():
        raise ValueError(
            f"Le fichier '{path}' n'existe pas. Appelle list_files pour voir les fichiers disponibles."
        )
    if not target.is_file():
        raise ValueError(f"'{path}' est un dossier, pas un fichier. Utilise list_files pour l'explorer.")

    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        raise ValueError(f"'{path}' n'est pas un fichier texte lisible (probablement binaire).")

    total = len(lines)
    if total == 0:
        return ""

    if start_line is None and end_line is None and total > MAX_LINES:
        raise ValueError(
            f"'{path}' contient {total} lignes, trop pour être lu en entier. "
            "Précise start_line et end_line pour lire un extrait."
        )

    start = start_line if start_line is not None else 1
    if start < 1:
        raise ValueError("start_line doit être >= 1.")
    if start > total:
        raise ValueError(f"'{path}' ne contient que {total} lignes, start_line={start} est hors limites.")

    end = total if end_line is None else min(end_line, total)
    if end < start:
        raise ValueError(f"end_line ({end_line}) doit être >= start_line ({start}).")

    selected = lines[start - 1 : end]
    return "\n".join(f"{i}: {line}" for i, line in enumerate(selected, start=start))


@mcp.tool()
def search_code(
    pattern: Annotated[str, Field(description="Expression régulière à chercher (comme grep).")],
    path: Annotated[str, Field(description="Dossier où chercher, relatif à la racine du dépôt.")] = ".",
) -> str:
    """Cherche un motif dans les fichiers du dépôt.

    Renvoie chaque ligne correspondante au format "fichier:ligne: contenu".
    Les dossiers .git, .venv et __pycache__ sont ignorés, les fichiers binaires aussi.
    """
    root = WORKSPACE / path

    if not root.exists():
        raise ValueError(
            f"Le dossier '{path}' n'existe pas. Appelle list_files('.') pour voir la structure du dépôt."
        )
    if not root.is_dir():
        raise ValueError(f"'{path}' est un fichier, pas un dossier. Utilise read_file pour le lire.")

    try:
        regex = re.compile(pattern)
    except re.error as e:
        raise ValueError(f"'{pattern}' n'est pas une expression régulière valide : {e}")

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


if __name__ == "__main__":
    mcp.run()
