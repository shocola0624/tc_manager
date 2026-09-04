from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_current_user
from auth.session import SessionSigner
from errors import install_exception_handlers
from repositories import get_attendance_current_window_repository
from routers.attendance import router as attendance_router
from sheets.repository import SheetRepository
from sheets.schemas import Role, User

ATTENDANCE_HEADER = ["activity_id", "discord_user_id", "status", "updated_at"]


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


def test_current_window_endpoint_returns_view_data(fake_client_factory):
    sheet = fake_client_factory(
        "view_attendance_current",
        header=ATTENDANCE_HEADER,
        rows=[["activity_1", "u1", "attending", "2026-09-04T00:00:00+09:00"]],
    )
    repo = SheetRepository(sheet, "view_attendance_current")

    app = FastAPI()
    install_exception_handlers(app)
    app.state.signer = SessionSigner("test-secret")
    app.include_router(attendance_router)
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_attendance_current_window_repository] = lambda: repo
    client = TestClient(app)

    response = client.get("/api/attendance/current-window")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["status"] == "attending"
