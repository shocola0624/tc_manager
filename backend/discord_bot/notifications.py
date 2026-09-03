from __future__ import annotations

import logging

from auth.dependencies import find_raw_user
from auth.discord_client import DiscordBotClient
from sheets.assignments_state import fold_assignment_log
from sheets.parsing import parse_records
from sheets.repository import SheetRepository
from sheets.schemas import Activity, AssignmentLogEntry, Item, User

from .locales import translate

logger = logging.getLogger(__name__)


def _find_activity(activities_repo: SheetRepository, activity_id: str) -> Activity | None:
    result = parse_records(activities_repo.read_all(), Activity)
    for activity in result.valid:
        if activity.activity_id == activity_id:
            return activity
    return None


async def notify_absent_user_if_still_assigned(
    *,
    activity_id: str,
    user: User,
    activities_repo: SheetRepository,
    assignments_repo: SheetRepository,
    items_repo: SheetRepository,
    bot_client: DiscordBotClient,
) -> None:
    """出欠を欠席に変更したとき、その活動で本人が持参担当のままの割り当てが
    残っていれば本人へDMする。DM送信の失敗(DM拒否・サーバー未共有等)は
    握りつぶし、出欠更新自体は妨げない(呼び出し元は結果を待たなくてよい)。
    """
    try:
        entries = parse_records(assignments_repo.read_all(), AssignmentLogEntry).valid
        slots = fold_assignment_log(entries)
        mine = [
            slot
            for slot in slots
            if slot.activity_id == activity_id and slot.assignee_id == user.discord_user_id
        ]
        if not mine:
            return

        items_by_id = {item.item_id: item for item in parse_records(items_repo.read_all(), Item).valid}
        item_names = [
            items_by_id[slot.item_id].name if slot.item_id and slot.item_id in items_by_id else (slot.custom_name or "")
            for slot in mine
        ]
        activity = _find_activity(activities_repo, activity_id)

        content = translate(
            user.locale,
            "notify.absent_with_assignment",
            activity_title=activity.title if activity else activity_id,
            items="、".join(name for name in item_names if name),
        )
        await bot_client.send_direct_message(user.discord_user_id, content)
    except Exception:
        logger.exception("failed to notify absent user about existing assignment")


async def notify_owner_item_assigned_while_absent(
    *,
    activity_id: str,
    item: Item,
    assignee_id: str | None,
    activities_repo: SheetRepository,
    users_repo: SheetRepository,
    bot_client: DiscordBotClient,
) -> None:
    """storage=owner かつ所有者が出席しない持ち物が活動に追加されたとき、
    所有者本人へDMする。DM送信の失敗は握りつぶし、追加処理自体は妨げない。
    """
    try:
        activity = _find_activity(activities_repo, activity_id)

        assignee_raw = find_raw_user(users_repo, assignee_id) if assignee_id else None
        assignee_name = assignee_raw.get("name") if assignee_raw else (assignee_id or "")

        owner_raw = find_raw_user(users_repo, item.owner_id)
        owner_locale = owner_raw.get("locale") if owner_raw else None

        content = translate(
            owner_locale,
            "notify.item_needed_while_absent",
            activity_title=activity.title if activity else activity_id,
            item_name=item.name,
            assignee_name=assignee_name,
        )
        await bot_client.send_direct_message(item.owner_id, content)
    except Exception:
        logger.exception("failed to notify owner about item needed while absent")
