from __future__ import annotations

from datetime import datetime

from auth.dependencies import find_raw_user
from auth.discord_client import DiscordBotClient
from sheets.assignments_state import AssignmentSlot, fold_assignment_log
from sheets.parsing import parse_records
from sheets.repository import SheetRepository
from sheets.schemas import Activity, AssignmentLogEntry, BudgetItem, Category, Item

from .locales import translate

# RSVP告知(announce.py)とは別の、確定情報をまとめた長文フォーマット用の投稿。
# ユーザー指定のテンプレートに厳密に従う(CLAUDE.md §7-4: Discord投稿文もtranslate()を通す)。
_WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]

# 器具グループの出力順。0件のカテゴリーは省略する。
_CATEGORY_ORDER = [
    Category.DRIPPER,
    Category.GRINDER,
    Category.SCALE,
    Category.KETTLE,
    Category.POT,
    Category.SCOOP,
    Category.THERMOMETER,
    Category.SERVER,
    Category.OTHER,
]


def _format_datetime_ja(dt: datetime) -> str:
    weekday = _WEEKDAY_JA[dt.weekday()]
    return f"{dt.month}/{dt.day}({weekday}) {dt.hour:02d}:{dt.minute:02d}"


def _mention(discord_user_id: str | None) -> str:
    return f" <@{discord_user_id}>" if discord_user_id else ""


def build_confirm_announcement_content(
    activity: Activity,
    *,
    owner_name: str,
    slots: list[AssignmentSlot],
    items_by_id: dict[str, Item],
    budget_items: list[BudgetItem],
) -> str:
    lines: list[str] = [
        "## 1.イベント名",
        activity.title,
        "",
        "## 2.開催日時・場所",
        _format_datetime_ja(activity.starts_at),
        f"@{activity.location}",
        "",
        "## 3.イベント概要",
        activity.description,
        "",
        "## 4.対象者",
        activity.target,
        "",
        "## 5.責任者/担当者",
        owner_name,
        "",
        "## 6.必要な資材・機材",
    ]

    by_category: dict[Category, list[tuple[Item, AssignmentSlot]]] = {}
    ad_hoc_slots: list[AssignmentSlot] = []
    for slot in slots:
        if slot.item_id is not None:
            item = items_by_id.get(slot.item_id)
            if item is None:
                continue
            by_category.setdefault(item.category, []).append((item, slot))
        else:
            ad_hoc_slots.append(slot)

    for category in _CATEGORY_ORDER:
        group = by_category.get(category)
        if not group:
            continue
        lines.append("")
        lines.append(f"### {translate('ja', f'category.{category.value}')}×{len(group)}")
        for item, slot in group:
            lines.append(f"{item.name} ({item.maker}){_mention(slot.assignee_id)}")

    if ad_hoc_slots:
        lines.append("")
        lines.append("### 資材")
        for slot in ad_hoc_slots:
            lines.append(f"{slot.custom_name or ''}{_mention(slot.assignee_id)}")

    lines.append("")
    lines.append("## 7.予算と費用")
    total = 0
    for budget_item in budget_items:
        lines.append(f"{budget_item.label} ¥{budget_item.amount_jpy:,}")
        total += budget_item.amount_jpy
    if budget_items:
        lines.append(f"合計: ¥{total:,}")

    lines.append("")
    lines.append("## 8.タスク")
    lines.append(activity.tasks)

    return "\n".join(lines)


async def confirm_activity(
    activity: Activity,
    *,
    bot_client: DiscordBotClient,
    users_repo: SheetRepository,
    assignments_repo: SheetRepository,
    items_repo: SheetRepository,
    budget_items_repo: SheetRepository,
    channel_id: str,
) -> str:
    """確定情報を組み立てて別チャンネルへ投稿する。announce_message_id のような永続化は
    行わない(何度でも押せて、そのたびに新規メッセージを投稿するだけでよい)。"""
    owner_raw = find_raw_user(users_repo, activity.owner_id)
    owner_name = owner_raw["name"] if owner_raw else activity.owner_id

    entries = parse_records(assignments_repo.read_all(), AssignmentLogEntry).valid
    slots = [
        slot for slot in fold_assignment_log(entries) if slot.activity_id == activity.activity_id
    ]

    items_by_id = {item.item_id: item for item in parse_records(items_repo.read_all(), Item).valid}

    budget_items = [
        item
        for item in parse_records(budget_items_repo.read_all(), BudgetItem).valid
        if item.activity_id == activity.activity_id and item.is_active
    ]

    content = build_confirm_announcement_content(
        activity,
        owner_name=owner_name,
        slots=slots,
        items_by_id=items_by_id,
        budget_items=budget_items,
    )
    message = await bot_client.create_message(channel_id, {"content": content})
    return message["id"]
