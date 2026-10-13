"""Unit tests for hedgedoc_mcp.auth (Config + build_client fallback logic)."""

from __future__ import annotations

import pytest

from hedgedoc_mcp import auth
from hedgedoc_mcp.auth import Config, ConfigError, build_client
from hedgedoc_mcp.client import SessionExpiredError


def test_config_from_env_requires_url(monkeypatch):
    monkeypatch.delenv("HEDGEDOC_URL", raising=False)
    with pytest.raises(ConfigError, match="HEDGEDOC_URL"):
        Config.from_env()


def test_config_from_env_requires_some_credential(monkeypatch):
    monkeypatch.setenv("HEDGEDOC_URL", "https://md.example.com")
    monkeypatch.delenv("HEDGEDOC_SESSION_COOKIE", raising=False)
    monkeypatch.delenv("HEDGEDOC_EMAIL", raising=False)
    monkeypatch.delenv("HEDGEDOC_PASSWORD", raising=False)
    with pytest.raises(ConfigError, match="No credentials"):
        Config.from_env()


def test_config_from_env_with_cookie(monkeypatch):
    monkeypatch.setenv("HEDGEDOC_URL", "https://md.example.com")
    monkeypatch.setenv("HEDGEDOC_SESSION_COOKIE", "abc123")
    monkeypatch.delenv("HEDGEDOC_EMAIL", raising=False)
    config = Config.from_env()
    assert config.base_url == "https://md.example.com"
    assert config.session_cookie == "abc123"
    assert config.session_cookie_name == "connect.sid"


def test_config_from_env_with_custom_cookie_name(monkeypatch):
    monkeypatch.setenv("HEDGEDOC_URL", "https://md.example.com")
    monkeypatch.setenv("HEDGEDOC_SESSION_COOKIE", "abc123")
    monkeypatch.setenv("HEDGEDOC_SESSION_COOKIE_NAME", "hedgedoc.sid")

    config = Config.from_env()

    assert config.session_cookie_name == "hedgedoc.sid"


def test_config_from_env_rejects_invalid_cookie_name(monkeypatch):
    monkeypatch.setenv("HEDGEDOC_URL", "https://md.example.com")
    monkeypatch.setenv("HEDGEDOC_SESSION_COOKIE", "abc123")
    monkeypatch.setenv("HEDGEDOC_SESSION_COOKIE_NAME", "not valid")

    with pytest.raises(ConfigError, match="HEDGEDOC_SESSION_COOKIE_NAME"):
        Config.from_env()


def test_config_from_env_with_login(monkeypatch):
    monkeypatch.setenv("HEDGEDOC_URL", "https://md.example.com")
    monkeypatch.delenv("HEDGEDOC_SESSION_COOKIE", raising=False)
    monkeypatch.setenv("HEDGEDOC_EMAIL", "a@b.com")
    monkeypatch.setenv("HEDGEDOC_PASSWORD", "secret")
    config = Config.from_env()
    assert config.email == "a@b.com"


def test_build_client_uses_valid_cookie(mocker):
    config = Config(
        base_url="https://md.example.com", session_cookie="valid", email=None, password=None
    )
    mocker.patch("hedgedoc_mcp.auth.HedgeDocClient.whoami", return_value={"status": "ok"})
    login_spy = mocker.patch("hedgedoc_mcp.auth.HedgeDocClient.login")

    build_client(config)
    login_spy.assert_not_called()


def test_build_client_passes_custom_cookie_name(mocker):
    config = Config(
        base_url="https://md.example.com",
        session_cookie="valid",
        email=None,
        password=None,
        session_cookie_name="hedgedoc.sid",
    )
    client_class = mocker.patch("hedgedoc_mcp.auth.HedgeDocClient")
    client_class.return_value.whoami.return_value = {"status": "ok"}

    build_client(config)

    client_class.assert_called_once_with(
        "https://md.example.com", session_cookie_name="hedgedoc.sid"
    )
    client_class.return_value.set_session_cookie.assert_called_once_with("valid")


def test_build_client_relogs_in_after_custom_cookie_expires(mocker):
    config = Config(
        base_url="https://md.example.com",
        session_cookie="expired",
        email="a@b.com",
        password="secret",
        session_cookie_name="hedgedoc.sid",
    )
    client_class = mocker.patch("hedgedoc_mcp.auth.HedgeDocClient")
    client_class.return_value.whoami.side_effect = SessionExpiredError("expired")

    build_client(config)

    client_class.assert_called_once_with(
        "https://md.example.com", session_cookie_name="hedgedoc.sid"
    )
    client_class.return_value.set_session_cookie.assert_called_once_with("expired")
    client_class.return_value.login.assert_called_once_with("a@b.com", "secret")


def test_build_client_falls_back_to_login_on_expired_cookie(mocker):
    config = Config(
        base_url="https://md.example.com",
        session_cookie="expired",
        email="a@b.com",
        password="secret",
    )
    mocker.patch(
        "hedgedoc_mcp.auth.HedgeDocClient.whoami", side_effect=SessionExpiredError("expired")
    )
    login_spy = mocker.patch("hedgedoc_mcp.auth.HedgeDocClient.login")

    build_client(config)
    login_spy.assert_called_once_with("a@b.com", "secret")


def test_build_client_raises_when_cookie_expired_and_no_login(mocker):
    config = Config(
        base_url="https://md.example.com", session_cookie="expired", email=None, password=None
    )
    mocker.patch(
        "hedgedoc_mcp.auth.HedgeDocClient.whoami", side_effect=SessionExpiredError("expired")
    )

    with pytest.raises(ConfigError, match="expired/invalid"):
        build_client(config)


def test_build_client_uses_login_when_no_cookie(mocker):
    config = Config(
        base_url="https://md.example.com", session_cookie=None, email="a@b.com", password="secret"
    )
    login_spy = mocker.patch("hedgedoc_mcp.auth.HedgeDocClient.login")

    build_client(config)
    login_spy.assert_called_once_with("a@b.com", "secret")


def test_cli_login_writes_custom_cookie_name_to_env_file(monkeypatch, mocker, tmp_path):
    client = mocker.Mock()
    client.get_session_cookie.return_value = "s%3Acookie"
    mocker.patch("hedgedoc_mcp.auth.HedgeDocClient", return_value=client)
    env_file = tmp_path / ".env"
    monkeypatch.setattr(
        "sys.argv",
        [
            "hedgedoc-mcp-login",
            "--url",
            "https://md.example.com",
            "--email",
            "user@example.com",
            "--password",
            "password",
            "--session-cookie-name",
            "hedgedoc.sid",
            "--write-env",
            str(env_file),
        ],
    )

    auth.cli_login()

    assert env_file.read_text() == (
        "HEDGEDOC_SESSION_COOKIE=s%3Acookie\nHEDGEDOC_SESSION_COOKIE_NAME=hedgedoc.sid\n"
    )
