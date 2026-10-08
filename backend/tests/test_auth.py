import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit
import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from app import google_auth as google
from app.db import connect
from app.security import (
    AUDIENCE,
    COOKIE,
    ISSUER,
    REFRESH_COOKIE,
    decode_access,
    digest,
    signing_key,
)


def test_access_jwt_signature_and_cookie_protection(account):
    token = account.cookies.get(COOKIE)
    claims = decode_access(token)
    assert claims["iss"] == ISSUER and claims["aud"] == AUDIENCE
    assert claims["exp"] - claims["iat"] <= 900
    assert claims["jti"] != account.cookies.get(REFRESH_COOKIE)
    with connect() as con:
        assert con.execute("SELECT token_hash FROM sessions").fetchone()[0] == digest(
            claims["jti"]
        )
        assert con.execute("SELECT token_hash FROM refresh_tokens").fetchone()[
            0
        ] == digest(account.cookies.get(REFRESH_COOKIE))
    assert (
        account.get(
            "/api/state", headers={"Authorization": "Bearer " + token}
        ).status_code
        == 200
    )
    assert (
        account.get(
            "/api/state", headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"exp": int(time.time()) - 60},
        {"iss": "wrong"},
        {"aud": "wrong"},
        {"iat": int(time.time()) + 3600},
        {"token_use": "refresh"},
        {"sub": "invalid"},
        {"jti": "unknown-session"},
        {"sub": "999999"},
    ],
)
def test_invalid_signed_access_claims_are_rejected(account, changes):
    claims = decode_access(account.cookies.get(COOKIE))
    claims.update(changes)
    token = jwt.encode(claims, signing_key(), algorithm="HS256")
    assert (
        account.get(
            "/api/state", headers={"Authorization": "Bearer " + token}
        ).status_code
        == 401
    )


def test_access_algorithms_and_missing_claims(account):
    claims = decode_access(account.cookies.get(COOKIE))
    for token in (
        jwt.encode(claims, "wrong-key-at-least-32-characters", algorithm="HS256"),
        jwt.encode(claims, None, algorithm="none"),
        jwt.encode(claims, signing_key(), algorithm="HS384"),
    ):
        assert (
            account.get(
                "/api/state", headers={"Authorization": "Bearer " + token}
            ).status_code
            == 401
        )
    for name in ("sub", "exp", "iat", "jti", "iss", "aud", "token_use"):
        data = {k: v for k, v in claims.items() if k != name}
        assert (
            account.get(
                "/api/state",
                headers={
                    "Authorization": "Bearer "
                    + jwt.encode(data, signing_key(), algorithm="HS256")
                },
            ).status_code
            == 401
        )


def test_refresh_rotation_replay_and_logout(account):
    old_access = account.cookies.get(COOKIE)
    old_refresh = account.cookies.get(REFRESH_COOKIE)
    with connect() as con:
        expiry = con.execute("SELECT expires_at FROM sessions").fetchone()[0]
    result = account.post("/api/auth/refresh")
    assert result.status_code == 200
    assert (
        "HttpOnly" in result.headers["set-cookie"]
        and "SameSite=strict" in result.headers["set-cookie"]
    )
    assert account.cookies.get(REFRESH_COOKIE) != old_refresh
    assert (
        account.get(
            "/api/state", headers={"Authorization": "Bearer " + old_access}
        ).status_code
        == 401
    )
    with connect() as con:
        assert con.execute("SELECT expires_at FROM sessions").fetchone()[0] == expiry
    assert (
        account.post(
            "/api/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE}={old_refresh}"}
        ).status_code
        == 401
    )
    new_access = account.cookies.get(COOKIE)
    new_refresh = account.cookies.get(REFRESH_COOKIE)
    account.post("/api/auth/logout")
    assert (
        account.get(
            "/api/state", headers={"Authorization": "Bearer " + new_access}
        ).status_code
        == 401
    )
    assert (
        account.post(
            "/api/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE}={new_refresh}"}
        ).status_code
        == 401
    )
    with connect() as con:
        assert con.execute("SELECT COUNT(*) FROM refresh_tokens").fetchone()[0] == 0


def test_refresh_credential_is_not_the_access_jti(account):
    claims = decode_access(account.cookies.get(COOKIE))
    assert (
        account.post(
            "/api/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE}={claims['jti']}"}
        ).status_code
        == 401
    )
    assert (
        account.post("/api/auth/refresh", headers={"X-Evolve-Request": ""}).status_code
        == 403
    )
    assert (
        account.post(
            "/api/auth/refresh", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_access_expiry_can_be_refreshed_and_expired_session_cannot(account):
    claims = decode_access(account.cookies.get(COOKIE))
    claims["exp"] = int(time.time()) - 1
    expired = jwt.encode(claims, signing_key(), algorithm="HS256")
    assert (
        account.get(
            "/api/state", headers={"Authorization": "Bearer " + expired}
        ).status_code
        == 401
    )
    assert account.post("/api/auth/refresh").status_code == 200
    with connect() as con:
        con.execute("UPDATE sessions SET expires_at='2000-01-01T00:00:00+00:00'")
    assert account.post("/api/auth/refresh").status_code == 401
    assert account.get("/api/state").status_code == 401


def test_signing_configuration_and_export_secrets(account, monkeypatch):
    exported = account.get("/api/export").text
    for value in (
        account.cookies.get(COOKIE),
        account.cookies.get(REFRESH_COOKIE),
        signing_key(),
    ):
        assert value not in exported
    monkeypatch.setenv("EVOLVE_JWT_SECRET", "too-short")
    with pytest.raises(RuntimeError):
        signing_key()
    monkeypatch.delenv("EVOLVE_JWT_SECRET")
    monkeypatch.setenv("EVOLVE_SECURE_COOKIES", "true")
    with pytest.raises(RuntimeError):
        signing_key()
    monkeypatch.setenv("EVOLVE_SECURE_COOKIES", "false")
    assert signing_key() == signing_key()


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv(
        "EVOLVE_GOOGLE_CLIENT_ID", "unit-client.apps.googleusercontent.com"
    )
    monkeypatch.setenv("EVOLVE_GOOGLE_CLIENT_SECRET", "test-google-secret")
    monkeypatch.setenv(
        "EVOLVE_GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback"
    )
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public.update(kid="test-key", alg="RS256", use="sig")
    jwks = jwt.PyJWKClient("https://www.googleapis.com/oauth2/v3/certs")
    monkeypatch.setattr(jwks, "fetch_data", lambda: {"keys": [public]})
    monkeypatch.setattr(google, "JWKS", jwks)
    state = {"private": private, "changes": {}, "status": 200, "request": None}
    original = httpx.Client

    def handle(request):
        state["request"] = parse_qs(request.content.decode())
        assert request.url == "https://oauth2.googleapis.com/token"
        with connect() as con:
            # attempt has already been consumed; nonce was captured from start URL.
            assert con.execute("SELECT COUNT(*) FROM oauth_attempts").fetchone()[0] == 0
        claims = {
            "sub": "google-subject-1",
            "email": "google@example.com",
            "email_verified": True,
            "name": "Google Learner",
            "iss": "https://accounts.google.com",
            "aud": "unit-client.apps.googleusercontent.com",
            "nonce": state["nonce"],
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        claims.update(state["changes"])
        return httpx.Response(
            state["status"],
            json={
                "id_token": jwt.encode(
                    claims,
                    state["private"],
                    algorithm="RS256",
                    headers={"kid": "test-key"},
                )
            },
        )

    monkeypatch.setattr(
        google.httpx,
        "Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs),
    )
    return state


def start(client, provider, intent="login", password=""):
    response = client.post(
        "/api/auth/google/start", json={"intent": intent, "password": password}
    )
    assert response.status_code == 200, response.text
    params = parse_qs(urlsplit(response.json()["url"]).query)
    provider["nonce"] = params["nonce"][0]
    return params


def callback(client, params, **extra):
    return client.get(
        "/api/auth/google/callback",
        params={"state": params["state"][0], "code": "test-code", **extra},
        follow_redirects=False,
    )


def test_google_unconfigured_is_explicit(client):
    assert client.get("/api/auth/config").json()["google_enabled"] is False
    assert client.post("/api/auth/google/start", json={}).status_code == 503
    assert "EVOLVE_GOOGLE_CLIENT_SECRET" not in client.get("/api/auth/config").text


def test_google_invalid_callback_configuration_is_disabled(client, monkeypatch):
    monkeypatch.setenv("EVOLVE_GOOGLE_CLIENT_ID", "configured-client")
    monkeypatch.setenv("EVOLVE_GOOGLE_CLIENT_SECRET", "private-test-secret")
    for redirect in (
        "http://example.com/api/auth/google/callback",
        "http://localhost:bad/api/auth/google/callback",
        "http://[invalid/api/auth/google/callback",
        "https://example.com/other-path",
        "https://user:password@example.com/api/auth/google/callback",
        "https://example.com/api/auth/google/callback?extra=1",
    ):
        monkeypatch.setenv("EVOLVE_GOOGLE_REDIRECT_URI", redirect)
        assert client.get("/api/auth/config").json()["google_enabled"] is False
        assert client.post("/api/auth/google/start", json={}).status_code == 503


def test_google_state_requires_the_initiating_browser_cookie(client, provider):
    params = start(client, provider)
    client.cookies.clear()
    assert callback(client, params).status_code == 403
    assert provider["request"] is None


def test_google_signup_relogin_jwt_and_pkce(client, provider):
    params = start(client, provider)
    assert params["scope"] == ["openid email profile"]
    assert params["code_challenge_method"] == ["S256"]
    assert callback(client, params).headers["location"] == "/#profile"
    sent = provider["request"]
    challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(sent["code_verifier"][0].encode()).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    assert challenge == params["code_challenge"][0]
    first = client.get("/api/auth/me").json()
    assert first["auth"]["google_linked"] and not first["auth"]["has_password"]
    assert decode_access(client.cookies.get(COOKIE))["sub"] == str(first["id"])
    assert client.post("/api/auth/refresh").status_code == 200
    client.post("/api/auth/logout")
    params = start(client, provider)
    assert callback(client, params).headers["location"] == "/#today"
    assert client.get("/api/auth/me").json()["id"] == first["id"]


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://attacker.example"},
        {"aud": "different-client"},
        {"azp": "different-client"},
        {"nonce": "wrong"},
        {"email_verified": False},
        {"exp": int(time.time()) - 60},
        {"iat": int(time.time()) + 7200},
        {"email": "not-an-email"},
        {"sub": ""},
    ],
)
def test_google_invalid_identity_rejected(client, provider, changes):
    provider["changes"] = changes
    params = start(client, provider)
    response = callback(client, params)
    assert response.headers["location"] == "/?auth_error=google-unavailable"
    assert client.get("/api/auth/me").status_code == 401
    with connect() as con:
        assert con.execute("SELECT COUNT(*) FROM identities").fetchone()[0] == 0


def test_google_signature_and_state_rejected(client, provider):
    params = start(client, provider)
    assert (
        client.get(
            "/api/auth/google/callback", params={"state": "wrong", "code": "x"}
        ).status_code
        == 403
    )
    assert provider["request"] is None
    provider["private"] = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert (
        callback(client, params).headers["location"]
        == "/?auth_error=google-unavailable"
    )
    assert callback(client, params).status_code == 403


def test_google_state_expiry_cancel_and_provider_error(client, provider):
    params = start(client, provider)
    with connect() as con:
        con.execute("UPDATE oauth_attempts SET expires_at='2000-01-01T00:00:00+00:00'")
    assert callback(client, params).status_code == 403
    params = start(client, provider)
    assert (
        callback(client, params, error="access_denied").headers["location"]
        == "/?auth_error=google-cancelled"
    )
    params = start(client, provider)
    provider["status"] = 400
    assert (
        callback(client, params).headers["location"]
        == "/?auth_error=google-unavailable"
    )


def test_google_collision_requires_password_and_explicit_link(account, provider):
    provider["changes"] = {"email": "learner@example.com"}
    uid = account.get("/api/auth/me").json()["id"]
    params = start(account, provider)
    assert (
        callback(account, params).headers["location"] == "/?auth_error=account-exists"
    )
    assert (
        account.post(
            "/api/auth/google/start", json={"intent": "link", "password": "wrong"}
        ).status_code
        == 401
    )
    params = start(account, provider, intent="link", password="a-long-test-password")
    assert (
        callback(account, params).headers["location"] == "/?auth=google-linked#settings"
    )
    assert account.get("/api/auth/me").json()["id"] == uid
    assert account.get("/api/auth/me").json()["auth"]["google_linked"]
    account.post("/api/auth/logout")
    params = start(account, provider)
    assert callback(account, params).headers["location"] == "/#today"
    assert account.get("/api/auth/me").json()["id"] == uid


def test_google_link_wrong_account_and_revoked_session(account, provider):
    params = start(account, provider, intent="link", password="a-long-test-password")
    assert (
        callback(account, params).headers["location"]
        == "/?auth_error=different-account"
    )
    params = start(account, provider, intent="link", password="a-long-test-password")
    account.post("/api/auth/logout")
    assert callback(account, params).status_code == 403
    with connect() as con:
        assert con.execute("SELECT COUNT(*) FROM identities").fetchone()[0] == 0


def test_google_only_delete_requires_matching_identity(client, provider):
    params = start(client, provider)
    callback(client, params)
    assert (
        client.request("DELETE", "/api/account", json={"password": ""}).status_code
        == 409
    )
    params = start(client, provider, intent="delete")
    provider["changes"] = {"sub": "different-subject"}
    assert (
        callback(client, params).headers["location"] == "/?auth_error=different-account"
    )
    provider["changes"] = {}
    params = start(client, provider, intent="delete")
    assert callback(client, params).headers["location"] == "/?auth=account-deleted"
    assert client.get("/api/auth/me").status_code == 401
    with connect() as con:
        for table in (
            "users",
            "identities",
            "sessions",
            "refresh_tokens",
            "oauth_attempts",
        ):
            assert con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_google_demo_cannot_link(client, provider):
    client.post("/api/auth/demo", json={})
    assert (
        client.post(
            "/api/auth/google/start", json={"intent": "link", "password": "x"}
        ).status_code
        == 409
    )
