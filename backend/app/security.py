import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request, Response
from .db import connect

COOKIE = "evolve_session"
TTL = 60 * 60 * 24 * 7


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(value):
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(value.encode(), salt=salt, n=16384, r=8, p=1)
    return f"{salt.hex()}:{key.hex()}"


def verify(value, stored):
    try:
        salt, expected = stored.split(":")
        actual = hashlib.scrypt(
            value.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def session(response: Response, user_id, demo=False):
    token = secrets.token_urlsafe(48)
    ttl = 86400 if demo else TTL
    with connect() as con:
        con.execute("DELETE FROM sessions WHERE expires_at<?", (now(),))
        con.execute(
            "INSERT INTO sessions VALUES(?,?,?)",
            (
                digest(token),
                user_id,
                (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat(),
            ),
        )
    response.set_cookie(
        COOKIE,
        token,
        max_age=ttl,
        httponly=True,
        secure=os.getenv("EVOLVE_SECURE_COOKIES", "false").lower() == "true",
        samesite="strict",
        path="/",
    )


def current_user(request: Request):
    token = request.cookies.get(COOKIE, "")
    with connect() as con:
        user = con.execute(
            "SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?",
            (digest(token), now()),
        ).fetchone()
    if not user or (user["demo_expires"] and user["demo_expires"] <= now()):
        raise HTTPException(401, "Please sign in to continue")
    return dict(user)


def throttle(request: Request, email=""):
    key = digest(
        f"{request.client.host if request.client else 'unknown'}:{email.lower()}"
    )
    ip_key = digest(f"ip:{request.client.host if request.client else 'unknown'}")
    at = time.time()
    with connect() as con:
        con.execute("DELETE FROM auth_attempts WHERE at<?", (at - 900,))
        count = con.execute(
            "SELECT COUNT(*) FROM auth_attempts WHERE key=?", (key,)
        ).fetchone()[0]
        ip_count = con.execute(
            "SELECT COUNT(*) FROM auth_attempts WHERE key=?", (ip_key,)
        ).fetchone()[0]
        if count >= 10 or ip_count >= 60:
            raise HTTPException(429, "Too many attempts. Try again in 15 minutes.")
        con.executemany(
            "INSERT INTO auth_attempts VALUES(?,?)", [(key, at), (ip_key, at)]
        )
