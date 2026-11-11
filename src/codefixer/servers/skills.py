from mcp.server import MCPServer

from codefixer.skills.loader import SKILLS_DIR, load_skill_headers

mcp = MCPServer("skills")


def _register_skill_resource(name: str, description: str) -> None:
    def read_skill() -> str:
        return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")

    mcp.resource(f"skill://{name}", name=name, description=description, mime_type="text/markdown")(
        read_skill
    )


for _header in load_skill_headers():
    _register_skill_resource(_header.name, _header.description)
