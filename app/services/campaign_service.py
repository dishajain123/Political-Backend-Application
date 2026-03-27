"""
Campaign Service
================
Service layer for ward campaign and donation lifecycle management.

Responsibilities:
- Campaign CRUD operations
- Donation submission with fraud detection
- OCR-based payment verification via pytesseract
- Duplicate screenshot detection via image hashing
- Duplicate transaction ID detection
- Campaign funding progress calculation

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pathlib import Path
from uuid import uuid4
import hashlib
import logging
import re

from fastapi import UploadFile
from pymongo.errors import DuplicateKeyError

from app.db.mongodb import get_database
from app.utils.pagination import create_paginated_response
from app.schemas.campaign_schema import CampaignResponse, CampaignProgressResponse
from app.schemas.donation_schema import DonationResponse
from app.core.roles import UserRole
from app.utils.receipt_generator import generate_receipt_pdf

logger = logging.getLogger(__name__)

_DONATION_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
_DONATION_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# ---------------------------------------------------------------------------
# Lazy OCR import — pytesseract is optional; service degrades gracefully
# ---------------------------------------------------------------------------
def _try_ocr(image_path: str) -> str:
    """
    Run pytesseract OCR on image_path.
    Returns raw extracted string, or empty string if pytesseract unavailable.
    """
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        return pytesseract.image_to_string(img)
    except ImportError:
        logger.warning("pytesseract or Pillow not installed — OCR skipped")
        return ""
    except Exception as exc:
        logger.warning("OCR failed for %s: %s", image_path, exc)
        return ""


# ---------------------------------------------------------------------------
# OCR parsing helpers
# ---------------------------------------------------------------------------
def _parse_ocr_amount(ocr_text: str) -> Optional[float]:
    """
    Extract a numeric amount from OCR text.
    Looks for patterns like: ₹500, Rs 500, Paid 500.00, Amount 500
    """
    patterns = [
        r"(?:₹|Rs\.?|INR|Amount|Paid|amount|paid)[:\s]*([0-9,]+(?:\.[0-9]{1,2})?)",
        r"([0-9,]+\.[0-9]{2})\s*(?:INR|₹|Rs)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            try:
                raw = match.group(1).replace(",", "")
                return float(raw)
            except ValueError:
                continue
    return None


def _parse_ocr_txn_id(ocr_text: str) -> Optional[str]:
    """
    Extract a UPI transaction / reference ID from OCR text.
    UPI Ref IDs are typically 12-digit numeric strings.
    Also matches patterns like: UPI Ref No, Transaction ID, Ref ID.
    """
    patterns = [
        r"(?:UPI\s*Ref(?:\s*No)?|UTR|Transaction\s*ID|Ref(?:erence)?\s*(?:ID|No)?)[:\s]*([A-Z0-9]{8,})",
        r"\b([0-9]{12})\b",  # 12-digit UPI reference numbers
    ]
    for pattern in patterns:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


# ---------------------------------------------------------------------------
# Image hash helper
# ---------------------------------------------------------------------------
def _compute_image_hash(file_bytes: bytes) -> str:
    """Return MD5 hex digest of raw image bytes for duplicate detection."""
    return hashlib.md5(file_bytes).hexdigest()


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------
class CampaignService:
    """Campaign and donation lifecycle service."""

    def __init__(self):
        self.db = get_database()
        self.campaigns = self.db.campaigns
        self.donations = self.db.donations
        self.users = self.db.users

    # -----------------------------------------------------------------------
    # Campaign operations
    # -----------------------------------------------------------------------

    async def create_campaign(self, payload, current_user) -> CampaignResponse:
        """
        Create a new ward campaign.
        Only Corporators are allowed (enforced via Permission in route layer).
        """
        count = await self.campaigns.count_documents({})
        campaign_id = f"CAMP-{datetime.utcnow().year}-{count + 1:04d}"
        now = datetime.utcnow()

        doc = {
            "campaign_id": campaign_id,
            "title": payload.title,
            "description": payload.description,
            "target_amount": payload.target_amount,
            "total_raised": 0.0,
            "upi_id": payload.upi_id,
            "upi_name": payload.upi_name,
            "created_by": current_user.user_id,
            "created_at": now,
            "is_active": True,
            "closed_at": None,
            "closed_by": None,
            "category": payload.category,
            "ward": payload.ward,
            "area": payload.area,
            "city": payload.city,
            "state": payload.state,
            "donation_count": 0,
        }

        result = await self.campaigns.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return CampaignResponse(**self._normalize_campaign(doc))

    async def list_campaigns(
        self,
        current_user,
        skip: int = 0,
        limit: int = 20,
        is_active: Optional[bool] = None,
        category: Optional[str] = None,
        ward: Optional[str] = None,
    ) -> dict:
        """
        List campaigns with optional filters.
        All roles can view active campaigns.
        """
        query = {}
        if is_active is not None:
            query["is_active"] = is_active
        if category:
            query["category"] = category
        if ward:
            query["ward"] = ward

        # Voters and Leaders see only active campaigns
        if current_user.role in (UserRole.VOTER, UserRole.LEADER):
            query["is_active"] = True

        total = await self.campaigns.count_documents(query)
        cursor = self.campaigns.find(query).sort("created_at", -1).skip(skip).limit(limit)

        items = []
        async for doc in cursor:
            items.append(CampaignResponse(**self._normalize_campaign(doc)))

        page = (skip // limit) + 1 if limit else 1
        return create_paginated_response(items=items, total=total, page=page, page_size=limit)

    async def get_campaign(self, campaign_id: str) -> CampaignResponse:
        """Fetch a single campaign by campaign_id or ObjectId."""
        doc = await self._get_campaign(campaign_id)
        return CampaignResponse(**self._normalize_campaign(doc))

    async def get_campaign_progress(self, campaign_id: str) -> CampaignProgressResponse:
        """Return funding progress details for a campaign."""
        doc = await self._get_campaign(campaign_id)
        target = doc.get("target_amount", 1)
        raised = doc.get("total_raised", 0.0)
        percentage = round((raised / target) * 100, 2) if target > 0 else 0.0
        return CampaignProgressResponse(
            campaign_id=doc.get("campaign_id", ""),
            title=doc.get("title", ""),
            target_amount=target,
            total_raised=raised,
            progress_percentage=min(percentage, 100.0),
            donation_count=doc.get("donation_count", 0),
            is_active=doc.get("is_active", False),
            remaining_amount=max(target - raised, 0.0),
        )

    async def close_campaign(self, campaign_id: str, current_user) -> bool:
        """Close a campaign so it no longer accepts donations."""
        doc = await self._get_campaign(campaign_id)
        now = datetime.utcnow()
        result = await self.campaigns.update_one(
            {"_id": doc["_id"]},
            {"$set": {"is_active": False, "closed_at": now, "closed_by": current_user.user_id}},
        )
        return result.modified_count > 0

    # -----------------------------------------------------------------------
    # Donation operations
    # -----------------------------------------------------------------------

    async def process_donation(
        self,
        payload,
        current_user,
        screenshot: Optional[UploadFile] = None,
    ) -> DonationResponse:
        """
        Process a citizen donation submission.

        Steps:
        1. Validate campaign exists and is active.
        2. Check for duplicate transaction_id.
        3. Save screenshot file.
        4. Compute image hash and check for duplicate screenshots.
        5. Run OCR on screenshot.
        6. Validate OCR amount vs submitted amount.
        7. Determine status: approved | pending_review.
        8. Persist donation document.
        9. If approved, update campaign totals.
        """
        # Step 1 — campaign exists and active
        campaign = await self._get_campaign(payload.campaign_id)
        if not campaign.get("is_active"):
            raise ValueError("This campaign is no longer accepting donations")

        now = datetime.utcnow()
        fraud_flags: List[str] = []
        is_duplicate_txn = False
        is_duplicate_screenshot = False
        is_amount_mismatch = False
        image_hash: Optional[str] = None
        screenshot_url: Optional[str] = None
        ocr_text: Optional[str] = None
        ocr_amount: Optional[float] = None
        ocr_txn_id: Optional[str] = None
        file_bytes: Optional[bytes] = None

        # Fetch contributor + corporator info for receipt
        contributor_doc = await self.users.find_one({"_id": ObjectId(current_user.user_id)})
        contributor_name = (contributor_doc or {}).get("full_name", "Unknown")
        contributor_role = current_user.role.value
        corporator_doc = await self.users.find_one({"_id": ObjectId(campaign.get("created_by"))})
        corporator_name = (corporator_doc or {}).get("full_name", "Unknown")

        receipt_id = f"RCPT-{datetime.utcnow().year}-{uuid4().hex[:8].upper()}"
        receipt_generated_at = now
        receipt_url: Optional[str] = None

        # Step 2 — duplicate transaction ID check
        existing_txn = await self.donations.find_one({"transaction_id": payload.transaction_id})
        if existing_txn:
            is_duplicate_txn = True
            fraud_flags.append(
                f"Duplicate transaction ID '{payload.transaction_id}' already linked to another donation"
            )

        # Step 3 — save screenshot
        if screenshot is not None:
            screenshot_url, file_bytes = await self._save_donation_screenshot(screenshot)

        # Step 4 — image hash and duplicate screenshot check
        if file_bytes is not None:
            image_hash = _compute_image_hash(file_bytes)
            existing_hash = await self.donations.find_one({"image_hash": image_hash})
            if existing_hash:
                is_duplicate_screenshot = True
                fraud_flags.append("Screenshot appears to have been used in a previous donation")

        # Step 5 — OCR
        if screenshot_url is not None:
            app_dir = Path(__file__).resolve().parents[1]
            abs_path = str(app_dir / screenshot_url.lstrip("/"))
            ocr_text = _try_ocr(abs_path)

            if ocr_text:
                # Step 6 — amount validation
                ocr_amount = _parse_ocr_amount(ocr_text)
                if ocr_amount is not None:
                    # Allow ±1 INR tolerance for floating-point display differences
                    if abs(ocr_amount - payload.amount) > 1.0:
                        is_amount_mismatch = True
                        fraud_flags.append(
                            f"Submitted amount ₹{payload.amount} does not match OCR amount ₹{ocr_amount}"
                        )
                else:
                    fraud_flags.append("OCR could not detect the paid amount")

                ocr_txn_id = _parse_ocr_txn_id(ocr_text)
            else:
                fraud_flags.append("OCR failed or screenshot unreadable")

        # Step 7 — determine status
        if fraud_flags:
            donation_status = "pending_review"
        else:
            donation_status = "approved"

        # Step 7.1 — generate receipt PDF
        try:
            receipt_url = generate_receipt_pdf(
                receipt_id=receipt_id,
                contributor_name=contributor_name,
                contributor_role=contributor_role,
                amount=payload.amount,
                campaign_title=campaign.get("title", ""),
                corporator_name=corporator_name,
                timestamp=receipt_generated_at,
                transaction_id=payload.transaction_id,
            )
        except Exception as exc:
            logger.error("Receipt generation failed: %s", exc)
            raise ValueError("Failed to generate receipt. Please try again.") from exc

        # Step 8 — persist
        count = await self.donations.count_documents({})
        donation_id = f"DON-{datetime.utcnow().year}-{count + 1:04d}"

        doc = {
            "donation_id": donation_id,
            "campaign_id": payload.campaign_id,
            "user_id": current_user.user_id,
            "amount": payload.amount,
            "transaction_id": payload.transaction_id,
            "screenshot_url": screenshot_url,
            "image_hash": image_hash,
            "ocr_text": ocr_text,
            "ocr_amount": ocr_amount,
            "ocr_txn_id": ocr_txn_id,
            "is_duplicate_screenshot": is_duplicate_screenshot,
            "is_amount_mismatch": is_amount_mismatch,
            "is_txn_id_duplicate": is_duplicate_txn,
            "fraud_flags": fraud_flags,
            "status": donation_status,
            "status_updated_at": now,
            "reviewed_by": None,
            "reviewed_at": None,
            "review_notes": None,
            "created_at": now,
            "receipt_id": receipt_id,
            "receipt_url": receipt_url,
            "contributor_name": contributor_name,
            "contributor_role": contributor_role,
            "campaign_title": campaign.get("title", ""),
            "corporator_name": corporator_name,
            "receipt_generated_at": receipt_generated_at,
        }

        try:
            result = await self.donations.insert_one(doc)
            doc["_id"] = str(result.inserted_id)
        except DuplicateKeyError:
            raise ValueError(
                f"Transaction ID '{payload.transaction_id}' already exists. "
                "Please use a unique transaction ID."
            )

        # Step 9 — update campaign totals immediately on submission
        doc["counted_in_campaign"] = True
        await self._adjust_campaign_totals(campaign["_id"], payload.amount, 1)

        return DonationResponse(**self._normalize_donation(doc))

    async def list_donations(
        self,
        current_user,
        campaign_id: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        """
        List donations.
        - Voters see only their own donations.
        - Corporators/OPS see all (or filtered by campaign).
        """
        query = {}
        if current_user.role == UserRole.VOTER:
            query["user_id"] = current_user.user_id
        if campaign_id:
            query["campaign_id"] = campaign_id
        if status:
            query["status"] = status

        total = await self.donations.count_documents(query)
        cursor = self.donations.find(query).sort("created_at", -1).skip(skip).limit(limit)

        items = []
        async for doc in cursor:
            items.append(DonationResponse(**self._normalize_donation(doc)))

        page = (skip // limit) + 1 if limit else 1
        return create_paginated_response(items=items, total=total, page=page, page_size=limit)

    async def list_user_donations(
        self,
        current_user,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        """
        List donations for the currently authenticated user (voter/leader).
        """
        query = {"user_id": current_user.user_id}
        total = await self.donations.count_documents(query)
        cursor = self.donations.find(query).sort("created_at", -1).skip(skip).limit(limit)

        items = []
        async for doc in cursor:
            items.append(DonationResponse(**self._normalize_donation(doc)))

        page = (skip // limit) + 1 if limit else 1
        return create_paginated_response(items=items, total=total, page=page, page_size=limit)

    async def review_donation(
        self,
        donation_id: str,
        payload,
        current_user,
    ) -> bool:
        """
        Corporator approves or rejects a pending_review donation.
        On approval, campaign totals are updated.
        """
        donation = await self._get_donation(donation_id)

        if donation.get("status") not in ("pending", "pending_review"):
            raise ValueError("Only pending or pending_review donations can be reviewed")

        action = payload.action.lower()
        if action not in ("approve", "reject"):
            raise ValueError("action must be 'approve' or 'reject'")

        new_status = "approved" if action == "approve" else "rejected"
        now = datetime.utcnow()

        result = await self.donations.update_one(
            {"_id": donation["_id"]},
            {
                "$set": {
                    "status": new_status,
                    "status_updated_at": now,
                    "reviewed_by": current_user.user_id,
                    "reviewed_at": now,
                    "review_notes": payload.review_notes,
                }
            },
        )

        # Adjust campaign totals based on review outcome
        if result.modified_count > 0:
            counted = donation.get("counted_in_campaign", False)
            campaign = await self._get_campaign(donation.get("campaign_id", ""))
            if new_status == "approved" and not counted:
                await self._adjust_campaign_totals(campaign["_id"], donation.get("amount", 0), 1)
                await self.donations.update_one(
                    {"_id": donation["_id"]},
                    {"$set": {"counted_in_campaign": True}},
                )
            if new_status == "rejected" and counted:
                await self._adjust_campaign_totals(campaign["_id"], -donation.get("amount", 0), -1)
                await self.donations.update_one(
                    {"_id": donation["_id"]},
                    {"$set": {"counted_in_campaign": False}},
                )

        return result.modified_count > 0

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    async def _get_campaign(self, campaign_id: str) -> dict:
        """Fetch campaign by campaign_id string or ObjectId."""
        query = {"campaign_id": campaign_id}
        if ObjectId.is_valid(campaign_id):
            query = {"$or": [{"_id": ObjectId(campaign_id)}, {"campaign_id": campaign_id}]}
        doc = await self.campaigns.find_one(query)
        if not doc:
            raise ValueError("Campaign not found")
        return doc

    async def _get_donation(self, donation_id: str) -> dict:
        """Fetch donation by donation_id string or ObjectId."""
        query = {"donation_id": donation_id}
        if ObjectId.is_valid(donation_id):
            query = {"$or": [{"_id": ObjectId(donation_id)}, {"donation_id": donation_id}]}
        doc = await self.donations.find_one(query)
        if not doc:
            raise ValueError("Donation not found")
        return doc

    async def _adjust_campaign_totals(self, campaign_object_id, amount_delta: float, count_delta: int) -> None:
        """Atomically adjust total_raised and donation_count on a campaign."""
        inc: Dict[str, Any] = {}
        if amount_delta:
            inc["total_raised"] = amount_delta
        if count_delta:
            inc["donation_count"] = count_delta
        if not inc:
            return
        await self.campaigns.update_one(
            {"_id": campaign_object_id},
            {"$inc": inc},
        )

    async def _save_donation_screenshot(self, upload_file: UploadFile):
        """
        Validate and persist uploaded screenshot.
        Returns (relative_url, raw_bytes).
        """
        def _ext_from_content_type(content_type: Optional[str]) -> Optional[str]:
            if not content_type:
                return None
            content_type = content_type.lower()
            if content_type in ("image/jpeg", "image/jpg"):
                return "jpg"
            if content_type == "image/png":
                return "png"
            return None

        filename = (upload_file.filename or "").strip()
        ext = Path(filename).suffix.lower().lstrip(".") if filename else ""
        if not ext:
            ext = _ext_from_content_type(getattr(upload_file, "content_type", None)) or ""

        if ext not in _DONATION_ALLOWED_EXTENSIONS:
            raise ValueError(
                "Screenshot must be a JPG or PNG image with a valid filename or content-type"
            )

        content = await upload_file.read()
        await upload_file.close()

        if not content:
            raise ValueError("Screenshot file is empty")
        if len(content) > _DONATION_MAX_FILE_SIZE:
            raise ValueError("Screenshot file size exceeds 10 MB limit")

        app_dir = Path(__file__).resolve().parents[1]
        upload_dir = app_dir / "static" / "donations"
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid4().hex}.{ext}"
        file_path = upload_dir / safe_name
        file_path.write_bytes(content)

        return f"/static/donations/{safe_name}", content

    @staticmethod
    def _normalize_campaign(doc: dict) -> dict:
        """Convert ObjectId and datetime fields for Pydantic serialization."""
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])

        for field in ("created_at", "closed_at"):
            value = doc.get(field)
            if isinstance(value, datetime):
                doc[field] = value.isoformat()

        # Compute progress percentage inline
        target = doc.get("target_amount", 0) or 0
        raised = doc.get("total_raised", 0.0) or 0.0
        doc["progress_percentage"] = round((raised / target) * 100, 2) if target > 0 else 0.0

        # Ensure campaign_id present (older docs may lack it)
        if "campaign_id" not in doc:
            doc["campaign_id"] = str(doc.get("_id", ""))

        return doc

    @staticmethod
    def _normalize_donation(doc: dict) -> dict:
        """Convert ObjectId and datetime fields for Pydantic serialization."""
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])

        for field in ("created_at", "status_updated_at", "reviewed_at", "receipt_generated_at"):
            value = doc.get(field)
            if isinstance(value, datetime):
                doc[field] = value.isoformat()

        # Ensure donation_id present
        if "donation_id" not in doc:
            doc["donation_id"] = str(doc.get("_id", ""))

        # Ensure list fields are not None
        if doc.get("fraud_flags") is None:
            doc["fraud_flags"] = []

        return doc
