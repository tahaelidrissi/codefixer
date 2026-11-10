from codefixer.agent.prompts import SYSTEM_PROMPT, build_system_prompt
from codefixer.skills.loader import SkillHeader


def test_build_system_prompt_with_no_skills_returns_the_base_prompt():
    assert build_system_prompt([]) == SYSTEM_PROMPT


def test_build_system_prompt_lists_each_skills_name_and_description():
    skills = [
        SkillHeader(name="write-pytest-test", description="How to write a regression test."),
        SkillHeader(name="debug-import-error", description="How to diagnose an import error."),
    ]

    prompt = build_system_prompt(skills)

    assert prompt.startswith(SYSTEM_PROMPT)
    for skill in skills:
        assert skill.name in prompt
        assert skill.description in prompt
