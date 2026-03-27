"""
Appointment Schema Module
=========================
Pydantic schemas for appointment-related endpoints.

Author: Political Communication Platform Team
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.utils.enums import AppointmentStatus, AppointmentReason


class AppointmentCreateRequest(BaseModel):
    """
    Create new appointment request.
    """
    requested_with: str = Field(..., description="Leader/Corporator user ID")
    reason: AppointmentReason
    description: Optional[str] = Field(default=None, max_length=500)
    appointment_date: datetime = Field(..., description="Proposed appointment date/time")
    duration_minutes: int = Field(default=30, ge=15, le=120)
    location: Optional[str] = None
    urgency_level: Optional[str] = Field(
        default="normal",
        description="low, normal, high"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "requested_with": "leader123",
                "reason": "personal_issue",
                "description": "Discuss water supply problem in my area",
                "appointment_date": "2024-02-20T10:30:00Z",
                "duration_minutes": 30,
                "location": "Community Center"
            }
        }

    @field_validator("urgency_level")
    @classmethod
    def validate_urgency_level(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return "normal"
        v = v.lower().strip()
        if v not in {"low", "normal", "high"}:
            raise ValueError("urgency_level must be one of: low, normal, high")
        return v


class AppointmentApproveRequest(BaseModel):
    """
    Approve an appointment request with optional modifications.
    """
    appointment_date: Optional[datetime] = Field(default=None, description="Confirm or change the appointment date")
    location: Optional[str] = Field(default=None, description="Confirm or change the meeting location")
    notes: Optional[str] = Field(default=None, max_length=500)
    
    class Config:
        json_schema_extra = {
            "example": {
                "appointment_date": "2024-02-20T10:30:00Z",
                "location": "My Office, Room 205",
                "notes": "Please bring relevant documents"
            }
        }


class AppointmentRejectRequest(BaseModel):
    """
    Reject an appointment request.
    """
    reason: str = Field(..., min_length=10, max_length=500)
    alternative_date: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Busy on that date, can offer alternative date",
                "alternative_date": "2024-02-25T15:00:00Z"
            }
        }


class AppointmentRescheduleRequest(BaseModel):
    """
    Reschedule an approved appointment.
    """
    new_appointment_date: datetime = Field(...)
    reason: Optional[str] = Field(default=None, max_length=500)
    new_location: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "new_appointment_date": "2024-02-25T10:30:00Z",
                "reason": "Urgent work commitment on original date",
                "new_location": "City Hall"
            }
        }


class AppointmentCancelRequest(BaseModel):
    """
    Cancel an appointment.
    """
    reason: str = Field(..., min_length=5, max_length=500)
    
    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Personal emergency"
            }
        }


class AppointmentCompleteRequest(BaseModel):
    """
    Mark appointment as completed.
    """
    meeting_notes: Optional[str] = Field(default=None, max_length=1000)
    attendees: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "meeting_notes": "Discussed water supply issues, leader committed to investigating",
                "attendees": ["voter123", "leader456"]
            }
        }


class AppointmentFeedbackRequest(BaseModel):
    """
    Provide feedback after appointment completion.
    """
    rating: int = Field(..., ge=1, le=5)
    comments: Optional[str] = Field(default=None, max_length=500)
    
    class Config:
        json_schema_extra = {
            "example": {
                "rating": 4,
                "comments": "Very responsive and helpful, good understanding of issues"
            }
        }


class AppointmentResponse(BaseModel):
    """
    Appointment response with full details.
    """
    id: str = Field(..., alias="_id")
    appointment_id: str
    requested_by: str
    requested_with: str
    requested_by_name: Optional[str] = None
    requested_with_name: Optional[str] = None
    reason: AppointmentReason
    appointment_date: str
    new_appointment_date: Optional[str] = None
    status: AppointmentStatus
    created_at: str
    location: Optional[str] = None
    feedback: Optional[dict] = None
    reschedule_reason: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "appointment_id": "APPT-2024-001",
                "requested_by": "voter123",
                "requested_with": "leader456",
                "reason": "personal_issue",
                "appointment_date": "2024-02-20T10:30:00Z",
                "status": "approved"
            }
        }


class AppointmentListResponse(BaseModel):
    """
    List of appointments with pagination.
    """
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[AppointmentResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 50,
                "page": 1,
                "page_size": 20,
                "total_pages": 3,
                "items": []
            }
        }


class AppointmentCalendarResponse(BaseModel):
    """
    Calendar view of appointments for a user.
    """
    date: str
    appointments: List[dict]
    total_appointments: int
    available_slots: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2024-02-20",
                "appointments": [],
                "total_appointments": 2,
                "available_slots": 6
        }
    }


# Backwards-compatible alias used by routes/services.
class AppointmentCreate(AppointmentCreateRequest):
    """Create new appointment request (legacy name)."""


class AppointmentUpdate(BaseModel):
    """
    Update appointment status and optional note.
    """
    status: AppointmentStatus
    note: Optional[str] = Field(default=None, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "status": "approved",
                "note": "See you at the scheduled time"
            }
        }
