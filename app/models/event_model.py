"""
Event Model Module
==================
Defines the Event data model for MongoDB.
Handles public events, rallies, town halls, campaigns, etc.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from bson import ObjectId

from app.utils.enums import EventType, EventStatus
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


class EventParticipation(BaseModel):
    """
    Record of participant attendance at an event.
    """
    user_id: str = Field(..., description="Participant user ID")
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    attended: bool = Field(default=False)
    feedback_rating: Optional[int] = Field(default=None, ge=1, le=5)
    feedback_comment: Optional[str] = None


class EventModel(BaseModel):
    """
    Event model for organizing political events, rallies, town halls, etc.
    
    Event lifecycle:
        Scheduled -> Ongoing -> Completed/Cancelled/Postponed
    """
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    
    # Event identification
    event_id: str = Field(..., description="Unique event tracking ID")
    title: str = Field(..., min_length=5, max_length=300)
    description: str = Field(..., min_length=10, max_length=3000)
    event_type: EventType
    
    # Creator
    created_by: str = Field(..., description="Corporator/Leader user ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Scheduling
    event_date: datetime = Field(..., description="Event start date and time")
    end_date: Optional[datetime] = None
    duration_hours: Optional[float] = None
    
    # Location
    location: LocationHierarchy = Field(..., description="Event venue location")
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    
    # Status
    status: EventStatus = Field(default=EventStatus.SCHEDULED)
    status_updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Event management
    estimated_attendees: Optional[int] = None
    actual_attendees: int = Field(default=0)
    participation_rate: float = Field(default=0.0)
    max_capacity: Optional[int] = None
    
    # Leadership
    assigned_leaders: List[str] = Field(
        default_factory=list,
        description="Leader user IDs assigned to manage event"
    )
    organizer_notes: Optional[str] = None
    
    # Content
    agenda: Optional[List[str]] = Field(
        default=None,
        description="Planned agenda items"
    )
    speakers: List[str] = Field(
        default_factory=list,
        description="Names of speakers/participants"
    )
    
    # Attachments
    banner_url: Optional[str] = None
    poster_url: Optional[str] = None
    document_urls: List[str] = Field(default_factory=list)
    media_urls: List[str] = Field(default_factory=list)
    
    # Participation
    registrations: List[EventParticipation] = Field(
        default_factory=list,
        description="List of registered participants"
    )
    registration_open: bool = Field(default=True)
    registration_deadline: Optional[datetime] = None
    
    # Cancellation/Postponement
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    postponed_to: Optional[datetime] = None
    postponement_reason: Optional[str] = None
    
    # Budget
    estimated_budget: Optional[float] = None
    actual_expense: Optional[float] = None
    budget_notes: Optional[str] = None
    
    # Visibility
    is_public: bool = Field(default=True)
    is_featured: bool = Field(default=False)
    visibility_level: str = Field(
        default="public",
        description="public, leaders_only, registered_only"
    )
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    priority: int = Field(default=0, description="Display priority")
    content_language: Optional[str] = Field(
        default=None,
        alias="language",
        description="Language code for this event (e.g., en, hi, mr)."
    )
    
    class Config:
        """Pydantic configuration"""
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "event_id": "EVT-2024-001",
                "title": "Community Health Awareness Drive",
                "description": "Free health checkup and awareness session",
                "event_type": "awareness",
                "created_by": "leader123",
                "event_date": "2024-02-25T09:00:00Z",
                "location": {
                    "state": "Maharashtra",
                    "city": "Mumbai",
                    "area": "Andheri",
                    "building": "Community Center"
                },
                "status": "scheduled",
                "estimated_attendees": 500
            }
        }
