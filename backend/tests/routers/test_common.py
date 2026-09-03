from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from auth.session import SessionSigner
from errors import install_exception_handlers
from routers._common import make_list_router
from sheets.repository import SheetRepository


class Widget(BaseModel):
    widget_id: str = Field(min_length=1)
    name: str


def _build_client(repo, active_user=None) -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    # get_current_user を素通しにしない限り、その依存チェーン(get_session_identity ->
    # get_signer)が request.app.state.signer を要求するため、常に設定しておく。
    app.state.signer = SessionSigner("test-secret")

    def get_widgets_repository() -> SheetRepository:
        return repo

    router = make_list_router(
        prefix="/api/widgets",
        tags=["widgets"],
        model=Widget,
        get_repository=get_widgets_repository,
    )
    app.include_router(router)
    if active_user is not None:
        app.dependency_overrides[get_current_user] = lambda: active_user
    return TestClient(app)


def test_list_requires_authentication(fake_client_factory):
    sheet = fake_client_factory("widgets", header=["widget_id", "name"], rows=[])
    repo = SheetRepository(sheet, "widgets")
    client = _build_client(repo)

    response = client.get("/api/widgets")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_list_returns_valid_rows_and_flags_invalid_ones(fake_client_factory, active_user):
    sheet = fake_client_factory(
        "widgets",
        header=["widget_id", "name"],
        rows=[["w1", "Widget One"], ["", "Missing id"]],
    )
    repo = SheetRepository(sheet, "widgets")
    client = _build_client(repo, active_user)

    response = client.get("/api/widgets")

    assert response.status_code == 200
    body = response.json()
    assert body["data"] == [{"widget_id": "w1", "name": "Widget One"}]
    assert len(body["invalid_rows"]) == 1
    assert body["invalid_rows"][0]["row_number"] == 3
    assert body["invalid_rows"][0]["raw"] == {"widget_id": "", "name": "Missing id"}
    assert body["invalid_rows"][0]["reason"]


def test_empty_sheet_returns_empty_envelope(fake_client_factory, active_user):
    sheet = fake_client_factory("widgets", header=["widget_id", "name"], rows=[])
    repo = SheetRepository(sheet, "widgets")
    client = _build_client(repo, active_user)

    response = client.get("/api/widgets")

    assert response.status_code == 200
    assert response.json() == {"data": [], "invalid_rows": []}
