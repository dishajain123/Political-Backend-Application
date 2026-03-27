"""
Poll Model Module
=================
Defines the Poll data model for MongoDB.
Handles polls, surveys, and voter opinion collection.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from bson import ObjectId
from app.utils.enums import PollStatus
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


class PollOption(BaseModel):
    """
    Individual option/choice in a poll.
    """
    option_id: str = Field(..., description="Unique option identifier")
    text: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    icon_url: Optional[str] = None
    votes: int = Field(default=0, ge=0)
    percentage: float = Field(default=0.0, ge=0, le=100)


class PollResponse(BaseModel):
    """
    Individual voter response to a poll.
    """
    user_id: Optional[str] = Field(default=None, description="Voter user ID")
    selected_option_id: str = Field(..., description="Selected poll option")
    response_text: Optional[str] = Field(
        default=None,
        max_length=500,
        description="For open-ended responses"
    )
    sentiment: Optional[str] = None
    responded_at: datetime = Field(default_factory=datetime.utcnow)


class PollModel(BaseModel):
    """
    Poll model for surveys and opinion collection.
    
    Poll lifecycle:
        Draft -> Active -> Closed -> Archived
    """
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    
    # Poll identification
    poll_id: str = Field(..., description="Unique poll tracking ID")
    title: str = Field(..., min_length=5, max_length=300)
    description: Optional[str] = Field(default=None, max_length=1000)
    
    # Creator
    created_by: str = Field(..., description="User ID (typically Corporator/Leader)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Poll type
    poll_type: str = Field(
        default="multiple_choice",
        description="multiple_choice, yes_no, rating, open_ended"
    )
    
    # Status
    status: PollStatus = Field(default=PollStatus.DRAFT)
    status_updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Duration
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # Options (for multiple choice, yes/no, rating polls)
    options: List[PollOption] = Field(
        default_factory=list,
        description="Available poll options"
    )
    
    # Allow other option
    allow_other: bool = Field(default=False)
    other_option_responses: List[str] = Field(
        default_factory=list,
        description="Responses to 'Other' option"
    )
    
    # Responses
    responses: List[PollResponse] = Field(
        default_factory=list,
        description="All voter responses"
    )
    total_responses: int = Field(default=0)
    
    # Targeting
    target_roles: List[str] = Field(
        default_factory=list,
        description="voter, leader, all"
    )
    target_regions: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Geographic targeting {states: [..], cities: [..], wards: [..], areas: [..]}"
    )
    target_geography: Optional[LocationHierarchy] = None
    target_demographics: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="Demographic targeting {age_groups: [], genders: [], occupations: [], education_levels: []}"
    )
    
    # Settings
    is_anonymous: bool = Field(default=True)
    allow_multiple_responses: bool = Field(default=False)
    show_results: str = Field(
        default="after_voting",
        description="immediately, after_voting, after_closing, never"
    )
    
    # Visibility
    is_public: bool = Field(default=True)
    is_featured: bool = Field(default=False)
    
    # Analytics
    view_count: int = Field(default=0)
    unique_responders: int = Field(default=0)
    participation_rate: float = Field(default=0.0, ge=0, le=100)
    anonymous_responders: List[str] = Field(default_factory=list)
    
    # Rich media
    banner_url: Optional[str] = None
    attachments: List[str] = Field(default_factory=list)
    
    # Closing
    auto_close_at: Optional[datetime] = None
    is_auto_closed: bool = Field(default=False)
    
    # Tags
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = Field(
        default=None,
        description="Policy, Service, Feedback, etc"
    )
    
    # Metadata
    priority: int = Field(default=0)
    notes: Optional[str] = None
    
    class Config:
        """Pydantic configuration"""
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "poll_id": "POLL-2024-001",
                "title": "Which infrastructure needs improvement in your area?",
                "created_by": "corporator123",
                "poll_type": "multiple_choice",
                "status": "active",
                "options": [
                    {
                        "option_id": "1",
                        "text": "Roads and Highways",
                        "votes": 245
                    },
                    {
                        "option_id": "2",
                        "text": "Water Supply",
                        "votes": 189
                    }
                ],
                "total_responses": 434
            }
        }
