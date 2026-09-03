from sheets.parsing import parse_records
from sheets.schemas import Item


def _item_row(**overrides: str) -> dict[str, str]:
    row = {
        "item_id": "item_1",
        "owner_id": "u1",
        "name": "V60",
        "maker": "Hario",
        "category": "dripper",
        "storage": "owner",
        "note": "",
    }
    row.update(overrides)
    return row


def test_missing_is_active_column_defaults_to_true():
    result = parse_records([_item_row()], Item)

    assert result.invalid == []
    assert result.valid[0].is_active is True


def test_empty_is_active_cell_defaults_to_true():
    result = parse_records([_item_row(is_active="")], Item)

    assert result.invalid == []
    assert result.valid[0].is_active is True


def test_explicit_false_is_respected():
    result = parse_records([_item_row(is_active="FALSE")], Item)

    assert result.invalid == []
    assert result.valid[0].is_active is False


def test_explicit_true_is_respected():
    result = parse_records([_item_row(is_active="TRUE")], Item)

    assert result.invalid == []
    assert result.valid[0].is_active is True


def test_invalid_is_active_value_is_flagged_as_invalid_row():
    result = parse_records([_item_row(is_active="maybe")], Item)

    assert result.valid == []
    assert len(result.invalid) == 1
