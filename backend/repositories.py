from fastapi import Request

from sheets.repository import AppendOnlyRepository, SheetRepository


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
