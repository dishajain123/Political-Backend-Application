"""
Campaign Schema Module
======================
Pydantic schemas for campaign-related endpoints.

Author: Political Communication Platform Team
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CampaignCreateRequest(BaseModel):
    """
    Create a new campaign request.
    Only Corporators can create campaigns.
    """

    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    target_amount: float = Field(..., gt=0, description="Fundraising goal in INR")
    upi_id: str = Field(..., description="UPI ID for receiving donations")
    upi_name: str = Field(..., description="Registered name on UPI account")
    category: str = Field(
        default="general",
        description="road_repair | school_infrastructure | drainage | water_supply | general",
    )
    ward: Optional[str] = Field(default=None)
    area: Optional[str] = Field(default=None)
    city: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Ward 5 Road Repair Drive",
                "description": "Fundraising to repair potholes on the main road in Ward 5",
                "target_amount": 500000.0,
                "upi_id": "ward5corp@upi",
                "upi_name": "Ward 5 Development Fund",
                "category": "road_repair",
                "ward": "Ward 5",
                "city": "Mumbai",
                "state": "Maharashtra",
            }
        }


class CampaignUpdateRequest(BaseModel):
    """
    Update an existing campaign.
    Corporators can update description and target amount.
    """

    description: Optional[str] = Field(default=None, min_length=10, max_length=2000)
    target_amount: Optional[float] = Field(default=None, gt=0)
    is_active: Optional[bool] = Field(default=None)

    class Config:
        json_schema_extra = {
            "example": {
                "description": "Updated campaign description with more details",
                "target_amount": 600000.0,
            }
        }


class CampaignResponse(BaseModel):
    """
    Campaign response with full details.
    """

    id: str = Field(..., alias="_id")
    campaign_id: str
    title: str
    description: str
    target_amount: float
    total_raised: float
    upi_id: str
    upi_name: str
    created_by: str
    created_at: str
    is_active: bool
    category: str
    ward: Optional[str] = None
    area: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    donation_count: int
    closed_at: Optional[str] = None
    progress_percentage: Optional[float] = None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "campaign_id": "CAMP-2024-001",
                "title": "Ward 5 Road Repair Drive",
                "target_amount": 500000.0,
                "total_raised": 125000.0,
                "donation_count": 42,
                "is_active": True,
                "progress_percentage": 25.0,
            }
        }


class CampaignProgressResponse(BaseModel):
    """
    Campaign funding progress details.
    """

    campaign_id: str
    title: str
    target_amount: float
    total_raised: float
    progress_percentage: float
    donation_count: int
    is_active: bool
    remaining_amount: float

    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "CAMP-2024-001",
                "title": "Ward 5 Road Repair Drive",
                "target_amount": 500000.0,
                "total_raised": 125000.0,
                "progress_percentage": 25.0,
                "donation_count": 42,
                "is_active": True,
                "remaining_amount": 375000.0,
            }
        }


class CampaignListResponse(BaseModel):
    """
    List of campaigns with pagination.
    """

    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[CampaignResponse]

    class Config:
        json_schema_extra = {
            "example": {
                "total": 12,
                "page": 1,
                "page_size": 20,
                "total_pages": 1,
                "items": [],
            }
        }