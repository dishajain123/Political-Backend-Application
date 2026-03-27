"""
Notification Schema Module
==========================
Pydantic schemas for notification-related endpoints.

Author: Political Communication Platform Team
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime
from app.utils.enums import NotificationType


class NotificationCreateRequest(BaseModel):
    """
    Create and send a notification.
    """
    user_id: str = Field(..., description="Recipient user ID")
    notification_type: NotificationType
    title: str = Field(..., min_length=5, max_length=200)
    message: str = Field(..., min_length=10, max_length=1000)
    body: Optional[str] = Field(default=None, max_length=2000)
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    related_resource_id: Optional[str] = None
    related_resource_type: Optional[str] = None
    priority: str = Field(default="normal")
    delivery_channels: Optional[Dict[str, bool]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "voter123",
                "notification_type": "complaint_update",
                "title": "Complaint Status Update",
                "message": "Your complaint has been assigned to a leader",
                "related_resource_id": "COMP-2024-001",
                "priority": "normal"
            }
        }


class BulkNotificationRequest(BaseModel):
    """
    Send notification to multiple users.
    """
    user_ids: List[str] = Field(..., description="List of recipient user IDs")
    notification_type: NotificationType
    title: str = Field(..., min_length=5, max_length=200)
    message: str = Field(..., min_length=10, max_length=1000)
    priority: str = Field(default="normal")
    delivery_channels: Optional[Dict[str, bool]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_ids": ["voter1", "voter2", "voter3"],
                "notification_type": "announcement",
                "title": "New Announcement",
                "message": "A new important announcement has been published",
                "priority": "high"
            }
        }


class NotificationMarkReadRequest(BaseModel):
    """
    Mark notification as read.
    """
    notification_ids: Optional[List[str]] = Field(
        default=None,
        description="Mark specific notifications as read"
    )
    mark_all: bool = Field(
        default=False,
        description="Mark all notifications as read"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "notification_ids": ["NOT-001", "NOT-002"]
            }
        }


class NotificationDismissRequest(BaseModel):
    """
    Dismiss/delete notification.
    """
    notification_ids: Optional[List[str]] = None
    dismiss_all: bool = Field(default=False)
    
    class Config:
        json_schema_extra = {
            "example": {
                "notification_ids": ["NOT-001"]
            }
        }


class NotificationUpdatePreferencesRequest(BaseModel):
    """
    Update user notification preferences.
    """
    delivery_channels: Optional[Dict[str, bool]] = None
    quiet_hours_enabled: bool = Field(default=False)
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None
    notification_types: Optional[Dict[str, bool]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "delivery_channels": {
                    "in_app": True,
                    "push": True,
                    "email": False,
                    "sms": False
                },
                "quiet_hours_enabled": True,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00"
            }
        }


class NotificationResponse(BaseModel):
    """
    Notification response with full details.
    """
    id: str = Field(..., alias="_id")
    notification_id: str
    user_id: str
    notification_type: NotificationType
    title: str
    message: str
    priority: str
    is_read: bool
    read_at: Optional[str] = None
    created_at: str
    action_url: Optional[str] = None
    related_resource_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "notification_id": "NOT-2024-001",
                "user_id": "voter123",
                "notification_type": "complaint_update",
                "title": "Complaint Status Update",
                "priority": "normal",
                "is_read": False
            }
        }


class NotificationListResponse(BaseModel):
    """
    List of notifications with pagination.
    """
    total: int
    page: int
    page_size: int
    total_pages: int
    unread_count: int
    items: List[NotificationResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 50,
                "page": 1,
                "page_size": 20,
                "total_pages": 3,
                "unread_count": 5,
                "items": []
            }
        }


class NotificationStatsResponse(BaseModel):
    """
    Notification statistics for user.
    """
    user_id: str
    total_notifications: int
    unread_count: int
    by_type: Dict[str, int]
    by_priority: Dict[str, int]
    delivery_status: Dict[str, int]
    last_notification_at: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "voter123",
                "total_notifications": 150,
                "unread_count": 5,
                "by_type": {
                    "announcement": 50,
                    "complaint_update": 40,
                    "event": 30
                }
            }
        }


class NotificationBatchResponse(BaseModel):
    """
    Response for bulk notification operations.
    """
    success: bool
    message: str
    total_sent: int
    total_failed: int
    failed_user_ids: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Notifications sent successfully",
                "total_sent": 45,
                "total_failed": 2,
                "failed_user_ids": ["user_invalid_1"]
            }
        }