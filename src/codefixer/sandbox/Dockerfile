FROM python:3.12-slim

# pytest: runs the target repo's tests. mcp[cli]: just enough to run
# codefixer's own workspace.py MCP server in here - not the rest of
# pyproject.toml (langchain, langgraph, etc. only matter on the host side).
RUN pip install --no-cache-dir pytest "mcp[cli]>=2.3.0"

RUN useradd --create-home --uid 1000 sandbox
USER sandbox

WORKDIR /repo

