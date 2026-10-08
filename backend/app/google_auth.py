"""Google OpenID Connect code flow with PKCE, state, nonce and explicit linking."""

import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit
import httpx
import jwt
from fastapi import HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from .db import connect
from .models import GoogleStart, Profile, Register
from .security import (
    current_user,
    decode_access,
    digest,
    now,
    request_token,
    secure_cookies,
    session,
    throttle,
    verify,
    clear_cookies,
)

STATE_COOKIE = "evolve_google_state"
CALLBACK_PATH = "/api/auth/google/callback"
JWKS = jwt.PyJWKClient(
    "https://www.googleapis.com/oauth2/v3/certs", lifespan=300, timeout=10
)


def configuration():
    client = os.getenv("EVOLVE_GOOGLE_CLIENT_ID", "").strip()
    secret = os.getenv("EVOLVE_GOOGLE_CLIENT_SECRET", "").strip()
    redirect = os.getenv("EVOLVE_GOOGLE_REDIRECT_URI", "").strip()
    try:
        parsed = urlsplit(redirect)
        parsed.port
    except ValueError:
        return {
            "enabled": False,
            "client": client,
            "secret": secret,
            "redirect": redirect,
        }
    valid = bool(
        client
        and secret
        and parsed.hostname
        and parsed.path == CALLBACK_PATH
        and not parsed.query
        and not parsed.fragment
        and not parsed.username
        and not parsed.password
        and (
            parsed.scheme == "https"
            or (
                parsed.scheme == "http"
                and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
                and not secure_cookies()
            )
        )
    )
    return {"enabled": valid, "client": client, "secret": secret, "redirect": redirect}


def auth_status(user=None):
    linked = False
    if user:
        with connect() as con:
            linked = bool(
                con.execute(
                    "SELECT 1 FROM identities WHERE user_id=? AND provider='google'",
                    (user["id"],),
                ).fetchone()
            )
    return {
        "method": "jwt",
        "google_enabled": configuration()["enabled"],
        "google_linked": linked,
        "has_password": bool(user and user["password_hash"]),
        "access_token_minutes": 15,
    }


def begin(data: GoogleStart, request: Request, response: Response):
    cfg = configuration()
    if not cfg["enabled"]:
        raise HTTPException(503, "Google sign-in is not configured on this server")
    throttle(request, "google")
    uid = binding = None
    if data.intent != "login":
        user = current_user(request)
        if user["demo"]:
            raise HTTPException(
                409, "Google accounts cannot be connected to a demo workspace"
            )
        if data.intent == "link" and not verify(data.password, user["password_hash"]):
            raise HTTPException(
                401, "Confirm your account password before linking Google"
            )
        if data.intent == "delete" and user["password_hash"]:
            raise HTTPException(
                409, "Use your password to confirm deletion of this account"
            )
        uid = user["id"]
        binding = digest(decode_access(request_token(request))["jti"])
    state, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    expires = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    with connect() as con:
        con.execute("DELETE FROM oauth_attempts WHERE expires_at<?", (now(),))
        previous = request.cookies.get(STATE_COOKIE)
        if previous:
            con.execute(
                "DELETE FROM oauth_attempts WHERE state_hash=?", (digest(previous),)
            )
        con.execute(
            "INSERT INTO oauth_attempts VALUES(?,?,?,?,?,?,?)",
            (digest(state), nonce, verifier, expires, data.intent, uid, binding),
        )
    response.set_cookie(
        STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=secure_cookies(),
        samesite="lax",
        path=CALLBACK_PATH,
    )
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return {
        "url": "https://accounts.google.com/o/oauth2/v2/auth?"
        + urlencode(
            {
                "client_id": cfg["client"],
                "redirect_uri": cfg["redirect"],
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
    }


def exchange(code, verifier, cfg):
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        response = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": cfg["client"],
                "client_secret": cfg["secret"],
                "redirect_uri": cfg["redirect"],
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
        )
        response.raise_for_status()
        token = response.json().get("id_token")
    if not isinstance(token, str) or len(token) > 16384:
        raise ValueError("Missing identity token")
    return token


def identity(token, nonce, client_id):
    header = jwt.get_unverified_header(token)
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise ValueError("Unsupported Google signature")
    key = JWKS.get_signing_key_from_jwt(token).key
    claims = jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=client_id,
        options={
            "require": [
                "sub",
                "exp",
                "iat",
                "iss",
                "aud",
                "nonce",
                "email",
                "email_verified",
            ],
            "verify_iss": False,
        },
    )
    if claims["iss"] not in {"accounts.google.com", "https://accounts.google.com"}:
        raise ValueError("Invalid issuer")
    if (
        claims.get("azp", client_id) != client_id
        or claims["email_verified"] is not True
    ):
        raise ValueError("Unverified Google identity")
    if not isinstance(claims["nonce"], str) or not hmac.compare_digest(
        claims["nonce"].encode(), nonce.encode()
    ):
        raise ValueError("Invalid nonce")
    if (
        not isinstance(claims["sub"], str)
        or not claims["sub"]
        or len(claims["sub"]) > 255
    ):
        raise ValueError("Invalid subject")
    email = Register(
        name="Google user", email=claims["email"], password="validation-only"
    ).email
    return {
        "subject": claims["sub"],
        "email": email,
        "name": str(claims.get("name") or "Google user")[:80],
    }


def resolve(info, attempt):
    with connect() as con:
        linked = con.execute(
            "SELECT u.* FROM identities i JOIN users u ON u.id=i.user_id WHERE i.provider='google' AND i.subject=?",
            (info["subject"],),
        ).fetchone()
        if attempt["intent"] in {"link", "delete"}:
            owner = con.execute(
                "SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE u.id=? AND s.token_hash=? AND s.expires_at>?",
                (attempt["user_id"], attempt["session_hash"], now()),
            ).fetchone()
            if not owner:
                raise HTTPException(401, "expired-session")
            if attempt["intent"] == "delete":
                if not linked or linked["id"] != owner["id"] or owner["password_hash"]:
                    raise HTTPException(409, "different-account")
                con.execute("DELETE FROM users WHERE id=?", (owner["id"],))
                return None, False
            if info["email"] != owner["email"] or (
                linked and linked["id"] != owner["id"]
            ):
                raise HTTPException(409, "different-account")
            prior = con.execute(
                "SELECT subject FROM identities WHERE provider='google' AND user_id=?",
                (owner["id"],),
            ).fetchone()
            if prior and prior["subject"] != info["subject"]:
                raise HTTPException(409, "different-account")
            con.execute(
                "INSERT OR IGNORE INTO identities VALUES('google',?,?,?)",
                (info["subject"], owner["id"], info["email"]),
            )
            return dict(owner), False
        if linked:
            return dict(linked), False
        if con.execute(
            "SELECT 1 FROM users WHERE email=?", (info["email"],)
        ).fetchone():
            raise HTTPException(409, "account-exists")
        uid = con.execute(
            "INSERT INTO users(email,name,password_hash,profile,created_at) VALUES(?,?,?,?,?)",
            (info["email"], info["name"], "", Profile().model_dump_json(), now()),
        ).lastrowid
        con.execute(
            "INSERT INTO identities VALUES('google',?,?,?)",
            (info["subject"], uid, info["email"]),
        )
        return dict(
            con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        ), True


def finish(request: Request):
    cfg = configuration()
    state = request.query_params.get("state", "")
    cookie = request.cookies.get(STATE_COOKIE, "")
    if (
        not state
        or len(state) > 128
        or not cookie
        or not hmac.compare_digest(state.encode(), cookie.encode())
    ):
        raise HTTPException(
            403, "Invalid Google sign-in state. Return to the app and try again."
        )
    with connect() as con:
        attempt = con.execute(
            "DELETE FROM oauth_attempts WHERE state_hash=? AND expires_at>? RETURNING *",
            (digest(state), now()),
        ).fetchone()
    if not attempt:
        raise HTTPException(
            403, "Google sign-in expired or was already used. Start again."
        )
    error = None
    user = None
    created = False
    try:
        if request.query_params.get("error"):
            error = "google-cancelled"
        elif not cfg["enabled"]:
            error = "google-unavailable"
        else:
            code = request.query_params.get("code", "")
            if not code or len(code) > 4096:
                raise ValueError("Missing code")
            info = identity(
                exchange(code, attempt["verifier"], cfg),
                attempt["nonce"],
                cfg["client"],
            )
            user, created = resolve(info, attempt)
    except HTTPException as exc:
        error = exc.detail
    except (
        httpx.HTTPError,
        jwt.PyJWTError,
        ValueError,
        TypeError,
        KeyError,
        sqlite3.IntegrityError,
    ):
        error = "google-unavailable"
    target = (
        "/?auth_error=" + str(error)
        if error
        else (
            "/?auth=account-deleted"
            if user is None
            else "/?auth=google-linked#settings"
            if attempt["intent"] == "link"
            else "/#profile"
            if created
            else "/#today"
        )
    )
    response = RedirectResponse(target, status_code=303)
    response.delete_cookie(
        STATE_COOKIE,
        path=CALLBACK_PATH,
        httponly=True,
        secure=secure_cookies(),
        samesite="lax",
    )
    if not error:
        if user is None:
            clear_cookies(response)
        else:
            session(response, user["id"], request=request)
    return response
