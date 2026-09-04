from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_auth_settings, get_bot_client, get_current_user
from auth.session import SessionSigner
from errors import install_exception_handlers
from repositories import get_items_repository
from routers.items import router as items_router
from sheets.repository import SheetRepository
from sheets.schemas import CIRCLE_OWNER_ID, Role, User

ITEMS_HEADER = [
    "item_id",
    "owner_id",
    "name",
    "maker",
    "category",
    "storage",
    "note",
    "is_active",
]


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


def _build_client(repo, user: User) -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    app.state.signer = SessionSigner("test-secret")
    app.include_router(items_router)
    app.dependency_overrides[get_items_repository] = lambda: repo
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_bot_client] = lambda: FakeBotClient()
    app.dependency_overrides[get_auth_settings] = lambda: SimpleNamespace(
        discord_log_channel_id="log-channel-1"
    )
    return TestClient(app)


@pytest.fixture
def items_repo(fake_client_factory) -> SheetRepository:
    sheet = fake_client_factory("items", header=ITEMS_HEADER, rows=[])
    return SheetRepository(sheet, "items")


def _create_payload(**overrides):
    payload = {
        "name": "V60",
        "maker": "Hario",
        "category": "dripper",
        "storage": "owner",
        "note": "",
    }
    payload.update(overrides)
    return payload


def test_create_item_defaults_owner_to_self(items_repo):
    client = _build_client(items_repo, _user())

    response = client.post("/api/items", json=_create_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["owner_id"] == "u1"
    assert body["is_active"] is True
    assert body["item_id"]

    stored = items_repo.read_all()
    assert len(stored) == 1
    assert stored[0]["item_id"] == body["item_id"]
    assert stored[0]["is_active"] == "TRUE"


def test_create_item_item_id_is_not_settable_by_client(items_repo):
    client = _build_client(items_repo, _user())

    response = client.post("/api/items", json=_create_payload())

    body = response.json()
    # クライアントから item_id を渡す余地がそもそも無い(ItemCreateRequest に項目が無い)
    assert body["item_id"] != ""


def test_member_cannot_create_circle_owned_item(items_repo):
    client = _build_client(items_repo, _user(role=Role.MEMBER))

    response = client.post("/api/items", json=_create_payload(owner_id=CIRCLE_OWNER_ID))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "owner_not_allowed"


def test_officer_can_create_circle_owned_item(items_repo):
    client = _build_client(items_repo, _user(role=Role.OFFICER))

    response = client.post("/api/items", json=_create_payload(owner_id=CIRCLE_OWNER_ID))

    assert response.status_code == 200
    assert response.json()["owner_id"] == CIRCLE_OWNER_ID


def test_cannot_create_item_owned_by_another_specific_user(items_repo):
    client = _build_client(items_repo, _user(role=Role.ADMIN))

    response = client.post("/api/items", json=_create_payload(owner_id="someone-else"))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "owner_not_allowed"


def test_owner_can_update_own_item(items_repo):
    client = _build_client(items_repo, _user())
    item_id = client.post("/api/items", json=_create_payload()).json()["item_id"]

    response = client.patch(f"/api/items/{item_id}", json={"name": "V60 02", "note": "新品"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "V60 02"
    assert body["note"] == "新品"
    assert body["maker"] == "Hario"  # 未指定フィールドは維持される


def test_member_cannot_update_others_item(items_repo):
    owner_client = _build_client(items_repo, _user(discord_user_id="u1"))
    item_id = owner_client.post("/api/items", json=_create_payload()).json()["item_id"]

    other_client = _build_client(items_repo, _user(discord_user_id="u2", role=Role.MEMBER))
    response = other_client.patch(f"/api/items/{item_id}", json={"name": "hijacked"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_item_edit"


def test_admin_can_update_others_item(items_repo):
    owner_client = _build_client(items_repo, _user(discord_user_id="u1"))
    item_id = owner_client.post("/api/items", json=_create_payload()).json()["item_id"]

    admin_client = _build_client(items_repo, _user(discord_user_id="admin1", role=Role.ADMIN))
    response = admin_client.patch(f"/api/items/{item_id}", json={"name": "fixed by admin"})

    assert response.status_code == 200
    assert response.json()["name"] == "fixed by admin"


def test_officer_can_update_circle_item_but_member_cannot(items_repo):
    officer_client = _build_client(items_repo, _user(discord_user_id="o1", role=Role.OFFICER))
    item_id = officer_client.post(
        "/api/items", json=_create_payload(owner_id=CIRCLE_OWNER_ID)
    ).json()["item_id"]

    response = officer_client.patch(f"/api/items/{item_id}", json={"name": "circle item"})
    assert response.status_code == 200

    member_client = _build_client(items_repo, _user(discord_user_id="m1", role=Role.MEMBER))
    response = member_client.patch(f"/api/items/{item_id}", json={"name": "nope"})
    assert response.status_code == 403


def test_update_unknown_item_returns_404(items_repo):
    client = _build_client(items_repo, _user(role=Role.ADMIN))

    response = client.patch("/api/items/does-not-exist", json={"name": "x"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "item_not_found"


def test_delete_sets_is_active_false_without_removing_the_row(items_repo):
    client = _build_client(items_repo, _user())
    item_id = client.post("/api/items", json=_create_payload()).json()["item_id"]

    response = client.delete(f"/api/items/{item_id}")

    assert response.status_code == 200
    assert response.json()["is_active"] is False

    stored = items_repo.read_all()
    assert len(stored) == 1
    assert stored[0]["item_id"] == item_id
    assert stored[0]["is_active"] == "FALSE"


def test_member_cannot_delete_others_item(items_repo):
    owner_client = _build_client(items_repo, _user(discord_user_id="u1"))
    item_id = owner_client.post("/api/items", json=_create_payload()).json()["item_id"]

    other_client = _build_client(items_repo, _user(discord_user_id="u2", role=Role.MEMBER))
    response = other_client.delete(f"/api/items/{item_id}")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden_item_edit"
