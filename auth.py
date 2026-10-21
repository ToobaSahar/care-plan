"""
Authentication for the care plan API.

This service holds the Supabase *service role* key, which bypasses row level
security completely. Every data route therefore has to answer, by itself, the
question the database can no longer answer for it: who is calling?

The bearer token is verified by handing it back to Supabase
(`GET /auth/v1/user`) rather than by validating the signature locally. That
costs one short round trip on a route that already spends seconds in an LLM,
and in exchange there is no JWT secret to distribute, no key rotation to
track, and no way to get the algorithm check wrong — the class of mistake
that turns token verification into an open door.

A valid token is necessary but not sufficient: the caller must also hold an
active row in `public.staff`, the same condition the RLS policies enforce.
"""

import logging
import time
from typing import Any, Callable, Dict, Optional, Tuple

import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import Config
from database import DatabaseManager
from permissions import CAREPLAN_GENERATE, has_permission

logger = logging.getLogger(__name__)

# `auto_error=False` so a missing header produces our own 401 with a useful
# message, rather than FastAPI's bare 403.
_bearer = HTTPBearer(auto_error=False)

# Verified tokens are held briefly so that a burst of calls from one screen
# does not become a burst of calls to the auth server. Well under the token's
# own lifetime, so a revoked session stops working promptly.
_CACHE_TTL_SECONDS = 60
_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

_staff_client = None


def _staff_table():
    """The service-role client, created once and only when first needed."""
    global _staff_client
    if _staff_client is None:
        _staff_client = DatabaseManager().supabase
    return _staff_client


def _unauthorised(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _verify_token(token: str) -> Dict[str, Any]:
    """Resolves a Supabase access token to its user, or raises 401."""
    cached = _cache.get(token)
    now = time.monotonic()
    if cached and cached[0] > now:
        return cached[1]

    # The `apikey` header only has to identify the project to GoTrue, so the
    # anon key is the right one; the service key is accepted as a fallback so
    # an existing deployment does not break on a newly required variable.
    project_key = Config.SUPABASE_KEY or Config.SUPABASE_SERVICE_KEY

    if not Config.SUPABASE_URL or not project_key:
        # Refusing is the only safe failure here. Falling through would let
        # every request past on a misconfigured deployment.
        logger.error("Supabase is not configured; refusing all authenticated requests.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on this server.",
        )

    try:
        response = requests.get(
            f"{Config.SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": project_key,
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning("Auth server unreachable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not verify your session. Try again shortly.",
        )

    if response.status_code != 200:
        raise _unauthorised("Your session is not valid. Sign in again.")

    user = response.json()
    if not user.get("id"):
        raise _unauthorised("Your session is not valid. Sign in again.")

    _cache[token] = (now + _CACHE_TTL_SECONDS, user)

    # The cache is per-process and tiny, but an unbounded dict is still a slow
    # leak. Expired entries are dropped whenever it grows past a sane size.
    if len(_cache) > 512:
        for key, (expiry, _) in list(_cache.items()):
            if expiry <= now:
                _cache.pop(key, None)

    return user


def _active_staff(user_id: str) -> Dict[str, Any]:
    """The caller's staff record, or 403 if they do not have an active one."""
    try:
        result = (
            _staff_table()
            .table("staff")
            .select("id, email, full_name, role, is_active")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("Could not read staff record for %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not confirm your access. Try again shortly.",
        )

    rows = result.data or []
    if not rows or not rows[0].get("is_active"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is not permitted to use the care plan service.",
        )
    return rows[0]


def require_staff(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Dict[str, Any]:
    """
    FastAPI dependency for any route that reads or writes service-user data.

    Returns the caller's staff record so handlers can attribute what they do.
    """
    if credentials is None or not credentials.credentials:
        raise _unauthorised("This endpoint requires a signed-in session.")

    user = _verify_token(credentials.credentials)
    staff = _active_staff(user["id"])

    logger.info("Authorised request from %s (%s)", staff.get("email"), staff.get("role"))
    return staff


def require_permission(permission: str) -> Callable[..., Dict[str, Any]]:
    """
    Builds a dependency that admits only callers holding `permission`.

    Routes name a capability rather than a role, so adding a role later is a
    row in `role_permissions` instead of an edit to every endpoint that would
    otherwise be testing `role == "admin"` by hand.
    """

    def dependency(staff: Dict[str, Any] = Depends(require_staff)) -> Dict[str, Any]:
        if not has_permission(staff.get("role"), permission):
            logger.info(
                "Refused %s to %s (role %s)", permission, staff.get("email"), staff.get("role")
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your role does not allow this action.",
            )
        return staff

    return dependency


# Generating a care plan writes records, so `viewer` is not enough.
require_write_access = require_permission(CAREPLAN_GENERATE)
