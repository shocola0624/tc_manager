from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from nacl.signing import SigningKey

import discord_bot.router as router_module
from discord_bot.router import router as discord_router
from errors import install_exception_handlers
from sheets.repository import SheetRepository

USERS_HEADER = ["discord_user_id", "name", "role", "is_active", "locale", "registered_at"]
ATTENDANCE_HEADER = ["activity_id", "discord_user_id", "status", "updated_at"]
ACTIVITIES_HEADER = [
    "activity_id",
    "starts_at",
    "duration_min",
    "location",
    "title",
    "description",
    "target",
    "owner_id",
    "tasks",
    "note",
    "announce_message_id",
    "is_active",
]
ITEMS_HEADER = ["item_id", "owner_id", "name", "maker", "category", "storage", "note", "is_active"]
ASSIGNMENTS_HEADER = [
    "timestamp",
    "activity_id",
    "item_id",
    "custom_name",
    "assignee_id",
    "action",
    "actor_id",
]


class FakeBotClient:
    def __init__(self) -> None:
        self.dm_calls: list[tuple[str, str]] = []

    async def send_direct_message(self, discord_user_id: str, content: str) -> None:
        self.dm_calls.append((discord_user_id, content))


class _Settings:
    def __init__(
        self,
        public_key_hex: str,
        *,
        application_id: str = "app-1",
        frontend_base_url: str = "http://localhost:5173",
    ) -> None:
        self.discord_public_key = public_key_hex
        self.discord_client_id = application_id
        self.frontend_base_url = frontend_base_url


def _build_app(
    fake_client_factory,
    *,
    users_rows=None,
    attendance_rows=None,
    activities_rows=None,
    items_rows=None,
    assignments_rows=None,
    bot_client=None,
):
    signing_key = SigningKey.generate()
    public_key_hex = signing_key.verify_key.encode().hex()

    users_client = fake_client_factory("users", header=USERS_HEADER, rows=users_rows or [])
    attendance_client = fake_client_factory(
        "attendance", header=ATTENDANCE_HEADER, rows=attendance_rows or []
    )
    activities_client = fake_client_factory(
        "activities", header=ACTIVITIES_HEADER, rows=activities_rows or []
    )
    items_client = fake_client_factory("items", header=ITEMS_HEADER, rows=items_rows or [])
    assignments_client = fake_client_factory(
        "assignments", header=ASSIGNMENTS_HEADER, rows=assignments_rows or []
    )

    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(discord_router)
    app.state.auth_settings = _Settings(public_key_hex)
    app.state.http_client = object()  # send_followup is monkeypatched wherever it matters
    app.state.users_repo = SheetRepository(users_client, "users")
    app.state.attendance_repo = SheetRepository(attendance_client, "attendance")
    app.state.activities_repo = SheetRepository(activities_client, "activities")
    app.state.items_repo = SheetRepository(items_client, "items")
    app.state.assignments_repo = SheetRepository(assignments_client, "assignments")
    app.state.bot_client = bot_client or FakeBotClient()

    return app, signing_key


def _post_signed(client: TestClient, signing_key: SigningKey, payload: dict):
    body = json.dumps(payload).encode()
    timestamp = "1700000000"
    signature = signing_key.sign(timestamp.encode() + body).signature.hex()
    return client.post(
        "/discord/interactions",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature-Ed25519": signature,
            "X-Signature-Timestamp": timestamp,
        },
    )


def test_ping_returns_pong(fake_client_factory):
    app, signing_key = _build_app(fake_client_factory)
    client = TestClient(app)

    response = _post_signed(client, signing_key, {"type": 1})

    assert response.status_code == 200
    assert response.json() == {"type": 1}


def test_invalid_signature_returns_401(fake_client_factory):
    app, _signing_key = _build_app(fake_client_factory)
    client = TestClient(app)

    response = client.post(
        "/discord/interactions",
        content=json.dumps({"type": 1}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Signature-Ed25519": "00" * 64,
            "X-Signature-Timestamp": "1700000000",
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_discord_signature"


def test_missing_signature_headers_returns_401(fake_client_factory):
    app, _signing_key = _build_app(fake_client_factory)
    client = TestClient(app)

    response = client.post("/discord/interactions", json={"type": 1})

    assert response.status_code == 401


def test_button_press_by_registered_user_records_attendance_and_sends_followup(
    fake_client_factory, monkeypatch
):
    app, signing_key = _build_app(
        fake_client_factory,
        users_rows=[["u1", "Alice", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"]],
    )

    sent = []

    async def fake_send_followup(
        http_client, application_id, interaction_token, *, content, ephemeral=True
    ):
        sent.append((application_id, interaction_token, content, ephemeral))

    monkeypatch.setattr(router_module, "send_followup", fake_send_followup)

    client = TestClient(app)
    payload = {
        "type": 3,
        "token": "interaction-token",
        "member": {"user": {"id": "u1"}},
        "data": {"custom_id": "attendance:activity_1:attending"},
    }

    response = _post_signed(client, signing_key, payload)

    assert response.status_code == 200
    assert response.json() == {"type": 6}

    stored = app.state.attendance_repo.read_all()
    assert len(stored) == 1
    assert stored[0]["activity_id"] == "activity_1"
    assert stored[0]["discord_user_id"] == "u1"
    assert stored[0]["status"] == "attending"

    assert len(sent) == 1
    application_id, interaction_token, content, ephemeral = sent[0]
    assert application_id == "app-1"
    assert interaction_token == "interaction-token"
    assert "出席" in content
    assert ephemeral is True


def test_button_press_by_unregistered_user_does_not_write_attendance(
    fake_client_factory, monkeypatch
):
    app, signing_key = _build_app(fake_client_factory)

    sent = []

    async def fake_send_followup(
        http_client, application_id, interaction_token, *, content, ephemeral=True
    ):
        sent.append(content)

    monkeypatch.setattr(router_module, "send_followup", fake_send_followup)

    client = TestClient(app)
    payload = {
        "type": 3,
        "token": "interaction-token",
        "member": {"user": {"id": "unknown-user"}},
        "data": {"custom_id": "attendance:activity_1:attending"},
    }

    response = _post_signed(client, signing_key, payload)

    assert response.status_code == 200
    assert app.state.attendance_repo.read_all() == []
    assert len(sent) == 1
    assert "http://localhost:5173" in sent[0]


def test_button_press_by_inactive_user_does_not_write_attendance(fake_client_factory, monkeypatch):
    app, signing_key = _build_app(
        fake_client_factory,
        users_rows=[["u1", "Alice", "member", "FALSE", "ja", "2026-01-01T00:00:00+09:00"]],
    )

    async def fake_send_followup(*args, **kwargs):
        return None

    monkeypatch.setattr(router_module, "send_followup", fake_send_followup)

    client = TestClient(app)
    payload = {
        "type": 3,
        "token": "interaction-token",
        "member": {"user": {"id": "u1"}},
        "data": {"custom_id": "attendance:activity_1:attending"},
    }

    response = _post_signed(client, signing_key, payload)

    assert response.status_code == 200
    assert app.state.attendance_repo.read_all() == []


def test_button_press_by_unfinished_registration_does_not_write_attendance(
    fake_client_factory, monkeypatch
):
    app, signing_key = _build_app(
        fake_client_factory,
        users_rows=[["u1", "Alice", "member", "TRUE", "ja", ""]],
    )

    async def fake_send_followup(*args, **kwargs):
        return None

    monkeypatch.setattr(router_module, "send_followup", fake_send_followup)

    client = TestClient(app)
    payload = {
        "type": 3,
        "token": "interaction-token",
        "member": {"user": {"id": "u1"}},
        "data": {"custom_id": "attendance:activity_1:attending"},
    }

    response = _post_signed(client, signing_key, payload)

    assert response.status_code == 200
    assert app.state.attendance_repo.read_all() == []


def test_absent_button_with_existing_assignment_sends_dm(fake_client_factory, monkeypatch):
    bot_client = FakeBotClient()
    app, signing_key = _build_app(
        fake_client_factory,
        users_rows=[["u1", "Alice", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"]],
        items_rows=[["i1", "u1", "Kettle", "Fellow", "kettle", "owner", "", "TRUE"]],
        assignments_rows=[["2026-01-01T00:00:00+09:00", "activity_1", "i1", "", "u1", "add", "u1"]],
        bot_client=bot_client,
    )

    async def fake_send_followup(*args, **kwargs):
        return None

    monkeypatch.setattr(router_module, "send_followup", fake_send_followup)

    client = TestClient(app)
    payload = {
        "type": 3,
        "token": "interaction-token",
        "member": {"user": {"id": "u1"}},
        "data": {"custom_id": "attendance:activity_1:absent"},
    }

    response = _post_signed(client, signing_key, payload)

    assert response.status_code == 200
    assert len(bot_client.dm_calls) == 1
    recipient, content = bot_client.dm_calls[0]
    assert recipient == "u1"
    assert "Kettle" in content


def test_absent_button_without_existing_assignment_does_not_send_dm(fake_client_factory, monkeypatch):
    bot_client = FakeBotClient()
    app, signing_key = _build_app(
        fake_client_factory,
        users_rows=[["u1", "Alice", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"]],
        bot_client=bot_client,
    )

    async def fake_send_followup(*args, **kwargs):
        return None

    monkeypatch.setattr(router_module, "send_followup", fake_send_followup)

    client = TestClient(app)
    payload = {
        "type": 3,
        "token": "interaction-token",
        "member": {"user": {"id": "u1"}},
        "data": {"custom_id": "attendance:activity_1:absent"},
    }

    response = _post_signed(client, signing_key, payload)

    assert response.status_code == 200
    assert bot_client.dm_calls == []


def test_unknown_custom_id_is_ignored(fake_client_factory, monkeypatch):
    app, signing_key = _build_app(fake_client_factory)
    calls = []

    async def fake_send_followup(*args, **kwargs):
        calls.append(1)

    monkeypatch.setattr(router_module, "send_followup", fake_send_followup)

    client = TestClient(app)
    payload = {
        "type": 3,
        "token": "interaction-token",
        "member": {"user": {"id": "u1"}},
        "data": {"custom_id": "something-else"},
    }

    response = _post_signed(client, signing_key, payload)

    assert response.status_code == 200
    assert response.json() == {"type": 6}
    assert calls == []
