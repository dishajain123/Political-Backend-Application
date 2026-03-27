"""
Campaign Model Module
=====================
Defines the Campaign data model for MongoDB.
Handles ward campaign creation, funding tracking, and lifecycle management.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from bson import ObjectId


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


class CampaignModel(BaseModel):
    """
    Main Campaign model.
    Represents ward-level community development campaigns created by Corporators.

    Workflow:
        Created by Corporator -> Active -> Citizens donate -> Target reached / Closed
    """

    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    # Campaign identification
    title: str = Field(..., min_length=5, max_length=200, description="Campaign title")
    description: str = Field(..., min_length=10, max_length=2000, description="Detailed campaign description")

    # Funding details
    target_amount: float = Field(..., gt=0, description="Fundraising goal in INR")
    total_raised: float = Field(default=0.0, ge=0, description="Total amount raised so far in INR")

    # UPI payment details for citizen contributions
    upi_id: str = Field(..., description="UPI ID where donations should be sent")
    upi_name: str = Field(..., description="Registered name on the UPI account")

    # Creator information
    created_by: str = Field(..., description="Corporator user ID who created the campaign")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Status
    is_active: bool = Field(default=True, description="Whether the campaign is accepting donations")
    closed_at: Optional[datetime] = Field(default=None, description="Timestamp when campaign was closed")
    closed_by: Optional[str] = Field(default=None, description="User ID who closed the campaign")

    # Category for reporting
    category: str = Field(
        default="general",
        description="Campaign category: road_repair, school_infrastructure, drainage, water_supply, general",
    )

    # Ward/location info (mirrors LocationHierarchy subset)
    ward: Optional[str] = Field(default=None, description="Ward this campaign belongs to")
    area: Optional[str] = Field(default=None, description="Area within the ward")
    city: Optional[str] = Field(default=None, description="City")
    state: Optional[str] = Field(default=None, description="State")

    # Donation count for quick stats
    donation_count: int = Field(default=0, ge=0, description="Number of approved donations received")

    class Config:
        """Pydantic configuration"""
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "title": "Ward 5 Road Repair Drive",
                "description": "Fundraising to repair potholes and resurface the main road in Ward 5",
                "target_amount": 500000.0,
                "upi_id": "ward5corp@upi",
                "upi_name": "Ward 5 Development Fund",
                "created_by": "corporator_user_id",
                "category": "road_repair",
                "ward": "Ward 5",
                "city": "Mumbai",
                "state": "Maharashtra",
            }
        }