import json
import os
import time
from datetime import datetime, timedelta, timezone

import bcrypt
from botocore.exceptions import ClientError
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from app import bucket

SECRET_KEY = os.environ.get("JWT_SECRET")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET env var must be set")

ALGORITHM = "HS256"
TOKEN_TTL = timedelta(days=30)
COOKIE_NAME = "paf_editor_token"
LOGIN_KEY = "meta/login.json"

_users_cache: dict | None = None
_users_cache_ts: float = 0.0
_CACHE_TTL = 60.0


def load_users() -> dict[str, str]:
    """Return {username: bcrypt_hash} from /meta/login.json. Cached ~60s."""
    global _users_cache, _users_cache_ts
    now = time.time()
    if _users_cache is not None and (now - _users_cache_ts) < _CACHE_TTL:
        return _users_cache
    try:
        raw = bucket.get_bytes(LOGIN_KEY)
        data = json.loads(raw)
        users = data.get("users", {})
    except ClientError:
        users = {}
    _users_cache = users
    _users_cache_ts = now
    return users


def invalidate_users_cache():
    global _users_cache, _users_cache_ts
    _users_cache = None
    _users_cache_ts = 0.0


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + TOKEN_TTL
    return jwt.encode({"sub": username, "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _read_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return request.cookies.get(COOKIE_NAME)


def get_current_user(request: Request) -> str:
    token = _read_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    if username not in load_users():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    return username


CurrentUser = Depends(get_current_user)
