"""
User Schema Module
==================
Pydantic schemas for user-related endpoints.
Used for request/response validation.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List, Any, Union

from pydantic import BaseModel, ConfigDict, Field, EmailStr
from app.utils.types import PyObjectId

from app.core.roles import UserRole
from app.utils.enums import (
    Gender,
    AgeGroup,
    EducationLevel,
    OccupationCategory,
    AnnualIncomeRange,
)
from app.utils.geo import LocationHierarchy


# -------------------------------------------------------------------
# Base Schema (shared config)
# -------------------------------------------------------------------

class BaseSchema(BaseModel):
    """
    Base schema with common Pydantic configuration.
    """
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        extra="forbid"   # Reject unexpected fields
    )


# -------------------------------------------------------------------
# User Create / Update
# -------------------------------------------------------------------

class UserCreateRequest(BaseSchema):
    """
    Create new user request schema.
    Used ONLY at API boundary (never reused internally).
    """
    email: EmailStr
    mobile_number: str = Field(..., description="Verified mobile number")
    password: str = Field(
        ...,
        min_length=8,
        repr=False,
        description="Plain text password (hashed immediately, never stored)"
    )
    full_name: str = Field(..., min_length=3, max_length=100)
    role: UserRole = Field(default=UserRole.VOTER)
    location: LocationHierarchy
    language_preference: str = Field(default="en")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "voter@example.com",
                "mobile_number": "+919876543210",
                "password": "securepassword123",
                "full_name": "Rajesh Kumar",
                "role": "voter",
                "location": {
                    "state": "Maharashtra",
                    "city": "Mumbai",
                    "ward": "Ward-A",
                    "area": "Andheri East"
                }
            }
        }
    )


class UserUpdateRequest(BaseSchema):
    """
    Update user profile request.
    Only mutable fields are allowed.
    Location updates should ideally go through a separate, audited flow.
    """
    full_name: Optional[str] = Field(default=None, min_length=3, max_length=100)
    profile_photo_url: Optional[str] = None
    language_preference: Optional[str] = None
    location: Optional[LocationHierarchy] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Rajesh Kumar Singh",
                "location": {
                    "state": "Maharashtra",
                    "city": "Mumbai",
                    "area": "Andheri West"
                }
            }
        }
    )


# -------------------------------------------------------------------
# User Responses (Safe, Non-Sensitive)
# -------------------------------------------------------------------

class LeaderTerritory(BaseSchema):
    """
    Territory assignment for leaders (response shape).
    """
    assigned_areas: List[str] = Field(default_factory=list)
    assigned_wards: List[str] = Field(default_factory=list)
    total_voters_assigned: int = Field(default=0)


class UserProfileResponse(BaseSchema):
    """
    User profile response schema.
    Does NOT include sensitive data like password.
    """
    id: PyObjectId = Field(..., alias="_id")
    email: str
    mobile_number: str
    full_name: str
    role: UserRole
    location: LocationHierarchy

    is_active: bool
    is_verified: bool
    is_mobile_verified: bool

    profile_photo_url: Optional[str] = None
    language_preference: str

    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    
    # Additional fields from database
    notification_preferences: Optional[dict] = None
    designation: Optional[str] = None
    constituency: Optional[str] = None
    assigned_leader_id: Optional[PyObjectId] = None
    territory: Optional[LeaderTerritory] = None
    performance: Optional[dict] = None
    assigned_by: Optional[PyObjectId] = None
    assigned_territory: Optional[LocationHierarchy] = None
    demographics: Optional[dict] = None
    engagement: Optional[dict] = None
    leader_responsibilities: Optional[List[str]] = None
    created_by: Optional[PyObjectId] = None
    voter_lookup: Optional[dict] = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "email": "voter@example.com",
                "mobile_number": "+919876543210",
                "full_name": "Rajesh Kumar",
                "role": "voter",
                "location": {
                    "state": "Maharashtra",
                    "city": "Mumbai",
                    "area": "Andheri East"
                },
                "is_active": True,
                "is_verified": True,
                "is_mobile_verified": True,
                "language_preference": "en",
                "created_at": "2026-01-26T10:30:00Z"
            }
        }
    )


class UserListResponse(BaseSchema):
    """
    Paginated list of users.
    """
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[UserProfileResponse]


# -------------------------------------------------------------------
# Voter-Specific Schemas (Analytics Only)
# -------------------------------------------------------------------

class VoterDemographicsRequest(BaseSchema):
    """
    Optional voter demographics.
    Used ONLY for analytics (never for targeting or discrimination).
    """
    voting_location: Optional[str] = Field(default=None, alias="votingLocation")
    age_group: Optional[AgeGroup] = Field(default=None, alias="ageGroup")
    gender: Optional[Gender] = None
    occupation: Optional[OccupationCategory] = Field(default=None, alias="occupationCategory")
    profession: Optional[str] = None
    education: Optional[EducationLevel] = Field(default=None, alias="educationLevel")
    family_adults: Optional[int] = Field(default=None, ge=0, alias="familyAdults")
    family_kids: Optional[int] = Field(default=None, ge=0, alias="familyKids")
    annual_income_range: Optional[AnnualIncomeRange] = Field(default=None, alias="annualIncomeRange")
    religion: Optional[str] = None
    issues_of_interest: List[str] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "age_group": "26_35",
                "gender": "male",
                "occupation": "employed_private",
                "education": "graduate",
                "issues_of_interest": [
                    "infrastructure",
                    "education",
                    "healthcare"
                ]
            }
        }
    )


class VoterEngagementResponse(BaseSchema):
    """
    Derived voter engagement metrics.
    Response-only schema.
    """
    user_id: str
    engagement_level: str
    issues_of_interest: List[str]

    total_complaints: int
    total_polls_participated: int
    total_feedback_given: int

    last_active_date: Optional[datetime] = None
    engagement_score: float


# -------------------------------------------------------------------
# Voter Profile (Voter-only updates)
# -------------------------------------------------------------------

class VoterProfileUpdateRequest(BaseSchema):
    """
    Voter profile update payload (voter only).
    Includes optional demographic and profile fields.
    """
    profile_photo_url: Optional[str] = Field(default=None, alias="profilePhotoUrl")
    voting_location: Optional[str] = Field(default=None, alias="votingLocation")
    age_group: Optional[AgeGroup] = Field(default=None, alias="ageGroup")
    gender: Optional[Gender] = None
    occupation: Optional[OccupationCategory] = Field(default=None, alias="occupationCategory")
    profession: Optional[str] = None
    education: Optional[EducationLevel] = Field(default=None, alias="educationLevel")
    family_adults: Optional[int] = Field(default=None, ge=0, alias="familyAdults")
    family_kids: Optional[int] = Field(default=None, ge=0, alias="familyKids")
    annual_income_range: Optional[AnnualIncomeRange] = Field(default=None, alias="annualIncomeRange")
    religion: Optional[str] = None
    issues_of_interest: Optional[List[str]] = Field(default=None, alias="issuesOfInterest")

# -------------------------------------------------------------------
# Leader / Territory Management
# -------------------------------------------------------------------

class LeaderAssignmentRequest(BaseSchema):
    """
    Assign a leader to voters in a defined territory.
    """
    leader_id: str = Field(..., description="Leader user ID")
    assigned_areas: List[str] = Field(..., description="Area codes")
    assigned_wards: List[str] = Field(default_factory=list)
    total_voters: int = Field(..., ge=1, description="Total voters in territory")
    responsibilities: Optional[List[str]] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "leader_id": "leader123",
                "assigned_areas": ["Andheri East", "Andheri West"],
                "assigned_wards": ["Ward-A", "Ward-B"],
                "total_voters": 5000,
                "responsibilities": ["complaint_followups", "event_coordination"]
            }
        }
    )


class LeaderPerformanceResponse(BaseSchema):
    """
    Derived leader performance metrics.
    Response-only schema.
    """
    leader_id: str
    full_name: str
    location: LocationHierarchy

    messages_shared: int
    complaints_followed_up: int
    complaints_handled: int
    complaints_resolved: int
    events_participated: int
    voter_interactions: int
    poll_responses: int
    poll_response_rate: float
    engagement_level: str

    average_response_time_hours: float
    rating: float
    performance_score: float
    tasks_assigned: int
    tasks_completed: int
    ground_verifications_completed: int


# -------------------------------------------------------------------
# Notifications
# -------------------------------------------------------------------

class NotificationPreferencesRequest(BaseSchema):
    """
    User notification preferences.
    """
    email: bool = Field(default=True)
    sms: bool = Field(default=True)
    push: bool = Field(default=True)

    quiet_hours_start: Optional[str] = Field(
        default=None,
        description="HH:MM format"
    )
    quiet_hours_end: Optional[str] = Field(
        default=None,
        description="HH:MM format"
    )

    receive_announcements: bool = Field(default=True)
    receive_polls: bool = Field(default=True)
    receive_events: bool = Field(default=True)
    receive_updates: bool = Field(default=True)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": True,
                "sms": True,
                "push": True,
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "08:00"
            }
        }
    )


# -------------------------------------------------------------------
# Ground Verification (Phase 6 - New)
# -------------------------------------------------------------------

class GroundVerificationRequest(BaseSchema):
    """
    Request to log a ground verification.
    """
    location: LocationHierarchy = Field(..., description="Where verification was done")
    photos: List[str] = Field(
        default_factory=list,
        description="URLs of verification photos"
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Any notes about the verification"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "location": {
                    "state": "Maharashtra",
                    "city": "Mumbai",
                    "area": "Andheri East",
                    "building": "Main Street Junction"
                },
                "photos": [
                    "https://example.com/photo1.jpg",
                    "https://example.com/photo2.jpg"
                ],
                "notes": "Pothole verified, measurements taken for repair estimate"
            }
        }
    )


# -------------------------------------------------------------------
# User Directory (For Appointment Booking)
# -------------------------------------------------------------------

class DirectoryUserLocation(BaseSchema):
    """Simplified location for directory."""
    area: str = ""
    ward: str = ""
    city: str = ""

class DirectoryUser(BaseSchema):
    """Non-PII user data for searchable directory."""
    id: str
    full_name: str
    role: str
    location: DirectoryUserLocation

class UserDirectoryResponse(BaseSchema):
    """Directory response schema."""
    success: bool = True
    data: List[DirectoryUser]
    total: int
