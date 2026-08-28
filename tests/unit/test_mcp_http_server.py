"""Unit tests for MCP streamable HTTP server helpers."""

from __future__ import annotations

from src.mcp_http_server import DEFAULT_MCP_PROTOCOL_VERSION, _normalize_initialize_payload


def test_normalize_initialize_adds_missing_protocol_version() -> None:
    payload: object = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "capabilities": {},
            "clientInfo": {"name": "curl-client", "version": "0.1"},
        },
    }

    assert _normalize_initialize_payload(payload) is True
    assert isinstance(payload, dict)
    assert payload["params"]["protocolVersion"] == DEFAULT_MCP_PROTOCOL_VERSION


def test_normalize_initialize_preserves_existing_protocol_version() -> None:
    payload: object = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05"},
    }

    assert _normalize_initialize_payload(payload) is False
    assert isinstance(payload, dict)
    assert payload["params"]["protocolVersion"] == "2024-11-05"


def test_normalize_initialize_ignores_non_initialize_requests() -> None:
    payload: object = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }

    assert _normalize_initialize_payload(payload) is False
    assert isinstance(payload, dict)
    assert "protocolVersion" not in payload["params"]
