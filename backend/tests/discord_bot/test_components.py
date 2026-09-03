from discord_bot.components import (
    AttendanceButtonPress,
    build_attendance_action_row,
    build_attendance_custom_id,
    parse_attendance_custom_id,
)
from sheets.schemas import AttendanceStatus


def test_custom_id_roundtrip():
    custom_id = build_attendance_custom_id("activity_1", AttendanceStatus.ATTENDING)

    assert custom_id == "attendance:activity_1:attending"
    assert parse_attendance_custom_id(custom_id) == AttendanceButtonPress(
        activity_id="activity_1", status=AttendanceStatus.ATTENDING
    )


def test_parse_rejects_unknown_prefix():
    assert parse_attendance_custom_id("other:activity_1:attending") is None


def test_parse_rejects_unknown_status():
    assert parse_attendance_custom_id("attendance:activity_1:maybe") is None


def test_parse_rejects_malformed_custom_id():
    assert parse_attendance_custom_id("attendance:onlytwo") is None
    assert parse_attendance_custom_id("") is None


def test_build_attendance_action_row_has_three_buttons_in_status_order():
    row = build_attendance_action_row("activity_1")

    buttons = row["components"]
    assert [b["custom_id"] for b in buttons] == [
        "attendance:activity_1:attending",
        "attendance:activity_1:absent",
        "attendance:activity_1:undecided",
    ]
    assert [b["label"] for b in buttons] == ["出席", "欠席", "未定"]
    # Success / Danger / Secondary(Discord Button Style 定数)
    assert [b["style"] for b in buttons] == [3, 4, 2]
