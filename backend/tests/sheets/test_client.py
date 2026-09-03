from unittest.mock import MagicMock

from sheets.client import SheetsClient


def _service_stub() -> MagicMock:
    return MagicMock()


def test_get_all_values_uses_quoted_range_and_spreadsheet_id():
    service = _service_stub()
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [["a", "b"]]
    }
    client = SheetsClient(service, "sheet123")

    result = client.get_all_values("users")

    assert result == [["a", "b"]]
    service.spreadsheets.return_value.values.return_value.get.assert_called_once_with(
        spreadsheetId="sheet123", range="'users'"
    )


def test_get_all_values_returns_empty_list_when_sheet_has_no_values():
    service = _service_stub()
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {}
    client = SheetsClient(service, "sheet123")

    assert client.get_all_values("users") == []


def test_append_row_uses_append_semantics_and_inserts_rows():
    service = _service_stub()
    client = SheetsClient(service, "sheet123")

    client.append_row("assignments", ["2026-09-01T00:00:00+09:00", "a1"])

    service.spreadsheets.return_value.values.return_value.append.assert_called_once_with(
        spreadsheetId="sheet123",
        range="'assignments'",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [["2026-09-01T00:00:00+09:00", "a1"]]},
    )


def test_update_row_targets_specific_row_number():
    service = _service_stub()
    client = SheetsClient(service, "sheet123")

    client.update_row("users", 3, ["u1", "Alice"])

    service.spreadsheets.return_value.values.return_value.update.assert_called_once_with(
        spreadsheetId="sheet123",
        range="'users'!A3",
        valueInputOption="RAW",
        body={"values": [["u1", "Alice"]]},
    )


def test_sheet_name_with_apostrophe_is_escaped_in_range():
    service = _service_stub()
    service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {}
    client = SheetsClient(service, "sheet123")

    client.get_all_values("it's a sheet")

    service.spreadsheets.return_value.values.return_value.get.assert_called_once_with(
        spreadsheetId="sheet123", range="'it''s a sheet'"
    )
