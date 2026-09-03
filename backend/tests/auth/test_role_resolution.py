from auth.config import AuthSettings
from auth.role_resolution import resolve_role
from sheets.schemas import Role


def test_no_guild_membership_defaults_to_member(auth_settings):
    assert resolve_role(None, auth_settings) == Role.MEMBER


def test_empty_role_list_defaults_to_member(auth_settings):
    assert resolve_role([], auth_settings) == Role.MEMBER


def test_admin_role_id_present_resolves_to_admin(auth_settings):
    assert resolve_role(["role-admin", "some-other-role"], auth_settings) == Role.ADMIN


def test_officer_role_id_present_resolves_to_officer(auth_settings):
    assert resolve_role(["role-officer"], auth_settings) == Role.OFFICER


def test_admin_takes_priority_over_officer(auth_settings):
    assert resolve_role(["role-officer", "role-admin"], auth_settings) == Role.ADMIN


def test_unrelated_roles_default_to_member(auth_settings):
    assert resolve_role(["some-other-role"], auth_settings) == Role.MEMBER


def test_missing_configured_role_ids_default_to_member():
    settings = AuthSettings(
        discord_client_id="x",
        discord_client_secret="x",
        discord_redirect_uri="x",
        discord_bot_token="x",
        discord_guild_id="x",
        discord_admin_role_id=None,
        discord_officer_role_id=None,
        discord_public_key="x",
        discord_announce_channel_id="x",
        discord_confirm_announce_channel_id="x",
        session_secret_key="x",
        frontend_base_url="x",
        cookie_secure=False,
    )
    assert resolve_role(["anything"], settings) == Role.MEMBER
