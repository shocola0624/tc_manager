from datetime import datetime

from pydantic import BaseModel, Field


class ActivityCreateRequest(BaseModel):
    starts_at: datetime
    duration_min: int
    location: str = ""
    title: str = Field(min_length=1)
    description: str = ""
    target: str = ""
    owner_id: str = Field(min_length=1)
    tasks: str = ""
    note: str = ""


class ActivityUpdateRequest(BaseModel):
    starts_at: datetime | None = None
    duration_min: int | None = None
    location: str | None = None
    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    target: str | None = None
    owner_id: str | None = Field(default=None, min_length=1)
    tasks: str | None = None
    note: str | None = None
