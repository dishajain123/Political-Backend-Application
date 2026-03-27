"""
Donation Model Module
=====================
Defines the Donation data model for MongoDB.
Handles citizen donations to ward campaigns with fraud detection support.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional
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


class DonationStatus:
    """Donation status constants"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"

    ALL = [PENDING, APPROVED, REJECTED, PENDING_REVIEW]


class DonationModel(BaseModel):
    """
    Donation model.
    Represents a citizen's UPI donation to a ward campaign.

    Fraud Detection Fields:
        image_hash   -- perceptual hash of screenshot to detect reuse
        ocr_text     -- raw text extracted from screenshot via pytesseract
        ocr_amount   -- amount parsed from OCR for cross-validation
        ocr_txn_id   -- transaction ID parsed from OCR for uniqueness check

    Workflow:
        Citizen submits donation + screenshot
        -> Fraud checks run (hash + OCR)
        -> status = approved | pending_review
        -> Corporator reviews pending_review donations
        -> Campaign total_raised updated on approval
    """

    id: Optional[PyObjectId] = Field(alias="_id", default=None)

    # Relationship keys
    campaign_id: str = Field(..., description="Campaign ID this donation belongs to")
    user_id: str = Field(..., description="Voter/citizen user ID who donated")

    # Donation details
    amount: float = Field(..., gt=0, description="Amount donated in INR as entered by the citizen")

    # Payment proof
    transaction_id: str = Field(..., description="UPI transaction reference ID entered by citizen")
    screenshot_url: Optional[str] = Field(
        default=None,
        description="URL/path of the uploaded UPI payment screenshot",
    )

    # Fraud detection
    image_hash: Optional[str] = Field(
        default=None,
        description="Perceptual hash (MD5 of pixel data) of screenshot for duplicate detection",
    )
    ocr_text: Optional[str] = Field(
        default=None,
        description="Raw text extracted from screenshot via pytesseract OCR",
    )
    ocr_amount: Optional[float] = Field(
        default=None,
        description="Amount parsed from OCR output for cross-validation against submitted amount",
    )
    ocr_txn_id: Optional[str] = Field(
        default=None,
        description="Transaction ID parsed from OCR output for verification",
    )

    # Fraud flags
    is_duplicate_screenshot: bool = Field(
        default=False,
        description="True if image_hash already exists in DB (reused screenshot)",
    )
    is_amount_mismatch: bool = Field(
        default=False,
        description="True if entered amount does not match OCR-extracted amount",
    )
    is_txn_id_duplicate: bool = Field(
        default=False,
        description="True if transaction_id already exists in another donation",
    )
    fraud_flags: list = Field(
        default_factory=list,
        description="List of human-readable fraud flag descriptions",
    )

    # Status
    status: str = Field(
        default=DonationStatus.PENDING,
        description="Donation status: pending | approved | rejected | pending_review",
    )
    status_updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Review fields (Corporator action)
    reviewed_by: Optional[str] = Field(default=None, description="Corporator user ID who reviewed")
    reviewed_at: Optional[datetime] = Field(default=None)
    review_notes: Optional[str] = Field(default=None, max_length=500)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration"""
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "campaign_id": "CAMP-2024-001",
                "user_id": "voter_user_id",
                "amount": 500.0,
                "transaction_id": "UPI-123456789",
                "screenshot_url": "/static/donations/screenshot.jpg",
                "status": "pending",
            }
        }