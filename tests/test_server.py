"""Tests for the MCP layer, driven through a real MCP client session."""

from __future__ import annotations

import asyncio
import json

import pytest
from fake_hedgedoc import Note
from mcp import types
from mcp.shared.memory import create_connected_server_and_client_session

from hedgedoc_mcp import server


@pytest.fixture(autouse=True)
def fresh_client():
    server._reset_client()
    yield
    server._reset_client()


@pytest.fixture
def env(hedgedoc, monkeypatch):
    monkeypatch.setenv("HEDGEDOC_URL", hedgedoc.url)
    monkeypatch.setenv("HEDGEDOC_EMAIL", "user@example.com")
    monkeypatch.setenv("HEDGEDOC_PASSWORD", "hunter2")
    monkeypatch.delenv("HEDGEDOC_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("HEDGEDOC_SESSION_COOKIE_NAME", raising=False)
    return hedgedoc


async def _session_call(make_request):
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as session:
        return await make_request(session)


def call(name: str, arguments: dict) -> types.CallToolResult:
    return asyncio.run(_session_call(lambda session: session.call_tool(name, arguments)))


def list_tools() -> list[types.Tool]:
    return asyncio.run(_session_call(lambda session: session.list_tools())).tools


def test_create_and_read_note(env):
    created = call("hedgedoc_create_note", {"content": "# Hello"})
    note_id = json.loads(created.content[0].text)["note_id"]

    read = call("hedgedoc_read_note", {"note_id": note_id})

    assert not created.isError
    assert not read.isError
    assert read.content[0].text == "# Hello"


def test_create_note_with_alias(env):
    created = call("hedgedoc_create_note", {"content": "# Hello", "alias": "my-alias"})

    assert json.loads(created.content[0].text)["note_id"] == "my-alias"


def test_errors_are_flagged_as_errors(env):
    result = call("hedgedoc_read_note", {"note_id": "missing"})

    assert result.isError
    assert "not found" in result.content[0].text


def test_missing_argument_is_flagged_as_error(env):
    result = call("hedgedoc_read_note", {})

    assert result.isError
    assert "note_id" in result.content[0].text


def test_config_error_is_flagged_as_error(monkeypatch):
    monkeypatch.delenv("HEDGEDOC_URL", raising=False)

    result = call("hedgedoc_whoami", {})

    assert result.isError
    assert "HEDGEDOC_URL is not set" in result.content[0].text


def test_expired_session_relogs_in_and_retries_once(env):
    assert not call("hedgedoc_whoami", {}).isError
    env.restart()  # invalidates the session the server is holding

    result = call("hedgedoc_list_history", {})

    assert not result.isError
    assert json.loads(result.content[0].text) == []
    assert [r for r in env.requests if r == ("POST", "/login")] == [("POST", "/login")] * 2


def test_wrong_password_is_reported_instead_of_looping(env, monkeypatch):
    monkeypatch.setenv("HEDGEDOC_PASSWORD", "wrong")

    result = call("hedgedoc_create_note", {"content": "# Hello"})

    assert result.isError
    assert "Login failed" in result.content[0].text
    assert env.notes == {}


def test_note_info(env):
    env.notes["abc"] = Note("# Title", owner=None)

    result = call("hedgedoc_note_info", {"note_id": "abc"})

    assert json.loads(result.content[0].text)["title"] == "Title"


def test_exposes_no_update_tool():
    names = {tool.name for tool in list_tools()}

    assert names == {
        "hedgedoc_create_note",
        "hedgedoc_read_note",
        "hedgedoc_note_info",
        "hedgedoc_whoami",
        "hedgedoc_list_history",
    }


def test_tool_metadata():
    tools = {tool.name: tool for tool in list_tools()}
    create = tools["hedgedoc_create_note"]

    assert {name for name, tool in tools.items() if not tool.annotations.readOnlyHint} == {
        "hedgedoc_create_note"
    }
    assert create.description.startswith("Create a new note on the HedgeDoc instance.\n")
    assert "\n    " not in create.description  # docstring indentation is stripped
    assert create.inputSchema["required"] == ["content"]
    assert "FreeURL" in create.inputSchema["properties"]["alias"]["description"]
    assert create.outputSchema is None
