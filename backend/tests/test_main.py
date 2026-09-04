from __future__ import annotations

import importlib
import json

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient


@pytest.fixture
def dummy_service_account_file(tmp_path) -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    data = {
        "type": "service_account",
        "project_id": "dummy",
        "private_key_id": "dummy",
        "private_key": pem,
        "client_email": "dummy@dummy.iam.gserviceaccount.com",
        "client_id": "dummy",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    path = tmp_path / "sa.json"
    path.write_text(json.dumps(data))
    return str(path)


@pytest.fixture
def app_module(monkeypatch, dummy_service_account_file):
    env = {
        "SPREADSHEET_ID": "dummy-sheet",
        "GOOGLE_SERVICE_ACCOUNT_FILE": dummy_service_account_file,
        "DISCORD_CLIENT_ID": "dummy-client",
        "DISCORD_CLIENT_SECRET": "dummy-secret",
        "DISCORD_REDIRECT_URI": "http://localhost:8000/auth/discord/callback",
        "DISCORD_BOT_TOKEN": "dummy-bot-token",
        "DISCORD_GUILD_ID": "dummy-guild",
        "DISCORD_ADMIN_ROLE_ID": "dummy-admin-role",
        "DISCORD_OFFICER_ROLE_ID": "dummy-officer-role",
        "DISCORD_PUBLIC_KEY": "ab" * 32,
        "DISCORD_ANNOUNCE_CHANNEL_ID": "dummy-channel",
        "DISCORD_CONFIRM_ANNOUNCE_CHANNEL_ID": "dummy-confirm-channel",
        "DISCORD_LOG_CHANNEL_ID": "dummy-log-channel",
        "SESSION_SECRET_KEY": "dummy-session-secret",
        "FRONTEND_BASE_URL": "http://localhost:5173",
        "COOKIE_SECURE": "false",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    import main as main_module

    importlib.reload(main_module)
    return main_module


def test_app_boots_and_registers_all_routers(app_module):
    with TestClient(app_module.app) as client:
        response = client.get("/openapi.json")
        paths = response.json()["paths"]

    for path in (
        "/auth/discord/login",
        "/auth/discord/callback",
        "/auth/register",
        "/auth/logout",
        "/auth/me",
        "/discord/interactions",
        "/api/users",
        "/api/items",
        "/api/activities",
        "/api/attendance",
        "/api/assignments",
    ):
        assert path in paths


def test_login_redirects_with_identify_scope_only(app_module):
    with TestClient(app_module.app) as client:
        response = client.get("/auth/discord/login", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://discord.com/oauth2/authorize")
    assert "scope=identify" in location
    assert "client_secret" not in location


def test_protected_endpoints_require_authentication(app_module):
    with TestClient(app_module.app) as client:
        response = client.get("/api/items")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
