"""
Feedback Schema Module
======================
Pydantic schemas for feedback-related endpoints.

Author: Political Communication Platform Team
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.utils.enums import FeedbackCategory


class FeedbackCreateRequest(BaseModel):
    """
    Create new feedback request.
    """
    category: FeedbackCategory
    title: str = Field(..., min_length=5, max_length=200)
    content: str = Field(..., min_length=10, max_length=2000)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    related_to: Optional[str] = Field(
        default=None,
        description="User ID if feedback is about a person (e.g., leader)"
    )
    related_event_id: Optional[str] = None
    related_poll_id: Optional[str] = None
    related_complaint_id: Optional[str] = None
    attachment_urls: List[str] = Field(default_factory=list)
    is_anonymous: bool = Field(default=False)
    is_public: bool = Field(default=False)
    requires_followup: bool = Field(default=False)
    reaction: Optional[str] = Field(
        default=None,
        description="agree, disagree, confused"
    )
    emoji: Optional[str] = Field(
        default=None,
        description="Emoji reaction (single character)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "category": "leader_performance",
                "title": "Excellent work by our local leader",
                "content": "The leader has been very responsive to community issues",
                "rating": 5,
                "is_public": True
            }
        }

    @classmethod
    def _normalize_reaction(cls, v: Optional[str]) -> Optional[str]:
        return v.lower().strip() if v else None

    @staticmethod
    def _is_valid_reaction(v: str) -> bool:
        return v in {"agree", "disagree", "confused"}

    @staticmethod
    def _is_valid_emoji(v: str) -> bool:
        return len(v.strip()) <= 4

    @field_validator("reaction")
    @classmethod
    def validate_reaction(cls, v: Optional[str]) -> Optional[str]:
        v = cls._normalize_reaction(v)
        if v and not cls._is_valid_reaction(v):
            raise ValueError("reaction must be one of: agree, disagree, confused")
        return v

    @field_validator("emoji")
    @classmethod
    def validate_emoji(cls, v: Optional[str]) -> Optional[str]:
        if v and not cls._is_valid_emoji(v):
            raise ValueError("emoji must be a single emoji character")
        return v


class FeedbackCreate(FeedbackCreateRequest):
    """Create new feedback request (legacy name)."""


class FeedbackUpdateRequest(BaseModel):
    """
    Update feedback details (only before review).
    """
    title: Optional[str] = Field(default=None, min_length=5, max_length=200)
    content: Optional[str] = Field(default=None, min_length=10, max_length=2000)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    attachment_urls: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Updated Feedback Title",
                "rating": 4
            }
        }


class FeedbackReviewRequest(BaseModel):
    """
    Review feedback by OPS/Corporator.
    """
    review_notes: str = Field(..., min_length=5, max_length=500)
    is_public: Optional[bool] = None
    action_taken: Optional[bool] = None
    action_description: Optional[str] = Field(default=None, max_length=500)
    
    class Config:
        json_schema_extra = {
            "example": {
                "review_notes": "Good feedback, will share with team",
                "is_public": True,
                "action_taken": True,
                "action_description": "Leader will focus on response time"
            }
        }


class FeedbackResponse(BaseModel):
    """
    Feedback response with full details.
    """
    id: str = Field(..., alias="_id")
    feedback_id: str
    category: FeedbackCategory
    title: str
    content: str
    rating: Optional[int] = None
    created_by: str
    created_at: str
    related_to: Optional[str] = None
    is_public: bool
    is_reviewed: bool
    sentiment: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "feedback_id": "FB-2024-001",
                "category": "leader_performance",
                "title": "Excellent work by our local leader",
                "rating": 5,
                "is_public": True,
                "sentiment": "positive"
            }
        }


class FeedbackListResponse(BaseModel):
    """
    List of feedback with pagination.
    """
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[FeedbackResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 200,
                "page": 1,
                "page_size": 20,
                "total_pages": 10,
                "items": []
            }
        }


class FeedbackSummaryResponse(BaseModel):
    """
    Summary of feedback for an entity (person/event/etc).
    """
    entity_id: str
    entity_type: str
    total_feedback: int
    average_rating: float
    positive_count: int
    neutral_count: int
    negative_count: int
    recent_feedback: List[FeedbackResponse]
    top_keywords: List[str]
    sentiment_distribution: dict
    
    class Config:
        json_schema_extra = {
            "example": {
                "entity_id": "leader123",
                "entity_type": "leader",
                "total_feedback": 45,
                "average_rating": 4.2,
                "positive_count": 35,
                "neutral_count": 7,
                "negative_count": 3,
                "top_keywords": ["responsive", "helpful", "dedicated"],
                "sentiment_distribution": {
                    "positive": 77.8,
                    "neutral": 15.6,
                    "negative": 6.7
                }
            }
        }


class FeedbackStatisticsResponse(BaseModel):
    """
    Feedback statistics for analytics dashboard.
    """
    total_feedback: int
    by_category: dict
    by_rating: dict
    average_rating: float
    sentiment_breakdown: dict
    trending_topics: List[str]
    high_priority_feedback_count: int
    pending_review_count: int
    pending_action_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_feedback": 500,
                "by_category": {
                    "leader_performance": 150,
                    "service_quality": 120,
                    "policy_feedback": 100
                },
                "by_rating": {
                    "5": 200,
                    "4": 150,
                    "3": 100
                },
                "average_rating": 4.1,
                "trending_topics": ["response_time", "accessibility", "communication"]
            }
        }
