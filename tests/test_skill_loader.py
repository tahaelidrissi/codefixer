import pytest

from codefixer.skills.loader import SkillHeader, load_skill_body, load_skill_headers


def test_load_skill_headers_finds_the_three_builtin_skills():
    headers = load_skill_headers()

    names = {header.name for header in headers}
    assert names == {"write-pytest-test", "debug-import-error", "repo-conventions"}
    assert all(header.description for header in headers)


def test_load_skill_headers_reads_only_the_front_matter(tmp_path):
    skill_dir = tmp_path / "example-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: example-skill\n"
        "description: An example skill for the test.\n"
        "---\n"
        "# Example\n\n"
        "A horizontal rule below should not confuse the parser:\n\n"
        "---\n\n"
        "More body text.\n",
        encoding="utf-8",
    )

    headers = load_skill_headers(skills_dir=tmp_path)

    assert headers == [SkillHeader(name="example-skill", description="An example skill for the test.")]


def test_load_skill_body_returns_the_content_after_the_front_matter(tmp_path):
    skill_dir = tmp_path / "example-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: example-skill\ndescription: An example skill.\n---\n# Example\n\nBody text.\n",
        encoding="utf-8",
    )

    body = load_skill_body("example-skill", skills_dir=tmp_path)

    assert body == "# Example\n\nBody text."


def test_load_skill_body_rejects_an_unknown_skill_name(tmp_path):
    with pytest.raises(ValueError, match="Unknown skill 'does-not-exist'"):
        load_skill_body("does-not-exist", skills_dir=tmp_path)
