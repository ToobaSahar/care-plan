"""
What each role is allowed to do.

`public.role_permissions` in the database is the source of truth; this module
reads it rather than restating it, so a permission added by migration takes
effect without a redeploy. The literal copy below exists only so the service
keeps working during a rollout where the code is newer than the schema — it is
a fallback, not a second definition, and it is logged loudly when used.
"""

import logging
import time
from typing import Dict, FrozenSet, Optional

logger = logging.getLogger(__name__)

# Permission names. Referred to by constant so a typo is an ImportError at
# startup rather than a silently-denied request in production.
RECORDS_READ = "records:read"
RECORDS_WRITE = "records:write"
CAREPLAN_GENERATE = "careplan:generate"
STAFF_READ = "staff:read"
STAFF_MANAGE = "staff:manage"

# Mirrors 20261021000200_staff_management.sql. Used only when the table cannot
# be read.
_FALLBACK: Dict[str, FrozenSet[str]] = {
    "viewer": frozenset({RECORDS_READ}),
    "assessor": frozenset({RECORDS_READ, RECORDS_WRITE, CAREPLAN_GENERATE}),
    "admin": frozenset(
        {RECORDS_READ, RECORDS_WRITE, CAREPLAN_GENERATE, STAFF_READ, STAFF_MANAGE}
    ),
}

# The matrix changes only by migration, so a long TTL is safe and keeps this
# off the hot path of every request.
_CACHE_TTL_SECONDS = 300
_cache: Optional[Dict[str, FrozenSet[str]]] = None
_cache_expiry: float = 0.0


def _load_from_database() -> Optional[Dict[str, FrozenSet[str]]]:
    try:
        from database import DatabaseManager

        rows = (
            DatabaseManager().supabase.table("role_permissions")
            .select("role, permission")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        logger.warning("Could not read role_permissions: %s", exc)
        return None

    if not rows:
        return None

    matrix: Dict[str, set] = {}
    for row in rows:
        matrix.setdefault(row["role"], set()).add(row["permission"])
    return {role: frozenset(perms) for role, perms in matrix.items()}


def permissions_for(role: Optional[str]) -> FrozenSet[str]:
    """Every permission held by `role`. Unknown roles hold none."""
    global _cache, _cache_expiry

    now = time.monotonic()
    if _cache is None or now >= _cache_expiry:
        loaded = _load_from_database()
        if loaded is None:
            logger.warning(
                "Falling back to the built-in permission matrix. Apply "
                "20261021000200_staff_management.sql to use the database copy."
            )
            loaded = _FALLBACK
        _cache = loaded
        _cache_expiry = now + _CACHE_TTL_SECONDS

    return _cache.get(role or "", frozenset())


def has_permission(role: Optional[str], permission: str) -> bool:
    return permission in permissions_for(role)


def invalidate_cache() -> None:
    """Forces the next check to re-read the matrix. For tests and migrations."""
    global _cache, _cache_expiry
    _cache = None
    _cache_expiry = 0.0
