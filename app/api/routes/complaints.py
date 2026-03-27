"""
Complaint Routes
================
API endpoints for complaint lifecycle management.
This module contains only request handling and delegates all
business logic to ComplaintService.

Author: Political Communication Platform Team
"""

from fastapi import APIRouter, Depends, Query, Path, Body, HTTPException, status, Request
from datetime import datetime
from typing import Optional

from app.api.dependencies import get_current_user, require_permission
from app.core.permissions import Permission
from app.core.roles import UserRole
from app.schemas.complaint_schema import (
    ComplaintCreateRequest,
    ComplaintUpdateStatusRequest,
    ComplaintResponse,
    ComplaintAnalyticsResponse,
    ComplaintResolveRequest,
    ComplaintAddNoteRequest,
    ComplaintEscalateRequest,
    ComplaintFeedbackRequest,
    ComplaintAcknowledgeRequest,
    # NEW CODE ADDED
    ComplaintDeclineRequest,
    ComplaintRequestVerificationRequest,
    ComplaintVerificationFeedbackRequest,
)
from app.api.dependencies import CurrentUser
from app.services.complaint_service import ComplaintService
from app.utils.enums import ComplaintStatus
from app.utils.pagination import get_paginated_params, PaginatedResponse

router = APIRouter(prefix="/complaints", tags=["Complaints"])


@router.get(
    "/analytics",
    response_model=ComplaintAnalyticsResponse,
    summary="Complaints analytics dashboard (OPS)",
)
async def complaints_analytics(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    state: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    ward: Optional[str] = Query(None),
    area: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    assigned_to: Optional[str] = Query(None),
    sla_hours: int = Query(72, ge=1, le=720),
    _=Depends(require_permission(Permission.VIEW_ADVANCED_ANALYTICS)),
):
    service = ComplaintService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.complaints_analytics(
        start_date=start,
        end_date=end,
        state=state,
        city=city,
        ward=ward,
        area=area,
        category=category,
        status=status,
        assigned_to=assigned_to,
        sla_hours=sla_hours,
    )


@router.post(
    "",
)
@router.post(
    "/",
    response_model=ComplaintResponse,
    summary="Raise a new complaint"
)
async def create_complaint(
    request: Request,
    current_user: CurrentUser = Depends(
        require_permission(Permission.CREATE_COMPLAINT)
    ),
):
    """
    Create a new complaint.

    Access:
    - VOTER: Creates own complaint
    - LEADER: Can create on behalf of assigned voters

    Flow:
    Voter -> Complaint created -> Status = PENDING
    Leader -> Complaint created on behalf -> Status = PENDING
    """
    service = ComplaintService()

    content_type = request.headers.get("content-type", "")
    upload_file = None
    if "multipart/form-data" in content_type:
        form = await request.form()
        data = {}
        for key, value in form.multi_items():
            if key in ("file", "image", "media", "attachment"):
                upload_file = value
                continue
            if isinstance(value, str):
                if value.strip() == "":
                    continue
                data[key] = value
        for json_key in ("location", "attachment_urls", "image_urls"):
            if json_key in data and isinstance(data[json_key], str):
                try:
                    import json
                    data[json_key] = json.loads(data[json_key])
                except Exception:
                    pass
        # If location was sent as flat fields, build location object
        if "location" not in data:
            loc = {}
            for k in ("state", "city", "ward", "area", "building", "booth_number"):
                if k in data and isinstance(data[k], str) and data[k].strip():
                    loc[k] = data[k].strip()
            if loc:
                data["location"] = loc
        # Normalize category/priority to lowercase for enums
        if "category" in data and isinstance(data["category"], str):
            data["category"] = data["category"].strip().lower()
        if "priority" in data and isinstance(data["priority"], str):
            data["priority"] = data["priority"].strip().lower()
    else:
        data = await request.json()

    try:
        payload = ComplaintCreateRequest(**data)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        return await service.create_complaint(payload, current_user, upload_file=upload_file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

@router.get(
    "",
)
@router.get(
    "/",
    response_model=PaginatedResponse[ComplaintResponse],
    summary="List complaints based on role visibility"
)
async def list_complaints(
    status: Optional[ComplaintStatus] = Query(None),
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    ward: Optional[str] = Query(None),
    area: Optional[str] = Query(None),
    pagination: tuple = Depends(get_paginated_params),
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_COMPLAINT)
    ),
):
    """
    Fetch complaints with role-based visibility.

    Visibility Rules:
    - VOTER: own complaints only (DATA ISOLATION)
    - LEADER: assigned complaints within their territory
    - CORPORATOR / OPS: all complaints
    
    Geographic Filtering:
    - Leaders automatically restricted to their assigned_territory
    - Additional location filters can narrow further
    """
    skip, limit = pagination
    service = ComplaintService()
    location_filters = {}
    if state:
        location_filters["location.state"] = state
    if city:
        location_filters["location.city"] = city
    if ward:
        location_filters["location.ward"] = ward
    if area:
        location_filters["location.area"] = area
    return await service.get_complaints(
        current_user=current_user,
        skip=skip,
        limit=limit,
        status=status,
        category=category,
        priority=priority,
        location_filters=location_filters if location_filters else None,
    )


@router.patch(
    "/{complaint_id}/assign",
    summary="Assign complaint to a leader"
)
async def assign_complaint(
    complaint_id: str = Path(...),
    leader_id: str = Query(...),
    current_user: CurrentUser = Depends(
        require_permission(Permission.ASSIGN_COMPLAINT)
    ),
):
    """
    Assign a complaint to a leader.

    Access:
    - CORPORATOR
    - OPS

    Validation:
    - Complaint must be from voter assigned to this leader
    - Complaint location must be within leader's territory

    Flow:
    Corporator → Assign → Status = ACKNOWLEDGED
    """
    service = ComplaintService()
    try:
        success = await service.assign_complaint(
            complaint_id=complaint_id,
            leader_id=leader_id,
            current_user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {"success": success}


@router.patch(
    "/{complaint_id}/acknowledge",
    summary="Leader acknowledges complaint receipt"
)
async def acknowledge_complaint(
    complaint_id: str = Path(...),
    payload: ComplaintAcknowledgeRequest = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Leader acknowledges receipt of assigned complaint.
    
    This is separate from assignment:
    - Assignment: Corporator assigns to Leader
    - Acknowledgment: Leader confirms receipt
    
    Access:
    - LEADER only
    
    Tracking:
    - Sets acknowledged_by_leader and acknowledged_at
    - Records expected_visit_date if provided
    - Adds acknowledgment note to audit trail
    """
    if current_user.role != UserRole.LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only leaders can acknowledge complaints"
        )
    
    service = ComplaintService()
    success = await service.acknowledge_complaint(
        complaint_id=complaint_id,
        payload=payload,
        current_user=current_user,
    )
    return {"success": success}


@router.patch(
    "/{complaint_id}/status",
    summary="Update complaint status"
)
async def update_complaint_status(
    complaint_id: str = Path(...),
    payload: ComplaintUpdateStatusRequest = Body(...),
    current_user: CurrentUser = Depends(
        require_permission(Permission.UPDATE_COMPLAINT_STATUS)
    ),
):
    """
    Update complaint status.

    Access:
    - LEADER (only assigned complaints, cannot resolve/close)
    - CORPORATOR (all complaints)
    - OPS (all complaints)

    Leader Restrictions:
    - Can update to: IN_PROGRESS, ON_HOLD
    - CANNOT update to: RESOLVED, CLOSED

    Flow:
    Leader → IN_PROGRESS → (escalate or corporator resolves)
    Corporator/OPS → Any status transition
    """
    service = ComplaintService()
    success = await service.update_complaint_status(
        complaint_id=complaint_id,
        payload=payload,
        current_user=current_user,
    )
    return {"success": success}


@router.patch(
    "/{complaint_id}/resolve",
    summary="Resolve complaint (Corporator/OPS only)"
)
async def resolve_complaint(
    complaint_id: str = Path(...),
    payload: ComplaintResolveRequest = Body(...),
    current_user: CurrentUser = Depends(
        require_permission(Permission.RESOLVE_COMPLAINT)
    ),
):
    """
    Resolve a complaint with resolution notes.
    
    Access:
    - CORPORATOR
    - OPS
    
    Restriction:
    - Leaders CANNOT resolve complaints
    - Must be resolved by higher authority
    
    Tracking:
    - If complaint was assigned to leader, increments their resolution count
    """
    service = ComplaintService()
    success = await service.resolve_complaint(complaint_id, payload, current_user)
    return {"success": success}


@router.patch(
    "/{complaint_id}/note",
    summary="Add complaint note"
)
async def add_complaint_note(
    complaint_id: str = Path(...),
    payload: ComplaintAddNoteRequest = Body(...),
    current_user: CurrentUser = Depends(
        require_permission(Permission.ADD_COMPLAINT_NOTE)
    ),
):
    """
    Add note to complaint.
    
    Note Types:
    - field_observation: Leader's on-ground observations
    - internal: Corporator/OPS internal notes
    - external: Voter-visible updates
    
    Leader Notes:
    - Automatically classified as field_observation
    - Tracks first_field_visit_at timestamp
    - Increments complaints_followed_up metric
    
    Access:
    - LEADER (assigned complaints only)
    - CORPORATOR (all complaints)
    - OPS (all complaints)
    """
    service = ComplaintService()
    success = await service.add_note(complaint_id, payload, current_user)
    return {"success": success}


@router.post(
    "/{complaint_id}/feedback",
    summary="Submit voter feedback for resolved complaint"
)
async def submit_complaint_feedback(
    complaint_id: str = Path(...),
    payload: ComplaintFeedbackRequest = Body(...),
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_COMPLAINT)
    ),
):
    """
    Voter submits satisfaction feedback on resolved complaint.
    
    Access:
    - VOTER (own complaints only)
    
    Requirements:
    - Complaint must be in RESOLVED or CLOSED status
    """
    service = ComplaintService()
    success = await service.add_voter_feedback(complaint_id, payload, current_user)
    return {"success": success}


@router.patch(
    "/{complaint_id}/escalate",
    summary="Escalate complaint"
)
async def escalate_complaint(
    complaint_id: str = Path(...),
    payload: ComplaintEscalateRequest = Body(...),
    current_user: CurrentUser = Depends(
        require_permission(Permission.UPDATE_COMPLAINT_STATUS)
    ),
):
    """
    Escalate complaint to higher authority.
    
    Use Cases:
    - Leader cannot resolve issue locally
    - SLA exceeded
    - Requires corporator intervention
    
    Access:
    - LEADER (assigned complaints)
    - CORPORATOR (all complaints)
    - OPS (all complaints)
    
    Tracking:
    - Sets is_escalated flag
    - Records escalation reason
    - Adds to audit trail
    """
    service = ComplaintService()
    success = await service.escalate(complaint_id, payload, current_user)
    return {"success": success}


@router.patch(
    "/{complaint_id}/decline",
    summary="Decline a complaint (Leader or Corporator)"
)
async def decline_complaint(
    complaint_id: str = Path(...),
    payload: ComplaintDeclineRequest = Body(...),
    current_user: CurrentUser = Depends(
        require_permission(Permission.UPDATE_COMPLAINT_STATUS)
    ),
):
    """
    Decline a complaint with a reason.

    Decline Categories:
    - not_feasible: Issue cannot be fixed
    - out_of_jurisdiction: Not within this ward/area
    - personal_request: Complaint is personal, not civic
    - other: Custom reason

    Access:
    - LEADER (assigned complaints only)
    - CORPORATOR (all complaints)
    - OPS (all complaints)

    Rules:
    - Cannot decline an already RESOLVED complaint
    - Sends notification to voter on decline
    - Recorded in audit trail

    Flow:
    Leader/Corporator → Decline → Status = DECLINED → Voter notified
    """
    service = ComplaintService()
    try:
        success = await service.decline_complaint(
            complaint_id=complaint_id,
            payload=payload,
            current_user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {"success": success}


@router.post(
    "/{complaint_id}/request-verification",
    summary="Corporator requests voter to verify resolution"
)
async def request_verification(
    complaint_id: str = Path(...),
    payload: ComplaintRequestVerificationRequest = Body(...),
    current_user: CurrentUser = Depends(
        require_permission(Permission.RESOLVE_COMPLAINT)
    ),
):
    """
    Corporator or OPS triggers the resolution verification flow.

    Flow:
    1. Corporator clicks 'Verify Resolution' on a RESOLVED complaint
    2. Sets verification_requested_at and verified_by_corporator=True
    3. Voter receives notification to submit rating + comment
    4. Voter submits via /verification-feedback endpoint

    Access:
    - CORPORATOR
    - OPS

    Requirements:
    - Complaint must be in RESOLVED status
    """
    if current_user.role == UserRole.LEADER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Corporator or OPS can request verification"
        )
    service = ComplaintService()
    try:
        success = await service.request_verification(
            complaint_id=complaint_id,
            payload=payload,
            current_user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {"success": success}


@router.post(
    "/{complaint_id}/verification-feedback",
    summary="Voter submits verification feedback after resolution"
)
async def submit_verification_feedback(
    complaint_id: str = Path(...),
    payload: ComplaintVerificationFeedbackRequest = Body(...),
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_COMPLAINT)
    ),
):
    """
    Voter submits rating and comment for the verification flow.

    Scoring Logic:
    - Rating >= 3: Leader performance score incremented (only once per complaint)
    - Rating < 3: Complaint is reopened (status → IN_PROGRESS)

    Access:
    - VOTER (own complaints only)

    Requirements:
    - Complaint must have verification_requested_at set
    - Voter must not have already submitted verification feedback
    """
    service = ComplaintService()
    try:
        success = await service.submit_verification_feedback(
            complaint_id=complaint_id,
            payload=payload,
            current_user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {"success": success}
