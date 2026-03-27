"""
Announcement Schema Module
==========================
Pydantic schemas for announcement-related endpoints.

Author: Political Communication Platform Team
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.utils.enums import AnnouncementStatus, AnnouncementPriority, AnnouncementCategory
from app.utils.geo import LocationHierarchy


class AnnouncementTargetRequest(BaseModel):
    """
    Target audience for announcement.
    """
    roles: Optional[List[str]] = Field(default=None)
    geography: Optional[LocationHierarchy] = None
    regions: Optional[List[LocationHierarchy]] = None
    issue_categories: Optional[List[str]] = None
    specific_users: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "roles": ["voter", "leader"],
                "geography": {
                    "state": "Maharashtra",
                    "city": "Mumbai"
                },
                "issue_categories": ["roads", "water_supply"]
            }
        }


class AnnouncementCreateRequest(BaseModel):
    """
    Create new announcement request.
    
    CRITICAL VALIDATIONS:
    - title: MANDATORY, 5-300 chars
    - content: MANDATORY, 20-5000 chars
    - category: MANDATORY, must be one of 5 types
    
    LEADER-SPECIFIC FIELDS:
    - parent_announcement_id: MANDATORY for Leaders (references Corporator announcement)
    - local_context: Leader's additional context/notes for their territory
    """
    title: str = Field(..., min_length=5, max_length=300, description="Title is mandatory")
    content: str = Field(..., min_length=20, max_length=5000, description="Body/content is mandatory")
    summary: Optional[str] = Field(default=None, max_length=500)
    priority: AnnouncementPriority = Field(default=AnnouncementPriority.NORMAL)
    category: AnnouncementCategory = Field(..., description="Category is MANDATORY - must be one of: announcement, policy, scheme, achievement, party_message")
    target: Optional[AnnouncementTargetRequest] = None
    featured_image_url: Optional[str] = None
    banner_url: Optional[str] = None
    attachment_urls: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    require_acknowledgment: bool = Field(default=False)
    enable_comments: bool = Field(default=True)
    is_public: bool = Field(default=True)
    scheduled_publish_at: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    content_language: Optional[str] = Field(
        default=None,
        alias="language",
        description="Language code for this announcement (e.g., en, hi, mr)."
    )
    
    # LEADER-SPECIFIC FIELDS
    parent_announcement_id: Optional[str] = Field(
        default=None,
        description="For Leaders: Reference to parent Corporator announcement (MANDATORY for Leader announcements)"
    )
    local_context: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="For Leaders: Additional local context/notes for assigned territory"
    )
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is not empty after stripping whitespace"""
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate content is not empty after stripping whitespace"""
        if not v or not v.strip():
            raise ValueError('Content/Body cannot be empty')
        return v.strip()
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "title": "New Community Development Initiative",
                "content": "We are pleased to announce a new initiative for community development. This comprehensive program will focus on infrastructure improvements, educational opportunities, and health services for all residents in our ward.",
                "category": "policy",
                "priority": "high",
                "target": {
                    "roles": ["voter", "leader"],
                    "geography": {
                        "state": "Maharashtra",
                        "city": "Mumbai"
                    }
                },
                "is_public": True
            }
        }


class AnnouncementCreate(AnnouncementCreateRequest):
    """Create new announcement request (legacy name)."""


class AnnouncementUpdateRequest(BaseModel):
    """
    Update announcement details.
    All fields are optional for partial updates.
    """
    title: Optional[str] = Field(default=None, min_length=5, max_length=300)
    content: Optional[str] = Field(default=None, min_length=20, max_length=5000)
    summary: Optional[str] = Field(default=None, max_length=500)
    priority: Optional[AnnouncementPriority] = None
    category: Optional[AnnouncementCategory] = None
    featured_image_url: Optional[str] = None
    tags: Optional[List[str]] = None
    is_pinned: Optional[bool] = None
    pin_until: Optional[datetime] = None
    local_context: Optional[str] = Field(default=None, max_length=2000, description="Leader's local context")
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        """Validate title is not empty if provided"""
        if v is not None and (not v or not v.strip()):
            raise ValueError('Title cannot be empty')
        return v.strip() if v else None
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: Optional[str]) -> Optional[str]:
        """Validate content is not empty if provided"""
        if v is not None and (not v or not v.strip()):
            raise ValueError('Content cannot be empty')
        return v.strip() if v else None
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Updated Announcement Title",
                "priority": "urgent",
                "category": "achievement"
            }
        }


class AnnouncementPublishRequest(BaseModel):
    """
    Publish a draft announcement.
    """
    scheduled_publish_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "scheduled_publish_at": "2024-02-20T09:00:00Z"
            }
        }


class AnnouncementAcknowledgeRequest(BaseModel):
    """
    Acknowledge receipt of announcement (if required).
    """
    acknowledgment_text: Optional[str] = Field(default=None, max_length=500)
    
    class Config:
        json_schema_extra = {
            "example": {
                "acknowledgment_text": "Understood and noted"
            }
        }


class AnnouncementResponse(BaseModel):
    """
    Announcement response with full details.
    """
    id: str = Field(..., alias="_id")
    announcement_id: str
    title: str
    content: Optional[str] = None
    summary: Optional[str] = None
    banner_url: Optional[str] = None
    priority: str
    status: str
    category: str
    created_by: str
    created_at: str
    published_at: Optional[str] = None
    expiry_date: Optional[str] = None
    is_public: bool
    is_pinned: bool
    metrics: dict
    parent_announcement_id: Optional[str] = None
    local_context: Optional[str] = None
    is_leader_message: bool = Field(default=False, description="True if created by Leader")
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "announcement_id": "ANN-2024-001",
                "title": "New Community Development Initiative",
                "content": "Full announcement content here...",
                "category": "policy",
                "priority": "high",
                "status": "published",
                "is_public": True,
                "metrics": {
                    "view_count": 450,
                    "share_count": 23
                }
            }
        }


class AnnouncementListResponse(BaseModel):
    """
    List of announcements with pagination.
    """
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[AnnouncementResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 100,
                "page": 1,
                "page_size": 10,
                "total_pages": 10,
                "items": []
            }
        }


class AnnouncementAnalyticsResponse(BaseModel):
    """
    Announcement engagement analytics.
    """
    announcement_id: str
    title: str
    priority: str
    category: str
    view_count: int
    unique_viewers: int
    share_count: int
    reaction_count: int
    comment_count: int
    acknowledgment_count: int
    acknowledgment_rate: float
    engagement_score: float
    reach: int
    impressions: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "announcement_id": "ANN-2024-001",
                "title": "New Community Development Initiative",
                "category": "policy",
                "view_count": 450,
                "unique_viewers": 400,
                "share_count": 23,
                "engagement_score": 0.65
            }
        }


class AnnouncementStatsResponse(BaseModel):
    """
    Announcement statistics for dashboard.
    """
    total_announcements: int
    by_priority: dict
    by_status: dict
    by_category: dict
    average_engagement_score: float
    most_viewed_announcements: List[dict]
    upcoming_scheduled: List[dict]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_announcements": 150,
                "by_priority": {
                    "urgent": 5,
                    "high": 25,
                    "normal": 100
                },
                "by_status": {
                    "draft": 10,
                    "published": 135,
                    "archived": 5
                },
                "by_category": {
                    "announcement": 50,
                    "policy": 30,
                    "scheme": 25,
                    "achievement": 20,
                    "party_message": 25
                }
            }
        }
