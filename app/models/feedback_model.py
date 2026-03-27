"""
Feedback Model Module
=====================
Defines the Feedback data model for MongoDB.
Handles user feedback, reviews, and suggestions.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from bson import ObjectId

from app.utils.enums import FeedbackCategory, SentimentType


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


class FeedbackModel(BaseModel):
    """
    Feedback model for collecting user opinions, suggestions, and reviews.
    
    Feedback can be related to:
    - General service quality
    - Leader performance
    - Policy feedback
    - Event experiences
    - App usability
    """
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    
    # Feedback identification
    feedback_id: str = Field(..., description="Unique feedback tracking ID")
    
    # Creator
    created_by: str = Field(..., description="User ID who gave feedback")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Content
    category: FeedbackCategory = Field(..., description="Type of feedback")
    title: str = Field(..., min_length=5, max_length=200)
    content: str = Field(..., min_length=10, max_length=2000)
    
    # Rating
    rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Overall rating (1-5 stars)"
    )
    
    # Target
    related_to: Optional[str] = Field(
        default=None,
        description="user_id of person feedback is about (e.g., leader)"
    )
    related_event_id: Optional[str] = None
    related_poll_id: Optional[str] = None
    related_complaint_id: Optional[str] = None
    
    # Sentiment analysis (optional, computed)
    sentiment: Optional[SentimentType] = None
    sentiment_score: Optional[float] = Field(
        default=None,
        ge=-1,
        le=1,
        description="Sentiment score from -1 (very negative) to 1 (very positive)"
    )
    
    # Keywords/Topics
    keywords: List[str] = Field(
        default_factory=list,
        description="Extracted keywords from feedback"
    )
    
    # Attachments
    attachment_urls: List[str] = Field(default_factory=list)
    
    # Status
    is_reviewed: bool = Field(default=False)
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    
    # Action
    action_taken: bool = Field(default=False)
    action_description: Optional[str] = None
    action_taken_by: Optional[str] = None
    action_taken_at: Optional[datetime] = None
    
    # Visibility
    is_public: bool = Field(default=False, description="Public in feedback section")
    is_featured: bool = Field(default=False)
    reaction: Optional[str] = Field(
        default=None,
        description="agree, disagree, confused"
    )
    emoji: Optional[str] = Field(
        default=None,
        description="Emoji reaction"
    )
    
    # Follow-up
    is_anonymous: bool = Field(default=False)
    requires_followup: bool = Field(default=False)
    followup_due_date: Optional[datetime] = None
    
    # Metadata
    tags: List[str] = Field(default_factory=list)
    priority: int = Field(default=0, ge=0, le=3)
    response_required: bool = Field(default=False)
    
    class Config:
        """Pydantic configuration"""
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "feedback_id": "FB-2024-001",
                "created_by": "voter123",
                "category": "leader_performance",
                "title": "Excellent work by our local leader",
                "content": "The leader has been very responsive to community issues",
                "rating": 5,
                "related_to": "leader456",
                "sentiment": "positive"
            }
        }
