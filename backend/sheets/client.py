from __future__ import annotations

from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from .config import Settings

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _quote_sheet_name(sheet_name: str) -> str:
    escaped = sheet_name.replace("'", "''")
    return f"'{escaped}'"


class SheetsClient:
    """Sheets API v4 への薄いラッパー。列名解決やモデル変換は行わず、
    セル値の生の読み書きのみを担当する。"""

    def __init__(self, service: Any, spreadsheet_id: str) -> None:
        self._service = service
        self._spreadsheet_id = spreadsheet_id

    @classmethod
    def from_settings(cls, settings: Settings) -> "SheetsClient":
        credentials = Credentials.from_service_account_file(
            settings.google_service_account_file, scopes=_SCOPES
        )
        service = build("sheets", "v4", credentials=credentials)
        return cls(service, settings.spreadsheet_id)

    def get_all_values(self, sheet_name: str) -> list[list[str]]:
        response = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, range=_quote_sheet_name(sheet_name))
            .execute()
        )
        return response.get("values", [])

    def get_header_row(self, sheet_name: str) -> list[str]:
        range_ = f"{_quote_sheet_name(sheet_name)}!1:1"
        response = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, range=range_)
            .execute()
        )
        rows = response.get("values", [])
        return rows[0] if rows else []

    def append_row(self, sheet_name: str, row: list[str]) -> None:
        self._service.spreadsheets().values().append(
            spreadsheetId=self._spreadsheet_id,
            range=_quote_sheet_name(sheet_name),
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

    def update_row(self, sheet_name: str, row_number_1based: int, row: list[str]) -> None:
        range_ = f"{_quote_sheet_name(sheet_name)}!A{row_number_1based}"
        self._service.spreadsheets().values().update(
            spreadsheetId=self._spreadsheet_id,
            range=range_,
            valueInputOption="RAW",
            body={"values": [row]},
        ).execute()

    def create_sheet(self, sheet_name: str) -> None:
        """新しいシートタブを追加する。運用上の初期セットアップ(1回限りの実行)向けで、
        通常のアプリのリクエストパスからは呼ばない(CLAUDE.md §1: シート構造は人間が作る)。"""
        self._service.spreadsheets().batchUpdate(
            spreadsheetId=self._spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": sheet_name}}}]},
        ).execute()
