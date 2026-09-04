from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_auth_settings, get_bot_client, get_current_user
from auth.discord_client import DiscordOAuthError
from auth.session import SessionSigner
from errors import install_exception_handlers
from repositories import (
    get_activities_repository,
    get_assignments_repository,
    get_budget_items_repository,
    get_items_repository,
    get_users_repository,
)
from routers.activities import router as activities_router
from sheets.repository import AppendOnlyRepository, SheetRepository
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
USERS_HEADER = ["discord_user_id", "name", "role", "is_active", "locale", "registered_at"]
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
BUDGET_ITEMS_HEADER = ["budget_item_id", "activity_id", "label", "amount_jpy", "is_active"]


class FakeBotClient:
    def __init__(self, *, fail: bool = False, message_id: str = "msg-1") -> None:
        self.fail = fail
        self.message_id = message_id
        self.calls: list[tuple[str, dict]] = []

    async def create_message(self, channel_id: str, payload: dict) -> dict:
        self.calls.append((channel_id, payload))
        if self.fail:
            raise DiscordOAuthError("boom")
        return {"id": self.message_id}


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


def _build_client(
    *,
    activities_repo,
    user: User,
    bot_client: FakeBotClient,
    users_repo=None,
    assignments_repo=None,
    items_repo=None,
    budget_items_repo=None,
    fake_client_factory=None,
) -> TestClient:
    app = FastAPI()
    install_exception_handlers(app)
    app.state.signer = SessionSigner("test-secret")
    app.include_router(activities_router)
    app.dependency_overrides[get_activities_repository] = lambda: activities_repo
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_bot_client] = lambda: bot_client
    app.dependency_overrides[get_users_repository] = lambda: (
        users_repo or SheetRepository(fake_client_factory("users", header=USERS_HEADER, rows=[]), "users")
    )
    app.dependency_overrides[get_assignments_repository] = lambda: (
        assignments_repo
        or AppendOnlyRepository(fake_client_factory("assignments", header=ASSIGNMENTS_HEADER, rows=[]), "assignments")
    )
    app.dependency_overrides[get_items_repository] = lambda: (
        items_repo or SheetRepository(fake_client_factory("items", header=ITEMS_HEADER, rows=[]), "items")
    )
    app.dependency_overrides[get_budget_items_repository] = lambda: (
        budget_items_repo
        or SheetRepository(fake_client_factory("budget_items", header=BUDGET_ITEMS_HEADER, rows=[]), "budget_items")
    )
    app.dependency_overrides[get_auth_settings] = lambda: SimpleNamespace(
        discord_announce_channel_id="channel-1",
        discord_confirm_announce_channel_id="confirm-channel-1",
        discord_log_channel_id="log-channel-1",
    )
    return TestClient(app)


@pytest.fixture
def activities_repo(fake_client_factory) -> SheetRepository:
    sheet = fake_client_factory("activities", header=ACTIVITIES_HEADER, rows=[])
    return SheetRepository(sheet, "activities")


def _create_activity(repo, fake_client_factory, **overrides) -> str:
    client = _build_client(
        activities_repo=repo, user=_user(), bot_client=FakeBotClient(), fake_client_factory=fake_client_factory
    )
    payload = {
        "starts_at": "2026-09-10T14:00:00+09:00",
        "duration_min": 120,
        "location": "部室",
        "title": "定例会",
        "description": "テイスティング会",
        "target": "新入部員歓迎",
        "owner_id": "o1",
        "tasks": "鍵を借りる",
        "note": "",
    }
    payload.update(overrides)
    return client.post("/api/activities", json=payload).json()["activity_id"]


def test_officer_can_confirm_activity_and_posts_to_confirm_channel(activities_repo, fake_client_factory):
    activity_id = _create_activity(activities_repo, fake_client_factory)
    users_repo = SheetRepository(
        fake_client_factory(
            "users",
            header=USERS_HEADER,
            rows=[["o1", "みなと", "officer", "TRUE", "ja", "2026-01-01T00:00:00+09:00"]],
        ),
        "users",
    )
    bot_client = FakeBotClient(message_id="msg-99")
    client = _build_client(
        activities_repo=activities_repo,
        user=_user(),
        bot_client=bot_client,
        users_repo=users_repo,
        fake_client_factory=fake_client_factory,
    )

    response = client.post(f"/api/activities/{activity_id}/confirm")

    assert response.status_code == 200
    assert len(bot_client.calls) == 1
    channel_id, payload = bot_client.calls[0]
    assert channel_id == "confirm-channel-1"
    content = payload["content"]
    assert "## 1.イベント名" in content
    assert "定例会" in content
    assert "@部室" in content
    assert "テイスティング会" in content
    assert "新入部員歓迎" in content
    assert "みなと" in content
    assert "鍵を借りる" in content
    # このリクエストは announce の RSVP チャンネルには一切投稿しない
    assert all(call[0] != "channel-1" for call in bot_client.calls)


def test_confirm_content_groups_items_by_category_and_lists_ad_hoc_and_budget(
    activities_repo, fake_client_factory
):
    activity_id = _create_activity(activities_repo, fake_client_factory)
    users_repo = SheetRepository(
        fake_client_factory(
            "users",
            header=USERS_HEADER,
            rows=[
                ["o1", "みなと", "officer", "TRUE", "ja", "2026-01-01T00:00:00+09:00"],
                ["u2", "あやの", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"],
            ],
        ),
        "users",
    )
    items_repo = SheetRepository(
        fake_client_factory(
            "items",
            header=ITEMS_HEADER,
            rows=[["i1", "u2", "V60ドリッパー02", "HARIO", "dripper", "owner", "", "TRUE"]],
        ),
        "items",
    )
    assignments_repo = AppendOnlyRepository(
        fake_client_factory(
            "assignments",
            header=ASSIGNMENTS_HEADER,
            rows=[
                ["2026-01-01T00:00:00+09:00", activity_id, "i1", "", "u2", "add", "o1"],
                ["2026-01-01T00:00:01+09:00", activity_id, "", "借り物のケトル", "", "add", "o1"],
            ],
        ),
        "assignments",
    )
    budget_items_repo = SheetRepository(
        fake_client_factory(
            "budget_items",
            header=BUDGET_ITEMS_HEADER,
            rows=[
                ["b1", activity_id, "豆", "1000", "TRUE"],
                ["b2", activity_id, "フィルター", "500", "TRUE"],
            ],
        ),
        "budget_items",
    )
    bot_client = FakeBotClient()
    client = _build_client(
        activities_repo=activities_repo,
        user=_user(),
        bot_client=bot_client,
        users_repo=users_repo,
        items_repo=items_repo,
        assignments_repo=assignments_repo,
        budget_items_repo=budget_items_repo,
        fake_client_factory=fake_client_factory,
    )

    response = client.post(f"/api/activities/{activity_id}/confirm")

    assert response.status_code == 200
    content = bot_client.calls[0][1]["content"]
    assert "### ドリッパー×1" in content
    assert "V60ドリッパー02 (HARIO) <@u2>" in content
    assert "### 資材" in content
    assert "借り物のケトル" in content
    assert "豆 ¥1,000" in content
    assert "フィルター ¥500" in content
    assert "合計: ¥1,500" in content
    # 他のカテゴリー(グラインダー等)は候補が無いので見出しごと出ない
    assert "グラインダー" not in content


def test_member_cannot_confirm_activity(activities_repo, fake_client_factory):
    activity_id = _create_activity(activities_repo, fake_client_factory)
    client = _build_client(
        activities_repo=activities_repo,
        user=_user(discord_user_id="m1", role=Role.MEMBER),
        bot_client=FakeBotClient(),
        fake_client_factory=fake_client_factory,
    )

    response = client.post(f"/api/activities/{activity_id}/confirm")

    assert response.status_code == 403


def test_confirm_unknown_activity_returns_404(activities_repo, fake_client_factory):
    client = _build_client(
        activities_repo=activities_repo, user=_user(), bot_client=FakeBotClient(), fake_client_factory=fake_client_factory
    )

    response = client.post("/api/activities/does-not-exist/confirm")

    assert response.status_code == 404


def test_confirm_failure_is_reported_as_502(activities_repo, fake_client_factory):
    activity_id = _create_activity(activities_repo, fake_client_factory)
    client = _build_client(
        activities_repo=activities_repo,
        user=_user(),
        bot_client=FakeBotClient(fail=True),
        fake_client_factory=fake_client_factory,
    )

    response = client.post(f"/api/activities/{activity_id}/confirm")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "discord_announce_failed"


def test_confirm_can_be_called_repeatedly(activities_repo, fake_client_factory):
    activity_id = _create_activity(activities_repo, fake_client_factory)
    bot_client = FakeBotClient()
    client = _build_client(
        activities_repo=activities_repo, user=_user(), bot_client=bot_client, fake_client_factory=fake_client_factory
    )

    client.post(f"/api/activities/{activity_id}/confirm")
    response = client.post(f"/api/activities/{activity_id}/confirm")

    assert response.status_code == 200
    assert len(bot_client.calls) == 2
