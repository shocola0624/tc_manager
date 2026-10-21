from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_auth_settings, get_bot_client, get_current_user
from auth.session import SessionSigner
from errors import install_exception_handlers
from repositories import get_task_assignees_repository, get_tasks_repository, get_users_repository
from routers.tasks import router as tasks_router
from sheets.repository import SheetRepository
from sheets.schemas import Role, User

TASKS_HEADER = [
    "task_id",
    "title",
    "description",
    "due_at",
    "status",
    "visibility",
    "related_activity_id",
    "reminder_offsets",
    "google_event_id",
    "is_active",
    "created_by",
    "created_at",
    "updated_at",
]
TASK_ASSIGNEES_HEADER = ["task_id", "member_id", "label"]
USERS_HEADER = ["discord_user_id", "name", "role", "is_active", "locale", "registered_at", "grade"]


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


class FakeBotClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def create_message(self, channel_id: str, payload: dict) -> dict:
        self.calls.append((channel_id, payload))
        return {"id": "msg-1"}


def _build_client(tasks_repo, assignees_repo, users_repo, user: User) -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(tasks_router)
    app.dependency_overrides[get_tasks_repository] = lambda: tasks_repo
    app.dependency_overrides[get_task_assignees_repository] = lambda: assignees_repo
    app.dependency_overrides[get_users_repository] = lambda: users_repo
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_bot_client] = lambda: FakeBotClient()
    app.dependency_overrides[get_auth_settings] = lambda: SimpleNamespace(
        discord_log_channel_id="log-channel-1"
    )
    return TestClient(app)


@pytest.fixture
def tasks_repo(fake_client_factory) -> SheetRepository:
    return SheetRepository(fake_client_factory("tasks", header=TASKS_HEADER, rows=[]), "tasks")


@pytest.fixture
def assignees_repo(fake_client_factory) -> SheetRepository:
    return SheetRepository(
        fake_client_factory("task_assignees", header=TASK_ASSIGNEES_HEADER, rows=[]),
        "task_assignees",
    )


@pytest.fixture
def users_repo(fake_client_factory) -> SheetRepository:
    repo = SheetRepository(fake_client_factory("users", header=USERS_HEADER, rows=[]), "users")
    for discord_user_id, role in [("u1", "member"), ("u2", "officer"), ("u3", "admin")]:
        repo.append(
            {
                "discord_user_id": discord_user_id,
                "name": discord_user_id,
                "role": role,
                "is_active": "TRUE",
                "locale": "ja",
                "registered_at": "2026-01-01T00:00:00+09:00",
                "grade": "",
            }
        )
    return repo


def _create_payload(**overrides):
    payload = {
        "title": "資料作成",
        "description": "",
        "due_at": "2026-10-20T18:00:00+09:00",
        "visibility": "member",
        "related_activity_id": None,
        "reminder_offsets": "-7d,-1d",
        "assignees": [],
    }
    payload.update(overrides)
    return payload


# --- 作成: visibility による可否 -------------------------------------------------


def test_member_can_create_member_visibility_task(tasks_repo, assignees_repo, users_repo):
    client = _build_client(tasks_repo, assignees_repo, users_repo, _user(role=Role.MEMBER))

    response = client.post("/api/tasks", json=_create_payload(visibility="member"))

    assert response.status_code == 200
    body = response.json()
    assert body["visibility"] == "member"
    assert body["status"] == "todo"
    assert body["task_id"]
    assert tasks_repo.read_all()[0]["task_id"] == body["task_id"]


@pytest.mark.parametrize("visibility", ["officer", "admin"])
def test_member_cannot_create_task_above_own_tier(tasks_repo, assignees_repo, users_repo, visibility):
    client = _build_client(tasks_repo, assignees_repo, users_repo, _user(role=Role.MEMBER))

    response = client.post("/api/tasks", json=_create_payload(visibility=visibility))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_task_visibility"
    assert tasks_repo.read_all() == []


def test_officer_can_create_officer_and_member_but_not_admin(tasks_repo, assignees_repo, users_repo):
    client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u2", role=Role.OFFICER))

    assert client.post("/api/tasks", json=_create_payload(visibility="officer")).status_code == 200
    assert client.post("/api/tasks", json=_create_payload(visibility="member")).status_code == 200
    response = client.post("/api/tasks", json=_create_payload(visibility="admin"))
    assert response.status_code == 403


def test_admin_can_create_task_at_any_visibility(tasks_repo, assignees_repo, users_repo):
    client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u3", role=Role.ADMIN))

    for visibility in ["member", "officer", "admin"]:
        response = client.post("/api/tasks", json=_create_payload(visibility=visibility))
        assert response.status_code == 200


# --- 作成: 担当者の可視性チェック -------------------------------------------------


def test_cannot_assign_member_to_officer_visibility_task(tasks_repo, assignees_repo, users_repo):
    client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u2", role=Role.OFFICER))

    response = client.post(
        "/api/tasks", json=_create_payload(visibility="officer", assignees=[{"member_id": "u1"}])
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_task_assignee"
    assert tasks_repo.read_all() == []


def test_can_assign_multiple_officers_to_officer_visibility_task(tasks_repo, assignees_repo, users_repo):
    users_repo.append(
        {
            "discord_user_id": "u4",
            "name": "u4",
            "role": "officer",
            "is_active": "TRUE",
            "locale": "ja",
            "registered_at": "2026-01-01T00:00:00+09:00",
            "grade": "",
        }
    )
    client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u2", role=Role.OFFICER))

    response = client.post(
        "/api/tasks",
        json=_create_payload(visibility="officer", assignees=[{"member_id": "u2"}, {"member_id": "u4"}]),
    )

    assert response.status_code == 200
    assert sorted(a["member_id"] for a in response.json()["assignees"]) == ["u2", "u4"]
    assert len(assignees_repo.read_all()) == 2


def test_create_rejects_unknown_assignee(tasks_repo, assignees_repo, users_repo):
    client = _build_client(tasks_repo, assignees_repo, users_repo, _user(role=Role.MEMBER))

    response = client.post(
        "/api/tasks", json=_create_payload(visibility="member", assignees=[{"member_id": "ghost"}])
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "assignee_not_found"


def test_can_assign_a_free_text_department_label(tasks_repo, assignees_repo, users_repo):
    """部門名などの自由記述の担当は、ロールチェックの対象外で誰でも指定できる。"""
    client = _build_client(tasks_repo, assignees_repo, users_repo, _user(role=Role.MEMBER))

    response = client.post(
        "/api/tasks", json=_create_payload(visibility="member", assignees=[{"label": "総務部門"}])
    )

    assert response.status_code == 200
    assert response.json()["assignees"] == [{"member_id": None, "label": "総務部門"}]
    assert assignees_repo.read_all() == [{"task_id": response.json()["task_id"], "member_id": "", "label": "総務部門"}]


def test_department_label_bypasses_visibility_check(tasks_repo, assignees_repo, users_repo):
    """officer 可視性のタスクでも、部門名は(実在する人物ではないため)ロール不足で弾かれない。"""
    client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u2", role=Role.OFFICER))

    response = client.post(
        "/api/tasks", json=_create_payload(visibility="officer", assignees=[{"label": "総務部門"}])
    )

    assert response.status_code == 200


def test_create_rejects_assignee_with_both_member_id_and_label(tasks_repo, assignees_repo, users_repo):
    client = _build_client(tasks_repo, assignees_repo, users_repo, _user(role=Role.MEMBER))

    response = client.post(
        "/api/tasks",
        json=_create_payload(visibility="member", assignees=[{"member_id": "u1", "label": "総務部門"}]),
    )

    assert response.status_code == 422


# --- 一覧: visibility によるフィルタリング -----------------------------------------


def test_list_tasks_filters_by_visibility(tasks_repo, assignees_repo, users_repo):
    admin_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u3", role=Role.ADMIN))
    for visibility in ["member", "officer", "admin"]:
        admin_client.post("/api/tasks", json=_create_payload(visibility=visibility, title=visibility))

    member_titles = {t["title"] for t in admin_client.get("/api/tasks").json()["data"]}
    assert member_titles == {"member", "officer", "admin"}

    member_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(role=Role.MEMBER))
    titles = {t["title"] for t in member_client.get("/api/tasks").json()["data"]}
    assert titles == {"member"}

    officer_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u2", role=Role.OFFICER))
    titles = {t["title"] for t in officer_client.get("/api/tasks").json()["data"]}
    assert titles == {"member", "officer"}


# --- 更新: 編集・ステータス変更・担当者差し替え -------------------------------------


def test_officer_can_change_status_of_officer_task(tasks_repo, assignees_repo, users_repo):
    officer_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u2", role=Role.OFFICER))
    task_id = officer_client.post("/api/tasks", json=_create_payload(visibility="officer")).json()["task_id"]

    response = officer_client.patch(f"/api/tasks/{task_id}", json={"status": "doing"})

    assert response.status_code == 200
    assert response.json()["status"] == "doing"


def test_member_cannot_modify_officer_task(tasks_repo, assignees_repo, users_repo):
    officer_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u2", role=Role.OFFICER))
    task_id = officer_client.post("/api/tasks", json=_create_payload(visibility="officer")).json()["task_id"]

    member_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(role=Role.MEMBER))
    response = member_client.patch(f"/api/tasks/{task_id}", json={"status": "doing"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_task_edit"


def test_update_replaces_assignees(tasks_repo, assignees_repo, users_repo):
    admin_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u3", role=Role.ADMIN))
    task_id = admin_client.post(
        "/api/tasks", json=_create_payload(visibility="member", assignees=[{"member_id": "u1"}])
    ).json()["task_id"]

    response = admin_client.patch(f"/api/tasks/{task_id}", json={"assignees": []})

    assert response.status_code == 200
    assert response.json()["assignees"] == []
    assert assignees_repo.read_all() == []


def test_update_can_switch_assignee_to_a_department_label(tasks_repo, assignees_repo, users_repo):
    admin_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u3", role=Role.ADMIN))
    task_id = admin_client.post(
        "/api/tasks", json=_create_payload(visibility="member", assignees=[{"member_id": "u1"}])
    ).json()["task_id"]

    response = admin_client.patch(f"/api/tasks/{task_id}", json={"assignees": [{"label": "総務部門"}]})

    assert response.status_code == 200
    assert response.json()["assignees"] == [{"member_id": None, "label": "総務部門"}]


def test_update_does_not_touch_assignees_when_field_omitted(tasks_repo, assignees_repo, users_repo):
    admin_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u3", role=Role.ADMIN))
    task_id = admin_client.post(
        "/api/tasks", json=_create_payload(visibility="member", assignees=[{"member_id": "u1"}])
    ).json()["task_id"]

    response = admin_client.patch(f"/api/tasks/{task_id}", json={"title": "更新後タイトル"})

    assert response.status_code == 200
    assert response.json()["assignees"] == [{"member_id": "u1", "label": None}]


def test_cannot_raise_visibility_above_own_tier_when_editing(tasks_repo, assignees_repo, users_repo):
    officer_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u2", role=Role.OFFICER))
    task_id = officer_client.post("/api/tasks", json=_create_payload(visibility="officer")).json()["task_id"]

    response = officer_client.patch(f"/api/tasks/{task_id}", json={"visibility": "admin"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_task_visibility"


# --- 削除(論理削除) ----------------------------------------------------------------


def test_delete_soft_deletes_task(tasks_repo, assignees_repo, users_repo):
    admin_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u3", role=Role.ADMIN))
    task_id = admin_client.post("/api/tasks", json=_create_payload(visibility="member")).json()["task_id"]

    response = admin_client.delete(f"/api/tasks/{task_id}")

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert tasks_repo.read_all()[0]["is_active"] == "FALSE"


def test_member_cannot_delete_officer_task(tasks_repo, assignees_repo, users_repo):
    officer_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u2", role=Role.OFFICER))
    task_id = officer_client.post("/api/tasks", json=_create_payload(visibility="officer")).json()["task_id"]

    member_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(role=Role.MEMBER))
    response = member_client.delete(f"/api/tasks/{task_id}")

    assert response.status_code == 403


def test_task_not_found_returns_404(tasks_repo, assignees_repo, users_repo):
    client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u3", role=Role.ADMIN))

    response = client.patch("/api/tasks/does-not-exist", json={"status": "doing"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "task_not_found"


# --- 不正な行の可視性(閲覧制限の抜け道にしない) -----------------------------------


def test_invalid_row_with_readable_visibility_is_hidden_from_lower_tier(tasks_repo, assignees_repo, users_repo):
    # status が不正な行(= Task としてパースできない)。visibility=officer は読み取れる。
    tasks_repo.append(
        {
            "task_id": "t_broken",
            "title": "broken",
            "description": "",
            "due_at": "2026-10-20T18:00:00+09:00",
            "status": "not-a-status",
            "visibility": "officer",
            "related_activity_id": "",
            "reminder_offsets": "",
            "google_event_id": "",
            "is_active": "TRUE",
            "created_by": "u2",
            "created_at": "2026-01-01T00:00:00+09:00",
            "updated_at": "2026-01-01T00:00:00+09:00",
        }
    )

    member_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(role=Role.MEMBER))
    assert member_client.get("/api/tasks").json()["invalid_rows"] == []

    officer_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u2", role=Role.OFFICER))
    assert len(officer_client.get("/api/tasks").json()["invalid_rows"]) == 1


def test_invalid_row_with_unreadable_visibility_is_admin_only(tasks_repo, assignees_repo, users_repo):
    tasks_repo.append(
        {
            "task_id": "t_broken",
            "title": "broken",
            "description": "",
            "due_at": "2026-10-20T18:00:00+09:00",
            "status": "todo",
            "visibility": "not-a-role",
            "related_activity_id": "",
            "reminder_offsets": "",
            "google_event_id": "",
            "is_active": "TRUE",
            "created_by": "u2",
            "created_at": "2026-01-01T00:00:00+09:00",
            "updated_at": "2026-01-01T00:00:00+09:00",
        }
    )

    officer_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u2", role=Role.OFFICER))
    assert officer_client.get("/api/tasks").json()["invalid_rows"] == []

    admin_client = _build_client(tasks_repo, assignees_repo, users_repo, _user(discord_user_id="u3", role=Role.ADMIN))
    assert len(admin_client.get("/api/tasks").json()["invalid_rows"]) == 1


def test_list_requires_authentication():
    app = FastAPI()
    install_exception_handlers(app)
    app.state.signer = SessionSigner("test-secret")
    app.include_router(tasks_router)
    client = TestClient(app)

    response = client.get("/api/tasks")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
