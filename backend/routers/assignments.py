from __future__ import annotations

from fastapi import Depends, Query

from auth.dependencies import find_raw_user, get_bot_client, get_current_user
from auth.discord_client import DiscordBotClient
from discord_bot.notifications import notify_owner_item_assigned_while_absent
from errors import AppError
from repositories import (
    get_activities_repository,
    get_assignments_repository,
    get_attendance_repository,
    get_items_repository,
    get_users_repository,
)
from sheets.assignment_candidates import compute_item_candidates
from sheets.assignments_state import fold_assignment_log
from sheets.parsing import parse_records
from sheets.repository import AppendOnlyRepository, SheetRepository
from sheets.schemas import (
    Attendance,
    AssignmentAction,
    AssignmentLogEntry,
    AttendanceStatus,
    Item,
    Storage,
    User,
)
from timeutil import now_iso8601

from ._common import make_list_router
from .assignments_permissions import can_assign
from .assignments_schemas import (
    AssignmentAddRequest,
    AssignmentRemoveRequest,
    AssignmentSlotOut,
    ItemCandidateOut,
)

# 生ログをそのまま返す一覧(監査・デバッグ用)。現在の状態は /current で畳み込んで返す。
router = make_list_router(
    prefix="/api/assignments",
    tags=["assignments"],
    model=AssignmentLogEntry,
    get_repository=get_assignments_repository,
)


def _attendance_by_user(attendance_repo: SheetRepository, activity_id: str) -> dict[str, AttendanceStatus]:
    result = parse_records(attendance_repo.read_all(), Attendance)
    return {row.discord_user_id: row.status for row in result.valid if row.activity_id == activity_id}


def _find_active_item_or_404(items_repo: SheetRepository, item_id: str) -> Item:
    result = parse_records(items_repo.read_all(), Item)
    for item in result.valid:
        if item.item_id == item_id and item.is_active:
            return item
    raise AppError(404, "item_not_found", "item not found")


@router.get("/candidates", response_model=list[ItemCandidateOut])
async def list_candidates(
    activity_id: str = Query(min_length=1),
    extended: bool = Query(default=False),
    items_repo: SheetRepository = Depends(get_items_repository),
    attendance_repo: SheetRepository = Depends(get_attendance_repository),
) -> list[ItemCandidateOut]:
    """候補一覧(CLAUDE.md §5)。カテゴリー・所有者フィルターはクライアント側で行う(CLAUDE.md §3)。"""
    active_items = [item for item in parse_records(items_repo.read_all(), Item).valid if item.is_active]
    attendance_by_user = _attendance_by_user(attendance_repo, activity_id)
    candidates = compute_item_candidates(active_items, attendance_by_user, extended_mode=extended)
    return [
        ItemCandidateOut(
            item=c.item, requires_assignee=c.requires_assignee, default_assignee_id=c.default_assignee_id
        )
        for c in candidates
        if c.is_candidate
    ]


@router.get("/current", response_model=list[AssignmentSlotOut])
async def list_current_assignments(
    assignments_repo: AppendOnlyRepository = Depends(get_assignments_repository),
) -> list[AssignmentSlotOut]:
    """追記専用ログを畳み込んだ現在の割り当て状態(CLAUDE.md §4)。activity_id での絞り込みは
    行わない。他の一覧エンドポイントと同様、クライアント側でキャッシュ後にフィルターする。"""
    valid_entries = parse_records(assignments_repo.read_all(), AssignmentLogEntry).valid
    slots = fold_assignment_log(valid_entries)
    return [
        AssignmentSlotOut(
            activity_id=slot.activity_id,
            item_id=slot.item_id,
            custom_name=slot.custom_name,
            assignee_id=slot.assignee_id,
            last_action_at=slot.last_action_at,
            last_actor_id=slot.last_actor_id,
        )
        for slot in slots
    ]


@router.post("", response_model=AssignmentLogEntry)
async def add_assignment(
    payload: AssignmentAddRequest,
    user: User = Depends(get_current_user),
    items_repo: SheetRepository = Depends(get_items_repository),
    attendance_repo: SheetRepository = Depends(get_attendance_repository),
    users_repo: SheetRepository = Depends(get_users_repository),
    activities_repo: SheetRepository = Depends(get_activities_repository),
    assignments_repo: AppendOnlyRepository = Depends(get_assignments_repository),
    bot_client: DiscordBotClient = Depends(get_bot_client),
) -> AssignmentLogEntry:
    """器具の選択(CLAUDE.md §5・§6)。read-modify-write は行わず、常に append する(CLAUDE.md §4)。"""
    attendance_by_user = _attendance_by_user(attendance_repo, payload.activity_id)

    if payload.item_id is not None:
        item = _find_active_item_or_404(items_repo, payload.item_id)
        # サーバーは常に extended_mode=True で評価する。「既定で見えるべきか」は
        # 候補一覧(GET /candidates)の関心事であり、追加時に問うのは
        # 「このアイテムを選ぶなら何が必要か」だけ。
        [candidate] = compute_item_candidates([item], attendance_by_user, extended_mode=True)

        if candidate.requires_assignee:
            if payload.assignee_id is None:
                raise AppError(422, "assignee_required", "assignee_id is required for this item")
            resolved_assignee_id = payload.assignee_id
            is_system_default = False
        elif candidate.default_assignee_id is not None:
            # storage=owner かつ所有者が出席: クライアント指定に関わらず所有者に固定する。
            resolved_assignee_id = candidate.default_assignee_id
            is_system_default = True
        else:
            if payload.assignee_id is not None:
                raise AppError(422, "assignee_not_allowed", "this item does not need an assignee")
            resolved_assignee_id = None
            is_system_default = True
    else:
        # アドホック入力: 担当者は任意(CLAUDE.md §5)。
        resolved_assignee_id = payload.assignee_id
        is_system_default = False

    if resolved_assignee_id is not None and find_raw_user(users_repo, resolved_assignee_id) is None:
        raise AppError(422, "assignee_not_found", "assignee_id does not match any user")

    if not can_assign(resolved_assignee_id, is_system_default=is_system_default, actor=user):
        raise AppError(403, "forbidden_assignee", "cannot assign this person")

    timestamp = now_iso8601()
    assignments_repo.append(
        {
            "timestamp": timestamp,
            "activity_id": payload.activity_id,
            "item_id": payload.item_id or "",
            "custom_name": payload.custom_name or "",
            "assignee_id": resolved_assignee_id or "",
            "action": "add",
            "actor_id": user.discord_user_id,
        }
    )

    if payload.item_id is not None and candidate.requires_assignee and item.storage == Storage.OWNER:
        # 拡張モードで所有者が出席しない持ち物が選ばれたケース。所有者本人へDM(ベストエフォート)。
        await notify_owner_item_assigned_while_absent(
            activity_id=payload.activity_id,
            item=item,
            assignee_id=resolved_assignee_id,
            activities_repo=activities_repo,
            users_repo=users_repo,
            bot_client=bot_client,
        )

    return AssignmentLogEntry(
        timestamp=timestamp,
        activity_id=payload.activity_id,
        item_id=payload.item_id,
        custom_name=payload.custom_name,
        assignee_id=resolved_assignee_id,
        action=AssignmentAction.ADD,
        actor_id=user.discord_user_id,
    )


@router.post("/remove", response_model=AssignmentLogEntry)
async def remove_assignment(
    payload: AssignmentRemoveRequest,
    user: User = Depends(get_current_user),
    assignments_repo: AppendOnlyRepository = Depends(get_assignments_repository),
) -> AssignmentLogEntry:
    """器具の解除。担当者に関わらず全 is_active ユーザーが行える(CLAUDE.md §6)。"""
    timestamp = now_iso8601()
    assignments_repo.append(
        {
            "timestamp": timestamp,
            "activity_id": payload.activity_id,
            "item_id": payload.item_id or "",
            "custom_name": payload.custom_name or "",
            "assignee_id": "",
            "action": "remove",
            "actor_id": user.discord_user_id,
        }
    )
    return AssignmentLogEntry(
        timestamp=timestamp,
        activity_id=payload.activity_id,
        item_id=payload.item_id,
        custom_name=payload.custom_name,
        assignee_id=None,
        action=AssignmentAction.REMOVE,
        actor_id=user.discord_user_id,
    )
