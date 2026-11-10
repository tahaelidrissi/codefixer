from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import StructuredTool
from langchain_groq import ChatGroq
from langgraph.graph import MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()

_PROVIDERS: dict[str, type[BaseChatModel]] = {
    "anthropic": ChatAnthropic,
    "groq": ChatGroq,
}


def _init_chat_model(model: str) -> BaseChatModel:
    """Picks the LangChain chat model class from a "provider:name" string
    (e.g. "groq:llama-3.3-70b-versatile"); a bare name with no prefix
    defaults to "anthropic". This is a tiny hand-written dispatch rather than
    LangChain's own init_chat_model, which pulls in the full `langchain`
    package for a feature we only need across two providers.
    """
    provider, _, name = model.partition(":")
    if not name:
        provider, name = "anthropic", model
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown model provider '{provider}'. Supported: {', '.join(_PROVIDERS)}.")
    return _PROVIDERS[provider](model=name)


def build_graph(tools: list[StructuredTool], model: str = "claude-opus-5-5") -> CompiledStateGraph:
    """Builds the ReAct loop: an agent node calls the LLM (with these tools bound),
    a conditional edge sends it to the tools node whenever the LLM asked for one,
    and the tools node's result goes back to the agent. Ends when the LLM answers
    without requesting a tool. `model` is a plain "provider:name" string, not
    hardcoded, so the same graph can run against different models and providers.
    """
    llm = _init_chat_model(model).bind_tools(tools)

    def agent_node(state: MessagesState) -> dict:
        return {"messages": [llm.invoke(state["messages"])]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    return graph.compile()
