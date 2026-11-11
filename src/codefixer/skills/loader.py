from dataclasses import dataclass
from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).resolve().parents[3] / "skills"


@dataclass(frozen=True)
class SkillHeader:
    name: str
    description: str


def load_skill_headers(skills_dirs: list[Path] | None = None) -> list[SkillHeader]:
    """Reads only the YAML front matter of each SKILL.md - progressive
    disclosure level 1. The body (the actual instructions) is read later,
    only for a skill the agent decides to load.

    `skills_dirs` defaults to just the built-in skills/. When a target
    repo's own .codefixer/skills/ is added after it, a skill with the same
    name there replaces the built-in one - more specific to the repo wins.
    """
    if skills_dirs is None:
        skills_dirs = [SKILLS_DIR]

    headers: dict[str, SkillHeader] = {}
    for skills_dir in skills_dirs:
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            _, front_matter, _ = skill_md.read_text(encoding="utf-8").split("---", 2)
            metadata = yaml.safe_load(front_matter)
            headers[metadata["name"]] = SkillHeader(name=metadata["name"], description=metadata["description"])
    return list(headers.values())


def load_skill_body(name: str, skills_dirs: list[Path] | None = None) -> str:
    """Reads one skill's full instructions (the part after the front matter) -
    progressive disclosure level 2, only for the one skill the agent asked
    for by name.

    Searched from the most specific directory to the least (same override
    order as load_skill_headers), so a repo's own version of a skill is
    the one actually loaded.
    """
    if skills_dirs is None:
        skills_dirs = [SKILLS_DIR]

    for skills_dir in reversed(skills_dirs):
        skill_md = skills_dir / name / "SKILL.md"
        if skill_md.exists():
            _, _, body = skill_md.read_text(encoding="utf-8").split("---", 2)
            return body.strip()
    raise ValueError(f"Unknown skill '{name}'.")
