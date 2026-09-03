from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_auth_settings, get_bot_client, get_current_user
from auth.discord_client import DiscordOAuthError
from auth.session import SessionSigner
from errors import install_exception_handlers
from repositories import get_activities_repository
from routers.activities import router as activities_router
from sheets.repository import SheetRepository
from sheets.schemas import Role, User

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


class FakeBotClient:
    def __init__(self, *, fail: bool = False, message_id: str = "msg-1") -> None:
        self.fail = fail
        self.message_id = message_id
        self.calls: list[tuple[str, dict]] = []

    async def create_message(self, channel_id: str, payload: dict) -> dict:
        self.calls.append((channel_id, payload))
        if self.fail:
            raise DiscordOAuthError("boom")
        return {"id": self.message_id}


def _user(**overrides) -> User:
    defaults = dict(
        discord_user_id="o1",
        name="Officer",
        role=Role.OFFICER,
        is_active=True,
        locale="ja",
        registered_at="2026-01-01T00:00:00+09:00",
    )
    defaults.update(overrides)
    return User(**defaults)


def _build_client(repo, user: User, bot_client: FakeBotClient) -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    app.state.signer = SessionSigner("test-secret")
    app.include_router(activities_router)
    app.dependency_overrides[get_activities_repository] = lambda: repo
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_bot_client] = lambda: bot_client
    app.dependency_overrides[get_auth_settings] = lambda: SimpleNamespace(
        discord_announce_channel_id="channel-1"
    )
    return TestClient(app)


@pytest.fixture
def activities_repo(fake_client_factory) -> SheetRepository:
    sheet = fake_client_factory("activities", header=ACTIVITIES_HEADER, rows=[])
    return SheetRepository(sheet, "activities")


def _create_activity(repo) -> str:
    client = _build_client(repo, _user(), FakeBotClient())
    payload = {
        "starts_at": "2026-09-10T14:00:00+09:00",
        "duration_min": 120,
        "location": "部室",
        "title": "定例会",
        "description": "",
        "target": "",
        "owner_id": "o1",
        "tasks": "",
        "note": "",
    }
    return client.post("/api/activities", json=payload).json()["activity_id"]


def test_officer_can_announce_activity(activities_repo):
    activity_id = _create_activity(activities_repo)
    bot_client = FakeBotClient(message_id="msg-42")
    client = _build_client(activities_repo, _user(), bot_client)

    response = client.post(f"/api/activities/{activity_id}/announce")

    assert response.status_code == 200
    assert response.json()["announce_message_id"] == "msg-42"

    assert len(bot_client.calls) == 1
    channel_id, payload = bot_client.calls[0]
    assert channel_id == "channel-1"
    assert "定例会" in payload["content"]
    buttons = payload["components"][0]["components"]
    assert [b["custom_id"] for b in buttons] == [
        f"attendance:{activity_id}:attending",
        f"attendance:{activity_id}:absent",
        f"attendance:{activity_id}:undecided",
    ]

    stored = activities_repo.read_all()
    assert stored[0]["announce_message_id"] == "msg-42"


def test_member_cannot_announce_activity(activities_repo):
    activity_id = _create_activity(activities_repo)
    client = _build_client(
        activities_repo, _user(discord_user_id="m1", role=Role.MEMBER), FakeBotClient()
    )

    response = client.post(f"/api/activities/{activity_id}/announce")

    assert response.status_code == 403


def test_announce_unknown_activity_returns_404(activities_repo):
    client = _build_client(activities_repo, _user(), FakeBotClient())

    response = client.post("/api/activities/does-not-exist/announce")

    assert response.status_code == 404


def test_announce_failure_is_reported_as_502(activities_repo):
    activity_id = _create_activity(activities_repo)
    client = _build_client(activities_repo, _user(), FakeBotClient(fail=True))

    response = client.post(f"/api/activities/{activity_id}/announce")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "discord_announce_failed"

    stored = activities_repo.read_all()
    assert stored[0]["announce_message_id"] == ""


def test_reannounce_overwrites_announce_message_id(activities_repo):
    activity_id = _create_activity(activities_repo)
    client = _build_client(activities_repo, _user(), FakeBotClient(message_id="msg-1"))
    client.post(f"/api/activities/{activity_id}/announce")

    client2 = _build_client(activities_repo, _user(), FakeBotClient(message_id="msg-2"))
    response = client2.post(f"/api/activities/{activity_id}/announce")

    assert response.json()["announce_message_id"] == "msg-2"
