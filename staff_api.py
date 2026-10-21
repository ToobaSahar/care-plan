"""
Managing the care team.

Creating an account needs the Supabase admin API, which needs the service role
key. That key bypasses row level security entirely, so it can only ever live
server-side — which is why adding a colleague is an endpoint here rather than
a Supabase call from the browser.

Every route is gated on a capability (`staff:read`, `staff:manage`) rather
than on a role name, so the day a `manager` role appears it is a row in
`role_permissions` and nothing in this file changes.
"""

import logging
import re
import secrets
import string
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, EmailStr, Field

from auth import require_permission, require_staff
from database import DatabaseManager
from permissions import STAFF_MANAGE, STAFF_READ, permissions_for

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/staff", tags=["staff"])

ROLES = ("admin", "assessor", "viewer")

# Unambiguous alphabet: no O/0, l/1/I. These passwords get read aloud and
# copied by hand, and a character nobody can transcribe is a support call.
_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
_PASSWORD_LENGTH = 20


def _generate_password() -> str:
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(_PASSWORD_LENGTH))


def _admin_client():
    return DatabaseManager().supabase


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------


class StaffMember(BaseModel):
    id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class StaffListResponse(BaseModel):
    staff: List[StaffMember]
    """What the caller may do, so the UI does not have to infer it from a role."""
    permissions: List[str]


class CreateStaffRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="assessor")


class CreateStaffResponse(BaseModel):
    staff: StaffMember
    """
    Shown once and never retrievable again — it is not stored anywhere in a
    readable form. The administrator passes it on; the colleague changes it.
    """
    temporary_password: str


class UpdateStaffRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_role(role: str) -> str:
    if role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown role '{role}'. Expected one of: {', '.join(ROLES)}.",
        )
    return role


def _supabase_message(exc: Exception) -> str:
    """Supabase errors arrive as prose; surface the useful part, not a stack."""
    text = str(exc)
    if "already been registered" in text or "already exists" in text:
        return "An account with that email address already exists."
    if "Password" in text:
        return "The generated password was rejected by the password policy."
    return "The account could not be created."


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=StaffListResponse)
async def list_staff(staff: Dict[str, Any] = Depends(require_permission(STAFF_READ))):
    """The whole roster, active and not — deactivated colleagues must stay visible."""
    try:
        rows = (
            _admin_client()
            .table("staff")
            .select("id, email, full_name, role, is_active, created_at, updated_at")
            .order("is_active", desc=True)
            .order("full_name")
            .execute()
            .data
            or []
        )
    except Exception as exc:
        logger.error("Could not list staff: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The team list could not be loaded.",
        )

    return StaffListResponse(
        staff=[StaffMember(**row) for row in rows],
        permissions=sorted(permissions_for(staff.get("role"))),
    )


@router.post("", response_model=CreateStaffResponse, status_code=status.HTTP_201_CREATED)
async def create_staff(
    request: CreateStaffRequest,
    staff: Dict[str, Any] = Depends(require_permission(STAFF_MANAGE)),
):
    """
    Creates the account and its roster entry together.

    The role travels in user metadata so the database trigger writes it as the
    row is created. Setting it afterwards would leave a window, however short,
    in which a new viewer held an assessor's permissions.
    """
    role = _validate_role(request.role)
    password = _generate_password()

    try:
        created = _admin_client().auth.admin.create_user(
            {
                "email": str(request.email),
                "password": password,
                # No SMTP is assumed, so the account is usable immediately and
                # the administrator hands over the password directly.
                "email_confirm": True,
                "user_metadata": {
                    "full_name": request.full_name.strip(),
                    "role": role,
                },
            }
        )
    except Exception as exc:
        logger.warning("create_user failed for %s: %s", request.email, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=_supabase_message(exc)
        )

    user = getattr(created, "user", None) or created
    user_id = getattr(user, "id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The account was not created. Try again.",
        )

    # Read back rather than assuming: the trigger owns the row, and reading it
    # confirms the trigger ran. A created account with no roster entry can
    # sign in and reach nothing, which is confusing to diagnose later.
    rows = (
        _admin_client()
        .table("staff")
        .select("id, email, full_name, role, is_active, created_at, updated_at")
        .eq("id", str(user_id))
        .limit(1)
        .execute()
        .data
        or []
    )

    if not rows:
        logger.error("No staff row for new user %s; is migration 200 applied?", user_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The account was created but could not be added to the team. "
                "Check that the staff migrations have been applied."
            ),
        )

    logger.info("%s created account %s as %s", staff.get("email"), request.email, role)
    return CreateStaffResponse(
        staff=StaffMember(**rows[0]), temporary_password=password
    )


@router.patch("/{staff_id}", response_model=StaffMember)
async def update_staff(
    staff_id: str = Path(min_length=36, max_length=36),
    request: UpdateStaffRequest = ...,
    staff: Dict[str, Any] = Depends(require_permission(STAFF_MANAGE)),
):
    """Changes a colleague's role, or withdraws and restores their access."""
    changes: Dict[str, Any] = {}
    if request.role is not None:
        changes["role"] = _validate_role(request.role)
    if request.is_active is not None:
        changes["is_active"] = request.is_active

    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nothing to change.",
        )

    # Locking yourself out is the one mistake with no in-product remedy. The
    # database refuses to drop the last administrator whoever asks; this
    # catches the commoner version first, with a message that explains it.
    if staff_id == staff.get("id"):
        if changes.get("is_active") is False:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You cannot deactivate your own account.",
            )
        if changes.get("role") not in (None, staff.get("role")):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You cannot change your own role. Ask another administrator.",
            )

    try:
        rows = (
            _admin_client()
            .table("staff")
            .update(changes)
            .eq("id", staff_id)
            .execute()
            .data
            or []
        )
    except Exception as exc:
        message = str(exc)
        if "last active administrator" in message:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Appoint another administrator before removing this one.",
            )
        logger.error("Could not update staff %s: %s", staff_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The change could not be saved.",
        )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such team member."
        )

    logger.info("%s updated %s: %s", staff.get("email"), staff_id, changes)
    return StaffMember(**rows[0])


@router.get("/me", response_model=StaffListResponse)
async def whoami(staff: Dict[str, Any] = Depends(require_staff)):
    """
    The caller's own record and capabilities.

    Any signed-in colleague may call this — it reports only what they already
    are, and gives the UI one place to ask what it should offer them.
    """
    return StaffListResponse(
        staff=[StaffMember(**staff)],
        permissions=sorted(permissions_for(staff.get("role"))),
    )
