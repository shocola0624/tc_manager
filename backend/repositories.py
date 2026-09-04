from fastapi import Depends, Request

from sheets.client import SheetsClient
from sheets.repository import AppendOnlyRepository, SheetRepository, ViewBackedRepository


def get_sheets_client(request: Request) -> SheetsClient:
    return request.app.state.sheets_client


def get_activities_current_window_repository(
    client: SheetsClient = Depends(get_sheets_client),
) -> ViewBackedRepository:
    """直近(過去1週間〜今後)の活動のみの軽量版(CLAUDE.md §9)。view_activities_current
    が読めなければ activities 全体へ自動フォールバックする。"""
    return ViewBackedRepository(
        client, source_sheet_name="activities", view_sheet_name="view_activities_current"
    )


def get_attendance_current_window_repository(
    client: SheetsClient = Depends(get_sheets_client),
) -> ViewBackedRepository:
    """直近の活動に紐づく出欠のみの軽量版(CLAUDE.md §9)。view_attendance_current が
    読めなければ attendance 全体へ自動フォールバックする。"""
    return ViewBackedRepository(
        client, source_sheet_name="attendance", view_sheet_name="view_attendance_current"
    )


def get_users_repository(request: Request) -> SheetRepository:
    return request.app.state.users_repo


def get_items_repository(request: Request) -> SheetRepository:
    return request.app.state.items_repo


def get_activities_repository(request: Request) -> SheetRepository:
    return request.app.state.activities_repo


def get_attendance_repository(request: Request) -> SheetRepository:
    return request.app.state.attendance_repo


def get_assignments_repository(request: Request) -> AppendOnlyRepository:
    return request.app.state.assignments_repo


def get_budget_items_repository(request: Request) -> SheetRepository:
    return request.app.state.budget_items_repo
