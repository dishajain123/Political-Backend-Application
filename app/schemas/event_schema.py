"""
Event Schema Module
===================
Pydantic schemas for event-related endpoints.

Author: Political Communication Platform Team
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.utils.enums import EventType, EventStatus
from app.utils.geo import LocationHierarchy


class EventCreateRequest(BaseModel):
    """
    Create new event request.
    """
    title: str = Field(..., min_length=5, max_length=300)
    description: str = Field(..., min_length=10, max_length=3000)
    event_type: EventType
    event_date: datetime = Field(...)
    end_date: Optional[datetime] = None
    duration_hours: Optional[float] = None
    location: LocationHierarchy
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    estimated_attendees: Optional[int] = None
    max_capacity: Optional[int] = None
    speakers: List[str] = Field(default_factory=list)
    agenda: Optional[List[str]] = None
    banner_url: Optional[str] = None
    poster_url: Optional[str] = None
    document_urls: Optional[List[str]] = None
    media_urls: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    is_public: bool = Field(default=True)
    registration_deadline: Optional[datetime] = None
    content_language: Optional[str] = Field(
        default=None,
        alias="language",
        description="Language code for this event (e.g., en, hi, mr)."
    )
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "title": "Community Health Awareness Drive",
                "description": "Free health checkup and awareness session",
                "event_type": "awareness",
                "event_date": "2024-02-25T09:00:00Z",
                "location": {
                    "state": "Maharashtra",
                    "city": "Mumbai",
                    "area": "Andheri"
                },
                "venue_name": "Community Center",
                "estimated_attendees": 500
            }
        }


class EventCreate(EventCreateRequest):
    """Create new event request (legacy name)."""


class EventUpdateRequest(BaseModel):
    """
    Update event details.
    """
    title: Optional[str] = Field(default=None, min_length=5, max_length=300)
    description: Optional[str] = Field(default=None, min_length=10, max_length=3000)
    event_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    speakers: Optional[List[str]] = None
    agenda: Optional[List[str]] = None
    estimated_attendees: Optional[int] = None
    organizer_notes: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Updated Event Title",
                "estimated_attendees": 600
            }
        }


class EventAssignLeaderRequest(BaseModel):
    """
    Assign leaders to manage an event.
    """
    leader_ids: List[str] = Field(..., description="List of leader user IDs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "leader_ids": ["leader1", "leader2", "leader3"]
            }
        }


class EventStatusUpdateRequest(BaseModel):
    """
    Update event status.
    """
    status: EventStatus
    reason: Optional[str] = Field(default=None, max_length=500)
    postponed_to: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "postponed",
                "reason": "Bad weather forecast",
                "postponed_to": "2024-03-05T09:00:00Z"
            }
        }


class EventRegisterRequest(BaseModel):
    """
    Register for an event.
    """
    is_attending: bool = Field(default=True)
    comments: Optional[str] = Field(default=None, max_length=500)
    number_of_attendees: int = Field(default=1, ge=1, le=10)
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_attending": True,
                "number_of_attendees": 2
            }
        }


class EventFeedbackRequest(BaseModel):
    """
    Provide feedback after event completion.
    """
    rating: int = Field(..., ge=1, le=5)
    comments: Optional[str] = Field(default=None, max_length=500)
    attended: bool = Field(default=True)
    
    class Config:
        json_schema_extra = {
            "example": {
                "rating": 4,
                "comments": "Well organized event, good speakers",
                "attended": True
            }
        }


class EventResponse(BaseModel):
    """
    Event response with full details.
    """
    id: str = Field(..., alias="_id")
    event_id: str
    title: str
    description: str
    event_type: EventType
    event_date: str
    location: LocationHierarchy
    status: EventStatus
    created_by: str
    created_at: str
    estimated_attendees: Optional[int] = None
    actual_attendees: int
    is_public: bool
    registrations_count: Optional[int] = None
    registrations_by_role: Optional[dict] = None
    is_registered: Optional[bool] = None
    
    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "event_id": "EVT-2024-001",
                "title": "Community Health Awareness",
                "event_type": "awareness",
                "status": "scheduled"
            }
        }


class EventListResponse(BaseModel):
    """
    List of events with pagination.
    """
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[EventResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 30,
                "page": 1,
                "page_size": 10,
                "total_pages": 3,
                "items": []
            }
        }


class EventAnalyticsResponse(BaseModel):
    """
    Event analytics and performance metrics.
    """
    event_id: str
    title: str
    status: EventStatus
    registrations: int
    actual_attendees: int
    attendance_rate: float
    average_feedback_rating: float
    total_feedback_count: int
    engagement_score: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "EVT-2024-001",
                "title": "Community Health Awareness",
                "registrations": 250,
                "actual_attendees": 200,
                "attendance_rate": 80.0,
                "average_feedback_rating": 4.3
            }
        }


class EventParticipantItem(BaseModel):
    user_id: str
    name: str
    role: str
    phone: Optional[str] = None
    attended: bool = False
    feedback_rating: Optional[int] = None
    registered_at: Optional[str] = None


class EventParticipantsResponse(BaseModel):
    event_id: str
    total_registered: int
    total_attended: int
    users: List[EventParticipantItem]
