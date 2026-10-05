from pydantic import BaseModel, Field

from sheets.schemas import Role


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class UpdateProfileRequest(BaseModel):
    """自分自身の氏名・学年のみを更新する(role/is_active/locale は対象外)。"""

    name: str = Field(min_length=1, max_length=100)
    grade: str = Field(default="", max_length=20)


class CurrentUserResponse(BaseModel):
    discord_user_id: str
    name: str
    role: Role
    is_active: bool
    locale: str
    grade: str = ""
