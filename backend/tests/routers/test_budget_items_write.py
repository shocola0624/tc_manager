import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_current_user
from auth.session import SessionSigner
from errors import install_exception_handlers
from repositories import get_budget_items_repository
from routers.budget_items import router as budget_items_router
from sheets.repository import SheetRepository
from sheets.schemas import Role, User

BUDGET_ITEMS_HEADER = ["budget_item_id", "activity_id", "label", "amount_jpy", "is_active"]


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


def _build_client(repo, user: User) -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    app.state.signer = SessionSigner("test-secret")
    app.include_router(budget_items_router)
    app.dependency_overrides[get_budget_items_repository] = lambda: repo
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


@pytest.fixture
def budget_items_repo(fake_client_factory) -> SheetRepository:
    sheet = fake_client_factory("budget_items", header=BUDGET_ITEMS_HEADER, rows=[])
    return SheetRepository(sheet, "budget_items")


def _create_payload(**overrides):
    payload = {"activity_id": "activity_1", "label": "豆", "amount_jpy": 1000}
    payload.update(overrides)
    return payload


def test_officer_can_create_budget_item(budget_items_repo):
    client = _build_client(budget_items_repo, _user(role=Role.OFFICER))

    response = client.post("/api/budget-items", json=_create_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["activity_id"] == "activity_1"
    assert body["label"] == "豆"
    assert body["amount_jpy"] == 1000
    assert body["is_active"] is True
    assert body["budget_item_id"]

    stored = budget_items_repo.read_all()
    assert len(stored) == 1
    assert stored[0]["is_active"] == "TRUE"


def test_admin_can_create_budget_item(budget_items_repo):
    client = _build_client(budget_items_repo, _user(discord_user_id="a1", role=Role.ADMIN))

    response = client.post("/api/budget-items", json=_create_payload())

    assert response.status_code == 200


def test_member_cannot_create_budget_item(budget_items_repo):
    client = _build_client(budget_items_repo, _user(role=Role.MEMBER))

    response = client.post("/api/budget-items", json=_create_payload())

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_role"


def test_multiple_budget_items_can_be_added_for_the_same_activity(budget_items_repo):
    client = _build_client(budget_items_repo, _user(role=Role.OFFICER))

    client.post("/api/budget-items", json=_create_payload(label="豆", amount_jpy=1000))
    client.post("/api/budget-items", json=_create_payload(label="フィルター", amount_jpy=500))

    stored = budget_items_repo.read_all()
    assert len(stored) == 2
    assert {row["label"] for row in stored} == {"豆", "フィルター"}


def test_delete_sets_is_active_false_without_removing_the_row(budget_items_repo):
    client = _build_client(budget_items_repo, _user(role=Role.OFFICER))
    budget_item_id = client.post("/api/budget-items", json=_create_payload()).json()["budget_item_id"]

    response = client.delete(f"/api/budget-items/{budget_item_id}")

    assert response.status_code == 200
    assert response.json()["is_active"] is False

    stored = budget_items_repo.read_all()
    assert len(stored) == 1
    assert stored[0]["budget_item_id"] == budget_item_id
    assert stored[0]["is_active"] == "FALSE"


def test_member_cannot_delete_budget_item(budget_items_repo):
    officer_client = _build_client(budget_items_repo, _user(discord_user_id="o1", role=Role.OFFICER))
    budget_item_id = officer_client.post("/api/budget-items", json=_create_payload()).json()["budget_item_id"]

    member_client = _build_client(budget_items_repo, _user(discord_user_id="m1", role=Role.MEMBER))
    response = member_client.delete(f"/api/budget-items/{budget_item_id}")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_role"


def test_delete_unknown_budget_item_returns_404(budget_items_repo):
    client = _build_client(budget_items_repo, _user(role=Role.ADMIN))

    response = client.delete("/api/budget-items/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "budget_item_not_found"


def test_list_budget_items_returns_created_rows(budget_items_repo):
    client = _build_client(budget_items_repo, _user(role=Role.OFFICER))
    client.post("/api/budget-items", json=_create_payload(label="豆", amount_jpy=1000))

    response = client.get("/api/budget-items")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["label"] == "豆"
