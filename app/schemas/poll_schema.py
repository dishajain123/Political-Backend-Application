"""
Poll Schema Module
==================
Pydantic schemas for poll-related endpoints.

Author: Political Communication Platform Team
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class PollOptionCreateRequest(BaseModel):
    """
    Create a poll option.
    """
    text: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    icon_url: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Roads and Highways",
                "description": "Focus on road infrastructure"
            }
        }


class PollCreateRequest(BaseModel):
    """
    Create new poll request.
    """
    title: str = Field(..., min_length=5, max_length=300)
    description: Optional[str] = Field(default=None, max_length=1000)
    poll_type: str = Field(
        default="multiple_choice",
        description="multiple_choice, yes_no, rating, open_ended"
    )
    options: Optional[List[PollOptionCreateRequest]] = Field(default=None)
    allow_other: bool = Field(default=False)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    target_roles: Optional[List[str]] = Field(default=None)
    target_regions: Optional[Dict[str, List[str]]] = Field(default=None)
    target_geography: Optional[Dict[str, Optional[str]]] = Field(default=None)
    target_demographics: Optional[Dict[str, List[str]]] = Field(default=None)
    is_anonymous: bool = Field(default=True)
    allow_multiple_responses: bool = Field(default=False)
    show_results: str = Field(
        default="after_voting",
        description="immediately, after_voting, after_closing, never"
    )
    is_public: bool = Field(default=True)
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Which infrastructure needs improvement?",
                "poll_type": "multiple_choice",
            "options": [
                {"text": "Roads and Highways"},
                {"text": "Water Supply"},
                {"text": "Electricity"}
            ],
            "target_roles": ["voter", "leader"],
            "target_regions": {"states": ["Maharashtra"], "cities": ["Mumbai"]},
            "is_public": True
        }
    }


class PollCreate(PollCreateRequest):
    """Create new poll request (legacy name)."""


class PollResponseRequest(BaseModel):
    """
    Submit response to a poll.
    """
    selected_option_id: Optional[str] = Field(default=None)
    response_text: Optional[str] = Field(default=None, max_length=500)
    
    class Config:
        json_schema_extra = {
            "example": {
                "selected_option_id": "1"
            }
        }


class PollVoteRequest(BaseModel):
    """
    Vote on a poll.
    """
    option_id: Optional[str] = Field(default=None)
    response_text: Optional[str] = Field(default=None, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "option_id": "1"
            }
        }


class PollUpdateRequest(BaseModel):
    """
    Update poll details (before publishing).
    """
    title: Optional[str] = Field(default=None, min_length=5, max_length=300)
    description: Optional[str] = Field(default=None, max_length=1000)
    options: Optional[List[PollOptionCreateRequest]] = None
    end_date: Optional[datetime] = None
    target_roles: Optional[List[str]] = None
    target_regions: Optional[Dict[str, List[str]]] = None
    target_geography: Optional[Dict[str, Optional[str]]] = None
    target_demographics: Optional[Dict[str, List[str]]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Updated Poll Title",
                "end_date": "2024-02-28T23:59:59Z"
            }
        }


class PollPublishRequest(BaseModel):
    """
    Publish a draft poll.
    """
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    target_roles: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2024-02-15T09:00:00Z",
                "end_date": "2024-02-20T18:00:00Z",
                "target_roles": ["voter", "leader"]
            }
        }


class PollCloseRequest(BaseModel):
    """
    Close an active poll.
    """
    reason: Optional[str] = Field(default=None, max_length=500)
    
    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Got sufficient responses for analysis"
            }
        }


class PollOptionResponse(BaseModel):
    """
    Poll option in response.
    """
    option_id: str
    text: str
    description: Optional[str] = None
    votes: int
    percentage: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "option_id": "1",
                "text": "Roads and Highways",
                "votes": 245,
                "percentage": 45.5
            }
        }


class PollResponse(BaseModel):
    """
    Poll response with full details.
    """
    id: str = Field(..., alias="_id")
    poll_id: str
    title: str
    poll_type: str
    status: str
    created_by: str
    created_at: str
    end_date: Optional[str] = None
    options: List[PollOptionResponse] = Field(default_factory=list)
    total_responses: int
    show_results: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "poll_id": "POLL-2024-001",
                "title": "Which infrastructure needs improvement?",
                "status": "active",
                "total_responses": 500
            }
        }


class PollListResponse(BaseModel):
    """
    List of polls with pagination.
    """
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[PollResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 50,
                "page": 1,
                "page_size": 10,
                "total_pages": 5,
                "items": []
            }
        }


class PollAnalyticsResponse(BaseModel):
    """
    Poll analytics and results.
    """
    poll_id: str
    title: str
    status: str
    total_responses: int
    participation_rate: float
    options: List[PollOptionResponse]
    average_completion_time_seconds: int
    engagement_score: float
    demographic_breakdown: Optional[Dict[str, Dict]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "poll_id": "POLL-2024-001",
                "title": "Which infrastructure needs improvement?",
                "total_responses": 500,
                "participation_rate": 35.2,
                "options": []
            }
        }
