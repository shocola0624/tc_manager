from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_auth_settings, get_bot_client, get_current_user
from errors import install_exception_handlers
from repositories import (
    get_activities_repository,
    get_assignments_repository,
    get_attendance_repository,
    get_items_repository,
    get_users_repository,
)
from routers.assignments import router as assignments_router
from sheets.repository import AppendOnlyRepository, SheetRepository
from sheets.schemas import Role, User

ASSIGNMENTS_HEADER = [
    "timestamp",
    "activity_id",
    "item_id",
    "custom_name",
    "assignee_id",
    "action",
    "actor_id",
]
ITEMS_HEADER = ["item_id", "owner_id", "name", "maker", "category", "storage", "note", "is_active"]
ATTENDANCE_HEADER = ["activity_id", "discord_user_id", "status", "updated_at"]
USERS_HEADER = ["discord_user_id", "name", "role", "is_active", "locale", "registered_at"]
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
    def __init__(self) -> None:
        self.dm_calls: list[tuple[str, str]] = []
        self.log_calls: list[tuple[str, dict]] = []

    async def send_direct_message(self, discord_user_id: str, content: str) -> None:
        self.dm_calls.append((discord_user_id, content))

    async def create_message(self, channel_id: str, payload: dict) -> dict:
        self.log_calls.append((channel_id, payload))
        return {"id": "msg-1"}


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
    assignments_repo=None,
    items_repo=None,
    attendance_repo=None,
    users_repo=None,
    activities_repo=None,
    bot_client=None,
    active_user=None,
    fake_client_factory=None,
) -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(assignments_router)
    app.dependency_overrides[get_assignments_repository] = lambda: assignments_repo
    app.dependency_overrides[get_items_repository] = lambda: items_repo
    app.dependency_overrides[get_attendance_repository] = lambda: attendance_repo
    app.dependency_overrides[get_users_repository] = lambda: users_repo
    app.dependency_overrides[get_activities_repository] = lambda: (
        activities_repo
        or SheetRepository(fake_client_factory("activities", header=ACTIVITIES_HEADER, rows=[]), "activities")
    )
    app.dependency_overrides[get_bot_client] = lambda: bot_client or FakeBotClient()
    app.dependency_overrides[get_current_user] = lambda: active_user
    app.dependency_overrides[get_auth_settings] = lambda: SimpleNamespace(
        discord_log_channel_id="log-channel-1"
    )
    return TestClient(app)


def _repos(fake_client_factory, *, items_rows=None, attendance_rows=None, users_rows=None, assignments_rows=None):
    items = SheetRepository(
        fake_client_factory("items", header=ITEMS_HEADER, rows=items_rows or []), "items"
    )
    attendance = SheetRepository(
        fake_client_factory("attendance", header=ATTENDANCE_HEADER, rows=attendance_rows or []),
        "attendance",
    )
    users = SheetRepository(
        fake_client_factory("users", header=USERS_HEADER, rows=users_rows or []), "users"
    )
    assignments = AppendOnlyRepository(
        fake_client_factory("assignments", header=ASSIGNMENTS_HEADER, rows=assignments_rows or []),
        "assignments",
    )
    return items, attendance, users, assignments


def test_list_assignment_log_returns_raw_entries_in_sheet_order(fake_client_factory, active_user):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        assignments_rows=[
            ["2026-01-01T10:00:00+09:00", "a1", "i1", "", "", "add", "u1"],
            # item_id と custom_name が両方指定されている不正行
            ["2026-01-01T11:00:00+09:00", "a1", "i1", "borrowed", "", "add", "u1"],
        ],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=active_user,
    )

    response = client.get("/api/assignments")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["item_id"] == "i1"
    assert len(body["invalid_rows"]) == 1
    assert body["invalid_rows"][0]["row_number"] == 3


# ---- candidates ----


def test_clubroom_item_is_always_in_candidates(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "CIRCLE", "V60", "Hario", "dripper", "clubroom", "", "TRUE"]],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(),
    )

    response = client.get("/api/assignments/candidates", params={"activity_id": "a1"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["requires_assignee"] is False
    assert body[0]["default_assignee_id"] is None


def test_owner_item_candidate_only_when_owner_attending_by_default(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "owner1", "Kettle", "Fellow", "kettle", "owner", "", "TRUE"]],
        attendance_rows=[["a1", "owner1", "absent", "2026-01-01T00:00:00+09:00"]],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(),
    )

    response = client.get("/api/assignments/candidates", params={"activity_id": "a1"})
    assert response.json() == []

    extended_response = client.get(
        "/api/assignments/candidates", params={"activity_id": "a1", "extended": "true"}
    )
    body = extended_response.json()
    assert len(body) == 1
    assert body[0]["requires_assignee"] is True
    assert body[0]["default_assignee_id"] is None


def test_owner_item_candidate_with_default_assignee_when_attending(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "owner1", "Kettle", "Fellow", "kettle", "owner", "", "TRUE"]],
        attendance_rows=[["a1", "owner1", "attending", "2026-01-01T00:00:00+09:00"]],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(),
    )

    response = client.get("/api/assignments/candidates", params={"activity_id": "a1"})

    body = response.json()
    assert len(body) == 1
    assert body[0]["requires_assignee"] is False
    assert body[0]["default_assignee_id"] == "owner1"


def test_inactive_item_is_not_a_candidate(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "CIRCLE", "Old scale", "Acaia", "scale", "clubroom", "", "FALSE"]],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(),
    )

    response = client.get("/api/assignments/candidates", params={"activity_id": "a1"})

    assert response.json() == []


# ---- add ----


def test_add_clubroom_item_needs_no_assignee(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "CIRCLE", "V60", "Hario", "dripper", "clubroom", "", "TRUE"]],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(),
    )

    response = client.post("/api/assignments", json={"activity_id": "a1", "item_id": "i1"})

    assert response.status_code == 200
    body = response.json()
    assert body["assignee_id"] is None
    assert body["action"] == "add"


def test_add_owner_item_forces_owner_as_assignee_ignoring_client_value(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "owner1", "Kettle", "Fellow", "kettle", "owner", "", "TRUE"]],
        attendance_rows=[["a1", "owner1", "attending", "2026-01-01T00:00:00+09:00"]],
        users_rows=[
            ["u1", "Alice", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"],
            ["owner1", "Owner", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"],
        ],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(discord_user_id="u1"),
    )

    response = client.post(
        "/api/assignments", json={"activity_id": "a1", "item_id": "i1", "assignee_id": "u1"}
    )

    assert response.status_code == 200
    assert response.json()["assignee_id"] == "owner1"


def test_add_clubroom_item_rejects_explicit_assignee(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "CIRCLE", "V60", "Hario", "dripper", "clubroom", "", "TRUE"]],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(),
    )

    response = client.post(
        "/api/assignments", json={"activity_id": "a1", "item_id": "i1", "assignee_id": "u1"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "assignee_not_allowed"


def test_add_other_item_requires_assignee(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "CIRCLE", "Borrowed scale", "Acaia", "scale", "other", "", "TRUE"]],
        users_rows=[["u2", "Bob", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"]],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(discord_user_id="u2"),
    )

    missing = client.post("/api/assignments", json={"activity_id": "a1", "item_id": "i1"})
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "assignee_required"

    ok = client.post(
        "/api/assignments", json={"activity_id": "a1", "item_id": "i1", "assignee_id": "u2"}
    )
    assert ok.status_code == 200
    assert ok.json()["assignee_id"] == "u2"


def test_add_ad_hoc_item_allows_unassigned(fake_client_factory):
    items, attendance, users, assignments = _repos(fake_client_factory)
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(),
    )

    response = client.post(
        "/api/assignments", json={"activity_id": "a1", "custom_name": "借り物のドリッパー"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] is None
    assert body["custom_name"] == "借り物のドリッパー"
    assert body["assignee_id"] is None


def test_add_unknown_item_returns_404(fake_client_factory):
    items, attendance, users, assignments = _repos(fake_client_factory)
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(),
    )

    response = client.post("/api/assignments", json={"activity_id": "a1", "item_id": "does-not-exist"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "item_not_found"


def test_add_unknown_assignee_is_rejected(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "CIRCLE", "Borrowed scale", "Acaia", "scale", "other", "", "TRUE"]],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(),
    )

    response = client.post(
        "/api/assignments", json={"activity_id": "a1", "item_id": "i1", "assignee_id": "ghost"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "assignee_not_found"


def test_member_can_assign_themselves_to_an_ad_hoc_item(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        users_rows=[["u1", "Alice", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"]],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(discord_user_id="u1", role=Role.MEMBER),
    )

    response = client.post(
        "/api/assignments",
        json={"activity_id": "a1", "custom_name": "借り物のミル", "assignee_id": "u1"},
    )

    assert response.status_code == 200


def test_member_cannot_assign_someone_else_to_an_ad_hoc_item(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        users_rows=[["u2", "Bob", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"]],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(discord_user_id="u1", role=Role.MEMBER),
    )

    response = client.post(
        "/api/assignments",
        json={"activity_id": "a1", "custom_name": "借り物のミル", "assignee_id": "u2"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_assignee"


def test_officer_can_assign_someone_else_to_an_ad_hoc_item(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        users_rows=[["u2", "Bob", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"]],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(discord_user_id="o1", role=Role.OFFICER),
    )

    response = client.post(
        "/api/assignments",
        json={"activity_id": "a1", "custom_name": "借り物のミル", "assignee_id": "u2"},
    )

    assert response.status_code == 200
    assert response.json()["assignee_id"] == "u2"


def test_add_requires_exactly_one_of_item_id_or_custom_name(fake_client_factory):
    items, attendance, users, assignments = _repos(fake_client_factory)
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(),
    )

    neither = client.post("/api/assignments", json={"activity_id": "a1"})
    assert neither.status_code == 422

    both = client.post(
        "/api/assignments", json={"activity_id": "a1", "item_id": "i1", "custom_name": "x"}
    )
    assert both.status_code == 422


# ---- remove & folding (no read-modify-write) ----


def test_add_then_remove_disappears_from_current(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "CIRCLE", "V60", "Hario", "dripper", "clubroom", "", "TRUE"]],
    )
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(),
    )

    client.post("/api/assignments", json={"activity_id": "a1", "item_id": "i1"})
    current_after_add = client.get("/api/assignments/current").json()
    assert len(current_after_add) == 1

    remove_response = client.post("/api/assignments/remove", json={"activity_id": "a1", "item_id": "i1"})
    assert remove_response.status_code == 200
    assert remove_response.json()["action"] == "remove"

    current_after_remove = client.get("/api/assignments/current").json()
    assert current_after_remove == []


def test_remove_does_not_require_being_the_assignee(fake_client_factory):
    """解除は担当者に関わらず全 is_active ユーザーが行える(CLAUDE.md §6)。"""
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "owner1", "Kettle", "Fellow", "kettle", "owner", "", "TRUE"]],
        attendance_rows=[["a1", "owner1", "attending", "2026-01-01T00:00:00+09:00"]],
        users_rows=[["u2", "Bob", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"]],
    )
    owner_client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(discord_user_id="owner1"),
    )
    owner_client.post("/api/assignments", json={"activity_id": "a1", "item_id": "i1"})

    other_member_client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(discord_user_id="u2", role=Role.MEMBER),
    )
    response = other_member_client.post(
        "/api/assignments/remove", json={"activity_id": "a1", "item_id": "i1"}
    )

    assert response.status_code == 200
    assert other_member_client.get("/api/assignments/current").json() == []


def test_concurrent_adds_are_both_preserved_as_separate_log_rows(fake_client_factory):
    """assignments への書き込みは append のみで read-modify-write をしない(CLAUDE.md §4)。
    「同時に2人が別の担当を選ぶ」操作をしても両方のログ行が残ることを確認する。"""
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "CIRCLE", "Borrowed scale", "Acaia", "scale", "other", "", "TRUE"]],
        users_rows=[
            ["u1", "Alice", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"],
            ["u2", "Bob", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"],
        ],
    )
    client1 = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(discord_user_id="u1"),
    )
    client2 = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        fake_client_factory=fake_client_factory,
        active_user=_user(discord_user_id="u2"),
    )

    client1.post("/api/assignments", json={"activity_id": "a1", "item_id": "i1", "assignee_id": "u1"})
    client2.post("/api/assignments", json={"activity_id": "a1", "item_id": "i1", "assignee_id": "u2"})

    raw_rows = assignments.read_all()
    assert len(raw_rows) == 2

    current = client1.get("/api/assignments/current").json()
    assert len(current) == 1
    assert current[0]["assignee_id"] == "u2"  # 後勝ち(timestamp 昇順で畳み込む)


# ---- DM notification when adding an absent owner's item (extended mode) ----


def test_adding_absent_owners_item_sends_dm_to_owner(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "owner1", "Kettle", "Fellow", "kettle", "owner", "", "TRUE"]],
        attendance_rows=[["a1", "owner1", "absent", "2026-01-01T00:00:00+09:00"]],
        users_rows=[
            ["owner1", "Owner", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"],
            ["u2", "Bob", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"],
        ],
    )
    bot_client = FakeBotClient()
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        bot_client=bot_client,
        fake_client_factory=fake_client_factory,
        active_user=_user(discord_user_id="u2"),
    )

    response = client.post(
        "/api/assignments", json={"activity_id": "a1", "item_id": "i1", "assignee_id": "u2"}
    )

    assert response.status_code == 200
    assert len(bot_client.dm_calls) == 1
    recipient, content = bot_client.dm_calls[0]
    assert recipient == "owner1"
    assert "Kettle" in content


def test_adding_attending_owners_item_does_not_send_dm(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "owner1", "Kettle", "Fellow", "kettle", "owner", "", "TRUE"]],
        attendance_rows=[["a1", "owner1", "attending", "2026-01-01T00:00:00+09:00"]],
        users_rows=[["owner1", "Owner", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"]],
    )
    bot_client = FakeBotClient()
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        bot_client=bot_client,
        fake_client_factory=fake_client_factory,
        active_user=_user(discord_user_id="owner1"),
    )

    response = client.post("/api/assignments", json={"activity_id": "a1", "item_id": "i1"})

    assert response.status_code == 200
    assert bot_client.dm_calls == []


def test_adding_clubroom_item_does_not_send_dm(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "CIRCLE", "V60", "Hario", "dripper", "clubroom", "", "TRUE"]],
    )
    bot_client = FakeBotClient()
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        bot_client=bot_client,
        fake_client_factory=fake_client_factory,
        active_user=_user(),
    )

    response = client.post("/api/assignments", json={"activity_id": "a1", "item_id": "i1"})

    assert response.status_code == 200
    assert bot_client.dm_calls == []


def test_adding_other_storage_item_does_not_send_dm(fake_client_factory):
    items, attendance, users, assignments = _repos(
        fake_client_factory,
        items_rows=[["i1", "CIRCLE", "Borrowed scale", "Acaia", "scale", "other", "", "TRUE"]],
        users_rows=[["u2", "Bob", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"]],
    )
    bot_client = FakeBotClient()
    client = _build_client(
        assignments_repo=assignments, items_repo=items, attendance_repo=attendance, users_repo=users,
        bot_client=bot_client,
        fake_client_factory=fake_client_factory,
        active_user=_user(discord_user_id="u2"),
    )

    response = client.post(
        "/api/assignments", json={"activity_id": "a1", "item_id": "i1", "assignee_id": "u2"}
    )

    assert response.status_code == 200
    assert bot_client.dm_calls == []
