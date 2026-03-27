"""
User Model Module
================
Defines the User data model for MongoDB.
Handles Corporators, Leaders, and Voters with role-specific fields.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, EmailStr
from app.utils.types import PyObjectId

from app.core.roles import UserRole
from app.utils.enums import (
    Gender,
    AgeGroup,
    EducationLevel,
    OccupationCategory,
    EngagementLevel,
    AnnualIncomeRange,
)
from app.utils.geo import LocationHierarchy


# Note: PyObjectId is now imported from app.utils.types


class VoterDemographics(BaseModel):
    """
    Demographic data for voters (for analytics only).
    This data is NEVER exposed publicly, only in aggregated analytics.
    """
    voting_location: Optional[str] = None
    age_group: Optional[AgeGroup] = None
    gender: Optional[Gender] = None
    religion: Optional[str] = None
    occupation: Optional[OccupationCategory] = None
    profession: Optional[str] = None
    education: Optional[EducationLevel] = None
    family_adults: Optional[int] = Field(default=None, ge=0)
    family_kids: Optional[int] = Field(default=None, ge=0)
    annual_income_range: Optional[AnnualIncomeRange] = None


class VoterEngagement(BaseModel):
    """
    Tracks voter engagement metrics.
    """
    level: EngagementLevel = Field(default=EngagementLevel.PASSIVE)
    issues_of_interest: List[str] = Field(default_factory=list)
    last_active_date: Optional[datetime] = None
    total_complaints: int = Field(default=0)
    total_polls_participated: int = Field(default=0)
    total_feedback_given: int = Field(default=0)


class LeaderTerritory(BaseModel):
    """
    Territory assignment for leaders.
    """
    assigned_areas: List[str] = Field(default_factory=list)
    assigned_wards: List[str] = Field(default_factory=list)
    total_voters_assigned: int = Field(default=0)


class LeaderPerformance(BaseModel):
    """
    Performance tracking for leaders.
    """
    messages_shared: int = Field(default=0)
    complaints_followed_up: int = Field(default=0)
    complaints_handled: int = Field(default=0)
    complaints_resolved: int = Field(default=0)
    events_participated: int = Field(default=0)
    voter_interactions: int = Field(default=0)
    poll_responses: int = Field(default=0)
    poll_response_rate: float = Field(default=0.0)
    engagement_level: str = Field(default="low")
    average_response_time_hours: float = Field(default=0.0)
    rating: float = Field(default=0.0, ge=0, le=5)
    tasks_assigned: int = Field(default=0)
    tasks_completed: int = Field(default=0)
    ground_verifications_completed: int = Field(default=0)


class UserModel(BaseModel):
    """
    Main User model supporting all roles: Corporator, Leader, Voter, Ops.
    Role-specific fields are optional and used based on the user's role.
    """
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    
    # Basic information (all roles)
    email: str
    mobile_number: str = Field(..., description="Verified mobile number")
    password_hash: str = Field(..., description="Bcrypt hashed password")
    full_name: str
    profile_photo_url: Optional[str] = None
    role: UserRole
    
    # Location (all roles)
    location: LocationHierarchy
    
    # Account status
    is_active: bool = Field(default=True)
    is_verified: bool = Field(default=False)
    is_mobile_verified: bool = Field(default=False)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    
    # Voter-specific fields
    assigned_leader_id: Optional[PyObjectId] = None  # Leader assigned to this voter
    demographics: Optional[VoterDemographics] = None  # Only for voters
    engagement: Optional[VoterEngagement] = None  # Only for voters
    
    # Leader-specific fields
    territory: Optional[LeaderTerritory] = None  # Only for leaders
    performance: Optional[LeaderPerformance] = None  # Only for leaders
    assigned_by: Optional[PyObjectId] = None  # Corporator who assigned this leader
    leader_responsibilities: List[str] = Field(default_factory=list)
    
    # Corporator-specific fields
    designation: Optional[str] = None  # MLA, MP, etc.
    constituency: Optional[str] = None
    
    # Preferences
    language_preference: str = Field(default="en")
    notification_preferences: dict = Field(
        default_factory=lambda: {
            "email": True,
            "sms": True,
            "push": True
        }
    )
    
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "email": "voter@example.com",
                "mobile_number": "+919876543210",
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
