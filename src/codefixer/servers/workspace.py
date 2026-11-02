from pathlib import Path
from typing import Annotated
import os
from pydantic import Field

from mcp.server import MCPServer

mcp = MCPServer("workspace")

WORKSPACE = Path(os.environ.get("CODEFIXER_WORKSPACE", ".")).resolve()
IGNORED = {".git", ".venv", "__pycache__"}


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