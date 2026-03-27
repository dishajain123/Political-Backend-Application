"""
Notification Routes
===================
API endpoints for in-app notifications.

Responsibilities:
- Fetch notifications for the logged-in user
- Mark notifications as read
- Ensure users can only access their own notifications
- VOTER role: receive notifications (consumers), cannot send

Access Control:
- VIEW_NOTIFICATION: All authenticated roles
- SEND_NOTIFICATION: Corporator, OPS (not available to Voters/Leaders)

Author: Political Communication Platform Team
"""

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from app.api.dependencies import require_permission, get_current_user, CurrentUser
from app.core.permissions import Permission
from app.services.notification_service import NotificationService
from app.schemas.notification_schema import (
    NotificationListResponse,
    NotificationResponse,
)
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    response_model_by_alias=False,
    summary="List notifications for current user"
)
@router.get(
    "/",
    response_model=NotificationListResponse,
    response_model_by_alias=False,
    summary="List notifications for current user"
)
async def list_notifications(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_NOTIFICATION)
    ),
):
    """
    Fetch notifications for the logged-in user.

    Access Control:
    - All authenticated roles (Voter, Leader, Corporator, OPS)
    - Users can ONLY view their own notifications

    Data Safety:
    - Notifications filtered by user_id at database query level
    - Users cannot access other users' notifications
    - Pagination: default 20 items/page, max 100

    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - is_read: Optional filter (True/False/None for all)

    Returns:
    - NotificationListResponse with paginated items
    - unread_count: Number of unread notifications
    - total: Total notifications for user
    """
    skip = (page - 1) * page_size
    limit = page_size
    
    service = NotificationService()
    try:
        return await service.list_for_user(
            user_id=current_user.user_id,
            skip=skip,
            limit=limit,
            is_read_filter=is_read,
        )
    except Exception as e:
        logger.error(f"Error listing notifications for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving notifications"
        )


@router.get(
    "/{notification_id}",
    response_model=NotificationResponse,
    response_model_by_alias=False,
    summary="Get a specific notification"
)
async def get_notification(
    notification_id: str = Path(..., description="Notification ID"),
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_NOTIFICATION)
    ),
):
    """
    Get a specific notification by ID.

    Access Control:
    - Users can ONLY view their own notifications
    - Ownership verified at service layer

    Data Safety:
    - Query includes both user_id and notification_id filters
    - Returns 404 if notification doesn't belong to user
    """
    service = NotificationService()
    try:
        notification = await service.get_by_id(
            notification_id=notification_id,
            user_id=current_user.user_id,
        )
        if not notification:
            logger.warning(
                f"Unauthorized access attempt: user {current_user.user_id} "
                f"tried to access notification {notification_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        return notification
    except Exception as e:
        logger.error(f"Error retrieving notification {notification_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving notification"
        )


@router.patch(
    "/{notification_id}/read",
    response_model=dict,
    summary="Mark notification as read"
)
async def mark_notification_read(
    notification_id: str = Path(..., description="Notification ID"),
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_NOTIFICATION)
    ),
):
    """
    Mark a notification as read.

    Access Control:
    - Users can ONLY mark their own notifications as read
    - Ownership verified at query level (user_id filter)

    Data Safety:
    - Query requires both user_id AND notification_id
    - Cannot modify another user's notification
    
    Returns:
    - {success: True, message: "..."} if marked
    - 404 if notification doesn't belong to user
    """
    service = NotificationService()
    try:
        success = await service.mark_as_read(
            notification_id=notification_id,
            user_id=current_user.user_id,
        )
        
        if not success:
            logger.warning(
                f"Unauthorized update attempt: user {current_user.user_id} "
                f"tried to mark notification {notification_id} as read"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found or already marked as read"
            )
        
        return {
            "success": True,
            "message": "Notification marked as read"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking notification {notification_id} as read: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating notification"
        )


@router.patch(
    "/mark-all-read",
    response_model=dict,
    summary="Mark all notifications as read"
)
async def mark_all_notifications_read(
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_NOTIFICATION)
    ),
):
    """
    Mark all notifications as read for current user.

    Access Control:
    - Users can only mark their OWN notifications as read
    - Scoped by user_id

    Returns:
    - {success: True, count: number_updated}
    """
    service = NotificationService()
    try:
        count = await service.mark_all_as_read(
            user_id=current_user.user_id,
        )
        
        return {
            "success": True,
            "message": f"Marked {count} notifications as read",
            "count": count
        }
    except Exception as e:
        logger.error(f"Error marking all notifications as read for user {current_user.user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating notifications"
        )


@router.delete(
    "/{notification_id}",
    response_model=dict,
    summary="Delete/dismiss a notification"
)
async def delete_notification(
    notification_id: str = Path(..., description="Notification ID"),
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_NOTIFICATION)
    ),
):
    """
    Delete/dismiss a notification.

    Access Control:
    - Users can ONLY delete their own notifications
    - Ownership verified at query level

    Returns:
    - {success: True, message: "..."} if deleted
    - 404 if notification doesn't belong to user
    """
    service = NotificationService()
    try:
        success = await service.delete(
            notification_id=notification_id,
            user_id=current_user.user_id,
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        return {
            "success": True,
            "message": "Notification deleted"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting notification {notification_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting notification"
        )


# ============================================================================
# ADMIN/INTERNAL ENDPOINTS - SEND NOTIFICATIONS
# ============================================================================

@router.post(
    "/send",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    summary="Send notification to user (admin only)"
)
async def send_notification(
    user_id: str = Query(..., description="Recipient user ID"),
    title: str = Query(..., min_length=5, max_length=200),
    message: str = Query(..., min_length=10, max_length=1000),
    notification_type: str = Query(default="general", description="Notification type"),
    current_user: CurrentUser = Depends(
        require_permission(Permission.SEND_NOTIFICATION)
    ),
):
    """
    Send a notification to a specific user.

    Access Control:
    - SEND_NOTIFICATION permission required
    - Only Corporator and OPS can send notifications
    - Voters cannot send notifications

    Query Parameters:
    - user_id: Recipient's user ID
    - title: Notification title (5-200 chars)
    - message: Notification message (10-1000 chars)
    - notification_type: Type of notification (default: "general")

    Returns:
    - {success: True, notification_id: "..."}
    """
    service = NotificationService()
    try:
        notification_id = await service.notify(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            sender_id=current_user.user_id,
        )
        
        return {
            "success": True,
            "message": f"Notification sent to user {user_id}",
            "notification_id": notification_id
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error sending notification"
        )