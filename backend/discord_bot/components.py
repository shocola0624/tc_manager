from __future__ import annotations

from dataclasses import dataclass

from sheets.schemas import AttendanceStatus

from .locales import translate

_CUSTOM_ID_PREFIX = "attendance"

# Discord Message Components API の定数(v10)。
_COMPONENT_TYPE_ACTION_ROW = 1
_COMPONENT_TYPE_BUTTON = 2

_BUTTON_STYLE_SUCCESS = 3
_BUTTON_STYLE_DANGER = 4
_BUTTON_STYLE_SECONDARY = 2

_BUTTON_STYLE_BY_STATUS: dict[AttendanceStatus, int] = {
    AttendanceStatus.ATTENDING: _BUTTON_STYLE_SUCCESS,
    AttendanceStatus.ABSENT: _BUTTON_STYLE_DANGER,
    AttendanceStatus.UNDECIDED: _BUTTON_STYLE_SECONDARY,
}

_LABEL_KEY_BY_STATUS: dict[AttendanceStatus, str] = {
    AttendanceStatus.ATTENDING: "button.attending",
    AttendanceStatus.ABSENT: "button.absent",
    AttendanceStatus.UNDECIDED: "button.undecided",
}


@dataclass(frozen=True)
class AttendanceButtonPress:
    activity_id: str
    status: AttendanceStatus


def build_attendance_custom_id(activity_id: str, status: AttendanceStatus) -> str:
    return f"{_CUSTOM_ID_PREFIX}:{activity_id}:{status.value}"


def parse_attendance_custom_id(custom_id: str) -> AttendanceButtonPress | None:
    """未知の custom_id(将来追加される他の機能のボタン等)は None を返し、呼び出し元で無視する。"""
    parts = custom_id.split(":", 2)
    if len(parts) != 3 or parts[0] != _CUSTOM_ID_PREFIX:
        return None
    _, activity_id, status_value = parts
    try:
        status = AttendanceStatus(status_value)
    except ValueError:
        return None
    if not activity_id:
        return None
    return AttendanceButtonPress(activity_id=activity_id, status=status)


def build_attendance_action_row(activity_id: str) -> dict:
    """出席/欠席/未定の3ボタンからなる action row(Discord message components)を返す。

    アナウンス本文自体が ja 固定のため、ボタンラベルも常に ja で組み立てる。
    """
    return {
        "type": _COMPONENT_TYPE_ACTION_ROW,
        "components": [
            {
                "type": _COMPONENT_TYPE_BUTTON,
                "style": _BUTTON_STYLE_BY_STATUS[status],
                "label": translate("ja", _LABEL_KEY_BY_STATUS[status]),
                "custom_id": build_attendance_custom_id(activity_id, status),
            }
            for status in AttendanceStatus
        ],
    }
