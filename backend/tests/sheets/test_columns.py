from sheets.columns import build_column_index, record_to_row, row_to_record


def test_build_column_index_maps_names_regardless_of_order():
    header = ["name", "discord_user_id", "role"]
    assert build_column_index(header) == {"name": 0, "discord_user_id": 1, "role": 2}


def test_build_column_index_ignores_empty_header_cells():
    header = ["name", "", "role"]
    assert build_column_index(header) == {"name": 0, "role": 2}


def test_row_to_record_pads_missing_trailing_cells():
    column_index = {"a": 0, "b": 1, "c": 2}
    assert row_to_record(["x", "y"], column_index) == {"a": "x", "b": "y", "c": ""}


def test_record_to_row_round_trip_is_order_independent():
    header = ["b", "a", "c"]
    column_index = build_column_index(header)
    record = {"a": "1", "b": "2", "c": "3"}

    row = record_to_row(record, column_index)

    assert row == ["2", "1", "3"]
    assert row_to_record(row, column_index) == record


def test_record_to_row_fills_unspecified_columns_with_empty_string():
    column_index = {"a": 0, "b": 1}
    assert record_to_row({"a": "1"}, column_index) == ["1", ""]
