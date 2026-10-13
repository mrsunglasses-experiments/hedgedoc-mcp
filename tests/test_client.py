"""Tests for hedgedoc_mcp.client against a fake HedgeDoc server (see fake_hedgedoc.py)."""

from __future__ import annotations

import socket

import pytest
from fake_hedgedoc import Note

from hedgedoc_mcp.client import (
    HedgeDocClient,
    HedgeDocError,
    SessionExpiredError,
)

EMAIL, PASSWORD = "user@example.com", "hunter2"


@pytest.fixture
def client(hedgedoc):
    return HedgeDocClient(hedgedoc.url)


@pytest.fixture
def logged_in(client):
    client.login(EMAIL, PASSWORD)
    return client


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        if self._json is None:
            raise ValueError("not JSON")
        return self._json


# -- Construction ---------------------------------------------------------


@pytest.mark.parametrize("cookie_name", ["", "contains space", "connect/sid"])
def test_rejects_invalid_session_cookie_name(cookie_name):
    with pytest.raises(HedgeDocError, match="cookie name"):
        HedgeDocClient("https://md.example.com", session_cookie_name=cookie_name)


@pytest.mark.parametrize("url", ["md.example.com", "localhost:3000", "ftp://md.example.com", ""])
def test_rejects_invalid_base_url(url):
    with pytest.raises(HedgeDocError, match="http"):
        HedgeDocClient(url)


def test_strips_trailing_slash_from_base_url():
    assert HedgeDocClient("https://md.example.com/").base_url == "https://md.example.com"


# -- Auth -----------------------------------------------------------------


def test_login_success(client):
    cookie = client.login(EMAIL, PASSWORD)

    assert cookie.startswith("s:")
    assert client.whoami()["name"] == EMAIL


def test_login_with_wrong_password_fails_even_though_a_cookie_is_set(client):
    with pytest.raises(HedgeDocError, match="Login failed"):
        client.login(EMAIL, "wrong")


def test_login_success_with_custom_session_cookie_name(hedgedoc):
    hedgedoc.session_name = "hedgedoc.sid"
    client = HedgeDocClient(hedgedoc.url, session_cookie_name="hedgedoc.sid")

    assert client.login(EMAIL, PASSWORD).startswith("s:")


def test_login_rejects_wrong_session_cookie_name(hedgedoc, client):
    hedgedoc.session_name = "hedgedoc.sid"

    with pytest.raises(HedgeDocError, match="HEDGEDOC_SESSION_COOKIE_NAME"):
        client.login(EMAIL, PASSWORD)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_manual_cookie_is_sent_to_hosts_with_a_port(hedgedoc, host):
    source = HedgeDocClient(hedgedoc.url)
    source.login(EMAIL, PASSWORD)

    client = HedgeDocClient(f"http://{host}:{hedgedoc.port}")
    client.set_session_cookie(source.get_session_cookie())

    assert client.whoami()["name"] == EMAIL


def test_login_after_expired_manual_cookie_does_not_conflict(hedgedoc):
    client = HedgeDocClient(f"http://localhost:{hedgedoc.port}")
    client.set_session_cookie("s%3Aexpired.sig")
    with pytest.raises(SessionExpiredError):
        client.whoami()

    client.login(EMAIL, PASSWORD)

    assert client.whoami()["name"] == EMAIL


def test_session_cookie_round_trips_without_double_encoding(logged_in):
    encoded = logged_in.get_session_cookie(encoded=True)

    assert encoded.startswith("s%3A")
    assert "%25" not in encoded
    assert logged_in.get_session_cookie(encoded=False) == encoded.replace("%3A", ":")


@pytest.mark.parametrize("value", ["s%3AaBc123", "s:aBc123"])
def test_set_session_cookie_accepts_raw_or_urlencoded(value):
    client = HedgeDocClient("https://md.example.com")
    client.set_session_cookie(value)

    assert client.get_session_cookie(encoded=False) == "s:aBc123"
    assert client.get_session_cookie(encoded=True) == "s%3AaBc123"


def test_set_session_cookie_uses_custom_cookie_name():
    client = HedgeDocClient("https://md.example.com", session_cookie_name="hedgedoc.sid")
    client.set_session_cookie("s%3AaBc123")

    assert client.get_session_cookie(encoded=False) == "s:aBc123"
    assert client._session.cookies.get("connect.sid") is None


def test_whoami_expired_raises(client):
    with pytest.raises(SessionExpiredError):
        client.whoami()


def test_session_lost_on_server_restart_raises_session_expired(hedgedoc, logged_in):
    hedgedoc.restart()

    with pytest.raises(SessionExpiredError):
        logged_in.whoami()


# -- Notes ----------------------------------------------------------------


def test_create_and_read_note(hedgedoc, logged_in):
    result = logged_in.create_note("# Hello")

    assert result.url == f"{hedgedoc.url}/{result.note_id}"
    assert logged_in.read_note(result.note_id) == "# Hello"
    assert hedgedoc.notes[result.note_id].owner == EMAIL


def test_create_note_without_session_raises_session_expired(client):
    with pytest.raises(SessionExpiredError):
        client.create_note("# Hello")


def test_create_note_forbidden_is_detected_when_server_url_differs(hedgedoc, client):
    # HedgeDoc redirects to its configured serverURL, which needn't match HEDGEDOC_URL.
    hedgedoc.server_url = "https://public.example.com"

    with pytest.raises(SessionExpiredError):
        client.create_note("# Hello")


def test_create_note_returns_server_url_when_it_differs(hedgedoc, logged_in):
    hedgedoc.server_url = "https://public.example.com"

    result = logged_in.create_note("# Hello")

    assert result.url == f"https://public.example.com/{result.note_id}"
    assert result.note_id in hedgedoc.notes


def test_create_note_with_alias(hedgedoc, logged_in):
    result = logged_in.create_note("# Hello", alias="my-alias")

    assert result.note_id == "my-alias"
    assert ("POST", "/new/my-alias") in hedgedoc.requests


def test_create_note_escapes_alias(hedgedoc, logged_in):
    result = logged_in.create_note("# Hello", alias="a b/c")

    assert ("POST", "/new/a%20b%2Fc") in hedgedoc.requests
    assert result.note_id == "a b/c"


def test_creating_existing_alias_conflicts_and_preserves_original_content(logged_in):
    logged_in.create_note("# Original", alias="existing-alias")
    with pytest.raises(HedgeDocError, match="already exists"):
        logged_in.create_note("# Replacement", alias="existing-alias")

    assert logged_in.read_note("existing-alias") == "# Original"


def test_create_note_with_alias_without_freeurl_explains_why(hedgedoc, logged_in):
    hedgedoc.allow_freeurl = False

    with pytest.raises(HedgeDocError, match="CMD_ALLOW_FREEURL"):
        logged_in.create_note("# Hello", alias="my-alias")


def test_update_note_is_unsupported_without_making_an_http_request(hedgedoc, client):
    with pytest.raises(HedgeDocError, match="Updating notes is unsupported"):
        client.update_note("my-alias", "# Replacement")

    assert hedgedoc.requests == []


def test_read_public_note_without_session(hedgedoc, client):
    hedgedoc.notes["abc"] = Note("# Content", owner=None)

    assert client.read_note("abc") == "# Content"


def test_read_private_note_without_session_raises_instead_of_returning_home_page(hedgedoc, client):
    hedgedoc.notes["secret"] = Note("# Secret", owner=EMAIL, permission="private")

    with pytest.raises(SessionExpiredError):
        client.read_note("secret")


def test_read_private_note_of_another_user_is_permission_denied(hedgedoc, logged_in):
    hedgedoc.notes["secret"] = Note("# Secret", owner="someone-else", permission="private")

    with pytest.raises(HedgeDocError, match="permission denied"):
        logged_in.read_note("secret")


def test_read_note_not_found_raises(client):
    with pytest.raises(HedgeDocError, match="not found"):
        client.read_note("missing")


def test_read_note_escapes_note_id(hedgedoc, logged_in):
    with pytest.raises(HedgeDocError, match="not found"):
        logged_in.read_note("me?x=")

    assert hedgedoc.requests[-1] == ("GET", "/me%3Fx%3D/download")


def test_read_note_rejects_empty_id(client):
    with pytest.raises(HedgeDocError, match="must not be empty"):
        client.read_note(" ")


def test_note_info_success(hedgedoc, client):
    hedgedoc.notes["abc"] = Note("# My Note", owner=None)

    info = client.note_info("abc")

    assert info.title == "My Note"
    assert info.viewcount == 0
    assert info.createtime == "2026-01-01T00:00:00.000Z"


def test_history_requires_auth(client):
    with pytest.raises(SessionExpiredError):
        client.history()


def test_history_success(logged_in):
    result = logged_in.create_note("# Note 1")

    assert logged_in.history() == [{"id": result.note_id, "text": result.note_id}]


def test_status_no_auth_needed(hedgedoc, client):
    hedgedoc.notes["abc"] = Note("# Content", owner=None)

    assert client.status()["notesCount"] == 1


# -- Transport failures ---------------------------------------------------


def test_network_error_is_wrapped_in_hedgedoc_error():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]  # closed again before the request: nothing listens

    with pytest.raises(HedgeDocError, match="failed"):
        HedgeDocClient(f"http://127.0.0.1:{port}").whoami()


def test_non_json_response_is_wrapped_in_hedgedoc_error(mocker):
    client = HedgeDocClient("https://md.example.com")
    mocker.patch.object(
        client._session,
        "get",
        return_value=_FakeResponse(
            text="<html>proxy page</html>", headers={"Content-Type": "text/html"}
        ),
    )

    with pytest.raises(HedgeDocError, match="expected JSON but got text/html"):
        client.whoami()


def test_redirect_away_from_instance_points_at_hedgedoc_url(mocker):
    client = HedgeDocClient("http://md.example.com")
    mocker.patch.object(
        client._session,
        "get",
        return_value=_FakeResponse(
            status_code=301, headers={"Location": "https://md.example.com/abc/download"}
        ),
    )

    with pytest.raises(HedgeDocError, match="HEDGEDOC_URL") as excinfo:
        client.read_note("abc")
    assert not isinstance(excinfo.value, SessionExpiredError)


def test_server_error_status_is_reported(mocker):
    client = HedgeDocClient("https://md.example.com")
    mocker.patch.object(client._session, "post", return_value=_FakeResponse(status_code=500))

    with pytest.raises(HedgeDocError, match="HTTP 500"):
        client.create_note("# Hello")
