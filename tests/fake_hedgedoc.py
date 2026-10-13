"""A tiny in-process HTTP server that mimics HedgeDoc 1.x's auth and note routes.

Behaviour follows HedgeDoc 1.10's source (app.js, lib/errors.js,
lib/web/note/util.js, lib/history.js, lib/web/userRouter.js):

- Every response except /status carries a session cookie
  (express-session with ``saveUninitialized: true``), including failed logins.
- POST /login redirects to the home page whether or not the credentials match.
- "Forbidden" for a logged-out user is a redirect to the home page; for a
  logged-in user it is an HTML 403 page.
- Creating an alias that already exists is a 409; aliases without FreeURL are
  forbidden.

Unlike mocks of ``requests.Session``, this exercises real cookie-jar and
redirect handling.
"""

from __future__ import annotations

import itertools
import json
import secrets
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlsplit


@dataclass
class Note:
    content: str
    owner: str | None
    permission: str = "freely"
    alias: str | None = None


@dataclass
class FakeHedgeDoc:
    users: dict[str, str] = field(default_factory=lambda: {"user@example.com": "hunter2"})
    session_name: str = "connect.sid"
    allow_anonymous: bool = False
    allow_freeurl: bool = True
    server_url: str | None = None  # CMD_DOMAIN-derived URL; defaults to the bound address
    notes: dict[str, Note] = field(default_factory=dict)
    sessions: dict[str, str | None] = field(default_factory=dict)
    requests: list[tuple[str, str]] = field(default_factory=list)  # (method, raw path)

    def __post_init__(self) -> None:
        self._ids = itertools.count(1)
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(self))
        self.port = self._httpd.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}"
        if self.server_url is None:
            self.server_url = self.url
        threading.Thread(
            target=self._httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        ).start()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def restart(self) -> None:
        """Drop all sessions, as a server restart or SESSION_SECRET rotation would."""
        self.sessions.clear()

    def new_note_id(self) -> str:
        return f"note{next(self._ids)}"


def _make_handler(hd: FakeHedgeDoc) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

        # -- session ---------------------------------------------------------

        def _load_session(self) -> None:
            self.sid = None
            self.new_cookie = False
            for part in self.headers.get("Cookie", "").split(";"):
                name, _, value = part.strip().partition("=")
                if name == hd.session_name:
                    sid = unquote(value).removeprefix("s:").split(".", 1)[0]
                    if sid in hd.sessions:
                        self.sid = sid
            if self.sid is None:
                self._new_session(None)

        def _new_session(self, user: str | None) -> None:
            self.sid = secrets.token_urlsafe(8)
            hd.sessions[self.sid] = user
            self.new_cookie = True

        @property
        def user(self) -> str | None:
            return hd.sessions.get(self.sid)

        # -- responses -------------------------------------------------------

        def _send(self, status, body=b"", content_type="text/html", headers=None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            if self.new_cookie and self.path_only != "/status":
                cookie = quote(f"s:{self.sid}.signature", safe="")
                self.send_header("Set-Cookie", f"{hd.session_name}={cookie}; Path=/; HttpOnly")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data) -> None:
            self._send(200, json.dumps(data).encode(), "application/json")

        def _redirect(self, location: str) -> None:
            self._send(302, headers={"Location": location})

        def _error(self, status: int) -> None:
            self._send(status, f"<html>{status} error page</html>".encode())

        def _forbidden(self) -> None:
            if self.user:
                self._error(403)
            else:
                self._redirect(f"{hd.server_url}/")

        def _can_view(self, note: Note) -> bool:
            if note.permission == "private":
                return self.user is not None and note.owner == self.user
            if note.permission in ("limited", "protected"):
                return self.user is not None
            return True

        # -- routing ---------------------------------------------------------

        def _route(self, method: str) -> list[str]:
            hd.requests.append((method, self.path))
            self.path_only = urlsplit(self.path).path
            self._load_session()
            return [unquote(s) for s in self.path_only.strip("/").split("/")]

        def do_GET(self) -> None:
            parts = self._route("GET")
            if parts == [""]:
                return self._send(200, b"<html>HedgeDoc home</html>")
            if parts == ["me"]:
                if self.user:
                    return self._json({"status": "ok", "id": "u1", "name": self.user})
                return self._json({"status": "forbidden"})
            if parts == ["status"]:
                return self._json({"onlineNotes": 0, "notesCount": len(hd.notes)})
            if parts == ["history"]:
                if not self.user:
                    return self._forbidden()
                return self._json({"history": [{"id": k, "text": k} for k in hd.notes]})
            if len(parts) == 2 and parts[1] in ("download", "info"):
                note = hd.notes.get(parts[0])
                if note is None:
                    return self._error(404)
                if not self._can_view(note):
                    return self._forbidden()
                if parts[1] == "download":
                    return self._send(200, note.content.encode(), "text/markdown; charset=UTF-8")
                return self._json(
                    {
                        "title": note.content.splitlines()[0].lstrip("# ") if note.content else "",
                        "description": None,
                        "viewcount": 0,
                        "createtime": "2026-01-01T00:00:00.000Z",
                        "updatetime": "2026-01-02T00:00:00.000Z",
                    }
                )
            return self._error(404)

        def do_POST(self) -> None:
            parts = self._route("POST")
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if parts == ["login"]:
                form = {k: v[0] for k, v in parse_qs(body.decode()).items()}
                if hd.users.get(form.get("email")) == form.get("password"):
                    self._new_session(form["email"])
                # Failure stores a flash message in the existing session; either way, go home.
                return self._redirect(f"{hd.server_url}/")
            if parts[0] == "new" and len(parts) <= 2:
                if not self.user and not hd.allow_anonymous:
                    return self._forbidden()
                alias = parts[1] if len(parts) == 2 else None
                if alias is not None:
                    if not hd.allow_freeurl:
                        return self._forbidden()
                    if alias in hd.notes:
                        return self._error(409)
                note_id = alias or hd.new_note_id()
                hd.notes[note_id] = Note(body.decode(), self.user, alias=alias)
                return self._redirect(f"{hd.server_url}/{quote(note_id, safe='')}")
            return self._error(404)

    return Handler
