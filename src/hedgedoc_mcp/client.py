"""HedgeDoc 1.x HTTP client.

HedgeDoc 1.x (the widely self-hosted version, as opposed to newer forks)
has NO API token system. Every write endpoint requires an authenticated
session, identified by the cookie name configured by the instance (normally
`connect.sid`) that Express issues on login. This module hides that detail
from callers (the MCP server, the CLI, and tests).

Endpoints used (from HedgeDoc's own OpenAPI spec, version 1.11.1):
    POST /login                  -- email+password login, sets connect.sid
    POST /new                    -- create a note, body = raw markdown
    POST /new/{alias}            -- create a note with a custom slug (needs FreeURL)
    GET  /{note}/download        -- raw markdown content (public notes need no auth)
    GET  /{note}/info            -- title, created/updated, viewcount (public notes)
    GET  /me                     -- verify session / get user info
    GET  /history                -- recently viewed/pinned notes (auth required)
    GET  /status                 -- instance-wide stats (no auth)

When a logged-out request hits something it may not access, HedgeDoc answers
with a redirect to its home page rather than a 401/403. Redirects are therefore
never followed: a redirect home is reported as ``SessionExpiredError``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, NoReturn
from urllib.parse import quote, unquote, urljoin, urlsplit

import requests

DEFAULT_SESSION_COOKIE_NAME = "connect.sid"
_COOKIE_NAME_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


class HedgeDocError(RuntimeError):
    """Raised for any HedgeDoc API failure (auth, network, not-found, etc.)."""


class SessionExpiredError(HedgeDocError):
    """Raised specifically when the stored session cookie is no longer valid.

    Callers should catch this and trigger a re-login (via `login()`) rather
    than treating it as a generic failure.
    """


def validate_session_cookie_name(cookie_name: str) -> str:
    """Return a valid HTTP cookie name, or raise ``HedgeDocError``."""
    if not _COOKIE_NAME_RE.fullmatch(cookie_name):
        raise HedgeDocError("Session cookie name must contain only RFC 6265 token characters.")
    return cookie_name


def validate_base_url(base_url: str) -> str:
    """Return ``base_url`` without a trailing slash, or raise ``HedgeDocError``."""
    url = base_url.strip().rstrip("/")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise HedgeDocError(
            f"Base URL must be an absolute http(s) URL such as https://md.example.com "
            f"(got {base_url!r})."
        )
    return url


@dataclass
class NoteInfo:
    title: str
    description: str | None
    viewcount: int
    createtime: str
    updatetime: str


@dataclass
class NoteResult:
    note_id: str
    url: str


class HedgeDocClient:
    """Thin wrapper around a HedgeDoc 1.x instance.

    Usage:
        client = HedgeDocClient(base_url="https://md.example.com")
        client.set_session_cookie(cookie_value)          # from a prior login
        # ...or...
        client.login(email="you@example.com", password="secret")

        result = client.create_note("# Hello\\n\\nWorld")
        content = client.read_note(result.note_id)

    Not thread-safe: share one instance across threads only behind a lock.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 20,
        session_cookie_name: str = DEFAULT_SESSION_COOKIE_NAME,
    ):
        self.base_url = validate_base_url(base_url)
        self.timeout = timeout
        self.session_cookie_name = validate_session_cookie_name(session_cookie_name)
        self._session = requests.Session()

    # -- Auth -----------------------------------------------------------

    def login(self, email: str, password: str) -> str:
        """Log in with email/password. Returns the raw (decoded) session cookie.

        HedgeDoc issues a session cookie and redirects home whether or not the
        credentials are right, so success is confirmed with ``whoami()``.

        Raises HedgeDocError if the instance has no local email/password
        auth enabled, or the credentials are wrong.
        """
        self._session.cookies.clear()  # a stale cookie would otherwise shadow the new one
        resp = self._post("/login", data={"email": email, "password": password})
        if resp.status_code >= 400:
            raise HedgeDocError(f"Login failed (HTTP {resp.status_code}).")
        try:
            self.whoami()
        except SessionExpiredError:
            raise HedgeDocError(
                "Login failed. Check that the credentials are correct and that "
                "email/password auth is enabled on this HedgeDoc instance (CMD_EMAIL=true)."
            ) from None

        cookie = self.get_session_cookie(encoded=False)
        if not cookie:
            raise HedgeDocError(
                f"Logged in, but the instance did not set a {self.session_cookie_name!r} "
                "cookie. Set HEDGEDOC_SESSION_COOKIE_NAME to the instance's session cookie name."
            )
        return cookie

    def set_session_cookie(self, cookie_value: str) -> None:
        """Install a previously-obtained session cookie.

        Accepts either the raw value or a URL-encoded value (as captured
        from a browser's cookie jar or `cookies.txt`).
        """
        host = urlsplit(self.base_url).hostname or ""
        # http.cookiejar stores host-only cookies under the bare hostname (no port),
        # with ".local" appended to dotless hosts like "localhost". Using the same key
        # makes the cookie match requests, and lets a later login replace it.
        domain = host if "." in host else f"{host}.local"
        value = quote(unquote(cookie_value), safe="")
        self._session.cookies.set(self.session_cookie_name, value, domain=domain, path="/")

    def get_session_cookie(self, encoded: bool = True) -> str | None:
        """Return the current session cookie: URL-encoded as sent on the wire, or decoded."""
        value = self._session.cookies.get(self.session_cookie_name)
        if value is None:
            return None
        return value if encoded else unquote(value)

    def whoami(self) -> dict:
        """Verify the session and return the logged-in user's profile.

        Raises SessionExpiredError if not authenticated.
        """
        data = self._json(self._get("/me"), "check the session")
        if not isinstance(data, dict):
            raise HedgeDocError("Could not check the session: unexpected response from /me.")
        if data.get("status") == "forbidden":
            raise SessionExpiredError(
                "Session cookie is missing, expired, or invalid. Call login() again."
            )
        return data

    # -- Notes ------------------------------------------------------------

    def create_note(self, content: str, alias: str | None = None) -> NoteResult:
        """Create a new note. Returns its ID and full URL.

        If the instance requires login for note creation (the common case)
        and the session is invalid, raises SessionExpiredError.
        """
        if alias:
            what = f"create note with alias '{alias}'"
            path = f"/new/{quote(alias, safe='')}"
        else:
            what = "create note"
            path = "/new"
        resp = self._post(
            path,
            data=content.encode("utf-8"),
            headers={"Content-Type": "text/markdown"},
        )
        if resp.status_code == 409:
            raise HedgeDocError(f"Could not {what}: that alias already exists.")
        if resp.status_code == 403 and alias:
            raise HedgeDocError(
                f"Could not {what}: forbidden. Custom aliases need FreeURL mode on the "
                "server (CMD_ALLOW_FREEURL=true) and must not be a reserved name."
            )

        location = resp.headers.get("Location", "")
        if not 300 <= resp.status_code < 400 or self._is_home(location):
            self._check(resp, what)
            raise HedgeDocError(f"Could not {what}: unexpected HTTP {resp.status_code}.")

        note_url = urljoin(f"{self.base_url}/", location)
        note_id = unquote(urlsplit(note_url).path.rstrip("/").rsplit("/", 1)[-1])
        return NoteResult(note_id=note_id, url=note_url)

    def read_note(self, note_id: str) -> str:
        """Fetch the raw markdown content of a note. Public notes need no auth."""
        resp = self._get(self._note_path(note_id, "download"))
        return self._check(resp, f"read note '{note_id}'").text

    def update_note(self, note_id: str, content: str) -> NoReturn:
        """Raise because HedgeDoc 1.x has no supported HTTP update endpoint.

        The browser edits through its Socket.IO collaborative-editing
        protocol. ``POST /new/{alias}`` only creates a new alias; it returns
        HTTP 409 when the alias already exists and does not alter that note.
        """
        del note_id, content
        raise HedgeDocError(
            "Updating notes is unsupported: HedgeDoc 1.x has no HTTP update endpoint. "
            "POST /new/{alias} creates notes only and returns HTTP 409 for an existing alias. "
            "See docs/LIMITATIONS.md."
        )

    def note_info(self, note_id: str) -> NoteInfo:
        """Fetch metadata: title, description, viewcount, timestamps."""
        data = self._json(self._get(self._note_path(note_id, "info")), f"get info for '{note_id}'")
        return NoteInfo(
            title=data.get("title", "Untitled"),
            description=data.get("description"),
            viewcount=data.get("viewcount", 0),
            createtime=data.get("createtime", ""),
            updatetime=data.get("updatetime", ""),
        )

    def history(self) -> list[dict]:
        """List the logged-in user's recently viewed/pinned notes. Requires auth."""
        data = self._json(self._get("/history"), "list history")
        if not isinstance(data, dict):
            raise HedgeDocError("Could not list history: unexpected response from /history.")
        return data.get("history", [])

    def status(self) -> dict:
        """Instance-wide stats (note count, online users, etc). No auth needed."""
        return self._json(self._get("/status"), "fetch instance status")

    # -- HTTP plumbing -------------------------------------------------------

    def _note_path(self, note_id: str, action: str) -> str:
        if not note_id.strip():
            raise HedgeDocError("Note ID must not be empty.")
        # Escape everything so an ID like "me?x=" can't reach another endpoint.
        return f"/{quote(note_id, safe='')}/{action}"

    def _get(self, path: str) -> requests.Response:
        return self._send(self._session.get, path)

    def _post(self, path: str, **kwargs: Any) -> requests.Response:
        return self._send(self._session.post, path, **kwargs)

    def _send(self, method: Any, path: str, **kwargs: Any) -> requests.Response:
        try:
            return method(
                f"{self.base_url}{path}", allow_redirects=False, timeout=self.timeout, **kwargs
            )
        except requests.RequestException as e:
            raise HedgeDocError(f"Request to {self.base_url}{path} failed: {e}") from e

    def _is_home(self, location: str) -> bool:
        """True if a redirect target is the instance's home page."""
        target = urlsplit(urljoin(f"{self.base_url}/", location)).path.rstrip("/")
        return target == urlsplit(self.base_url).path.rstrip("/")

    def _check(self, resp: requests.Response, what: str) -> requests.Response:
        """Return ``resp`` if it succeeded; otherwise raise a descriptive error."""
        status = resp.status_code
        if 300 <= status < 400:
            location = resp.headers.get("Location", "")
            if self._is_home(location):
                raise SessionExpiredError(
                    f"Could not {what}: HedgeDoc redirected to its home page, which means "
                    "the session is missing or expired (or anonymous access is disabled)."
                )
            raise HedgeDocError(
                f"Could not {what}: unexpected redirect to {location!r}. Check that "
                "HEDGEDOC_URL matches the instance's configured domain and protocol."
            )
        if status == 403:
            raise HedgeDocError(f"Could not {what}: permission denied (HTTP 403).")
        if status == 404:
            raise HedgeDocError(f"Could not {what}: not found.")
        if status >= 400:
            raise HedgeDocError(f"Could not {what}: HTTP {status}.")
        return resp

    def _json(self, resp: requests.Response, what: str) -> Any:
        self._check(resp, what)
        try:
            return resp.json()
        except ValueError as e:
            content_type = resp.headers.get("Content-Type", "unknown")
            raise HedgeDocError(
                f"Could not {what}: expected JSON but got {content_type}. "
                "Check that HEDGEDOC_URL points at a HedgeDoc 1.x instance."
            ) from e
