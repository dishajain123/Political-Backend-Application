"""
Announcement Model Module
==========================
Defines the Announcement data model for MongoDB.
Handles official announcements from corporators/leaders.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from bson import ObjectId

from app.utils.enums import AnnouncementStatus, AnnouncementPriority, AnnouncementCategory
from app.utils.geo import LocationHierarchy


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


class AnnouncementTarget(BaseModel):
    """
    Targeting information for announcements.
    Determines who sees this announcement.
    """
    roles: List[str] = Field(
        default_factory=list,
        description="voter, leader, all"
    )
    geography: Optional[LocationHierarchy] = None
    regions: Optional[List[LocationHierarchy]] = None
    issue_categories: List[str] = Field(
        default_factory=list,
        description="Issue categories for targeting (e.g., roads, water_supply)"
    )
    specific_users: List[str] = Field(
        default_factory=list,
        description="Specific user IDs (if targeted)"
    )


class AnnouncementMetrics(BaseModel):
    """
    Engagement metrics for announcements.
    """
    view_count: int = Field(default=0)
    unique_viewers: List[str] = Field(default_factory=list)
    share_count: int = Field(default=0)
    reaction_count: int = Field(default=0)
    comment_count: int = Field(default=0)
    acknowledgment_count: int = Field(default=0)
    acknowledgment_users: List[str] = Field(default_factory=list)


class AnnouncementModel(BaseModel):
    """
    Announcement model for official communications from leadership.
    
    Announcement lifecycle:
        Draft -> Published -> Archived
    """
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    
    # Announcement identification
    announcement_id: str = Field(..., description="Unique announcement tracking ID")
    
    # Creator
    created_by: str = Field(..., description="Corporator/Leader user ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Content
    title: str = Field(..., min_length=5, max_length=300)
    content: str = Field(..., min_length=20, max_length=5000)
    summary: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Short summary for preview"
    )
    
    # Status
    status: AnnouncementStatus = Field(default=AnnouncementStatus.DRAFT)
    status_updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Publishing
    priority: AnnouncementPriority = Field(default=AnnouncementPriority.NORMAL)
    published_at: Optional[datetime] = None
    scheduled_publish_at: Optional[datetime] = None
    
    # Expiry
    expiry_date: Optional[datetime] = None
    expires_on: Optional[datetime] = None
    
    # Targeting
    target: AnnouncementTarget = Field(default_factory=AnnouncementTarget)
    content_language: Optional[str] = Field(
        default=None,
        alias="language",
        description="Language code for this announcement (e.g., en, hi, mr)."
    )
    
    # Media
    featured_image_url: Optional[str] = None
    banner_url: Optional[str] = None
    attachment_urls: List[str] = Field(default_factory=list)
    video_urls: List[str] = Field(default_factory=list)
    media_gallery: List[str] = Field(default_factory=list)
    
    # Tags and categories
    tags: List[str] = Field(default_factory=list)
    category: AnnouncementCategory = Field(default=AnnouncementCategory.ANNOUNCEMENT)
    hashtags: List[str] = Field(default_factory=list)
    
    # Authority information
    authority_level: str = Field(
        default="leader",
        description="corporator, leader, ops"
    )
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    
    # Engagement
    metrics: AnnouncementMetrics = Field(default_factory=AnnouncementMetrics)
    is_pinned: bool = Field(default=False)
    pin_until: Optional[datetime] = None
    
    # Features
    enable_comments: bool = Field(default=True)
    enable_sharing: bool = Field(default=True)
    require_acknowledgment: bool = Field(default=False)
    acknowledgment_count: int = Field(default=0)
    
    # Updates
    update_history: List[Dict] = Field(
        default_factory=list,
        description="History of updates to announcement"
    )
    
    # Related content
    related_announcement_ids: List[str] = Field(default_factory=list)
    related_event_ids: List[str] = Field(default_factory=list)
    related_poll_ids: List[str] = Field(default_factory=list)
    
    # Metadata
    visibility: str = Field(
        default="public",
        description="public, private, restricted"
    )
    urgency: str = Field(
        default="normal",
        description="normal, important, urgent, critical"
    )
    requires_action: bool = Field(default=False)
    action_required_by: Optional[datetime] = None
    
    class Config:
        """Pydantic configuration"""
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "announcement_id": "ANN-2024-001",
                "title": "New Community Development Initiative",
                "content": "We are pleased to announce a new initiative...",
                "created_by": "corporator123",
                "status": "published",
                "priority": "high",
                "target": {
                    "roles": ["voter", "leader"],
                    "geography": {
                        "state": "Maharashtra",
                        "city": "Mumbai"
                    }
                }
            }
        }
