from dataclasses import dataclass
from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).resolve().parents[3] / "skills"


@dataclass(frozen=True)
class SkillHeader:
    name: str
    description: str


def load_skill_headers(skills_dir: Path = SKILLS_DIR) -> list[SkillHeader]:
    """Reads only the YAML front matter of each SKILL.md - progressive
    disclosure level 1. The body (the actual instructions) is read later,
    only for a skill the agent decides to load.
    """
    headers = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        _, front_matter, _ = skill_md.read_text(encoding="utf-8").split("---", 2)
        metadata = yaml.safe_load(front_matter)
        headers.append(SkillHeader(name=metadata["name"], description=metadata["description"]))
    return headers
