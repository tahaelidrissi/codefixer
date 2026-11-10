from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

_MAX_ARG_LEN = 80
_MAX_RESULT_LEN = 200
_MAX_ANSWER_LEN = 500


def _truncate(text: str, max_len: int) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= max_len else text[:max_len] + "..."


def format_step(message: BaseMessage) -> str | None:
    """Turns one message from the agent loop into a human-readable line: a
    tool call (name + truncated arguments), a tool result (truncated
    content), or the final answer. Returns None for messages that aren't a
    reasoning step to show (system/human).
    """
    if isinstance(message, AIMessage):
        if message.tool_calls:
            calls = []
            for call in message.tool_calls:
                args = ", ".join(f"{k}={_truncate(str(v), _MAX_ARG_LEN)}" for k, v in call["args"].items())
                calls.append(f"[tool] {call['name']}({args})")
            return "\n".join(calls)
        if message.content:
            return f"[answer] {_truncate(str(message.content), _MAX_ANSWER_LEN)}"
        return None
    if isinstance(message, ToolMessage):
        return f"[result] {_truncate(str(message.content), _MAX_RESULT_LEN)}"
    return None
