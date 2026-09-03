from sheets.parsing import parse_records
from sheets.schemas import Activity


def _activity_row(**overrides: str) -> dict[str, str]:
    row = {
        "activity_id": "activity_1",
        "starts_at": "2026-09-10T14:00:00+09:00",
        "duration_min": "120",
        "location": "部室",
        "title": "定例会",
        "description": "",
        "target": "",
        "owner_id": "u1",
        "tasks": "",
        "note": "",
        "announce_message_id": "",
    }
    row.update(overrides)
    return row


def test_missing_is_active_column_defaults_to_true():
    result = parse_records([_activity_row()], Activity)

    assert result.invalid == []
    assert result.valid[0].is_active is True


def test_empty_is_active_cell_defaults_to_true():
    result = parse_records([_activity_row(is_active="")], Activity)

    assert result.invalid == []
    assert result.valid[0].is_active is True


def test_explicit_false_is_respected():
    result = parse_records([_activity_row(is_active="FALSE")], Activity)

    assert result.invalid == []
    assert result.valid[0].is_active is False


def test_invalid_is_active_value_is_flagged_as_invalid_row():
    result = parse_records([_activity_row(is_active="maybe")], Activity)

    assert result.valid == []
    assert len(result.invalid) == 1
