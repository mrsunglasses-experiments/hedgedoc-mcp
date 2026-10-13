"""hedgedoc-mcp: an MCP server exposing HedgeDoc 1.x as agent tools.

Exposes:
    hedgedoc_create_note   -- create a new note, returns its URL
    hedgedoc_read_note     -- fetch a note's raw markdown
    hedgedoc_update_note   -- reports that HTTP updates are unsupported
    hedgedoc_note_info     -- title, timestamps, viewcount for a note
    hedgedoc_whoami        -- verify the current session / show logged-in user
    hedgedoc_list_history  -- recently viewed/pinned notes for the logged-in user

Any MCP-compatible agent (Claude Code, Codex, Hermes, custom clients) can
load this server and get direct read/write access to a self-hosted
HedgeDoc instance -- see README.md for setup instructions per client.
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .auth import Config, ConfigError, build_client
from .client import HedgeDocError, SessionExpiredError

server = Server("hedgedoc-mcp")

_client = None  # lazily built on first tool call, so import-time never needs network


def _get_client():
    global _client
    if _client is None:
        try:
            config = Config.from_env()
        except ConfigError as e:
            raise RuntimeError(str(e)) from e
        _client = build_client(config)
    return _client


def _reset_client():
    """Force a rebuild (fresh login) on the next call -- used after SessionExpiredError."""
    global _client
    _client = None


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="hedgedoc_create_note",
            description=(
                "Create a new note on the HedgeDoc instance. "
                "Returns JSON with two fields: 'note_id' (the unique identifier / URL slug) "
                "and 'url' (the full URL where the note can be viewed or shared). "
                "Use `alias` to assign a human-readable slug such as 'q3-research-notes'. "
                "HedgeDoc 1.x does not support updating either aliases or random-ID notes "
                "over HTTP. "
                "Alias support requires FreeURL mode enabled on the server "
                "(CMD_ALLOW_FREEURL=true)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": (
                            "Full markdown content for the note. "
                            "Supports standard CommonMark plus HedgeDoc extensions "
                            "(diagrams, math, front matter, etc.)."
                        ),
                    },
                    "alias": {
                        "type": "string",
                        "description": (
                            "Optional custom URL slug, e.g. 'meeting-2026-08-16' or 'q3-research'. "
                            "Must be URL-safe (letters, digits, hyphens). "
                            "Requires FreeURL mode on the server."
                        ),
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="hedgedoc_read_note",
            description=(
                "Fetch the raw markdown content of an existing note by its ID or alias. "
                "Returns the note's markdown as a plain string. "
                "This is a public endpoint — no authentication is required to read notes "
                "on instances that allow public access."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": (
                            "The note's unique ID (e.g. 'AbC123XyZ') or custom alias "
                            "(e.g. 'my-meeting-notes'). Both forms are accepted."
                        ),
                    },
                },
                "required": ["note_id"],
            },
        ),
        Tool(
            name="hedgedoc_update_note",
            description=(
                "Unsupported operation. HedgeDoc 1.x has no HTTP endpoint to update note content. "
                "Its browser editor uses a Socket.IO collaborative-editing protocol instead. "
                "POST /new/{alias} does not overwrite an existing alias: it returns HTTP 409. "
                "This tool returns a clear error and does not modify the note."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": (
                            "The note ID or alias. This is retained for API compatibility; "
                            "the operation is unsupported."
                        ),
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "Requested markdown content. This is retained for API compatibility; "
                            "the operation is unsupported."
                        ),
                    },
                },
                "required": ["note_id", "content"],
            },
        ),
        Tool(
            name="hedgedoc_note_info",
            description=(
                "Get metadata for a note. "
                "Returns JSON with: 'title' (string), 'description' (string or null), "
                "'viewcount' (integer — total views), "
                "'createtime' and 'updatetime' "
                "(ISO 8601 timestamps, e.g. '2026-08-16T10:30:00.000Z'). "
                "This is a public endpoint — no authentication required."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "note_id": {
                        "type": "string",
                        "description": "Note ID or alias.",
                    },
                },
                "required": ["note_id"],
            },
        ),
        Tool(
            name="hedgedoc_whoami",
            description=(
                "Verify the current session is valid and return the logged-in user's profile. "
                "Returns JSON with user info (name, email, photo, provider, etc.). "
                "Call this to confirm the server is correctly authenticated before "
                "attempting write operations, or to identify which account is active."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="hedgedoc_list_history",
            description=(
                "List the logged-in user's recently viewed and pinned notes. "
                "Returns a JSON array of note objects. Each object includes: "
                "'id' (note ID or alias), 'text' (note title), 'tags' (array of strings), "
                "'pinned' (boolean), and 'time' (last-viewed timestamp in milliseconds). "
                "Requires a valid session — will raise an error if not authenticated."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        client = _get_client()
        result = await asyncio.to_thread(_dispatch, client, name, arguments)
        return [TextContent(type="text", text=result)]
    except SessionExpiredError:
        # One automatic retry: rebuild the client (fresh login) and try once more.
        _reset_client()
        try:
            client = _get_client()
            result = await asyncio.to_thread(_dispatch, client, name, arguments)
            return [TextContent(type="text", text=result)]
        except (HedgeDocError, ConfigError) as e:
            return [TextContent(type="text", text=f"Error: {e}")]
    except (HedgeDocError, ConfigError, RuntimeError) as e:
        return [TextContent(type="text", text=f"Error: {e}")]


def _dispatch(client, name: str, arguments: dict) -> str:
    if name == "hedgedoc_create_note":
        result = client.create_note(arguments["content"], arguments.get("alias"))
        return json.dumps({"note_id": result.note_id, "url": result.url}, indent=2)

    if name == "hedgedoc_read_note":
        content = client.read_note(arguments["note_id"])
        return content

    if name == "hedgedoc_update_note":
        client.update_note(arguments["note_id"], arguments["content"])
        return f"Note '{arguments['note_id']}' updated."

    if name == "hedgedoc_note_info":
        info = client.note_info(arguments["note_id"])
        return json.dumps(
            {
                "title": info.title,
                "description": info.description,
                "viewcount": info.viewcount,
                "createtime": info.createtime,
                "updatetime": info.updatetime,
            },
            indent=2,
        )

    if name == "hedgedoc_whoami":
        data = client.whoami()
        return json.dumps(data, indent=2)

    if name == "hedgedoc_list_history":
        history = client.history()
        return json.dumps(history, indent=2)

    raise HedgeDocError(f"Unknown tool: {name}")


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Entry point for the `hedgedoc-mcp` console script."""
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
