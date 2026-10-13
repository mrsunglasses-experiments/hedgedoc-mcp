"""hedgedoc-mcp: an MCP server exposing HedgeDoc 1.x as agent tools.

Exposes:
    hedgedoc_create_note   -- create a new note, returns its URL
    hedgedoc_read_note     -- fetch a note's raw markdown
    hedgedoc_note_info     -- title, timestamps, viewcount for a note
    hedgedoc_whoami        -- verify the current session / show logged-in user
    hedgedoc_list_history  -- recently viewed/pinned notes for the logged-in user

There is deliberately no update tool: HedgeDoc 1.x has no HTTP endpoint for
editing a note (see docs/LIMITATIONS.md).

Any MCP-compatible agent (Claude Code, Codex, Hermes, custom clients) can
load this server and get direct read/write access to a self-hosted
HedgeDoc instance -- see README.md for setup instructions per client.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
import threading
from collections.abc import Callable
from typing import Annotated, TypeVar

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .auth import Config, build_client
from .client import HedgeDocClient, SessionExpiredError

T = TypeVar("T")

mcp = FastMCP("hedgedoc-mcp", log_level="WARNING")  # no per-request INFO noise

_client: HedgeDocClient | None = None  # built on first tool call, so import never needs network
# Serializes tool calls: the client's requests.Session isn't thread-safe, and
# concurrent calls must not race to rebuild the client after a session expiry.
_client_lock = threading.Lock()

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
_CREATES = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
)

NoteId = Annotated[
    str,
    Field(
        description=(
            "The note's unique ID (e.g. 'AbC123XyZ') or custom alias "
            "(e.g. 'my-meeting-notes'). Both forms are accepted."
        )
    ),
]


def _get_client() -> HedgeDocClient:
    global _client
    if _client is None:
        _client = build_client(Config.from_env())
    return _client


def _reset_client() -> None:
    """Force a rebuild (fresh login) on the next call -- used after SessionExpiredError."""
    global _client
    _client = None


def _with_client(action: Callable[[HedgeDocClient], T]) -> T:
    with _client_lock:
        try:
            return action(_get_client())
        except SessionExpiredError:
            # One automatic retry: rebuild the client (fresh login) and try once more.
            _reset_client()
            return action(_get_client())


async def _call(action: Callable[[HedgeDocClient], T]) -> T:
    # Runs in a worker thread because logging in and every request are blocking I/O.
    # Exceptions propagate: FastMCP reports them to the agent with isError=True.
    return await asyncio.to_thread(_with_client, action)


def _tool(annotations: ToolAnnotations) -> Callable:
    """Register a tool, using its docstring (dedented) as the description agents see."""

    def register(fn: Callable) -> Callable:
        return mcp.tool(
            description=inspect.cleandoc(fn.__doc__ or ""),
            annotations=annotations,
            structured_output=False,
        )(fn)

    return register


@_tool(_CREATES)
async def hedgedoc_create_note(
    content: Annotated[
        str,
        Field(
            description=(
                "Full markdown content for the note. Supports standard CommonMark plus "
                "HedgeDoc extensions (diagrams, math, front matter, etc.)."
            )
        ),
    ],
    alias: Annotated[
        str | None,
        Field(
            description=(
                "Optional custom URL slug, e.g. 'meeting-2026-08-16' or 'q3-research'. "
                "Must be URL-safe (letters, digits, hyphens). Requires FreeURL mode on the server."
            )
        ),
    ] = None,
) -> str:
    """Create a new note on the HedgeDoc instance.

    Returns JSON with two fields: 'note_id' (the unique identifier / URL slug)
    and 'url' (the full URL where the note can be viewed or shared).
    Use `alias` to assign a human-readable slug such as 'q3-research-notes'.
    Notes cannot be edited afterwards: HedgeDoc 1.x has no HTTP endpoint for
    updating note content, so write the complete content in one call.
    Alias support requires FreeURL mode enabled on the server (CMD_ALLOW_FREEURL=true).
    """
    result = await _call(lambda client: client.create_note(content, alias or None))
    return json.dumps({"note_id": result.note_id, "url": result.url}, indent=2)


@_tool(_READ_ONLY)
async def hedgedoc_read_note(note_id: NoteId) -> str:
    """Fetch the raw markdown content of an existing note by its ID or alias.

    Returns the note's markdown as a plain string. Public notes can be read
    without authentication; private ones need the configured account's access.
    """
    return await _call(lambda client: client.read_note(note_id))


@_tool(_READ_ONLY)
async def hedgedoc_note_info(note_id: NoteId) -> str:
    """Get metadata for a note.

    Returns JSON with: 'title' (string), 'description' (string or null),
    'viewcount' (integer — total views), 'createtime' and 'updatetime'
    (ISO 8601 timestamps, e.g. '2026-08-16T10:30:00.000Z').
    Public notes need no authentication.
    """
    info = await _call(lambda client: client.note_info(note_id))
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


@_tool(_READ_ONLY)
async def hedgedoc_whoami() -> str:
    """Verify the current session is valid and return the logged-in user's profile.

    Returns JSON with user info (status, id, name, photo).
    Call this to confirm the server is correctly authenticated before
    attempting write operations, or to identify which account is active.
    """
    return json.dumps(await _call(lambda client: client.whoami()), indent=2)


@_tool(_READ_ONLY)
async def hedgedoc_list_history() -> str:
    """List the logged-in user's recently viewed and pinned notes.

    Returns a JSON array of note objects. Each object includes:
    'id' (note ID or alias), 'text' (note title), 'tags' (array of strings),
    'pinned' (boolean), and 'time' (last-viewed timestamp in milliseconds).
    Requires a valid session — returns an error if not authenticated.
    """
    return json.dumps(await _call(lambda client: client.history()), indent=2)


def main() -> None:
    """Entry point for the `hedgedoc-mcp` console script."""
    try:
        mcp.run()  # stdio transport
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
