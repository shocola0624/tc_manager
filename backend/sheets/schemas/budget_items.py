from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from ._coerce import parse_bool_default_true


class BudgetItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    budget_item_id: str = Field(min_length=1)
    activity_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    amount_jpy: int
    # 論理削除フラグ。items と同じ方針(空欄は TRUE として扱う)。
    is_active: Annotated[bool, BeforeValidator(parse_bool_default_true)] = True
