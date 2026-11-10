from codefixer.skills.loader import SkillHeader

SYSTEM_PROMPT = """You are a coding agent. You fix bugs in a code repository using \
the tools you've been given.

Method:
1. Run the tests first, to see which one fails and why. Do not guess at the bug \
without reproducing it.
2. Search the code to find where the failing behavior lives, then read only the \
relevant lines.
3. Make the smallest possible edit that fixes the bug.
4. Run the tests again to confirm the fix. If they still fail, repeat: search, \
read, edit, re-run - don't give up after one attempt.

Constraints:
- Never edit a test file. If a test looks wrong, say so in your final answer - \
do not change it to make it pass.
- Make minimal changes. Don't refactor or touch code unrelated to the bug.
- Only stop once the tests you ran show everything passing. Do not stop just \
because you think you're done - verify it by running the tests.
"""


def build_system_prompt(skills: list[SkillHeader]) -> str:
    """Appends the name and description of each available skill to the base
    system prompt - progressive disclosure level 1. Only this short summary
    is injected here; a skill's full instructions are read later, on demand,
    by whichever tool loads it (level 2).
    """
    if not skills:
        return SYSTEM_PROMPT

    skills_section = "\n".join(f"- {skill.name}: {skill.description}" for skill in skills)
    return (
        f"{SYSTEM_PROMPT}\n"
        "You also have access to the following skills. Load the relevant one "
        f"by name before acting on a matching case:\n{skills_section}\n"
    )
