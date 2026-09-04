from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_current_user
from auth.session import SessionSigner
from errors import install_exception_handlers
from repositories import get_activities_current_window_repository, get_activities_repository
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
        discord_user_id="u1",
        name="Alice",
        role=Role.MEMBER,
        is_active=True,
        locale="ja",
        registered_at="2026-01-01T00:00:00+09:00",
    )
    defaults.update(overrides)
    return User(**defaults)


def _build_client(*, current_window_repo, activities_repo=None) -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    app.state.signer = SessionSigner("test-secret")
    app.include_router(activities_router)
    app.dependency_overrides[get_current_user] = lambda: _user()
    app.dependency_overrides[get_activities_current_window_repository] = lambda: current_window_repo
    if activities_repo is not None:
        app.dependency_overrides[get_activities_repository] = lambda: activities_repo
    return TestClient(app)


def test_current_window_endpoint_returns_view_data(fake_client_factory):
    """ホーム画面向けの軽量エンドポイントは view_activities_current 由来のデータを返す。"""
    sheet = fake_client_factory(
        "view_activities_current",
        header=ACTIVITIES_HEADER,
        rows=[
            [
                "activity_1",
                "2026-09-10T14:00:00+09:00",
                "60",
                "部室",
                "直近の活動",
                "",
                "",
                "o1",
                "",
                "",
                "",
                "TRUE",
            ]
        ],
    )
    repo = SheetRepository(sheet, "view_activities_current")
    client = _build_client(current_window_repo=repo)

    response = client.get("/api/activities/current-window")

    assert response.status_code == 200
    body = response.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["title"] == "直近の活動"


def test_current_window_endpoint_does_not_affect_full_list_endpoint(fake_client_factory):
    """/current-window の追加が既存の GET /api/activities(過去タブ等が使う全件取得)に
    影響しないことを確認する。"""
    windowed_sheet = fake_client_factory(
        "view_activities_current",
        header=ACTIVITIES_HEADER,
        rows=[
            [
                "activity_recent",
                "2026-09-10T14:00:00+09:00",
                "60",
                "",
                "recent",
                "",
                "",
                "o1",
                "",
                "",
                "",
                "TRUE",
            ]
        ],
    )
    full_sheet = fake_client_factory(
        "activities",
        header=ACTIVITIES_HEADER,
        rows=[
            [
                "activity_old",
                "2020-01-01T00:00:00+09:00",
                "60",
                "",
                "old",
                "",
                "",
                "o1",
                "",
                "",
                "",
                "TRUE",
            ],
            [
                "activity_recent",
                "2026-09-10T14:00:00+09:00",
                "60",
                "",
                "recent",
                "",
                "",
                "o1",
                "",
                "",
                "",
                "TRUE",
            ],
        ],
    )
    client = _build_client(
        current_window_repo=SheetRepository(windowed_sheet, "view_activities_current"),
        activities_repo=SheetRepository(full_sheet, "activities"),
    )

    full_response = client.get("/api/activities")
    windowed_response = client.get("/api/activities/current-window")

    assert len(full_response.json()["data"]) == 2
    assert len(windowed_response.json()["data"]) == 1
