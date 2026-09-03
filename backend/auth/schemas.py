from pydantic import BaseModel, Field

from sheets.schemas import Role


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CurrentUserResponse(BaseModel):
    discord_user_id: str
    name: str
    role: Role
    is_active: bool
    locale: str
