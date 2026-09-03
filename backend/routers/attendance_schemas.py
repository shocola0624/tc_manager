from pydantic import BaseModel

from sheets.schemas import AttendanceStatus


class AttendanceUpdateRequest(BaseModel):
    status: AttendanceStatus
