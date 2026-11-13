import asyncio
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from codefixer.agent.github_client import open_pull_request, push_fix_branch
from codefixer.agent.review import DiffReview, review_diff


class ApprovalState(TypedDict):
    problem: str
    diff: str
    model: str
    repo_dir: str
    owner: str
    repo: str
    issue_number: int
    issue_title: str
    review: DiffReview
    approved: bool
    branch: str | None
    pr_url: str | None


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


def _build_open_pr_node(open_pr):
    def node(state: ApprovalState) -> dict:
        """Only runs once a branch actually exists - a rejected approval
        leaves `branch` as None, and there's nothing to open a PR for. A
        plain sync node calling asyncio.run(): the graph itself is driven
        through the sync invoke()/get_state() API in cli.py, which has no
        running event loop at that point, so this doesn't collide with one.
        """
        if not state["branch"]:
            return {"pr_url": None}
        review = state["review"]
        body = f"Fixes #{state['issue_number']}.\n\n{review.summary}"
        pr_url = asyncio.run(open_pr(state["owner"], state["repo"], state["branch"], state["issue_title"], body))
        return {"pr_url": pr_url}

    return node


def build_approval_graph(checkpointer: BaseCheckpointSaver | None = None, open_pr=open_pull_request) -> CompiledStateGraph:
    """review -> approve -> push -> open_pr: the self-review from review.py
    feeds the human pause, the push only happens if the human approves, and
    the PR only opens if the push actually happened. A separate graph from
    build_graph() in graph.py - that one fixes the bug, this one decides
    whether the fix is allowed to leave the machine, two different concerns
    kept independently editable.

    `checkpointer` defaults to an in-memory one, enough for interrupt() to
    suspend and resume within a single process - what tests use, so they
    don't touch disk. The CLI passes a durable one (SqliteSaver) so a paused
    approval survives past the process that created it.

    `open_pr` defaults to the real `open_pull_request` (a genuine GitHub API
    call); tests override it with a fake, the same reason the push step is
    tested against a local bare repo rather than real GitHub.
    """
    graph = StateGraph(ApprovalState)
    graph.add_node("review", _review_node)
    graph.add_node("approve", _approve_node)
    graph.add_node("push", _push_node)
    graph.add_node("open_pr", _build_open_pr_node(open_pr))
    graph.set_entry_point("review")
    graph.add_edge("review", "approve")
    graph.add_edge("approve", "push")
    graph.add_edge("push", "open_pr")
    return graph.compile(checkpointer=checkpointer or InMemorySaver())
