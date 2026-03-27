"""
Notification Model Module
==========================
Defines the Notification data model for MongoDB.
Handles in-app and push notifications for users.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from bson import ObjectId

from app.utils.enums import NotificationType


class PyObjectId(ObjectId):
    """Custom type for MongoDB ObjectId with Pydantic"""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class NotificationModel(BaseModel):
    """
    Notification model for in-app and push notifications.
    
    Types:
    - Announcement: New announcement published
    - Poll: New poll opened or reminder
    - Event: Event scheduled or reminder
    - Complaint Update: Complaint status change
    - Appointment Update: Appointment status change
    - System: System alerts
    - General: Other notifications
    """
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    
    # Notification identification
    notification_id: str = Field(..., description="Unique notification tracking ID")
    
    # Recipient
    user_id: str = Field(..., description="Recipient user ID")
    
    # Content
    notification_type: NotificationType
    title: str = Field(..., min_length=5, max_length=200)
    message: str = Field(..., min_length=10, max_length=1000)
    body: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Detailed message body"
    )
    
    # Metadata
    icon_url: Optional[str] = None
    image_url: Optional[str] = None
    
    # Actionable link
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    related_resource_id: Optional[str] = Field(
        default=None,
        description="ID of related announcement/complaint/event/etc"
    )
    related_resource_type: Optional[str] = Field(
        default=None,
        description="Type of related resource"
    )
    
    # Status
    is_read: bool = Field(default=False)
    read_at: Optional[datetime] = None
    
    # Priority
    priority: str = Field(
        default="normal",
        description="low, normal, high, urgent"
    )
    
    # Delivery
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivery_channels: Dict[str, bool] = Field(
        default_factory=lambda: {
            "in_app": True,
            "push": False,
            "email": False,
            "sms": False
        },
        description="Which channels to send through"
    )
    
    # Channel-specific statuses
    in_app_status: str = Field(default="pending", description="pending, sent, displayed")
    push_status: str = Field(default="not_sent", description="not_sent, sent, failed")
    email_status: str = Field(default="not_sent", description="not_sent, sent, failed")
    sms_status: str = Field(default="not_sent", description="not_sent, sent, failed")
    
    # Failure info
    delivery_error: Optional[str] = None
    retry_count: int = Field(default=0)
    last_retry_at: Optional[datetime] = None
    
    # Expiry
    expires_at: Optional[datetime] = None
    is_expired: bool = Field(default=False)
    
    # Engagement
    clicked: bool = Field(default=False)
    clicked_at: Optional[datetime] = None
    dismissed: bool = Field(default=False)
    dismissed_at: Optional[datetime] = None
    
    # User preferences context
    respects_quiet_hours: bool = Field(default=True)
    force_send: bool = Field(default=False, description="Override quiet hours if critical")
    
    # Tags
    tags: list[str] = Field(default_factory=list)
    category: Optional[str] = None
    
    # Localization
    content_language: str = Field(default="en", alias="language")
    
    class Config:
        """Pydantic configuration"""
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "notification_id": "NOT-2024-001",
                "user_id": "voter123",
                "notification_type": "complaint_update",
                "title": "Complaint Status Update",
                "message": "Your complaint has been assigned to a leader",
                "related_resource_id": "COMP-2024-001",
                "related_resource_type": "complaint",
                "priority": "normal",
                "is_read": False
            }
        }
