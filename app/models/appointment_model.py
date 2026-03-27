"""
Appointment Model Module
========================
Defines the Appointment data model for MongoDB.
Handles appointment requests between voters and leaders/corporators.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from bson import ObjectId

from app.utils.enums import AppointmentStatus, AppointmentReason


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


class AppointmentFeedback(BaseModel):
    """
    Feedback provided after appointment completion.
    """
    rating: int = Field(..., ge=1, le=5, description="Satisfaction rating")
    comments: Optional[str] = None
    given_by: str = Field(..., description="User ID who gave feedback")
    given_at: datetime = Field(default_factory=datetime.utcnow)


class AppointmentModel(BaseModel):
    """
    Appointment model for scheduling meetings between voters and leaders/corporators.
    
    Workflow:
        Requested by voter -> Approved/Rejected -> Rescheduled/Completed -> Cancelled
    """
    
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    
    # Appointment identification
    appointment_id: str = Field(..., description="Unique appointment tracking ID")
    
    # Participants
    requested_by: str = Field(..., description="Voter user ID")
    requested_with: str = Field(..., description="Leader/Corporator user ID")
    
    # Request details
    reason: AppointmentReason = Field(
        ...,
        description="Purpose of appointment"
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Additional details about the appointment"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Scheduled details
    appointment_date: datetime = Field(..., description="Proposed appointment date and time")
    duration_minutes: int = Field(default=30, ge=15, le=120)
    location: Optional[str] = Field(
        default=None,
        description="Meeting location (office, online, etc)"
    )
    urgency_level: Optional[str] = Field(
        default="normal",
        description="low, normal, high"
    )
    
    # Status
    status: AppointmentStatus = Field(default=AppointmentStatus.REQUESTED)
    status_updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Approval/Rejection
    approved_or_rejected_by: Optional[str] = None
    approved_or_rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    # Rescheduling
    reschedule_count: int = Field(default=0)
    new_appointment_date: Optional[datetime] = None
    reschedule_reason: Optional[str] = None
    
    # Completion
    completed_at: Optional[datetime] = None
    attendees: List[str] = Field(
        default_factory=list,
        description="List of user IDs who attended"
    )
    meeting_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Notes from the meeting"
    )
    
    # Cancellation
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancellation_reason: Optional[str] = None
    
    # Feedback
    feedback: Optional[AppointmentFeedback] = None
    
    # Reminders
    reminder_sent: bool = Field(default=False)
    reminder_sent_at: Optional[datetime] = None
    
    # Metadata
    is_priority: bool = Field(default=False)
    tags: List[str] = Field(default_factory=list)
    linked_complaint_id: Optional[str] = None  # If related to a complaint
    
    class Config:
        """Pydantic configuration"""
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "appointment_id": "APPT-2024-001",
                "requested_by": "voter123",
                "requested_with": "leader456",
                "reason": "personal_issue",
                "description": "Discuss local water supply issues",
                "appointment_date": "2024-02-15T10:30:00Z",
                "location": "Community Center",
                "status": "requested"
            }
        }
