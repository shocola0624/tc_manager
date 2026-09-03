from discord_bot.notifications import (
    notify_absent_user_if_still_assigned,
    notify_owner_item_assigned_while_absent,
)
from sheets.repository import AppendOnlyRepository, SheetRepository
from sheets.schemas import Item, Role, User

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
USERS_HEADER = ["discord_user_id", "name", "role", "is_active", "locale", "registered_at"]


class FakeBotClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.dm_calls: list[tuple[str, str]] = []

    async def send_direct_message(self, discord_user_id: str, content: str) -> None:
        if self.fail:
            raise RuntimeError("boom")
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


def _item(**overrides) -> Item:
    defaults = dict(
        item_id="i1",
        owner_id="owner1",
        name="Kettle",
        maker="Fellow",
        category="kettle",
        storage="owner",
        note="",
        is_active=True,
    )
    defaults.update(overrides)
    return Item(**defaults)


# ---- notify_absent_user_if_still_assigned ----


async def test_no_dm_when_no_assignment_exists(fake_client_factory):
    activities_repo = SheetRepository(
        fake_client_factory("activities", header=ACTIVITIES_HEADER, rows=[]), "activities"
    )
    assignments_repo = AppendOnlyRepository(
        fake_client_factory("assignments", header=ASSIGNMENTS_HEADER, rows=[]), "assignments"
    )
    items_repo = SheetRepository(fake_client_factory("items", header=ITEMS_HEADER, rows=[]), "items")
    bot_client = FakeBotClient()

    await notify_absent_user_if_still_assigned(
        activity_id="a1",
        user=_user(),
        activities_repo=activities_repo,
        assignments_repo=assignments_repo,
        items_repo=items_repo,
        bot_client=bot_client,
    )

    assert bot_client.dm_calls == []


async def test_dm_sent_with_activity_title_and_item_name_when_assignment_exists(fake_client_factory):
    activities_repo = SheetRepository(
        fake_client_factory(
            "activities",
            header=ACTIVITIES_HEADER,
            rows=[
                [
                    "a1",
                    "2026-09-10T14:00:00+09:00",
                    "120",
                    "部室",
                    "定例会",
                    "",
                    "",
                    "o1",
                    "",
                    "",
                    "",
                    "TRUE",
                ]
            ],
        ),
        "activities",
    )
    assignments_repo = AppendOnlyRepository(
        fake_client_factory(
            "assignments",
            header=ASSIGNMENTS_HEADER,
            rows=[["2026-01-01T00:00:00+09:00", "a1", "i1", "", "u1", "add", "u1"]],
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

    await notify_absent_user_if_still_assigned(
        activity_id="a1",
        user=_user(discord_user_id="u1"),
        activities_repo=activities_repo,
        assignments_repo=assignments_repo,
        items_repo=items_repo,
        bot_client=bot_client,
    )

    assert len(bot_client.dm_calls) == 1
    recipient, content = bot_client.dm_calls[0]
    assert recipient == "u1"
    assert "定例会" in content
    assert "Kettle" in content


async def test_dm_ignores_assignment_for_a_different_activity(fake_client_factory):
    activities_repo = SheetRepository(
        fake_client_factory("activities", header=ACTIVITIES_HEADER, rows=[]), "activities"
    )
    assignments_repo = AppendOnlyRepository(
        fake_client_factory(
            "assignments",
            header=ASSIGNMENTS_HEADER,
            rows=[["2026-01-01T00:00:00+09:00", "other-activity", "i1", "", "u1", "add", "u1"]],
        ),
        "assignments",
    )
    items_repo = SheetRepository(fake_client_factory("items", header=ITEMS_HEADER, rows=[]), "items")
    bot_client = FakeBotClient()

    await notify_absent_user_if_still_assigned(
        activity_id="a1",
        user=_user(discord_user_id="u1"),
        activities_repo=activities_repo,
        assignments_repo=assignments_repo,
        items_repo=items_repo,
        bot_client=bot_client,
    )

    assert bot_client.dm_calls == []


async def test_dm_failure_does_not_propagate(fake_client_factory):
    activities_repo = SheetRepository(
        fake_client_factory("activities", header=ACTIVITIES_HEADER, rows=[]), "activities"
    )
    assignments_repo = AppendOnlyRepository(
        fake_client_factory(
            "assignments",
            header=ASSIGNMENTS_HEADER,
            rows=[["2026-01-01T00:00:00+09:00", "a1", "i1", "", "u1", "add", "u1"]],
        ),
        "assignments",
    )
    items_repo = SheetRepository(fake_client_factory("items", header=ITEMS_HEADER, rows=[]), "items")
    bot_client = FakeBotClient(fail=True)

    # 例外は握りつぶされ、呼び出し元には伝播しない。
    await notify_absent_user_if_still_assigned(
        activity_id="a1",
        user=_user(discord_user_id="u1"),
        activities_repo=activities_repo,
        assignments_repo=assignments_repo,
        items_repo=items_repo,
        bot_client=bot_client,
    )


# ---- notify_owner_item_assigned_while_absent ----


async def test_owner_notified_with_activity_title_item_and_assignee_name(fake_client_factory):
    activities_repo = SheetRepository(
        fake_client_factory(
            "activities",
            header=ACTIVITIES_HEADER,
            rows=[
                [
                    "a1",
                    "2026-09-10T14:00:00+09:00",
                    "120",
                    "部室",
                    "定例会",
                    "",
                    "",
                    "o1",
                    "",
                    "",
                    "",
                    "TRUE",
                ]
            ],
        ),
        "activities",
    )
    users_repo = SheetRepository(
        fake_client_factory(
            "users",
            header=USERS_HEADER,
            rows=[
                ["owner1", "Owner", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"],
                ["u2", "Bob", "member", "TRUE", "ja", "2026-01-01T00:00:00+09:00"],
            ],
        ),
        "users",
    )
    bot_client = FakeBotClient()

    await notify_owner_item_assigned_while_absent(
        activity_id="a1",
        item=_item(owner_id="owner1"),
        assignee_id="u2",
        activities_repo=activities_repo,
        users_repo=users_repo,
        bot_client=bot_client,
    )

    assert len(bot_client.dm_calls) == 1
    recipient, content = bot_client.dm_calls[0]
    assert recipient == "owner1"
    assert "定例会" in content
    assert "Kettle" in content
    assert "Bob" in content


async def test_owner_notification_failure_does_not_propagate(fake_client_factory):
    activities_repo = SheetRepository(
        fake_client_factory("activities", header=ACTIVITIES_HEADER, rows=[]), "activities"
    )
    users_repo = SheetRepository(fake_client_factory("users", header=USERS_HEADER, rows=[]), "users")
    bot_client = FakeBotClient(fail=True)

    await notify_owner_item_assigned_while_absent(
        activity_id="a1",
        item=_item(),
        assignee_id="u2",
        activities_repo=activities_repo,
        users_repo=users_repo,
        bot_client=bot_client,
    )
