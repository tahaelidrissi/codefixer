from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from pydantic import BaseModel, Field

from codefixer.agent.graph import init_chat_model


class Report(BaseModel):
    cause: str = Field(description="A short explanation of what caused the bug.")
    files_modified: list[str] = Field(description="Repo-relative paths the agent edited.")
    tests_passed: bool = Field(description="Whether the last test run was green.")


class _Cause(BaseModel):
    cause: str = Field(description="A short explanation of what caused the bug.")


def _extract_files_modified(messages: list[BaseMessage]) -> list[str]:
    """Reads edit_file calls straight from the trace, instead of asking the
    LLM to recall which files it touched - it already happened, it's a fact."""
    paths: list[str] = []
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                if call["name"] == "edit_file":
                    path = call["args"]["path"]
                    if path not in paths:
                        paths.append(path)
    return paths


def _extract_tests_passed(messages: list[BaseMessage]) -> bool:
    """Reads the last run_tests result, not the LLM's claim about it."""
    for message in reversed(messages):
        if isinstance(message, ToolMessage) and message.name == "run_tests":
            return "failed" not in message.content and "passed" in message.content
    return False


def build_report(messages: list[BaseMessage], model: str = "claude-opus-5-5") -> Report:
    """Builds the agent's final report from a finished run. files_modified and
    tests_passed are extracted from the tool-call trace, which is a fact we
    already have; only `cause` - a judgment only the model can make - is
    asked of the LLM, through structured output rather than free text.
    """
    # method="json_schema" instead of the default "function_calling": on Groq,
    # forcing a tool call sometimes left the model answering in plain text
    # anyway, which Groq then rejects outright rather than passing it through.
    llm = init_chat_model(model).with_structured_output(_Cause, method="json_schema")
    cause = llm.invoke([*messages, ("user", "In one sentence, what caused this bug?")])

    return Report(
        cause=cause.cause,
        files_modified=_extract_files_modified(messages),
        tests_passed=_extract_tests_passed(messages),
    )
