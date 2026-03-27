"""
Complaint Model Module
======================
Defines the Complaint data model for MongoDB.
Handles complaint creation, tracking, assignment, and resolution.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from bson import ObjectId

from app.utils.enums import (
    ComplaintStatus,
    ComplaintCategory,
    ComplaintPriority
)
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


class ComplaintNote(BaseModel):
    """
    Internal note on a complaint.
    Used to track progress and updates by assigned leader/ops.
    """
    added_by: str = Field(..., description="User ID of note author")
    content: str = Field(..., description="Note content")
    added_at: datetime = Field(default_factory=datetime.utcnow)
    is_internal: bool = Field(default=True, description="Visible only to ops/leader")


class ComplaintAudit(BaseModel):
    """
    Audit trail for complaint status changes.
    """
    status_from: ComplaintStatus
    status_to: ComplaintStatus
    changed_by: str = Field(..., description="User ID who made the change")
    reason: Optional[str] = None
    changed_at: datetime = Field(default_factory=datetime.utcnow)


class ComplaintModel(BaseModel):
    """
    Main Complaint model.
    Represents citizen complaints about infrastructure, services, corruption, etc.
    
    Workflow:
        Created by voter -> Assigned to leader -> In progress -> Resolved -> Closed
    """
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    
    # Complaint identification
    complaint_id: str = Field(..., description="Unique complaint tracking ID")
    
    # Creator information
    created_by: str = Field(..., description="Voter user ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Complaint content
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    category: ComplaintCategory
    priority: ComplaintPriority = Field(default=ComplaintPriority.MEDIUM)
    
    # Location
    location: LocationHierarchy = Field(..., description="Where the issue occurred")
    
    # Status tracking
    status: ComplaintStatus = Field(default=ComplaintStatus.PENDING)
    status_updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Assignment
    assigned_to: Optional[str] = None  # Leader user ID
    assigned_at: Optional[datetime] = None
    assigned_by: Optional[str] = None  # Corporator/OPS user ID
    
    # Resolution
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    
    # Attachments
    attachment_urls: List[str] = Field(
        default_factory=list,
        description="URLs of supporting documents/images"
    )
    image_urls: List[str] = Field(
        default_factory=list,
        description="Image evidence URLs"
    )
    voice_note_url: Optional[str] = Field(
        default=None,
        description="Voice note URL"
    )

    # NEW CODE ADDED - Feature 1: Single primary image upload
    image_url: Optional[str] = Field(
        default=None,
        description="Primary image URL or base64 data URL uploaded by voter"
    )
    image_uploaded_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when primary image was uploaded"
    )

    # Internal tracking
    notes: List[ComplaintNote] = Field(
        default_factory=list,
        description="Internal notes from leader/ops"
    )
    audit_trail: List[ComplaintAudit] = Field(
        default_factory=list,
        description="Status change history"
    )
    
    # Escalation
    is_escalated: bool = Field(default=False)
    escalated_at: Optional[datetime] = None
    escalation_reason: Optional[str] = None

    # NEW CODE ADDED - Feature 2: Decline fields
    decline_reason: Optional[str] = Field(
        default=None,
        description="Reason provided when complaint was declined"
    )
    declined_by: Optional[str] = Field(
        default=None,
        description="User ID of leader or corporator who declined"
    )
    declined_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when complaint was declined"
    )
    
    # Feedback
    voter_satisfaction_rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Rating given by voter after resolution"
    )
    voter_feedback: Optional[str] = None
    feedback_given_at: Optional[datetime] = None
    sentiment: Optional[str] = Field(
        default=None,
        description="Sentiment derived from complaint text"
    )

    # NEW CODE ADDED - Feature 3: Resolution verification fields
    verification_requested_at: Optional[datetime] = Field(
        default=None,
        description="When corporator requested voter verification of resolution"
    )
    verified_by_corporator: bool = Field(
        default=False,
        description="Whether corporator has triggered verification flow"
    )
    voter_feedback_rating: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description="Rating submitted by voter during verification flow"
    )
    voter_feedback_comment: Optional[str] = Field(
        default=None,
        description="Comment submitted by voter during verification flow"
    )
    performance_score_updated: bool = Field(
        default=False,
        description="Whether leader performance score was incremented for this complaint"
    )
    
    # Metadata
    estimated_resolution_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    is_public: bool = Field(default=False, description="Visible in public complaints list")
    
    class Config:
        """Pydantic configuration"""
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "complaint_id": "COMP-2024-001",
                "created_by": "user123",
                "title": "Pothole on Main Street",
                "description": "Large pothole causing traffic hazards",
                "category": "roads",
                "priority": "high",
                "location": {
                    "state": "Maharashtra",
                    "city": "Mumbai",
                    "area": "Andheri",
                    "building": "Main Street Junction"
                },
                "status": "pending"
            }
        }