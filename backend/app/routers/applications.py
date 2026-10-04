"""The Application Workspace API.

Five endpoints, deliberately. A list, a detail, a create, a patch and one
checklist sub-resource. The alternative - an endpoint per field, or per
transition - would multiply the surface a client has to keep correct without
adding a single guarantee.

Ownership is not a parameter anywhere in this module. Every handler receives the
account that ``require_user`` resolved from the session cookie, and every query is
scoped by it. A request that names a different user is either ignored or rejected,
never obeyed. Nothing here reads ``user_id`` from a body, a query string or a
path.

Cross-user access answers **404**, not 403, because a 403 confirms the resource
exists and would turn this API into an existence oracle for other students'
applications.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_user
from ..models import User
from ..schemas_application import (
    APPLICATION_OUTCOMES,
    ApplicationCreateRequest,
    ApplicationDetail,
    ApplicationListResponse,
    ApplicationPatchRequest,
    ChecklistItemPatchRequest,
)
from ..schemas_dashboard import APPLICATION_STATES
from ..services import application_workspace as workspace
from ..services.application_workspace import WorkspaceError

router = APIRouter(prefix="/applications", tags=["applications"])


def _same_origin_guard(request: Request) -> None:
    """Refuse a state-changing request that arrived from another origin.

    Defence in depth, not the primary defence. The session cookie is
    ``SameSite=lax``, which already stops a browser attaching it to a cross-site
    POST, PUT or DELETE. This closes the other cases: an older or misconfigured
    client that dropped ``SameSite``, and a same-site subdomain that should not
    be driving this API.

    A request with no ``Origin`` at all is allowed. That covers server-to-server
    calls and curl, which cannot be CSRF victims because they carry no ambient
    credentials. A request with an ``Origin`` that is not ours is refused - the
    only case where an ambient credential could be doing the damage.
    """
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return

    origin = request.headers.get("origin")
    if not origin:
        return

    from ..core.config import get_settings

    if origin.rstrip("/") in {allowed.rstrip("/") for allowed in get_settings().allowed_origins}:
        return

    raise WorkspaceError("This request did not come from an allowed origin.")


@router.get("", response_model=ApplicationListResponse)
@router.get("/", response_model=ApplicationListResponse, include_in_schema=False)
def list_applications(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    as_of: date | None = Query(
        default=None,
        description="Evaluate deadlines as of this date. Defaults to today; injectable so a response is reproducible.",
    ),
) -> ApplicationListResponse:
    """Every application this student owns, in deterministic decision order.

    No ``user_id`` parameter. The list is the caller's and nobody else's, which
    is why the endpoint takes nothing to identify whose list it wants.
    """
    return workspace.list_for_user(db, user, as_of=as_of)


@router.get("/{application_id}", response_model=ApplicationDetail)
def read_application(
    application_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    as_of: date | None = Query(default=None),
) -> ApplicationDetail:
    """One application with its checklist, note and borrowed Match values."""
    record = workspace.get_owned(db, user, application_id)
    return workspace.build_detail(db, user, record, as_of=as_of)


@router.post("", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def start_application(
    payload: ApplicationCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    as_of: date | None = Query(default=None),
) -> ApplicationDetail:
    """Start an application. Idempotent for a given scholarship."""
    _same_origin_guard(request)
    record = workspace.create_application(db, user, payload.scholarship_id, as_of=as_of)
    return workspace.build_detail(db, user, record, as_of=as_of)


@router.patch("/{application_id}", response_model=ApplicationDetail)
def update_application(
    application_id: int,
    payload: ApplicationPatchRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    as_of: date | None = Query(default=None),
) -> ApplicationDetail:
    """Change state, outcome or note, guarded by optimistic concurrency.

    ``expected_version`` is mandatory. A write that does not say which version it
    read cannot be checked for staleness, and a 409 is the correct answer to a
    write that would overwrite a newer edit rather than the 200 a silent lost
    update would produce.
    """
    _same_origin_guard(request)
    record = workspace.patch_application(db, user, application_id, payload)
    return workspace.build_detail(db, user, record, as_of=as_of)


@router.patch("/{application_id}/checklist/{item_key}", response_model=ApplicationDetail)
def update_checklist_item(
    application_id: int,
    item_key: str,
    payload: ChecklistItemPatchRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    as_of: date | None = Query(default=None),
) -> ApplicationDetail:
    """Complete or un-complete one task. Idempotent."""
    _same_origin_guard(request)
    record = workspace.set_checklist_item(
        db, user, application_id, item_key, payload.completed, payload.expected_version
    )
    return workspace.build_detail(db, user, record, as_of=as_of)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def discard_application(
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    """Discard an application started by accident.

    Refused for a submitted application, whose history is a record of something
    that actually happened.
    """
    _same_origin_guard(request)
    workspace.withdraw_or_delete(db, user, application_id)


__all__ = ["router"]