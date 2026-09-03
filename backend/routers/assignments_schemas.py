from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

from sheets.schemas import Item


class AssignmentAddRequest(BaseModel):
    activity_id: str = Field(min_length=1)
    item_id: str | None = None
    custom_name: str | None = Field(default=None, min_length=1)
    assignee_id: str | None = None

    @model_validator(mode="after")
    def _item_id_xor_custom_name(self) -> Self:
        if (self.item_id is None) == (self.custom_name is None):
            raise ValueError("item_id と custom_name はどちらか一方のみ指定する")
        return self


class AssignmentRemoveRequest(BaseModel):
    activity_id: str = Field(min_length=1)
    item_id: str | None = None
    custom_name: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _item_id_xor_custom_name(self) -> Self:
        if (self.item_id is None) == (self.custom_name is None):
            raise ValueError("item_id と custom_name はどちらか一方のみ指定する")
        return self


class ItemCandidateOut(BaseModel):
    item: Item
    requires_assignee: bool
    default_assignee_id: str | None


class AssignmentSlotOut(BaseModel):
    activity_id: str
    item_id: str | None
    custom_name: str | None
    assignee_id: str | None
    last_action_at: datetime
    last_actor_id: str
