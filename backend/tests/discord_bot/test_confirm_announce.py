from datetime import datetime, timedelta, timezone

from discord_bot.confirm_announce import build_confirm_announcement_content, confirm_activity
from sheets.assignments_state import AssignmentSlot
from sheets.parsing import parse_records
from sheets.repository import AppendOnlyRepository, SheetRepository
from sheets.schemas import Activity, BudgetItem, Item

JST = timezone(timedelta(hours=9))

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


def _activity(**overrides) -> Activity:
    defaults = dict(
        activity_id="activity_1",
        starts_at=datetime(2026, 9, 10, 14, 0, tzinfo=JST),
        duration_min=120,
        location="部室",
        title="定例会",
        description="産地の異なるエチオピア豆を飲み比べます。",
        target="新入部員歓迎",
        owner_id="o1",
        tasks="鍵を借りる",
        note="",
        announce_message_id=None,
        is_active=True,
    )
    defaults.update(overrides)
    return Activity(**defaults)


def _slot(**overrides) -> AssignmentSlot:
    defaults = dict(
        activity_id="activity_1",
        item_id="i1",
        custom_name=None,
        assignee_id="u2",
        last_action_at=datetime(2026, 1, 1, tzinfo=JST),
        last_actor_id="o1",
    )
    defaults.update(overrides)
    return AssignmentSlot(**defaults)


def _item(**overrides) -> Item:
    defaults = dict(
        item_id="i1",
        owner_id="u2",
        name="V60ドリッパー02",
        maker="HARIO",
        category="dripper",
        storage="owner",
        note="",
        is_active=True,
    )
    defaults.update(overrides)
    return Item(**defaults)


def test_content_includes_all_eight_sections_in_order():
    content = build_confirm_announcement_content(
        _activity(), owner_name="みなと", slots=[], items_by_id={}, budget_items=[]
    )

    headers = [
        "## 1.イベント名",
        "## 2.開催日時・場所",
        "## 3.イベント概要",
        "## 4.対象者",
        "## 5.責任者/担当者",
        "## 6.必要な資材・機材",
        "## 7.予算と費用",
        "## 8.タスク",
    ]
    positions = [content.index(h) for h in headers]
    assert positions == sorted(positions)


def test_datetime_and_location_are_formatted():
    content = build_confirm_announcement_content(
        _activity(), owner_name="みなと", slots=[], items_by_id={}, budget_items=[]
    )

    assert "9/10(木) 14:00" in content
    assert "9/10(木) 14:00〜" not in content  # RSVP告知(announce.py)とは違い末尾の〜は付けない
    assert "@部室" in content


def test_owner_name_is_shown_without_mention():
    content = build_confirm_announcement_content(
        _activity(), owner_name="みなと", slots=[], items_by_id={}, budget_items=[]
    )

    assert "みなと" in content
    assert "<@o1>" not in content


def test_registered_item_is_grouped_by_category_with_count_and_mention():
    item = _item()
    slot = _slot(item_id="i1", assignee_id="u2")

    content = build_confirm_announcement_content(
        _activity(), owner_name="みなと", slots=[slot], items_by_id={"i1": item}, budget_items=[]
    )

    assert "### ドリッパー×1" in content
    assert "V60ドリッパー02 (HARIO) <@u2>" in content


def test_item_without_assignee_omits_mention():
    item = _item(storage="clubroom")
    slot = _slot(item_id="i1", assignee_id=None)

    content = build_confirm_announcement_content(
        _activity(), owner_name="みなと", slots=[slot], items_by_id={"i1": item}, budget_items=[]
    )

    assert "V60ドリッパー02 (HARIO)" in content
    assert "<@" not in content


def test_empty_categories_are_omitted():
    item = _item(category="dripper")
    slot = _slot(item_id="i1")

    content = build_confirm_announcement_content(
        _activity(), owner_name="みなと", slots=[slot], items_by_id={"i1": item}, budget_items=[]
    )

    assert "ドリッパー" in content
    assert "グラインダー" not in content
    assert "サーバー" not in content


def test_ad_hoc_slots_are_listed_under_materials_section():
    slot = _slot(item_id=None, custom_name="借り物のケトル", assignee_id="u3")

    content = build_confirm_announcement_content(
        _activity(), owner_name="みなと", slots=[slot], items_by_id={}, budget_items=[]
    )

    assert "### 資材" in content
    assert "借り物のケトル <@u3>" in content


def test_materials_section_omitted_when_no_ad_hoc_items():
    content = build_confirm_announcement_content(
        _activity(), owner_name="みなと", slots=[], items_by_id={}, budget_items=[]
    )

    assert "### 資材" not in content


def test_budget_items_are_listed_with_total():
    budget_items = [
        BudgetItem(budget_item_id="b1", activity_id="activity_1", label="豆", amount_jpy=1000, is_active=True),
        BudgetItem(
            budget_item_id="b2", activity_id="activity_1", label="フィルター", amount_jpy=500, is_active=True
        ),
    ]

    content = build_confirm_announcement_content(
        _activity(), owner_name="みなと", slots=[], items_by_id={}, budget_items=budget_items
    )

    assert "豆 ¥1,000" in content
    assert "フィルター ¥500" in content
    assert "合計: ¥1,500" in content


def test_budget_total_omitted_when_no_budget_items():
    content = build_confirm_announcement_content(
        _activity(), owner_name="みなと", slots=[], items_by_id={}, budget_items=[]
    )

    assert "合計" not in content


async def test_confirm_activity_posts_to_given_channel_without_persisting_message_id(fake_client_factory):
    activities_sheet = fake_client_factory(
        "activities",
        header=ACTIVITIES_HEADER,
        rows=[
            [
                "activity_1",
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
    )
    activities_repo = SheetRepository(activities_sheet, "activities")
    users_repo = SheetRepository(
        fake_client_factory(
            "users", header=USERS_HEADER, rows=[["o1", "みなと", "officer", "TRUE", "ja", "2026-01-01T00:00:00+09:00"]]
        ),
        "users",
    )
    assignments_repo = AppendOnlyRepository(
        fake_client_factory("assignments", header=ASSIGNMENTS_HEADER, rows=[]), "assignments"
    )
    items_repo = SheetRepository(fake_client_factory("items", header=ITEMS_HEADER, rows=[]), "items")
    budget_items_repo = SheetRepository(
        fake_client_factory("budget_items", header=BUDGET_ITEMS_HEADER, rows=[]), "budget_items"
    )

    class FakeBotClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        async def create_message(self, channel_id: str, payload: dict) -> dict:
            self.calls.append((channel_id, payload))
            return {"id": "msg-confirm-1"}

    bot_client = FakeBotClient()

    activity = parse_records(activities_repo.read_all(), Activity).valid[0]

    message_id = await confirm_activity(
        activity,
        bot_client=bot_client,
        users_repo=users_repo,
        assignments_repo=assignments_repo,
        items_repo=items_repo,
        budget_items_repo=budget_items_repo,
        channel_id="confirm-channel-1",
    )

    assert message_id == "msg-confirm-1"
    assert bot_client.calls[0][0] == "confirm-channel-1"
    # announce_message_id のような永続化はしない(activities シートは書き換えない)
    stored = activities_repo.read_all()
    assert stored[0]["announce_message_id"] == ""
