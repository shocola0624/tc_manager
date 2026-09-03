from pydantic import BaseModel, Field

from sheets.schemas import Category, Storage


class ItemCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    maker: str = ""
    category: Category
    storage: Storage
    note: str = ""
    owner_id: str | None = None  # 省略時はログインユーザー自身


class ItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    maker: str | None = None
    category: Category | None = None
    storage: Storage | None = None
    note: str | None = None
