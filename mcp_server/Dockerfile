# MCP service image (PLAN.md §16.2), built from the repo root so core/ can be copied in.
FROM python:3.12-slim
WORKDIR /srv
COPY mcp_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY core ./core
COPY mcp_server ./mcp_server
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "mcp_server.server"]
