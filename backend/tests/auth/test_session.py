import time

from auth.session import CookieSpec, SessionSigner


def test_sign_then_unsign_round_trip():
    signer = SessionSigner("secret")
    spec = CookieSpec(name="c", salt="s", max_age_seconds=60)

    token = signer.sign(spec, {"discord_user_id": "u1"})

    assert signer.unsign(spec, token) == {"discord_user_id": "u1"}


def test_unsign_rejects_tampered_token():
    signer = SessionSigner("secret")
    spec = CookieSpec(name="c", salt="s", max_age_seconds=60)

    token = signer.sign(spec, {"discord_user_id": "u1"})

    assert signer.unsign(spec, token + "tampered") is None


def test_unsign_rejects_garbage_token():
    signer = SessionSigner("secret")
    spec = CookieSpec(name="c", salt="s", max_age_seconds=60)

    assert signer.unsign(spec, "not-a-real-token") is None


def test_unsign_rejects_expired_token():
    signer = SessionSigner("secret")
    spec = CookieSpec(name="c", salt="s", max_age_seconds=0)

    token = signer.sign(spec, {"discord_user_id": "u1"})
    time.sleep(1.05)

    assert signer.unsign(spec, token) is None


def test_different_salts_are_not_interchangeable():
    signer = SessionSigner("secret")
    spec_a = CookieSpec(name="a", salt="salt-a", max_age_seconds=60)
    spec_b = CookieSpec(name="b", salt="salt-b", max_age_seconds=60)

    token = signer.sign(spec_a, {"discord_user_id": "u1"})

    assert signer.unsign(spec_b, token) is None


def test_different_secret_key_cannot_verify_token():
    signer_a = SessionSigner("secret-a")
    signer_b = SessionSigner("secret-b")
    spec = CookieSpec(name="c", salt="s", max_age_seconds=60)

    token = signer_a.sign(spec, {"discord_user_id": "u1"})

    assert signer_b.unsign(spec, token) is None
