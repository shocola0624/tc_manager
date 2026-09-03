from __future__ import annotations

import json

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from nacl.signing import SigningKey

from discord_bot.signature import verify_discord_signature
from errors import install_exception_handlers


class _Settings:
    def __init__(self, public_key_hex: str) -> None:
        self.discord_public_key = public_key_hex


def _build_app(public_key_hex: str) -> FastAPI:
    app = FastAPI()
    install_exception_handlers(app)
    app.state.auth_settings = _Settings(public_key_hex)

    @app.post("/echo")
    async def echo(body: bytes = Depends(verify_discord_signature)):
        return json.loads(body)

    return app


@pytest.fixture
def signing_key() -> SigningKey:
    return SigningKey.generate()


def _sign(signing_key: SigningKey, timestamp: str, body: bytes) -> str:
    return signing_key.sign(timestamp.encode() + body).signature.hex()


def test_valid_signature_passes_body_through(signing_key):
    public_key_hex = signing_key.verify_key.encode().hex()
    app = _build_app(public_key_hex)
    client = TestClient(app)

    body = json.dumps({"type": 1}).encode()
    timestamp = "1700000000"
    signature = _sign(signing_key, timestamp, body)

    response = client.post(
        "/echo",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature-Ed25519": signature,
            "X-Signature-Timestamp": timestamp,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"type": 1}


def test_tampered_body_is_rejected(signing_key):
    public_key_hex = signing_key.verify_key.encode().hex()
    app = _build_app(public_key_hex)
    client = TestClient(app)

    timestamp = "1700000000"
    signature = _sign(signing_key, timestamp, json.dumps({"type": 1}).encode())

    response = client.post(
        "/echo",
        content=json.dumps({"type": 999}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Signature-Ed25519": signature,
            "X-Signature-Timestamp": timestamp,
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_discord_signature"


def test_signature_from_wrong_key_is_rejected(signing_key):
    public_key_hex = signing_key.verify_key.encode().hex()
    app = _build_app(public_key_hex)
    client = TestClient(app)

    other_key = SigningKey.generate()
    body = json.dumps({"type": 1}).encode()
    timestamp = "1700000000"
    signature = _sign(other_key, timestamp, body)

    response = client.post(
        "/echo",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Signature-Ed25519": signature,
            "X-Signature-Timestamp": timestamp,
        },
    )

    assert response.status_code == 401


def test_missing_headers_are_rejected(signing_key):
    public_key_hex = signing_key.verify_key.encode().hex()
    app = _build_app(public_key_hex)
    client = TestClient(app)

    response = client.post("/echo", json={"type": 1})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_discord_signature"


def test_malformed_signature_hex_is_rejected(signing_key):
    public_key_hex = signing_key.verify_key.encode().hex()
    app = _build_app(public_key_hex)
    client = TestClient(app)

    response = client.post(
        "/echo",
        content=json.dumps({"type": 1}).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Signature-Ed25519": "not-hex",
            "X-Signature-Timestamp": "1700000000",
        },
    )

    assert response.status_code == 401
