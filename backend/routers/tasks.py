from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from auth.dependencies import get_auth_settings, get_bot_client, get_current_user
from auth.config import AuthSettings
from auth.discord_client import DiscordBotClient
from discord_bot.write_log import log_write
from envelope import InvalidRowOut, ListResponse
from errors import AppError
from repositories import get_task_assignees_repository, get_tasks_repository, get_users_repository
from sheets.parsing import InvalidRow, parse_records
from sheets.repository import SheetRepository
from sheets.schemas import Role, Task, User
from timeutil import JST

from .tasks_permissions import can_access_visibility, can_assign, can_create_task, can_modify_task
from .tasks_schemas import TaskAssigneeInput, TaskCreateRequest, TaskOut, TaskUpdateRequest
from ulid import generate_ulid

router = APIRouter(prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(get_current_user)])


def _find_task_or_404(tasks_repo: SheetRepository, task_id: str) -> Task:
    result = parse_records(tasks_repo.read_all(), Task)
    for task in result.valid:
        if task.task_id == task_id:
            return task
    raise AppError(404, "task_not_found", "task not found")


def _assignees_for(assignees_repo: SheetRepository, task_id: str) -> list[TaskAssigneeInput]:
    assignees: list[TaskAssigneeInput] = []
    for row in assignees_repo.read_all():
        if row.get("task_id") != task_id:
            continue
        member_id = row.get("member_id") or None
        label = row.get("label") or None
        if member_id is None and label is None:
            continue
        assignees.append(TaskAssigneeInput(member_id=member_id, label=label))
    return assignees


def _replace_assignees(
    assignees_repo: SheetRepository, task_id: str, assignees: list[TaskAssigneeInput]
) -> None:
    kept = [row for row in assignees_repo.read_all() if row.get("task_id") != task_id]
    new_rows = [
        {"task_id": task_id, "member_id": a.member_id or "", "label": a.label or ""} for a in assignees
    ]
    assignees_repo.replace_all([*kept, *new_rows])


def _resolve_member_assignees(users_repo: SheetRepository, assignees: list[TaskAssigneeInput]) -> list[User]:
    """member_id 指定の担当者のみを解決する。label(部門名等の自由記述)は実在する
    ユーザーではないため、ロールに基づく可視性チェックの対象外とする。"""
    member_ids = [a.member_id for a in assignees if a.member_id is not None]
    if not member_ids:
        return []
    raw_by_id = {row.get("discord_user_id"): row for row in users_repo.read_all()}
    resolved: list[User] = []
    for member_id in member_ids:
        raw = raw_by_id.get(member_id)
        if raw is None:
            raise AppError(422, "assignee_not_found", f"user not found: {member_id}")
        try:
            resolved.append(User.model_validate(raw))
        except ValidationError as exc:
            raise AppError(422, "assignee_not_found", f"invalid user row: {member_id}") from exc
    return resolved


def _check_assignees_allowed(users_repo: SheetRepository, assignees: list[TaskAssigneeInput], visibility: Role) -> None:
    for member in _resolve_member_assignees(users_repo, assignees):
        if not can_assign(member, visibility):
            raise AppError(403, "forbidden_task_assignee", f"{member.discord_user_id} cannot be assigned")


def _can_see_invalid_row(user: User, row: InvalidRow) -> bool:
    """壊れた行でも、可能な限り visibility を読み取って閲覧可否を判定する。
    visibility 自体が読めない行は admin にしか見せない(閲覧制限の抜け道にしない)。"""
    if user.role == Role.ADMIN:
        return True
    try:
        visibility = Role(row.raw.get("visibility", ""))
    except ValueError:
        return False
    return can_access_visibility(user, visibility)


@router.get("", response_model=ListResponse[TaskOut])
async def list_tasks(
    user: User = Depends(get_current_user),
    tasks_repo: SheetRepository = Depends(get_tasks_repository),
    assignees_repo: SheetRepository = Depends(get_task_assignees_repository),
) -> ListResponse[TaskOut]:
    task_result = parse_records(tasks_repo.read_all(), Task)

    assignees_by_task: dict[str, list[TaskAssigneeInput]] = {}
    for row in assignees_repo.read_all():
        task_id = row.get("task_id")
        member_id = row.get("member_id") or None
        label = row.get("label") or None
        if not task_id or (member_id is None and label is None):
            continue
        assignees_by_task.setdefault(task_id, []).append(TaskAssigneeInput(member_id=member_id, label=label))

    data = [
        TaskOut(**task.model_dump(), assignees=assignees_by_task.get(task.task_id, []))
        for task in task_result.valid
        if can_access_visibility(user, task.visibility)
    ]
    invalid_rows = [
        InvalidRowOut.from_invalid_row(row) for row in task_result.invalid if _can_see_invalid_row(user, row)
    ]
    return ListResponse(data=data, invalid_rows=invalid_rows)


@router.post("", response_model=TaskOut)
async def create_task(
    payload: TaskCreateRequest,
    user: User = Depends(get_current_user),
    tasks_repo: SheetRepository = Depends(get_tasks_repository),
    assignees_repo: SheetRepository = Depends(get_task_assignees_repository),
    users_repo: SheetRepository = Depends(get_users_repository),
    bot_client: DiscordBotClient = Depends(get_bot_client),
    settings: AuthSettings = Depends(get_auth_settings),
) -> TaskOut:
    if not can_create_task(user, payload.visibility):
        raise AppError(403, "forbidden_task_visibility", "cannot create a task at this visibility")

    _check_assignees_allowed(users_repo, payload.assignees, payload.visibility)

    now = datetime.now(JST)
    task = Task(
        task_id=generate_ulid(),
        title=payload.title,
        description=payload.description,
        due_at=payload.due_at,
        visibility=payload.visibility,
        related_activity_id=payload.related_activity_id,
        reminder_offsets=payload.reminder_offsets,
        google_event_id=None,
        is_active=True,
        created_by=user.discord_user_id,
        created_at=now,
        updated_at=now,
    )
    record = {
        "task_id": task.task_id,
        "title": task.title,
        "description": task.description,
        "due_at": task.due_at.isoformat(),
        "status": task.status.value,
        "visibility": task.visibility.value,
        "related_activity_id": task.related_activity_id or "",
        "reminder_offsets": task.reminder_offsets,
        "google_event_id": "",
        "is_active": "TRUE",
        "created_by": task.created_by,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }
    # ユーザー要件: タスクの「追加」のみ書き込みログに残す(編集・ステータス変更・
    # cron からの書き込みはログ対象外)。担当者行(task_assignees)の追記も対象外。
    await log_write(
        lambda: tasks_repo.append(record),
        bot_client=bot_client,
        channel_id=settings.discord_log_channel_id,
        actor_name=user.name,
        actor_id=user.discord_user_id,
        sheet_name="tasks",
        operation="append",
        record=record,
    )
    for assignee in payload.assignees:
        assignees_repo.append(
            {"task_id": task.task_id, "member_id": assignee.member_id or "", "label": assignee.label or ""}
        )

    return TaskOut(**task.model_dump(), assignees=payload.assignees)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: str,
    payload: TaskUpdateRequest,
    user: User = Depends(get_current_user),
    tasks_repo: SheetRepository = Depends(get_tasks_repository),
    assignees_repo: SheetRepository = Depends(get_task_assignees_repository),
    users_repo: SheetRepository = Depends(get_users_repository),
) -> TaskOut:
    task = _find_task_or_404(tasks_repo, task_id)
    if not can_modify_task(user, task):
        raise AppError(403, "forbidden_task_edit", "cannot edit this task")

    updates = payload.model_dump(exclude_unset=True, exclude={"assignees"})
    new_visibility: Role = updates.get("visibility", task.visibility)
    if "visibility" in updates and not can_create_task(user, new_visibility):
        raise AppError(403, "forbidden_task_visibility", "cannot set this visibility")

    if payload.assignees is not None:
        _check_assignees_allowed(users_repo, payload.assignees, new_visibility)

    updated = task.model_copy(update={**updates, "updated_at": datetime.now(JST)})
    record = {
        "title": updated.title,
        "description": updated.description,
        "due_at": updated.due_at.isoformat(),
        "status": updated.status.value,
        "visibility": updated.visibility.value,
        "related_activity_id": updated.related_activity_id or "",
        "reminder_offsets": updated.reminder_offsets,
        "updated_at": updated.updated_at.isoformat(),
    }
    tasks_repo.update_by_key("task_id", task_id, record)

    if payload.assignees is not None:
        _replace_assignees(assignees_repo, task_id, payload.assignees)
        assignees = payload.assignees
    else:
        assignees = _assignees_for(assignees_repo, task_id)

    return TaskOut(**updated.model_dump(), assignees=assignees)


@router.delete("/{task_id}", response_model=TaskOut)
async def delete_task(
    task_id: str,
    user: User = Depends(get_current_user),
    tasks_repo: SheetRepository = Depends(get_tasks_repository),
    assignees_repo: SheetRepository = Depends(get_task_assignees_repository),
) -> TaskOut:
    task = _find_task_or_404(tasks_repo, task_id)
    if not can_modify_task(user, task):
        raise AppError(403, "forbidden_task_edit", "cannot edit this task")

    tasks_repo.update_by_key("task_id", task_id, {"is_active": "FALSE"})
    assignees = _assignees_for(assignees_repo, task_id)
    updated = task.model_copy(update={"is_active": False})
    return TaskOut(**updated.model_dump(), assignees=assignees)
