"""
Events Routes
=============
API endpoints for event management with leader assignment and participation tracking.

Author: Political Communication Platform Team
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from app.services.event_service import EventService
from app.schemas.event_schema import (
    EventCreate,
    EventUpdateRequest,
    EventResponse,
    EventStatusUpdateRequest,
)
from app.api.dependencies import (
    get_current_user,
    require_permission,
    CurrentUser,
)
from app.core.permissions import Permission
from app.core.roles import UserRole
from app.db.mongodb import get_database
from bson import ObjectId

router = APIRouter(prefix="/events", tags=["Events"])


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    current_user: CurrentUser = Depends(require_permission(Permission.CREATE_EVENT)),
):
    """
    Create a new event (Corporator only).
    
    MANDATORY FIELDS:
    - title: 5-300 chars
    - description: 10-3000 chars
    - event_type: rally, meeting, workshop, seminar, conference, training
    - event_date: Future datetime
    - location: state + city required
    
    OPTIONAL FIELDS:
    - end_date, duration_hours, venue details, agenda, speakers, etc.
    
    Creates in SCHEDULED status.
    
    Requires: CREATE_EVENT permission (Corporator)
    """
    service = EventService()
    try:
        return await service.create(payload, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("", status_code=status.HTTP_200_OK)
@router.get("/", status_code=status.HTTP_200_OK)
async def list_events(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    List events with role-based visibility.
    
    CRITICAL FILTERING:
    - Public events visible to all
    - Leaders see assigned events + public
    - Corporator sees all events
    
    Query params:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - status: scheduled, ongoing, completed, cancelled, postponed
    - event_type: awareness, public_meeting, campaign, celebration, rally, town_hall, other
    """
    service = EventService()
    db = get_database()
    user_doc = await db.users.find_one({"_id": ObjectId(current_user.user_id)})
    user_location = user_doc.get("location", {}) if user_doc else {}
    user_language = user_doc.get("language_preference") if user_doc else None
    return await service.list(
        page=page,
        page_size=page_size,
        status=status,
        event_type=event_type,
        user_role=current_user.role.value,
        user_id=current_user.user_id,
        user_location=user_location,
        user_language=user_language,
    )


@router.get("/{event_id}", status_code=status.HTTP_200_OK)
async def get_event(
    event_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Get a specific event by event_id.
    
    Returns: Event details with participation metrics
    """
    service = EventService()
    try:
        return await service.get_by_id(event_id, current_user.role.value, current_user.user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.put("/{event_id}", status_code=status.HTTP_200_OK)
async def update_event(
    event_id: str,
    payload: EventUpdateRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.UPDATE_EVENT)),
):
    """
    Update an event (creator or corporator).
    """
    service = EventService()
    try:
        return await service.update(event_id, payload, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{event_id}/status", response_model=EventResponse, status_code=status.HTTP_200_OK)
async def update_event_status(
    event_id: str,
    payload: EventStatusUpdateRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.UPDATE_EVENT)),
):
    """
    Update event status (corporator or creator).
    """
    service = EventService()
    try:
        return await service.update_status(event_id, payload, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.DELETE_EVENT)),
):
    """
    Soft delete an event (cancel).
    """
    service = EventService()
    try:
        await service.delete(event_id, current_user)
        return None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{event_id}/assign-leader", status_code=status.HTTP_200_OK)
async def assign_leader(
    event_id: str,
    leader_id: str = Query(..., description="Leader user ID to assign"),
    current_user: CurrentUser = Depends(require_permission(Permission.ASSIGN_EVENT_LEADER)),
):
    """
    Assign a leader to an event.
    
    CRITICAL:
    - Only corporator or event creator can assign
    - Leader must exist and have leader role
    - No duplicate assignments
    
    Query params:
    - leader_id: User ID of leader to assign
    
    Requires: ASSIGN_EVENT_LEADER permission
    """
    service = EventService()
    try:
        success = await service.assign_leader(event_id, leader_id, current_user)
        if success:
            return {"message": "Leader assigned successfully"}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to assign leader",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{event_id}/reassign-leader", status_code=status.HTTP_200_OK)
async def reassign_leader(
    event_id: str,
    old_leader_id: str = Query(..., description="Current leader user ID"),
    new_leader_id: str = Query(..., description="New leader user ID"),
    current_user: CurrentUser = Depends(require_permission(Permission.ASSIGN_EVENT_LEADER)),
):
    """
    Reassign event leadership from one leader to another.
    
    CRITICAL:
    - Removes old leader, assigns new leader
    - Only corporator or event creator can reassign
    - Both leaders must exist
    
    Query params:
    - old_leader_id: Current leader's user ID
    - new_leader_id: New leader's user ID
    
    Requires: ASSIGN_EVENT_LEADER permission
    """
    service = EventService()
    try:
        success = await service.reassign_leader(event_id, old_leader_id, new_leader_id, current_user)
        if success:
            return {"message": "Leader reassigned successfully"}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to reassign leader",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete("/{event_id}/remove-leader", status_code=status.HTTP_200_OK)
async def remove_leader(
    event_id: str,
    leader_id: str = Query(..., description="Leader user ID to remove"),
    current_user: CurrentUser = Depends(require_permission(Permission.ASSIGN_EVENT_LEADER)),
):
    """
    Remove a leader from an event.
    
    CRITICAL:
    - Only corporator or event creator can remove
    - Leader is removed from assigned_leaders list
    
    Query params:
    - leader_id: Leader's user ID to remove
    
    Requires: ASSIGN_EVENT_LEADER permission
    """
    service = EventService()
    try:
        success = await service.remove_leader(event_id, leader_id, current_user)
        if success:
            return {"message": "Leader removed successfully"}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to remove leader",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{event_id}/register", status_code=status.HTTP_200_OK)
async def register_for_event(
    event_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Register for an event (open to all roles).
    
    CRITICAL:
    - Check registration is open
    - Prevent duplicate registrations
    - Track registration timestamp
    """
    service = EventService()
    try:
        success = await service.register_participant(event_id, current_user.user_id)
        if success:
            return {"message": "Registered for event successfully"}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to register for event",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{event_id}/mark-attendance", status_code=status.HTTP_200_OK)
async def mark_attendance(
    event_id: str,
    user_id: str = Query(..., description="Participant user ID"),
    attended: bool = Query(True, description="Attendance status"),
    current_user: CurrentUser = Depends(require_permission(Permission.TRACK_EVENT_PARTICIPATION)),
):
    """
    Mark participant as attended/not attended.
    
    CRITICAL:
    - Only event leaders/corporator can mark attendance
    - Automatically recalculates participation metrics
    
    Query params:
    - user_id: Participant's user ID
    - attended: True/False (default: True)
    
    Requires: TRACK_EVENT_PARTICIPATION permission
    """
    service = EventService()
    try:
        success = await service.mark_attendance(event_id, user_id, attended)
        if success:
            return {"message": "Attendance marked successfully"}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to mark attendance",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{event_id}/metrics", status_code=status.HTTP_200_OK)
async def get_event_metrics(
    event_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.TRACK_EVENT_PARTICIPATION)),
):
    """
    Get participation and engagement metrics for an event.
    
    RETURNS:
    - Total registrations
    - Actual attendees
    - Participation rate (%)
    - Assigned leaders count
    - Event status
    
    Requires: TRACK_EVENT_PARTICIPATION permission (Corporator/Leader)
    """
    service = EventService()
    try:
        return await service.get_metrics(event_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
