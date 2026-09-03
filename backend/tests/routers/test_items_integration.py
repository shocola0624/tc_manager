from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_current_user
from auth.session import SessionSigner
from errors import install_exception_handlers
from repositories import get_items_repository
from routers.items import router as items_router
from sheets.repository import SheetRepository

ITEMS_HEADER = ["item_id", "owner_id", "name", "maker", "category", "storage", "note"]


def _build_client(repo, active_user) -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    app.include_router(items_router)
    app.dependency_overrides[get_items_repository] = lambda: repo
    app.dependency_overrides[get_current_user] = lambda: active_user
    return TestClient(app)


def test_list_items_parses_valid_rows_and_flags_unknown_category(fake_client_factory, active_user):
    sheet = fake_client_factory(
        "items",
        header=ITEMS_HEADER,
        rows=[
            ["i1", "CIRCLE", "Hario V60", "Hario", "dripper", "clubroom", ""],
            ["i2", "u1", "Broken Grinder", "Acme", "not_a_category", "owner", ""],
        ],
    )
    repo = SheetRepository(sheet, "items")
    client = _build_client(repo, active_user)

    response = client.get("/api/items")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["item_id"] == "i1"
    assert body["data"][0]["category"] == "dripper"
    assert len(body["invalid_rows"]) == 1
    assert body["invalid_rows"][0]["row_number"] == 3


def test_list_items_requires_login(fake_client_factory):
    sheet = fake_client_factory("items", header=ITEMS_HEADER, rows=[])
    repo = SheetRepository(sheet, "items")
    app = FastAPI()
    install_exception_handlers(app)
    app.state.signer = SessionSigner("test-secret")
    app.include_router(items_router)
    app.dependency_overrides[get_items_repository] = lambda: repo
    client = TestClient(app)

    response = client.get("/api/items")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
