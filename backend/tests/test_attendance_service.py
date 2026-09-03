from attendance_service import set_attendance
from sheets.repository import SheetRepository
from sheets.schemas import AttendanceStatus

ATTENDANCE_HEADER = ["activity_id", "discord_user_id", "status", "updated_at"]


def _repo(fake_client_factory, rows=None) -> SheetRepository:
    client = fake_client_factory("attendance", header=ATTENDANCE_HEADER, rows=rows or [])
    return SheetRepository(client, "attendance")


def test_set_attendance_appends_when_no_existing_row(fake_client_factory):
    repo = _repo(fake_client_factory)

    result = set_attendance(repo, "activity_1", "u1", AttendanceStatus.ATTENDING)

    assert result.status == AttendanceStatus.ATTENDING
    stored = repo.read_all()
    assert len(stored) == 1
    assert stored[0]["activity_id"] == "activity_1"
    assert stored[0]["discord_user_id"] == "u1"
    assert stored[0]["status"] == "attending"
    assert stored[0]["updated_at"]


def test_set_attendance_updates_existing_row_in_place(fake_client_factory):
    repo = _repo(
        fake_client_factory,
        rows=[["activity_1", "u1", "undecided", "2026-01-01T00:00:00+09:00"]],
    )

    set_attendance(repo, "activity_1", "u1", AttendanceStatus.ABSENT)

    stored = repo.read_all()
    assert len(stored) == 1
    assert stored[0]["status"] == "absent"


def test_set_attendance_is_keyed_by_activity_and_user(fake_client_factory):
    repo = _repo(
        fake_client_factory,
        rows=[["activity_1", "u1", "attending", "2026-01-01T00:00:00+09:00"]],
    )

    set_attendance(repo, "activity_1", "u2", AttendanceStatus.ATTENDING)

    stored = repo.read_all()
    assert len(stored) == 2
