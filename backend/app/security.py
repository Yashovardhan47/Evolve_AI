import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, Request, Response
from .db import connect

COOKIE = "evolve_session"
REFRESH_COOKIE = "evolve_refresh"
TTL = 60 * 60 * 24 * 7
ACCESS_TTL = 15 * 60
ISSUER = "evolve-ai"
AUDIENCE = "evolve-api"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def secure_cookies():
    return os.getenv("EVOLVE_SECURE_COOKIES", "false").lower() == "true"


def signing_key():
    configured = os.getenv("EVOLVE_JWT_SECRET", "")
    if configured:
        if len(configured.encode()) < 32:
            raise RuntimeError("EVOLVE_JWT_SECRET must contain at least 32 bytes")
        return configured
    if secure_cookies():
        raise RuntimeError("Set EVOLVE_JWT_SECRET before starting an HTTPS deployment")
    with connect() as con:
        con.execute(
            "INSERT OR IGNORE INTO app_keys VALUES('jwt',?)",
            (secrets.token_urlsafe(48),),
        )
        return con.execute("SELECT value FROM app_keys WHERE name='jwt'").fetchone()[0]


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


def decode_access(token):
    try:
        claims = jwt.decode(
            token,
            signing_key(),
            algorithms=["HS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={
                "require": ["sub", "jti", "iat", "exp", "iss", "aud", "token_use"]
            },
        )
        if (
            claims["token_use"] != "access"
            or not claims["sub"].isdigit()
            or not isinstance(claims["jti"], str)
        ):
            raise ValueError("Invalid token claims")
        return claims
    except (jwt.PyJWTError, ValueError, TypeError, AttributeError):
        raise HTTPException(401, "Please sign in to continue")


def request_token(request):
    authorization = request.headers.get("authorization")
    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(401, "Use a valid Bearer access token")
        return token
    return request.cookies.get(COOKIE, "")


def current_user(request: Request):
    claims = decode_access(request_token(request))
    with connect() as con:
        user = con.execute(
            "SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token_hash=? AND s.user_id=? AND s.expires_at>?",
            (digest(claims["jti"]), int(claims["sub"]), now()),
        ).fetchone()
    if not user or (user["demo_expires"] and user["demo_expires"] <= now()):
        raise HTTPException(401, "Please sign in to continue")
    return dict(user)


def clear_cookies(response):
    response.delete_cookie(
        COOKIE, path="/", secure=secure_cookies(), httponly=True, samesite="strict"
    )
    response.delete_cookie(
        REFRESH_COOKIE,
        path="/api/auth",
        secure=secure_cookies(),
        httponly=True,
        samesite="strict",
    )


def session(response: Response, user_id, demo=False, request=None, rotating=False):
    sid, refresh = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    key = signing_key()
    timestamp = datetime.now(timezone.utc)
    expires = timestamp + timedelta(seconds=86400 if demo else TTL)
    with connect() as con:
        con.execute("DELETE FROM sessions WHERE expires_at<?", (now(),))
        if request is not None:
            previous = digest(request.cookies.get(REFRESH_COOKIE, ""))
            if rotating:
                existing = con.execute(
                    "DELETE FROM sessions WHERE token_hash=(SELECT session_hash FROM refresh_tokens WHERE token_hash=?) AND user_id=? AND expires_at>? RETURNING expires_at",
                    (previous, user_id, now()),
                ).fetchone()
                if not existing:
                    raise HTTPException(401, "Please sign in to continue")
                expires = datetime.fromisoformat(existing["expires_at"])
            else:
                con.execute(
                    "DELETE FROM sessions WHERE token_hash=(SELECT session_hash FROM refresh_tokens WHERE token_hash=?)",
                    (previous,),
                )
        con.execute(
            "INSERT INTO sessions VALUES(?,?,?)",
            (digest(sid), user_id, expires.isoformat()),
        )
        con.execute(
            "INSERT INTO refresh_tokens VALUES(?,?)", (digest(refresh), digest(sid))
        )
    access_expiry = min(expires, timestamp + timedelta(seconds=ACCESS_TTL))
    token = jwt.encode(
        {
            "sub": str(user_id),
            "jti": sid,
            "iat": timestamp,
            "exp": access_expiry,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "token_use": "access",
        },
        key,
        algorithm="HS256",
    )
    response.set_cookie(
        COOKIE,
        token,
        max_age=max(1, int((access_expiry - timestamp).total_seconds())),
        httponly=True,
        secure=secure_cookies(),
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=max(1, int((expires - timestamp).total_seconds())),
        httponly=True,
        secure=secure_cookies(),
        samesite="strict",
        path="/api/auth",
    )


def refresh_session(request, response):
    with connect() as con:
        user = con.execute(
            "SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id JOIN refresh_tokens r ON r.session_hash=s.token_hash WHERE r.token_hash=? AND s.expires_at>?",
            (digest(request.cookies.get(REFRESH_COOKIE, "")), now()),
        ).fetchone()
    if not user or (user["demo_expires"] and user["demo_expires"] <= now()):
        raise HTTPException(401, "Please sign in to continue")
    session(response, user["id"], bool(user["demo"]), request=request, rotating=True)
    return dict(user)


def revoke_session(request):
    keys = set()
    with connect() as con:
        row = con.execute(
            "SELECT session_hash FROM refresh_tokens WHERE token_hash=?",
            (digest(request.cookies.get(REFRESH_COOKIE, "")),),
        ).fetchone()
        if row:
            keys.add(row[0])
    try:
        keys.add(digest(decode_access(request_token(request))["jti"]))
    except HTTPException:
        pass
    with connect() as con:
        for key in keys:
            con.execute("DELETE FROM sessions WHERE token_hash=?", (key,))
            con.execute("DELETE FROM oauth_attempts WHERE session_hash=?", (key,))


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
