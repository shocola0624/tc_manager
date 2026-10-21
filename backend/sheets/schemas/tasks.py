import re
from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

from ._coerce import empty_str_to_none, parse_bool_default_true
from .common import Role, TaskStatus

_OFFSET_SEGMENT = re.compile(r"^-\d+[dhm]$")


class Task(BaseModel):
    """tasks シートの1行。visibility は既存の Role をそのまま流用し、閲覧・作成・担当者
    指定・ステータス変更・編集・削除のすべてを「自分のロール以上か」という1つの階層
    チェックで判定する(routers/tasks_permissions.py)。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    due_at: datetime
    status: TaskStatus = TaskStatus.TODO
    visibility: Role
    related_activity_id: Annotated[str | None, BeforeValidator(empty_str_to_none)] = None
    # 期限からの相対オフセットをカンマ区切りで持つ(例 "-7d,-1d,-2h")。幹部がセルを直接
    # 編集して調整できることを優先し、別テーブルには分けない(ユーザー要件)。
    reminder_offsets: str = ""
    google_event_id: Annotated[str | None, BeforeValidator(empty_str_to_none)] = None
    # 論理削除フラグ。task_assignees/reminder_log が task_id を参照し続けるため、
    # 削除は物理削除ではなく is_active=FALSE への更新として扱う(items/activities と同じ方針)。
    is_active: Annotated[bool, BeforeValidator(parse_bool_default_true)] = True
    created_by: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime

    @field_validator("reminder_offsets")
    @classmethod
    def _validate_offsets(cls, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        segments = [segment.strip() for segment in value.split(",")]
        for segment in segments:
            if not _OFFSET_SEGMENT.match(segment):
                raise ValueError(f"invalid reminder offset segment: {segment!r}")
        return ",".join(segments)


class TaskAssignee(BaseModel):
    """task_assignees シートの1行(join)。1タスクにつき複数行持てる。

    担当は個人(member_id = users.discord_user_id)だけでなく、部門名のような
    未登録の自由記述(label)でも指定できる。assignments.item_id/custom_name と同じ
    排他パターン(CLAUDE.md §5 のアドホック入力に相当)。
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    task_id: str = Field(min_length=1)
    member_id: Annotated[str | None, BeforeValidator(empty_str_to_none)] = None
    label: Annotated[str | None, BeforeValidator(empty_str_to_none)] = None

    @model_validator(mode="after")
    def _member_id_xor_label(self) -> Self:
        if (self.member_id is None) == (self.label is None):
            raise ValueError("member_id と label はどちらか一方のみ指定する")
        return self
