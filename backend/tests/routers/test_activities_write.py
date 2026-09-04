from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_auth_settings, get_bot_client, get_current_user
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


class FakeBotClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def create_message(self, channel_id: str, payload: dict) -> dict:
        self.calls.append((channel_id, payload))
        return {"id": "msg-1"}


def _build_client(repo, user: User) -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    app.state.signer = SessionSigner("test-secret")
    app.include_router(activities_router)
    app.dependency_overrides[get_activities_repository] = lambda: repo
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_bot_client] = lambda: FakeBotClient()
    app.dependency_overrides[get_auth_settings] = lambda: SimpleNamespace(
        discord_log_channel_id="log-channel-1"
    )
    return TestClient(app)


@pytest.fixture
def activities_repo(fake_client_factory) -> SheetRepository:
    sheet = fake_client_factory("activities", header=ACTIVITIES_HEADER, rows=[])
    return SheetRepository(sheet, "activities")


def _create_payload(**overrides):
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
    payload.update(overrides)
    return payload


def test_officer_can_create_activity(activities_repo):
    client = _build_client(activities_repo, _user(role=Role.OFFICER))

    response = client.post("/api/activities", json=_create_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "定例会"
    assert body["is_active"] is True
    assert body["announce_message_id"] is None
    assert body["activity_id"]

    stored = activities_repo.read_all()
    assert len(stored) == 1
    assert stored[0]["is_active"] == "TRUE"


def test_admin_can_create_activity(activities_repo):
    client = _build_client(activities_repo, _user(discord_user_id="a1", role=Role.ADMIN))

    response = client.post("/api/activities", json=_create_payload())

    assert response.status_code == 200


def test_member_cannot_create_activity(activities_repo):
    client = _build_client(activities_repo, _user(discord_user_id="m1", role=Role.MEMBER))

    response = client.post("/api/activities", json=_create_payload())

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_role"


def test_officer_can_update_activity_preserving_unset_fields(activities_repo):
    client = _build_client(activities_repo, _user(role=Role.OFFICER))
    activity_id = client.post("/api/activities", json=_create_payload()).json()["activity_id"]

    response = client.patch(f"/api/activities/{activity_id}", json={"title": "臨時会", "tasks": "鍵を借りる"})

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "臨時会"
    assert body["tasks"] == "鍵を借りる"
    assert body["location"] == "部室"  # 未指定フィールドは維持される


def test_member_cannot_update_activity(activities_repo):
    officer_client = _build_client(activities_repo, _user(role=Role.OFFICER))
    activity_id = officer_client.post("/api/activities", json=_create_payload()).json()["activity_id"]

    member_client = _build_client(activities_repo, _user(discord_user_id="m1", role=Role.MEMBER))
    response = member_client.patch(f"/api/activities/{activity_id}", json={"title": "hijacked"})

    assert response.status_code == 403


def test_update_unknown_activity_returns_404(activities_repo):
    client = _build_client(activities_repo, _user(role=Role.ADMIN))

    response = client.patch("/api/activities/does-not-exist", json={"title": "x"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "activity_not_found"


def test_delete_sets_is_active_false_without_removing_the_row(activities_repo):
    client = _build_client(activities_repo, _user(role=Role.OFFICER))
    activity_id = client.post("/api/activities", json=_create_payload()).json()["activity_id"]

    response = client.delete(f"/api/activities/{activity_id}")

    assert response.status_code == 200
    assert response.json()["is_active"] is False

    stored = activities_repo.read_all()
    assert len(stored) == 1
    assert stored[0]["activity_id"] == activity_id
    assert stored[0]["is_active"] == "FALSE"


def test_member_cannot_delete_activity(activities_repo):
    officer_client = _build_client(activities_repo, _user(role=Role.OFFICER))
    activity_id = officer_client.post("/api/activities", json=_create_payload()).json()["activity_id"]

    member_client = _build_client(activities_repo, _user(discord_user_id="m1", role=Role.MEMBER))
    response = member_client.delete(f"/api/activities/{activity_id}")

    assert response.status_code == 403
