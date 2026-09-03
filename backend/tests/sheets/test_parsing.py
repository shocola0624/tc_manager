from sheets.parsing import parse_records
from sheets.schemas import AssignmentLogEntry, User


def _user_row(**overrides: str) -> dict[str, str]:
    row = {
        "discord_user_id": "u1",
        "name": "Alice",
        "role": "member",
        "is_active": "TRUE",
        "locale": "ja",
        "registered_at": "2026-01-01T00:00:00+09:00",
    }
    row.update(overrides)
    return row


def test_parse_records_accepts_well_formed_row():
    result = parse_records([_user_row()], User)

    assert len(result.valid) == 1
    assert result.invalid == []
    assert result.valid[0].discord_user_id == "u1"


def test_parse_records_treats_empty_registered_at_as_unregistered():
    result = parse_records([_user_row(registered_at="")], User)

    assert result.invalid == []
    assert result.valid[0].registered_at is None


def test_parse_records_rejects_unknown_role_code_value():
    result = parse_records([_user_row(role="unknown_role")], User)

    assert result.valid == []
    assert len(result.invalid) == 1
    assert result.invalid[0].reason


def test_parse_records_rejects_empty_required_field():
    result = parse_records([_user_row(discord_user_id="")], User)

    assert result.valid == []
    assert len(result.invalid) == 1


def test_parse_records_reports_correct_absolute_row_numbers_and_keeps_going():
    rows = [_user_row(), _user_row(role="unknown_role"), _user_row(discord_user_id="")]

    result = parse_records(rows, User, start_row_number=2)

    assert len(result.valid) == 1
    assert [row.row_number for row in result.invalid] == [3, 4]


def _assignment_row(**overrides: str) -> dict[str, str]:
    row = {
        "timestamp": "2026-01-01T00:00:00+09:00",
        "activity_id": "a1",
        "item_id": "i1",
        "custom_name": "",
        "assignee_id": "",
        "action": "add",
        "actor_id": "u1",
    }
    row.update(overrides)
    return row


def test_parse_records_rejects_assignment_row_with_both_item_id_and_custom_name():
    result = parse_records([_assignment_row(custom_name="borrowed dripper")], AssignmentLogEntry)

    assert result.valid == []
    assert len(result.invalid) == 1


def test_parse_records_rejects_assignment_row_with_neither_item_id_nor_custom_name():
    result = parse_records([_assignment_row(item_id="")], AssignmentLogEntry)

    assert result.valid == []
    assert len(result.invalid) == 1


def test_parse_records_accepts_assignment_row_with_only_custom_name():
    result = parse_records(
        [_assignment_row(item_id="", custom_name="borrowed dripper")], AssignmentLogEntry
    )

    assert len(result.valid) == 1
    assert result.invalid == []
