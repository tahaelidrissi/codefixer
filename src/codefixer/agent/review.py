from pydantic import BaseModel, Field

from codefixer.agent.graph import DEFAULT_MODEL, init_chat_model

_REVIEW_PROMPT = """You are reviewing a code change made by another agent to fix the
problem below, before a human decides whether to let it reach GitHub.

Problem the change was supposed to fix:
{problem}

Diff:
{diff}

Judge it the way a careful reviewer would: is the change minimal (no unrelated
edits, no leftover debug code), and does it plausibly fix the stated problem?
A missing regression test is worth noting but is not on its own a blocker.
"""


class DiffReview(BaseModel):
    summary: str = Field(description="One or two sentences describing what the diff actually changes.")
    concerns: str = Field(
        description="Anything a human reviewer should know before approving: unrelated changes, "
        "leftover debug code, a fix that looks unrelated to the problem, a missing regression "
        "test, etc. Empty string if there's nothing to flag."
    )


def review_diff(problem: str, diff: str, model: str = DEFAULT_MODEL) -> DiffReview:
    """Has the model review its own (or another agent's) diff before it's
    allowed to reach GitHub - a second judgment call, independent of
    `build_report`, which only describes what happened rather than whether
    it should be trusted."""
    llm = init_chat_model(model).with_structured_output(DiffReview, method="json_schema")
    return llm.invoke(_REVIEW_PROMPT.format(problem=problem, diff=diff))
