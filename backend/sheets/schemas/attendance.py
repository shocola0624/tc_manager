from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .common import AttendanceStatus


class Attendance(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    activity_id: str = Field(min_length=1)
    discord_user_id: str = Field(min_length=1)
    status: AttendanceStatus
    updated_at: datetime
