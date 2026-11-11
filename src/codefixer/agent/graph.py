from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool, ToolException, tool
from langchain_groq import ChatGroq
from langgraph.graph import MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from codefixer.agent.prompts import build_system_prompt
from codefixer.skills.loader import SkillHeader, load_skill_body, load_skill_headers

load_dotenv()

_PROVIDERS: dict[str, type[BaseChatModel]] = {
    "anthropic": ChatAnthropic,
    "groq": ChatGroq,
}

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_MAX_TURNS = 25


def init_chat_model(model: str) -> BaseChatModel:
    """Picks the LangChain chat model class from a "provider:name" string
    (e.g. "groq:llama-3.3-70b-versatile"); a bare name with no prefix
    defaults to "anthropic". This is a tiny hand-written dispatch rather than
    LangChain's own init_chat_model, which pulls in the full `langchain`
    package for a feature we only need across two providers. Shared with
    report.py so both pick a model the same way.
    """
    provider, _, name = model.partition(":")
    if not name:
        provider, name = "anthropic", model
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown model provider '{provider}'. Supported: {', '.join(_PROVIDERS)}.")
    return _PROVIDERS[provider](model=name)


def _build_skill_tool() -> StructuredTool:
    """A local tool, not routed through the MCP workspace server: skills are
    CodeFixer's own bundled knowledge, not something another agent needs to
    reuse over the protocol. Converts the loader's ValueError into
    ToolException so a bad skill name reaches the LLM as a normal failed
    tool call instead of crashing the run - same pattern as every other
    tool in this graph.
    """

    @tool
    def load_skill(name: str) -> str:
        """Load the full instructions of one of the skills listed in the
        system prompt, by its exact name."""
        try:
            return load_skill_body(name)
        except ValueError as exc:
            raise ToolException(str(exc)) from exc

    return load_skill


def build_graph(
    tools: list[StructuredTool],
    model: str = DEFAULT_MODEL,
    max_turns: int = DEFAULT_MAX_TURNS,
    skills: list[SkillHeader] | None = None,
) -> CompiledStateGraph:
    """Builds the ReAct loop: an agent node calls the LLM (with these tools bound),
    a conditional edge sends it to the tools node whenever the LLM asked for one,
    and the tools node's result goes back to the agent. Ends when the LLM answers
    without requesting a tool. `model` is a plain "provider:name" string, not
    hardcoded, so the same graph can run against different models and providers.

    `max_turns` caps LangGraph's recursion_limit so a stuck agent can't loop
    forever; it's baked into the compiled graph itself (not left for the
    caller to pass at invoke time) so no future caller can forget it. Hitting
    the limit raises GraphRecursionError - left uncaught here, since silently
    swallowing it would make a failed run look like a clean one.

    `skills` defaults to the real skills shipped in skills/; it's only a
    parameter so tests can pass a controlled list instead. The system prompt
    is built once here, not re-read on every turn, since skills don't change
    during a run.
    """
    if skills is None:
        skills = load_skill_headers()
    system_prompt = build_system_prompt(skills)
    all_tools = [*tools, _build_skill_tool()] if skills else tools
    llm = init_chat_model(model).bind_tools(all_tools)

    def agent_node(state: MessagesState) -> dict:
        response = llm.invoke([SystemMessage(content=system_prompt), *state["messages"]])
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    # LangGraph's ToolNode only converts its own ToolInvocationError into a
    # message for the LLM by default - any other exception, including our
    # ToolException for a deliberate tool failure, crashes the whole run
    # unless listed here. Same anticipated-failure-vs-crash split as the MCP
    # server's ToolError, one layer up.
    graph.add_node("tools", ToolNode(all_tools, handle_tool_errors=(ToolException,)))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile().with_config(recursion_limit=max_turns)
