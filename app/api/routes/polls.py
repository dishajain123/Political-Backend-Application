"""
Poll Routes
===========
API endpoints for poll management, voting, and results.

Author: Political Communication Platform Team
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from app.services.poll_service import PollService
from app.schemas.poll_schema import PollCreate, PollResponse, PollVoteRequest, PollUpdateRequest
from app.api.dependencies import (
    get_current_user,
    require_permission,
    get_paginated_params,
    CurrentUser,
)
from app.core.permissions import Permission
from app.core.roles import UserRole

router = APIRouter(prefix="/polls", tags=["Polls"])


@router.post("", response_model=PollResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=PollResponse, status_code=status.HTTP_201_CREATED)
async def create_poll(
    payload: PollCreate,
    current_user: CurrentUser = Depends(require_permission(Permission.CREATE_POLL)),
):
    """
    Create a new poll (Corporator only).
    
    MANDATORY:
    - title: 5-300 chars
    - options: minimum 2 options
    - target_roles: which roles can vote
    - target_regions: geographic targeting (optional)
    
    Requires: CREATE_POLL permission (Corporator)
    """
    service = PollService()
    return await service.create(payload, current_user)


@router.get("", status_code=status.HTTP_200_OK)
@router.get("/", status_code=status.HTTP_200_OK)
async def list_polls(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query("active", description="Filter by status"),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    List polls targeted for current user.
    
    CRITICAL FILTERING:
    - Only active/published polls visible to voters
    - Respects role + region targeting
    - Hides individual responses (privacy)
    
    Query params:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - status: draft, active, closed (default: active for voters)
    """
    skip = (page - 1) * page_size
    service = PollService()
    
    # Get user location from DB for targeting
    # TODO: Cache this in token claims
    db = get_database()
    user_doc = await db.users.find_one({"_id": ObjectId(current_user.user_id)})
    user_location = user_doc.get("location", {}) if user_doc else {}
    
    return await service.list(
        skip=skip,
        limit=page_size,
        user_role=current_user.role.value,
        user_id=current_user.user_id,
        user_location=user_location,
        status=status or "active",
    )


@router.get("/{poll_id}", response_model=PollResponse)
async def get_poll(
    poll_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Get a specific poll.
    
    PRIVACY:
    - Hides individual responses from non-creators
    - Respects show_results setting
    """
    service = PollService()
    try:
        return await service.get_by_id(poll_id, current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.put("/{poll_id}", response_model=PollResponse)
async def update_poll(
    poll_id: str,
    payload: PollUpdateRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.CREATE_POLL)),
):
    """
    Update a draft poll (Corporator only).
    """
    service = PollService()
    try:
        return await service.update(poll_id, payload.dict(exclude_unset=True), current_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/{poll_id}/vote", status_code=status.HTTP_200_OK)
async def vote_on_poll(
    poll_id: str,
    payload: PollVoteRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Record a vote on a poll.
    
    PRIVACY:
    - If is_anonymous=True: user_id NOT stored with response
    - If is_anonymous=False: user_id stored (corporator can see)
    - Enforces single vote per user (if allow_multiple_responses=False)
    
    Returns: Success message
    """
    service = PollService()
    try:
        return await service.vote(
            poll_id=poll_id,
            option_id=payload.option_id,
            user_id=current_user.user_id,
            response_text=payload.response_text,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get("/{poll_id}/results", status_code=status.HTTP_200_OK)
async def get_poll_results(
    poll_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Get aggregated poll results.
    
    CRITICAL PRIVACY:
    - Shows percentages only (not individual vote counts for regular users)
    - Respects show_results setting (immediately, after_voting, after_closing, never)
    - Only creators see detailed vote counts
    - Anonymous polls never show user identities
    
    Returns: {
        poll_id,
        title,
        total_responses,
        options: [{option_id, text, votes, percentage}],
        is_anonymous,
        participation_rate
    }
    """
    service = PollService()
    try:
        return await service.get_results(
            poll_id=poll_id,
            user_role=current_user.role.value,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{poll_id}/publish", response_model=PollResponse)
async def publish_poll(
    poll_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.CREATE_POLL)),
):
    """
    Publish a draft poll (make it active).
    
    TRIGGERS: Notification sent to targeted users
    
    Requires: CREATE_POLL permission (Corporator)
    """
    service = PollService()
    try:
        return await service.publish(poll_id, current_user.user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{poll_id}/close", response_model=PollResponse)
async def close_poll(
    poll_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.CLOSE_POLL)),
):
    """
    Close a poll (stop voting).
    
    Requires: CLOSE_POLL permission (Corporator)
    """
    service = PollService()
    try:
        return await service.close(poll_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


# Required imports for routes
from app.db.mongodb import get_database
from bson import ObjectId
