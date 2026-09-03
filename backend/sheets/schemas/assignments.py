from datetime import datetime
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from ._coerce import empty_str_to_none
from .common import AssignmentAction


class AssignmentLogEntry(BaseModel):
    """assignments シートの1行。追記専用ログの要素。"""

    model_config = ConfigDict(str_strip_whitespace=True)

    timestamp: datetime
    activity_id: str = Field(min_length=1)
    item_id: Annotated[str | None, BeforeValidator(empty_str_to_none)] = None
    custom_name: Annotated[str | None, BeforeValidator(empty_str_to_none)] = None
    assignee_id: Annotated[str | None, BeforeValidator(empty_str_to_none)] = None
    action: AssignmentAction
    actor_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _item_id_xor_custom_name(self) -> Self:
        if (self.item_id is None) == (self.custom_name is None):
            raise ValueError("item_id と custom_name はどちらか一方のみ指定する")
        return self

    @property
    def slot_key(self) -> str:
        """(activity_id と組み合わせて)割り当て枠を一意に識別するキー"""
        assert self.item_id is not None or self.custom_name is not None
        return self.item_id if self.item_id is not None else f"custom:{self.custom_name}"
