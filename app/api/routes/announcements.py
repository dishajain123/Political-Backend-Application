"""
Announcement Routes
===================
API endpoints for announcement management with role-based targeting and privacy.

Author: Political Communication Platform Team
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from bson import ObjectId
from app.services.announcement_service import AnnouncementService
from app.schemas.announcement_schema import (
    AnnouncementCreateRequest,
    AnnouncementUpdateRequest,
    AnnouncementResponse,
    AnnouncementListResponse,
    AnnouncementPublishRequest,
    AnnouncementAcknowledgeRequest,
)
from app.api.dependencies import (
    get_current_user,
    require_permission,
    CurrentUser,
)
from app.core.permissions import Permission
from app.core.roles import UserRole
from app.db.mongodb import get_database

router = APIRouter(prefix="/announcements", tags=["Announcements"])


@router.get("", response_model=AnnouncementListResponse, response_model_by_alias=False)
@router.get("/", response_model=AnnouncementListResponse, response_model_by_alias=False)
async def list_announcements(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status (draft, published, archived)"),
    priority: Optional[str] = Query(None, description="Filter by priority (low, normal, high, urgent)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_public: Optional[bool] = Query(None, description="Filter by public/private"),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    List announcements with pagination and filters.
    
    CRITICAL FILTERING:
    - Only shows announcements targeted to user's role
    - Respects geographic targeting (state/city)
    - Hides viewer/acknowledgment identities
    - Draft announcements only visible to creator/corporator
    
    Query params:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - status: Filter by status (draft, published, archived)
    - priority: Filter by priority (low, normal, high, urgent)
    - category: Filter by category
    - is_public: Filter by public/private announcements
    """
    # Get user's location for targeting
    db = get_database()
    user_doc = await db.users.find_one({"_id": ObjectId(current_user.user_id)})
    user_location = user_doc.get("location", {}) if user_doc else {}
    user_issues = (user_doc.get("engagement", {}) or {}).get("issues_of_interest", []) if user_doc else []
    user_language = user_doc.get("language_preference") if user_doc else None
    
    service = AnnouncementService()
    return await service.list(
        page=page,
        page_size=page_size,
        status=status,
        priority=priority,
        category=category,
        is_public=is_public,
        user_id=current_user.user_id,
        user_role=current_user.role.value,
        user_location=user_location,
        user_issues=user_issues,
        user_language=user_language,
    )


@router.get("/{announcement_id}", response_model=AnnouncementResponse, response_model_by_alias=False)
async def get_announcement(
    announcement_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Get a specific announcement by ID.
    
    PRIVACY:
    - Hides who viewed/acknowledged the announcement
    - Respects targeting rules
    - Increments view count (private metric)
    
    Params:
    - announcement_id: Announcement ID or announcement_id field
    """
    service = AnnouncementService()
    try:
        db = get_database()
        user_doc = await db.users.find_one({"_id": ObjectId(current_user.user_id)})
        user_location = user_doc.get("location", {}) if user_doc else {}
        user_issues = (user_doc.get("engagement", {}) or {}).get("issues_of_interest", []) if user_doc else []
        user_language = user_doc.get("language_preference") if user_doc else None
        return await service.get_by_id(
            announcement_id,
            user_role=current_user.role.value,
            user_location=user_location,
            user_id=current_user.user_id,
            user_issues=user_issues,
            user_language=user_language,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED, response_model_by_alias=False)
@router.post("/", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED, response_model_by_alias=False)
async def create_announcement(
    payload: AnnouncementCreateRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.CREATE_ANNOUNCEMENT)),
):
    """
    Create a new announcement.
    
    MANDATORY FIELDS:
    - title: 5-300 chars
    - content: 20+ chars
    - category: announcement, alert, policy, service, feedback (from 5 enum values)
    - target: role + geographic targeting (optional, defaults to all voters)
    
    OPTIONAL FIELDS:
    - summary, priority, featured_image, tags, require_acknowledgment, etc.
    
    Creates in DRAFT status - must be published to reach audience.
    
    Requires: CREATE_ANNOUNCEMENT permission (Corporator, Leader)
    """
    service = AnnouncementService()
    try:
        return await service.create(payload, current_user.user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{announcement_id}", response_model=AnnouncementResponse, response_model_by_alias=False)
async def update_announcement(
    announcement_id: str,
    payload: AnnouncementUpdateRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.UPDATE_ANNOUNCEMENT)),
):
    """
    Update an existing announcement (draft only).
    
    RESTRICTIONS:
    - Can only update draft announcements
    - Cannot update published announcements
    - Creator only (enforced in service)
    
    Requires: UPDATE_ANNOUNCEMENT permission
    """
    service = AnnouncementService()
    try:
        return await service.update(announcement_id, payload, current_user.user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{announcement_id}/publish", response_model=AnnouncementResponse, response_model_by_alias=False)
async def publish_announcement(
    announcement_id: str,
    payload: AnnouncementPublishRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.UPDATE_ANNOUNCEMENT)),
):
    """
    Publish a draft announcement.
    
    TRIGGERS:
    - Notifications sent to targeted users (role + location)
    - Announcement becomes visible to audience
    - published_at timestamp set
    
    Requires: UPDATE_ANNOUNCEMENT permission
    """
    service = AnnouncementService()
    try:
        return await service.publish(announcement_id, payload, current_user.user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/{announcement_id}/acknowledge", response_model=dict)
async def acknowledge_announcement(
    announcement_id: str,
    payload: AnnouncementAcknowledgeRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Acknowledge receipt of an announcement (if require_acknowledgment=True).
    
    PRIVACY:
    - Tracked privately in metrics
    - Not exposed to viewers
    - Only aggregated count visible (acknowledgment_count)
    """
    service = AnnouncementService()
    try:
        await service.acknowledge(announcement_id, current_user.user_id, payload)
        return {"message": "Announcement acknowledged successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.delete("/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_announcement(
    announcement_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.DELETE_ANNOUNCEMENT)),
):
    """
    Delete an announcement (soft delete - archive).
    
    RESULT:
    - Announcement status set to ARCHIVED
    - Not visible to viewers anymore
    - Historical data preserved
    
    Requires: DELETE_ANNOUNCEMENT permission (Corporator)
    """
    service = AnnouncementService()
    try:
        await service.delete(announcement_id, current_user.user_id)
        return None
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
