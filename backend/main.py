from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.config import AuthSettings
from auth.discord_client import DiscordBotClient, DiscordOAuthClient
from auth.router import router as auth_router
from auth.session import SessionSigner
from discord_bot.router import router as discord_interactions_router
from errors import install_exception_handlers
from routers.activities import router as activities_router
from routers.assignments import router as assignments_router
from routers.attendance import router as attendance_router
from routers.budget_items import router as budget_items_router
from routers.items import router as items_router
from routers.users import router as users_router
from sheets.client import SheetsClient
from sheets.config import Settings as SheetsSettings
from sheets.repository import AppendOnlyRepository, SheetRepository


def create_app() -> FastAPI:
    auth_settings = AuthSettings()
    sheets_settings = SheetsSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            app.state.auth_settings = auth_settings
            app.state.http_client = http_client
            app.state.signer = SessionSigner(auth_settings.session_secret_key)
            app.state.oauth_client = DiscordOAuthClient(auth_settings, http_client)
            app.state.bot_client = DiscordBotClient(auth_settings, http_client)

            sheets_client = SheetsClient.from_settings(sheets_settings)
            app.state.sheets_client = sheets_client
            app.state.users_repo = SheetRepository(sheets_client, "users")
            app.state.items_repo = SheetRepository(sheets_client, "items")
            app.state.activities_repo = SheetRepository(sheets_client, "activities")
            app.state.attendance_repo = SheetRepository(sheets_client, "attendance")
            app.state.assignments_repo = AppendOnlyRepository(sheets_client, "assignments")
            app.state.budget_items_repo = SheetRepository(sheets_client, "budget_items")

            yield

    app = FastAPI(title="Techspresso for Students API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[auth_settings.frontend_base_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(discord_interactions_router)
    app.include_router(users_router)
    app.include_router(items_router)
    app.include_router(activities_router)
    app.include_router(attendance_router)
    app.include_router(assignments_router)
    app.include_router(budget_items_router)
    return app


app = create_app()
