"""
Appointments Routes
===================
API endpoints for appointment management with complete lifecycle and notifications.

Author: Political Communication Platform Team
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from datetime import datetime
from app.services.appointment_service import AppointmentService
from app.schemas.appointment_schema import (
    AppointmentCreate,
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentApproveRequest,
)
from app.api.dependencies import (
    get_current_user,
    require_permission,
    CurrentUser,
)
from app.core.permissions import Permission

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post("", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    payload: AppointmentCreate,
    current_user: CurrentUser = Depends(require_permission(Permission.REQUEST_APPOINTMENT)),
):
    """
    Create an appointment request (Voter/Leader).
    
    MANDATORY FIELDS:
    - requested_with: User ID of leader/corporator
    - reason: Purpose (personal_issue, complaint_follow_up, service_request, etc.)
    - appointment_date: Future datetime
    
    OPTIONAL FIELDS:
    - description, location, duration_minutes, tags, linked_complaint_id
    
    Creates in REQUESTED status - awaits approval from requested_with user.
    
    TRIGGERS: Notification sent to requested_with user
    
    Requires: REQUEST_APPOINTMENT permission (Voter)
    """
    service = AppointmentService()
    try:
        return await service.create(payload, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", response_model=AppointmentListResponse, status_code=status.HTTP_200_OK)
@router.get("/", response_model=AppointmentListResponse, status_code=status.HTTP_200_OK)
async def list_appointments(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    reason: Optional[str] = Query(None, description="Filter by reason"),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    List appointments with RBAC enforcement.
    
    CRITICAL PRIVACY:
    - Voter: sees own appointments only (as requester or requested)
    - Leader: sees appointments where they're requested_with
    - Corporator: sees all appointments
    
    Query params:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - status: requested, approved, rejected, rescheduled, completed, cancelled
    - reason: personal_issue, community_issue, feedback, complaint_followup, general_meeting, other
    """
    service = AppointmentService()
    return await service.list(
        user=current_user,
        page=page,
        page_size=page_size,
        status=status,
        reason=reason,
    )


@router.post("/{appointment_id}/approve", response_model=AppointmentResponse, status_code=status.HTTP_200_OK)
async def approve_appointment(
    appointment_id: str,
    payload: Optional[AppointmentApproveRequest] = None,
    current_user: CurrentUser = Depends(require_permission(Permission.APPROVE_APPOINTMENT)),
):
    """
    Approve an appointment request.
    
    CRITICAL:
    - Only the requested_with user can approve
    - Status must be REQUESTED
    - Appointment time is confirmed
    
    TRIGGERS: Notification sent to requester confirming approval
    
    Requires: APPROVE_APPOINTMENT permission (Leader/Corporator)
    """
    service = AppointmentService()
    try:
        return await service.approve(appointment_id, current_user, payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{appointment_id}/reject", response_model=AppointmentResponse, status_code=status.HTTP_200_OK)
async def reject_appointment(
    appointment_id: str,
    rejection_reason: str = Query(..., description="Reason for rejection", min_length=5),
    current_user: CurrentUser = Depends(require_permission(Permission.APPROVE_APPOINTMENT)),
):
    """
    Reject an appointment request with reason.
    
    CRITICAL:
    - Only the requested_with user can reject
    - Status must be REQUESTED
    - Rejection reason is mandatory
    
    TRIGGERS: Notification sent to requester with rejection reason
    
    Query params:
    - rejection_reason: Why the appointment is being rejected
    
    Requires: APPROVE_APPOINTMENT permission
    """
    service = AppointmentService()
    try:
        return await service.reject(appointment_id, rejection_reason, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{appointment_id}/reschedule", response_model=AppointmentResponse, status_code=status.HTTP_200_OK)
async def reschedule_appointment(
    appointment_id: str,
    new_date: str = Query(..., description="New appointment date (ISO 8601 format)"),
    reason: Optional[str] = Query(None, description="Reason for rescheduling (optional)"),
    current_user: CurrentUser = Depends(require_permission(Permission.RESCHEDULE_APPOINTMENT)),
):
    """
    Reschedule an approved appointment to a new date/time.
    
    CRITICAL:
    - Only approved appointments can be rescheduled
    - Either party (requester or requested_with) can reschedule
    - New date must be in future
    - Reason is mandatory
    - Reschedule count is tracked
    
    TRIGGERS: Notification sent to other party with new date and reason
    
    Query params:
    - new_date: New appointment datetime (ISO 8601 format: 2024-02-20T10:30:00Z)
    - reason: Why rescheduling is needed (optional)
    
    Requires: RESCHEDULE_APPOINTMENT permission
    """
    service = AppointmentService()
    try:
        new_datetime = datetime.fromisoformat(new_date.replace('Z', '+00:00'))
        return await service.reschedule(appointment_id, new_datetime, reason, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use ISO 8601 format (2024-02-20T10:30:00Z)",
        )


@router.post("/{appointment_id}/complete", response_model=AppointmentResponse, status_code=status.HTTP_200_OK)
async def complete_appointment(
    appointment_id: str,
    attendees: list = Query(..., description="List of user IDs who attended"),
    meeting_notes: str = Query(..., description="Notes from the meeting", min_length=5),
    current_user: CurrentUser = Depends(require_permission(Permission.APPROVE_APPOINTMENT)),
):
    """
    Mark appointment as completed after meeting.
    
    CRITICAL:
    - Only the requested_with user can mark as complete
    - Records attendees and meeting notes
    - Allows feedback submission after completion
    
    Query params:
    - attendees: Comma-separated user IDs who attended
    - meeting_notes: Summary of meeting discussion
    
    Requires: APPROVE_APPOINTMENT permission
    """
    service = AppointmentService()
    try:
        return await service.complete(appointment_id, attendees, meeting_notes, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{appointment_id}/cancel", response_model=AppointmentResponse, status_code=status.HTTP_200_OK)
async def cancel_appointment(
    appointment_id: str,
    cancellation_reason: str = Query(..., description="Reason for cancellation", min_length=5),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Cancel an appointment (can be done by either party before completion).
    
    CRITICAL:
    - Either requester or requested_with can cancel
    - Cannot cancel completed appointments
    - Reason is mandatory
    
    TRIGGERS: Notification sent to other party with cancellation reason
    
    Query params:
    - cancellation_reason: Why the appointment is being cancelled
    
    Authorization: Any authenticated user (RBAC enforced in service)
    """
    service = AppointmentService()
    try:
        return await service.cancel(appointment_id, cancellation_reason, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{appointment_id}", response_model=AppointmentResponse, status_code=status.HTTP_200_OK)
async def get_appointment(
    appointment_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Get a specific appointment by appointment_id.
    
    CRITICAL PRIVACY:
    - Only participants (requester, requested_with) can view
    - Corporator/OPS can view all
    
    Returns: Appointment details with full history
    """
    service = AppointmentService()
    try:
        return await service.get_by_id(appointment_id, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
