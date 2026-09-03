from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from ._coerce import parse_bool_default_true
from .common import Category, Storage


class Item(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    item_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)  # discord_user_id または CIRCLE_OWNER_ID
    name: str = Field(min_length=1)
    maker: str = ""
    category: Category
    storage: Storage
    note: str = ""
    # 論理削除フラグ。物理削除すると assignments の追記ログが参照する item_id が
    # 解決不能になるため、削除は is_active=FALSE への更新として扱う。
    is_active: Annotated[bool, BeforeValidator(parse_bool_default_true)] = True
