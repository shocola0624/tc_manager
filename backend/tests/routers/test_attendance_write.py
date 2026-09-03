import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_bot_client, get_current_user
from auth.session import SessionSigner
from errors import install_exception_handlers
from repositories import (
    get_activities_repository,
    get_assignments_repository,
    get_attendance_repository,
    get_items_repository,
)
from routers.attendance import router as attendance_router
from sheets.repository import AppendOnlyRepository, SheetRepository
from sheets.schemas import Role, User

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


def _user(**overrides) -> User:
    defaults = dict(
        discord_user_id="u1",
        name="Alice",
        role=Role.MEMBER,
        is_active=True,
        locale="ja",
        registered_at="2026-01-01T00:00:00+09:00",
    )
    defaults.update(overrides)
    return User(**defaults)


def _build_client(
    *,
    attendance_repo,
    user: User,
    activities_repo=None,
    items_repo=None,
    assignments_repo=None,
    bot_client=None,
    fake_client_factory=None,
) -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    app.state.signer = SessionSigner("test-secret")
    app.include_router(attendance_router)
    app.dependency_overrides[get_attendance_repository] = lambda: attendance_repo
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_activities_repository] = lambda: (
        activities_repo or SheetRepository(fake_client_factory("activities", header=ACTIVITIES_HEADER, rows=[]), "activities")
    )
    app.dependency_overrides[get_items_repository] = lambda: (
        items_repo or SheetRepository(fake_client_factory("items", header=ITEMS_HEADER, rows=[]), "items")
    )
    app.dependency_overrides[get_assignments_repository] = lambda: (
        assignments_repo
        or AppendOnlyRepository(fake_client_factory("assignments", header=ASSIGNMENTS_HEADER, rows=[]), "assignments")
    )
    app.dependency_overrides[get_bot_client] = lambda: bot_client or FakeBotClient()
    return TestClient(app)


@pytest.fixture
def attendance_repo(fake_client_factory) -> SheetRepository:
    sheet = fake_client_factory("attendance", header=ATTENDANCE_HEADER, rows=[])
    return SheetRepository(sheet, "attendance")


def test_user_can_set_own_attendance(attendance_repo, fake_client_factory):
    client = _build_client(attendance_repo=attendance_repo, user=_user(), fake_client_factory=fake_client_factory)

    response = client.put("/api/attendance/activity_1", json={"status": "attending"})

    assert response.status_code == 200
    body = response.json()
    assert body["activity_id"] == "activity_1"
    assert body["discord_user_id"] == "u1"
    assert body["status"] == "attending"

    stored = attendance_repo.read_all()
    assert len(stored) == 1
    assert stored[0]["status"] == "attending"


def test_setting_attendance_again_updates_the_same_row(attendance_repo, fake_client_factory):
    client = _build_client(attendance_repo=attendance_repo, user=_user(), fake_client_factory=fake_client_factory)
    client.put("/api/attendance/activity_1", json={"status": "undecided"})

    response = client.put("/api/attendance/activity_1", json={"status": "absent"})

    assert response.status_code == 200
    stored = attendance_repo.read_all()
    assert len(stored) == 1
    assert stored[0]["status"] == "absent"


def test_cannot_write_other_users_attendance(attendance_repo, fake_client_factory):
    """discord_user_id はリクエストボディで指定できず、常にログイン中の本人になる。"""
    client = _build_client(
        attendance_repo=attendance_repo, user=_user(discord_user_id="u1"), fake_client_factory=fake_client_factory
    )
    client.put("/api/attendance/activity_1", json={"status": "attending"})

    other_client = _build_client(
        attendance_repo=attendance_repo, user=_user(discord_user_id="u2"), fake_client_factory=fake_client_factory
    )
    other_client.put("/api/attendance/activity_1", json={"status": "absent"})

    stored = {row["discord_user_id"]: row["status"] for row in attendance_repo.read_all()}
    assert stored == {"u1": "attending", "u2": "absent"}


def test_invalid_status_is_rejected(attendance_repo, fake_client_factory):
    client = _build_client(attendance_repo=attendance_repo, user=_user(), fake_client_factory=fake_client_factory)

    response = client.put("/api/attendance/activity_1", json={"status": "maybe"})

    assert response.status_code == 422


def test_absent_with_no_existing_assignment_does_not_send_dm(attendance_repo, fake_client_factory):
    bot_client = FakeBotClient()
    client = _build_client(
        attendance_repo=attendance_repo, user=_user(), bot_client=bot_client, fake_client_factory=fake_client_factory
    )

    response = client.put("/api/attendance/activity_1", json={"status": "absent"})

    assert response.status_code == 200
    assert bot_client.dm_calls == []


def test_absent_with_existing_assignment_sends_dm_to_self(attendance_repo, fake_client_factory):
    assignments_repo = AppendOnlyRepository(
        fake_client_factory(
            "assignments",
            header=ASSIGNMENTS_HEADER,
            rows=[["2026-01-01T00:00:00+09:00", "activity_1", "i1", "", "u1", "add", "u1"]],
        ),
        "assignments",
    )
    items_repo = SheetRepository(
        fake_client_factory(
            "items", header=ITEMS_HEADER, rows=[["i1", "u1", "Kettle", "Fellow", "kettle", "owner", "", "TRUE"]]
        ),
        "items",
    )
    bot_client = FakeBotClient()
    client = _build_client(
        attendance_repo=attendance_repo,
        user=_user(discord_user_id="u1"),
        assignments_repo=assignments_repo,
        items_repo=items_repo,
        bot_client=bot_client,
        fake_client_factory=fake_client_factory,
    )

    response = client.put("/api/attendance/activity_1", json={"status": "absent"})

    assert response.status_code == 200
    assert len(bot_client.dm_calls) == 1
    recipient, content = bot_client.dm_calls[0]
    assert recipient == "u1"
    assert "Kettle" in content


def test_attending_does_not_trigger_dm_even_with_existing_assignment(attendance_repo, fake_client_factory):
    assignments_repo = AppendOnlyRepository(
        fake_client_factory(
            "assignments",
            header=ASSIGNMENTS_HEADER,
            rows=[["2026-01-01T00:00:00+09:00", "activity_1", "i1", "", "u1", "add", "u1"]],
        ),
        "assignments",
    )
    bot_client = FakeBotClient()
    client = _build_client(
        attendance_repo=attendance_repo,
        user=_user(discord_user_id="u1"),
        assignments_repo=assignments_repo,
        bot_client=bot_client,
        fake_client_factory=fake_client_factory,
    )

    response = client.put("/api/attendance/activity_1", json={"status": "attending"})

    assert response.status_code == 200
    assert bot_client.dm_calls == []
