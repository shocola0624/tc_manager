from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from sheets.schemas import Role, Task, TaskStatus


class TaskAssigneeInput(BaseModel):
    """担当者1人分の指定。member_id(登録済みユーザー)か label(部門名などの自由記述)の
    どちらか一方のみを指定する(sheets/schemas/tasks.py の TaskAssignee と対になる)。"""

    member_id: str | None = None
    label: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def _member_id_xor_label(self) -> Self:
        if (self.member_id is None) == (self.label is None):
            raise ValueError("member_id と label はどちらか一方のみ指定する")
        return self


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    due_at: datetime
    visibility: Role
    related_activity_id: str | None = None
    reminder_offsets: str = ""
    assignees: list[TaskAssigneeInput] = Field(default_factory=list)


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    due_at: datetime | None = None
    status: TaskStatus | None = None
    visibility: Role | None = None
    related_activity_id: str | None = None
    reminder_offsets: str | None = None
    assignees: list[TaskAssigneeInput] | None = None


class TaskOut(Task):
    """一覧・作成・更新のレスポンス共通形。担当者一覧を結合して返す(CLAUDE.md §1)。"""

    assignees: list[TaskAssigneeInput] = Field(default_factory=list)
