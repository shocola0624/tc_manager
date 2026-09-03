from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from ._coerce import empty_str_to_none, parse_bool
from .common import Role


class User(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    discord_user_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    role: Role
    is_active: Annotated[bool, BeforeValidator(parse_bool)]
    locale: str = "ja"
    registered_at: Annotated[datetime | None, BeforeValidator(empty_str_to_none)] = None
