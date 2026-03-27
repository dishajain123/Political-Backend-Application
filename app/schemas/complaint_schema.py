"""
Complaint Schema Module
=======================
Pydantic schemas for complaint-related endpoints.

Author: Political Communication Platform Team
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.utils.enums import ComplaintStatus, ComplaintCategory, ComplaintPriority
from app.utils.geo import LocationHierarchy


class ComplaintCreateRequest(BaseModel):
    """
    Create new complaint request.
    """
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    category: ComplaintCategory
    priority: ComplaintPriority = Field(default=ComplaintPriority.MEDIUM)
    location: LocationHierarchy
    attachment_urls: List[str] = Field(default_factory=list)
    image_urls: List[str] = Field(default_factory=list)
    on_behalf_of_voter_id: Optional[str] = Field(
        default=None,
        description="Leader-only: voter ID for complaint raised on behalf of assigned voter"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Pothole on Main Street",
                "description": "Large pothole causing traffic hazards",
                "category": "roads",
                "priority": "high",
                "location": {
                    "state": "Maharashtra",
                    "city": "Mumbai",
                    "area": "Andheri"
                },
            }
        }


class ComplaintUpdateStatusRequest(BaseModel):
    """
    Update complaint status by leader/OPS.
    """
    status: ComplaintStatus
    notes: Optional[str] = Field(default=None, max_length=500)
    estimated_resolution_date: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "in_progress",
                "notes": "Contractor has been contacted for repair"
            }
        }


class ComplaintResolveRequest(BaseModel):
    """
    Resolve a complaint with closure information.
    """
    resolution_notes: str = Field(..., min_length=10, max_length=1000)
    attachment_urls: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "resolution_notes": "Pothole has been repaired successfully",
                "attachment_urls": ["url_to_completion_photo"]
            }
        }


class ComplaintAssignRequest(BaseModel):
    """
    Assign a complaint to a leader.
    """
    leader_id: str = Field(..., description="Leader user ID")
    assignment_notes: Optional[str] = Field(default=None, max_length=500)
    estimated_resolution_date: Optional[datetime] = None
    priority: Optional[ComplaintPriority] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "leader_id": "leader123",
                "assignment_notes": "Assigned to local area leader",
                "priority": "high"
            }
        }


class ComplaintAddNoteRequest(BaseModel):
    """
    Add note to a complaint.
    
    LEADER FIELD NOTES:
    - Leaders add field_observation notes
    - Includes on-ground verification details
    - Separate from internal corporator notes
    """
    content: str = Field(..., min_length=5, max_length=500)
    is_internal: bool = Field(default=True, description="False for voter-visible notes")
    note_type: str = Field(
        default="internal",
        description="Note type: 'field_observation' (Leader), 'internal' (Ops/Corporator), 'external' (Voter-visible)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "Visited site: confirmed pothole depth is 8 inches, requires immediate repair",
                "is_internal": True,
                "note_type": "field_observation"
            }
        }


class ComplaintAcknowledgeRequest(BaseModel):
    """
    Leader acknowledges receipt of assigned complaint.
    This is separate from assignment - Leader confirms they've received it.
    """
    acknowledgment_notes: Optional[str] = Field(default=None, max_length=500)
    expected_visit_date: Optional[datetime] = Field(
        default=None,
        description="When Leader plans to visit the complaint site"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "acknowledgment_notes": "Received. Will visit site tomorrow morning.",
                "expected_visit_date": "2026-02-03T10:00:00Z"
            }
        }


class ComplaintFeedbackRequest(BaseModel):
    """
    Voter feedback on resolved complaint.
    """
    satisfaction_rating: int = Field(..., ge=1, le=5)
    feedback: Optional[str] = Field(default=None, max_length=500)
    
    class Config:
        json_schema_extra = {
            "example": {
                "satisfaction_rating": 4,
                "feedback": "Good response time, though took longer than expected"
            }
        }


# NEW CODE ADDED - Feature 2: Decline request schema
class ComplaintDeclineRequest(BaseModel):
    """
    Decline a complaint - used by Leader or Corporator.
    Cannot decline already resolved complaints.
    """
    decline_reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for declining the complaint (optional)"
    )
    decline_category: str = Field(
        default="other",
        description="Category: not_feasible, out_of_jurisdiction, personal_request, other"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "decline_reason": "This complaint falls outside our ward jurisdiction",
                "decline_category": "out_of_jurisdiction"
            }
        }


# NEW CODE ADDED - Feature 3: Request verification schema
class ComplaintRequestVerificationRequest(BaseModel):
    """
    Corporator requests voter to verify resolution quality.
    Triggers a notification to voter to submit feedback.
    """
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional note from corporator about the verification request"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "notes": "Please confirm if the pothole repair meets your satisfaction"
            }
        }


# NEW CODE ADDED - Feature 3: Extended voter feedback for verification
class ComplaintVerificationFeedbackRequest(BaseModel):
    """
    Voter submits feedback specifically for the resolution verification flow.
    If rating >= 3: leader score incremented (once per complaint).
    If rating < 3: complaint is reopened.
    """
    rating: int = Field(..., ge=1, le=5, description="Satisfaction rating 1-5")
    comment: Optional[str] = Field(default=None, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "rating": 4,
                "comment": "Repair was done but took 2 weeks longer than promised"
            }
        }


class ComplaintResponse(BaseModel):
    """
    Complaint response with full details.
    """
    id: str = Field(..., alias="_id")
    complaint_id: str
    title: str
    description: str
    category: ComplaintCategory
    priority: ComplaintPriority
    location: LocationHierarchy
    status: ComplaintStatus
    created_by: str
    created_at: str
    assigned_to: Optional[str] = None
    assigned_at: Optional[str] = None
    acknowledged_by_leader: Optional[str] = None
    acknowledged_at: Optional[str] = None
    first_field_visit_at: Optional[str] = None
    resolved_at: Optional[str] = None
    voter_satisfaction_rating: Optional[int] = None
    is_public: bool
    is_escalated: Optional[bool] = None
    escalated_at: Optional[str] = None
    # NEW CODE ADDED - Feature 1: Image fields in response
    image_url: Optional[str] = None
    image_uploaded_at: Optional[str] = None
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None
    file_uploaded_at: Optional[str] = None
    attachment_urls: Optional[List[str]] = None
    file_url: Optional[str] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None
    file_uploaded_at: Optional[str] = None
    attachment_urls: Optional[List[str]] = None
    # NEW CODE ADDED - Feature 2: Decline fields in response
    decline_reason: Optional[str] = None
    declined_by: Optional[str] = None
    declined_at: Optional[str] = None
    # NEW CODE ADDED - Feature 3: Verification fields in response
    verification_requested_at: Optional[str] = None
    verified_by_corporator: Optional[bool] = None
    voter_feedback_rating: Optional[int] = None
    voter_feedback_comment: Optional[str] = None
    performance_score_updated: Optional[bool] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "complaint_id": "COMP-2024-001",
                "title": "Pothole on Main Street",
                "status": "in_progress",
                "assigned_to": "leader123",
                "acknowledged_by_leader": "leader123",
                "acknowledged_at": "2026-02-02T10:00:00Z",
                "image_url": "https://storage.example.com/complaints/image.jpg"
            }
        }


class ComplaintListResponse(BaseModel):
    """
    List of complaints with pagination.
    """
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[ComplaintResponse]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total": 150,
                "page": 1,
                "page_size": 20,
                "total_pages": 8,
                "items": []
            }
        }


class ComplaintEscalateRequest(BaseModel):
    """
    Escalate a complaint to higher authority.
    """
    reason: str = Field(..., min_length=10, max_length=500)
    
    class Config:
        json_schema_extra = {
            "example": {
                "reason": "Complaint not resolved within SLA, escalating to corporator"
            }
        }


class ComplaintStatisticsResponse(BaseModel):
    """
    Complaint statistics for analytics.
    """
    total_complaints: int
    by_status: dict
    by_category: dict
    by_priority: dict
    average_resolution_time_days: float
    satisfaction_score: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_complaints": 500,
                "by_status": {
                    "pending": 50,
                    "in_progress": 100,
                    "resolved": 350
                },
                "by_category": {
                    "roads": 150,
                    "water_supply": 100
                }
            }
        }


class ComplaintAnalyticsSummary(BaseModel):
    total_complaints: int = 0
    pending: int = 0
    in_progress: int = 0
    resolved: int = 0
    rejected: int = 0
    closed: int = 0
    acknowledged: int = 0
    resolution_rate_pct: float = 0.0
    avg_resolution_time_hours: float = 0.0


class ComplaintStatusDistribution(BaseModel):
    label: str
    count: int
    percent: float = Field(0.0, alias="percent")


class ComplaintTimePoint(BaseModel):
    date: str
    value: float


class ComplaintStatusTransitionPoint(BaseModel):
    date: str
    status: str
    value: int


class ComplaintAreaItem(BaseModel):
    label: str
    value: int


class ComplaintResolutionItem(BaseModel):
    label: str
    value: float


class ComplaintUserItem(BaseModel):
    id: str
    label: str
    value: int


class ComplaintAssigneeItem(BaseModel):
    id: str
    label: str
    value: int
    resolution_rate_pct: float = 0.0


class ComplaintHeatPoint(BaseModel):
    ward: str = ""
    area: str = ""
    count: int = 0


class ComplaintAnalyticsResponse(BaseModel):
    summary: ComplaintAnalyticsSummary
    status_counts: List[ComplaintStatusDistribution]
    status_transitions: List[ComplaintStatusTransitionPoint]
    complaints_over_time_daily: List[ComplaintTimePoint]
    complaints_over_time_weekly: List[ComplaintTimePoint]
    complaints_over_time_monthly: List[ComplaintTimePoint]
    resolution_trend: List[ComplaintTimePoint]
    avg_resolution_time_trend: List[ComplaintTimePoint]
    peak_hours: List[ComplaintAreaItem]
    peak_days: List[ComplaintAreaItem]
    area_distribution: List[ComplaintAreaItem]
    ward_distribution: List[ComplaintAreaItem]
    region_distribution: List[ComplaintAreaItem]
    top_problem_areas: List[ComplaintAreaItem]
    area_resolution_rate: List[ComplaintResolutionItem]
    category_distribution: List[ComplaintAreaItem]
    category_resolution_time: List[ComplaintResolutionItem]
    user_complaints: List[ComplaintUserItem]
    top_complainants: List[ComplaintUserItem]
    repeat_complainants: int
    complaint_frequency_trend: List[ComplaintTimePoint]
    avg_handling_time_hours: float
    resolution_efficiency_pct: float
    pending_backlog_trend: List[ComplaintTimePoint]
    sla_breach_count: int
    assignee_distribution: List[ComplaintAssigneeItem]
    assignee_resolution_rate: List[ComplaintAssigneeItem]
    workload_distribution: List[ComplaintAssigneeItem]
    heatmap: List[ComplaintHeatPoint]
