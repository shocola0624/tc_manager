from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from ._coerce import empty_str_to_none, parse_bool_default_true


class Activity(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    activity_id: str = Field(min_length=1)
    starts_at: datetime
    duration_min: int
    location: str = ""
    title: str = Field(min_length=1)
    description: str = ""
    target: str = ""
    owner_id: str = Field(min_length=1)
    tasks: str = ""
    note: str = ""
    announce_message_id: Annotated[str | None, BeforeValidator(empty_str_to_none)] = None
    # 論理削除フラグ。attendance/assignments が activity_id を参照し続けるため、
    # 削除は物理削除ではなく is_active=FALSE への更新として扱う(items と同じ方針)。
    is_active: Annotated[bool, BeforeValidator(parse_bool_default_true)] = True
