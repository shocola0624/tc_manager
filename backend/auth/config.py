from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    discord_client_id: str
    discord_client_secret: str
    discord_redirect_uri: str
    discord_bot_token: str
    discord_guild_id: str
    discord_admin_role_id: str | None = None
    discord_officer_role_id: str | None = None
    discord_public_key: str
    discord_announce_channel_id: str
    discord_confirm_announce_channel_id: str

    session_secret_key: str
    frontend_base_url: str
    cookie_secure: bool = True
