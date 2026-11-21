# Remote MCP server for the phonehome registry (streamable HTTP on :8787).
#   docker build -t phonehome-mcp . && docker run -p 8787:8787 phonehome-mcp
# The registry data is baked in at build time; set PHONEHOME_DATA=/nonexistent to read the live API instead.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY phonehome ./phonehome
COPY data ./data
RUN pip install --no-cache-dir ".[mcp]"
EXPOSE 8787
ENTRYPOINT ["phonehome-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8787"]
