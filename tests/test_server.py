"""Tests for MCP-facing error behaviour."""

from __future__ import annotations

import asyncio

from hedgedoc_mcp import server
from hedgedoc_mcp.client import HedgeDocError


def test_update_tool_reports_unsupported_operation(mocker):
    client = mocker.Mock()
    client.update_note.side_effect = HedgeDocError("Updating notes is unsupported")
    mocker.patch("hedgedoc_mcp.server._get_client", return_value=client)

    async def run_synchronously(function, *args):
        return function(*args)

    mocker.patch("hedgedoc_mcp.server.asyncio.to_thread", side_effect=run_synchronously)

    result = asyncio.run(
        server.call_tool(
            "hedgedoc_update_note", {"note_id": "existing-alias", "content": "# Replacement"}
        )
    )

    assert result[0].text == "Error: Updating notes is unsupported"


def test_update_tool_description_does_not_claim_it_updates_notes():
    tools = asyncio.run(server.list_tools())
    update_tool = next(tool for tool in tools if tool.name == "hedgedoc_update_note")

    assert "Unsupported operation" in update_tool.description
    assert "does not modify the note" in update_tool.description
