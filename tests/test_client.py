"""Unit tests for hedgedoc_mcp.client — mocked HTTP, no real HedgeDoc needed."""

from __future__ import annotations

import pytest
import requests

from hedgedoc_mcp.client import (
    HedgeDocClient,
    HedgeDocError,
    SessionExpiredError,
)


@pytest.fixture
def client():
    return HedgeDocClient("https://md.example.com")


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def test_login_success(client, mocker):
    mock_post = mocker.patch.object(client._session, "post")
    mock_post.return_value = _FakeResponse(status_code=302)
    client._session.cookies.set("connect.sid", "abc123", domain="md.example.com")

    cookie = client.login("user@example.com", "hunter2")
    assert cookie == "abc123"
    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert kwargs["data"] == {"email": "user@example.com", "password": "hunter2"}


def test_login_success_with_custom_session_cookie_name(mocker):
    client = HedgeDocClient("https://md.example.com", session_cookie_name="hedgedoc.sid")
    mocker.patch.object(client._session, "post", return_value=_FakeResponse(status_code=302))
    client._session.cookies.set("hedgedoc.sid", "abc123", domain="md.example.com")

    assert client.login("user@example.com", "hunter2") == "abc123"


def test_login_rejects_wrong_session_cookie_name(client, mocker):
    mocker.patch.object(client._session, "post", return_value=_FakeResponse(status_code=302))
    client._session.cookies.set("hedgedoc.sid", "abc123", domain="md.example.com")

    with pytest.raises(HedgeDocError, match="Login failed"):
        client.login("user@example.com", "hunter2")


def test_login_failure_raises(client, mocker):
    mocker.patch.object(client._session, "post", return_value=_FakeResponse(status_code=401))
    with pytest.raises(HedgeDocError, match="Login failed"):
        client.login("user@example.com", "wrong")


def test_set_session_cookie_decodes_urlencoded(client):
    client.set_session_cookie("s%3AaBc123")
    assert client.get_session_cookie(encoded=False) == "s:aBc123"


def test_set_session_cookie_accepts_raw(client):
    client.set_session_cookie("plain-value-no-percent")
    assert client.get_session_cookie(encoded=False) == "plain-value-no-percent"


def test_set_session_cookie_uses_custom_cookie_name():
    client = HedgeDocClient("https://md.example.com", session_cookie_name="hedgedoc.sid")
    client.set_session_cookie("s%3AaBc123")

    assert client.get_session_cookie(encoded=False) == "s:aBc123"
    assert client._session.cookies.get("connect.sid") is None


@pytest.mark.parametrize("cookie_name", ["", "contains space", "connect/sid"])
def test_rejects_invalid_session_cookie_name(cookie_name):
    with pytest.raises(HedgeDocError, match="cookie name"):
        HedgeDocClient("https://md.example.com", session_cookie_name=cookie_name)


def test_whoami_success(client, mocker):
    mocker.patch.object(
        client._session,
        "get",
        return_value=_FakeResponse(json_data={"status": "ok", "name": "kanishk"}),
    )
    data = client.whoami()
    assert data["name"] == "kanishk"


def test_whoami_expired_raises(client, mocker):
    mocker.patch.object(
        client._session, "get", return_value=_FakeResponse(json_data={"status": "forbidden"})
    )
    with pytest.raises(SessionExpiredError):
        client.whoami()


def test_create_note_success(client, mocker):
    mocker.patch.object(
        client._session,
        "post",
        return_value=_FakeResponse(
            status_code=302, headers={"Location": "https://md.example.com/abc123XYZ"}
        ),
    )
    result = client.create_note("# Hello")
    assert result.note_id == "abc123XYZ"
    assert result.url == "https://md.example.com/abc123XYZ"


def test_create_note_relative_location(client, mocker):
    mocker.patch.object(
        client._session,
        "post",
        return_value=_FakeResponse(status_code=302, headers={"Location": "/relativeId"}),
    )
    result = client.create_note("# Hello")
    assert result.note_id == "relativeId"
    assert result.url == "https://md.example.com/relativeId"


def test_create_note_redirect_to_home_means_expired(client, mocker):
    mocker.patch.object(
        client._session,
        "post",
        return_value=_FakeResponse(status_code=302, headers={"Location": "/"}),
    )
    with pytest.raises(SessionExpiredError):
        client.create_note("# Hello")


def test_create_note_non_redirect_raises(client, mocker):
    mocker.patch.object(client._session, "post", return_value=_FakeResponse(status_code=500))
    with pytest.raises(HedgeDocError, match="Unexpected status"):
        client.create_note("# Hello")


def test_create_note_with_alias_uses_alias_path(client, mocker):
    mock_post = mocker.patch.object(
        client._session,
        "post",
        return_value=_FakeResponse(
            status_code=302, headers={"Location": "https://md.example.com/my-alias"}
        ),
    )
    client.create_note("# Hello", alias="my-alias")
    args, _ = mock_post.call_args
    assert args[0] == "https://md.example.com/new/my-alias"


def test_creating_existing_alias_conflicts_and_preserves_original_content(client, mocker):
    notes = {}

    def post(url, data, **_kwargs):
        alias = url.rsplit("/", 1)[-1]
        if alias in notes:
            return _FakeResponse(status_code=409)
        notes[alias] = data.decode("utf-8")
        return _FakeResponse(status_code=302, headers={"Location": f"/{alias}"})

    def get(url, **_kwargs):
        note_id = url.removesuffix("/download").rsplit("/", 1)[-1]
        return _FakeResponse(status_code=200, text=notes[note_id])

    mocker.patch.object(client._session, "post", side_effect=post)
    mocker.patch.object(client._session, "get", side_effect=get)

    client.create_note("# Original", alias="existing-alias")
    with pytest.raises(HedgeDocError, match="Unexpected status 409"):
        client.create_note("# Replacement", alias="existing-alias")

    assert client.read_note("existing-alias") == "# Original"


def test_update_note_is_unsupported_without_making_an_http_request(client, mocker):
    post = mocker.patch.object(client._session, "post")

    with pytest.raises(HedgeDocError, match="Updating notes is unsupported"):
        client.update_note("my-alias", "# Replacement")

    post.assert_not_called()


def test_read_note_success(client, mocker):
    mocker.patch.object(
        client._session, "get", return_value=_FakeResponse(status_code=200, text="# Content")
    )
    assert client.read_note("abc") == "# Content"


def test_read_note_not_found_raises(client, mocker):
    mocker.patch.object(client._session, "get", return_value=_FakeResponse(status_code=404))
    with pytest.raises(HedgeDocError, match="not found"):
        client.read_note("missing")


def test_note_info_success(client, mocker):
    mocker.patch.object(
        client._session,
        "get",
        return_value=_FakeResponse(
            status_code=200,
            json_data={
                "title": "My Note",
                "description": "desc",
                "viewcount": 5,
                "createtime": "2026-01-01T00:00:00Z",
                "updatetime": "2026-01-02T00:00:00Z",
            },
        ),
    )
    info = client.note_info("abc")
    assert info.title == "My Note"
    assert info.viewcount == 5


def test_history_requires_auth(client, mocker):
    mocker.patch.object(
        client._session, "get", return_value=_FakeResponse(json_data={"status": "forbidden"})
    )
    with pytest.raises(SessionExpiredError):
        client.history()


def test_history_success(client, mocker):
    mocker.patch.object(
        client._session,
        "get",
        return_value=_FakeResponse(json_data={"history": [{"id": "abc", "text": "Note 1"}]}),
    )
    history = client.history()
    assert len(history) == 1
    assert history[0]["text"] == "Note 1"


def test_status_no_auth_needed(client, mocker):
    mocker.patch.object(
        client._session,
        "get",
        return_value=_FakeResponse(json_data={"notesCount": 42, "onlineUsers": 3}),
    )
    data = client.status()
    assert data["notesCount"] == 42
