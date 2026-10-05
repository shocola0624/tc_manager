import pytest

from auth.config import AuthSettings
from sheets.repository import SheetRepository

USERS_HEADER = ["discord_user_id", "name", "role", "is_active", "locale", "registered_at", "grade"]


@pytest.fixture
def auth_settings() -> AuthSettings:
    return AuthSettings(
        discord_client_id="client-id",
        discord_client_secret="client-secret",
        discord_redirect_uri="http://localhost:8000/auth/discord/callback",
        discord_bot_token="bot-token",
        discord_guild_id="guild-1",
        discord_admin_role_id="role-admin",
        discord_officer_role_id="role-officer",
        discord_public_key="ab" * 32,
        discord_announce_channel_id="channel-1",
        discord_confirm_announce_channel_id="confirm-channel-1",
        discord_log_channel_id="log-channel-1",
        session_secret_key="test-secret-key",
        frontend_base_url="http://localhost:5173",
        cookie_secure=False,
    )


@pytest.fixture
def users_repo(fake_client_factory) -> SheetRepository:
    client = fake_client_factory("users", header=USERS_HEADER, rows=[])
    return SheetRepository(client, "users")
