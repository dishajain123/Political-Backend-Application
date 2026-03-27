"""
Donation Schema Module
======================
Pydantic schemas for donation-related endpoints.

Author: Political Communication Platform Team
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class DonationCreateRequest(BaseModel):
    """
    Submit a donation to a campaign.
    Citizens upload their UPI payment screenshot for verification.

    Fraud Detection:
        Backend will run OCR on the screenshot and hash-check for duplicates.
        If suspicious, status will be set to pending_review.
    """

    campaign_id: str = Field(..., description="Campaign ID to donate to")
    amount: float = Field(..., gt=0, description="Amount donated in INR")
    transaction_id: str = Field(
        ...,
        min_length=5,
        max_length=100,
        description="UPI transaction reference ID from payment receipt",
    )
    # screenshot is handled as a file upload (UploadFile) in the route layer

    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "CAMP-2024-001",
                "amount": 500.0,
                "transaction_id": "UPI123456789",
            }
        }


class DonationReviewRequest(BaseModel):
    """
    Corporator reviews a pending_review donation.
    Can approve or reject after manual verification.
    """

    action: str = Field(
        ...,
        description="Action to take: 'approve' or 'reject'",
    )
    review_notes: Optional[str] = Field(default=None, max_length=500)

    class Config:
        json_schema_extra = {
            "example": {
                "action": "approve",
                "review_notes": "Manually verified UPI screenshot — transaction confirmed",
            }
        }


class DonationResponse(BaseModel):
    """
    Donation response with full details.
    """

    id: str = Field(..., alias="_id")
    donation_id: str
    campaign_id: str
    user_id: str
    amount: float
    transaction_id: str
    screenshot_url: Optional[str] = None
    status: str
    created_at: str
    status_updated_at: str
    is_duplicate_screenshot: bool
    is_amount_mismatch: bool
    is_txn_id_duplicate: bool
    fraud_flags: List[str]
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None
    # OCR fields visible to corporator for audit
    ocr_amount: Optional[float] = None
    ocr_txn_id: Optional[str] = None
    # Receipt details
    receipt_id: Optional[str] = None
    receipt_url: Optional[str] = None
    contributor_name: Optional[str] = None
    contributor_role: Optional[str] = None
    campaign_title: Optional[str] = None
    corporator_name: Optional[str] = None
    receipt_generated_at: Optional[str] = None

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439012",
                "donation_id": "DON-2024-001",
                "campaign_id": "CAMP-2024-001",
                "user_id": "voter123",
                "amount": 500.0,
                "transaction_id": "UPI123456789",
                "status": "approved",
                "fraud_flags": [],
            }
        }


class DonationListResponse(BaseModel):
    """
    List of donations with pagination.
    """

    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[DonationResponse]

    class Config:
        json_schema_extra = {
            "example": {
                "total": 42,
                "page": 1,
                "page_size": 20,
                "total_pages": 3,
                "items": [],
            }
        }
