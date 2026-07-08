import os

from fastapi import Depends, HTTPException, Request, status

# Auth is performed by the gateway ingress, which forwards the authenticated
# identity and roles on every request. We trust these headers.
USER_ID_HEADER = "X-User-Id"
ROLES_HEADER = "X-User-Roles"
REQUIRED_ROLE = "pafnet.editor"


def _parse_roles(raw: str) -> list[str]:
    return [r.strip() for r in raw.split(",") if r.strip()]


def get_current_user(request: Request) -> str:
    # In production the gateway always sets these headers. For local dev (no
    # gateway) fall back to DEV_USER_ID / DEV_USER_ROLES env vars when unset.
    user_id = request.headers.get(USER_ID_HEADER) or os.environ.get("DEV_USER_ID")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    roles_raw = request.headers.get(ROLES_HEADER)
    if roles_raw is None:
        roles_raw = os.environ.get("DEV_USER_ROLES", "")
    roles = _parse_roles(roles_raw)

    if REQUIRED_ROLE not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {REQUIRED_ROLE} role",
        )
    return user_id


CurrentUser = Depends(get_current_user)
