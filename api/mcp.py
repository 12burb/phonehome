"""Vercel Python function: the phonehome MCP server over stateless streamable HTTP, served at /mcp."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from phonehome.mcp_server import asgi_app

_inner = asgi_app("/mcp")


async def app(scope, receive, send):
    # Vercel may hand us the rewritten path (/api/mcp) or the original (/mcp); serve both.
    if scope.get("type") == "http" and scope.get("path", "").startswith("/api/mcp"):
        scope = dict(scope, path="/mcp" + scope["path"][len("/api/mcp"):], raw_path=b"/mcp")
    await _inner(scope, receive, send)
