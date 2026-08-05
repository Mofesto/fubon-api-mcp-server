"""MCP v2 / protocol revision 2026-07-28 contract tests."""

import asyncio
import os
from unittest.mock import patch

import httpx2
import pytest
from mcp import Client
from mcp.server.mcpserver import MCPServer
from mcp.types import LATEST_PROTOCOL_VERSION

from fubon_api_mcp_server import server


def test_sdk_targets_mcp_v2_and_2026_protocol():
    assert LATEST_PROTOCOL_VERSION == "2026-07-28"
    assert isinstance(server.mcp, MCPServer)
    assert server.mcp.name == "fubon-api-mcp-server"
    assert server.mcp.version


def test_mcp_v2_client_uses_discovery_and_structured_tool_output():
    asyncio.run(_exercise_modern_client())


async def _exercise_modern_client():
    mcp_server = MCPServer("contract-test", version="test")

    @mcp_server.tool()
    def echo(value: str) -> dict[str, str]:
        return {"status": "success", "data": value}

    async with Client(mcp_server) as client:
        assert client.protocol_version == "2026-07-28"
        result = await client.call_tool("echo", {"value": "ok"})

    assert result.is_error is False
    assert result.structured_content == {"status": "success", "data": "ok"}
    assert result.meta is not None
    assert result.meta["io.modelcontextprotocol/serverInfo"]["name"] == "contract-test"


def test_streamable_http_defaults_to_stateless_2026_transport():
    with (
        patch.dict(
            os.environ,
            {
                "FUBON_MCP_TRANSPORT": "streamable-http",
                "FUBON_MCP_HOST": "127.0.0.1",
                "FUBON_MCP_PORT": "8123",
                "FUBON_MCP_HTTP_PATH": "/mcp",
            },
            clear=False,
        ),
        patch.object(server.mcp, "run") as run,
    ):
        server.run_mcp_server()

    run.assert_called_once_with(
        "streamable-http",
        host="127.0.0.1",
        port=8123,
        streamable_http_path="/mcp",
        json_response=False,
        stateless_http=True,
    )


def test_streamable_http_stateless_endpoint_accepts_2026_request():
    asyncio.run(_exercise_stateless_http())


async def _exercise_stateless_http():
    mcp_server = MCPServer("http-contract", version="test")

    @mcp_server.tool()
    def echo(value: str) -> dict[str, str]:
        return {"status": "success", "data": value}

    app = mcp_server.streamable_http_app(stateless_http=True, json_response=True)
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "echo",
            "arguments": {"value": "ok"},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {"name": "test-client", "version": "test"},
            },
        },
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "mcp-protocol-version": "2026-07-28",
        "mcp-method": "tools/call",
        "mcp-name": "echo",
    }

    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as http:
            response = await http.post("/mcp", json=body, headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["structuredContent"] == {"status": "success", "data": "ok"}
    assert "mcp-session-id" not in {key.lower() for key in response.headers}


def test_unknown_transport_fails_closed():
    with patch.dict(os.environ, {"FUBON_MCP_TRANSPORT": "unknown"}, clear=False):
        with pytest.raises(ValueError, match="FUBON_MCP_TRANSPORT"):
            server.run_mcp_server()
