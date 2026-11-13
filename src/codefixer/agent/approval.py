from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from codefixer.agent.github_client import push_fix_branch
from codefixer.agent.review import DiffReview, review_diff


class ApprovalState(TypedDict):
    problem: str
    diff: str
    model: str
    repo_dir: str
    issue_number: int
    review: DiffReview
    approved: bool
    branch: str | None


def _review_node(state: ApprovalState) -> dict:
    return {"review": review_diff(state["problem"], state["diff"], state["model"])}


def _approve_node(state: ApprovalState) -> dict:
    """Pauses the graph here until resumed with Command(resume=<bool>) - the
    actual human-in-the-loop point. What's passed to interrupt() is exactly
    what a caller needs to show someone to decide: the diff itself, plus the
    self-review's summary and any concerns."""
    review = state["review"]
    approved = interrupt({"diff": state["diff"], "summary": review.summary, "concerns": review.concerns})
    return {"approved": approved}


def _push_node(state: ApprovalState) -> dict:
    if not state["approved"]:
        return {"branch": None}
    return {"branch": push_fix_branch(Path(state["repo_dir"]), state["issue_number"])}


def build_approval_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """review -> approve -> push: the self-review from review.py feeds the
    human pause, and the push only happens if the human approves. A separate
    graph from build_graph() in graph.py - that one fixes the bug, this one
    decides whether the fix is allowed to leave the machine, two different
    concerns kept independently editable.

    `checkpointer` defaults to an in-memory one, enough for interrupt() to
    suspend and resume within a single process - what tests use, so they
    don't touch disk. The CLI passes a durable one (SqliteSaver) so a paused
    approval survives past the process that created it.
    """
    graph = StateGraph(ApprovalState)
    graph.add_node("review", _review_node)
    graph.add_node("approve", _approve_node)
    graph.add_node("push", _push_node)
    graph.set_entry_point("review")
    graph.add_edge("review", "approve")
    graph.add_edge("approve", "push")
    return graph.compile(checkpointer=checkpointer or InMemorySaver())
