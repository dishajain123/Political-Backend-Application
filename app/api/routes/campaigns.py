"""
Campaign Routes
===============
API endpoints for ward campaign creation, listing, and donation processing.
All business logic is delegated to CampaignService.

Author: Political Communication Platform Team
"""

import logging

from fastapi import APIRouter, Depends, Query, Path, Body, HTTPException, status, Request
from typing import Optional

from app.api.dependencies import get_current_user, require_permission
from app.core.permissions import Permission
from app.core.roles import UserRole
from app.schemas.campaign_schema import (
    CampaignCreateRequest,
    CampaignResponse,
    CampaignProgressResponse,
)
from app.schemas.donation_schema import (
    DonationCreateRequest,
    DonationReviewRequest,
    DonationResponse,
)
from app.api.dependencies import CurrentUser
from app.services.campaign_service import CampaignService
from app.utils.pagination import get_paginated_params, PaginatedResponse

import json

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Campaign endpoints
# ---------------------------------------------------------------------------


@router.post(
    "",
)
@router.post(
    "/",
    response_model=CampaignResponse,
    summary="Create a new ward campaign (Corporator only)",
)
async def create_campaign(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Create a ward-level fundraising campaign.

    Access:
    - CORPORATOR only

    The campaign will be immediately active and visible to all users.
    Citizens can donate once a campaign is created.
    """
    if current_user.role not in (UserRole.CORPORATOR, UserRole.OPS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Corporators or OPS can create campaigns",
        )

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        data = {}
        for key, value in form.multi_items():
            if isinstance(value, str) and value.strip():
                data[key] = value.strip()
        for field in ("target_amount",):
            if field in data:
                try:
                    data[field] = float(data[field])
                except ValueError:
                    pass
    else:
        data = await request.json()

    try:
        payload = CampaignCreateRequest(**data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    service = CampaignService()
    try:
        return await service.create_campaign(payload, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get(
    "",
)
@router.get(
    "/",
    response_model=PaginatedResponse[CampaignResponse],
    summary="List campaigns",
)
async def list_campaigns(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    ward: Optional[str] = Query(None, description="Filter by ward"),
    pagination: tuple = Depends(get_paginated_params),
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_COMPLAINT)
    ),
):
    """
    List all campaigns.

    Visibility:
    - VOTER / LEADER: active campaigns only
    - CORPORATOR / OPS: all campaigns (active and closed)

    Filters:
    - is_active, category, ward
    """
    skip, limit = pagination
    service = CampaignService()
    return await service.list_campaigns(
        current_user=current_user,
        skip=skip,
        limit=limit,
        is_active=is_active,
        category=category,
        ward=ward,
    )


@router.get(
    "/{campaign_id}",
    response_model=CampaignResponse,
    summary="Get campaign details",
)
async def get_campaign(
    campaign_id: str = Path(..., description="Campaign ID or MongoDB ObjectId"),
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_COMPLAINT)
    ),
):
    """
    Retrieve full details of a single campaign.

    Access:
    - All authenticated users
    """
    service = CampaignService()
    try:
        return await service.get_campaign(campaign_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get(
    "/{campaign_id}/progress",
    response_model=CampaignProgressResponse,
    summary="Get campaign funding progress",
)
async def get_campaign_progress(
    campaign_id: str = Path(...),
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_COMPLAINT)
    ),
):
    """
    Return funding progress for a campaign.

    Response includes:
    - target_amount
    - total_raised
    - progress_percentage (capped at 100%)
    - remaining_amount
    - donation_count

    Access:
    - All authenticated users
    """
    service = CampaignService()
    try:
        return await service.get_campaign_progress(campaign_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.patch(
    "/{campaign_id}/close",
    summary="Close a campaign (Corporator only)",
)
async def close_campaign(
    campaign_id: str = Path(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Close a campaign so it no longer accepts donations.

    Access:
    - CORPORATOR who created the campaign
    - OPS
    """
    if current_user.role not in (UserRole.CORPORATOR, UserRole.OPS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Corporators or OPS can close campaigns",
        )

    service = CampaignService()
    try:
        success = await service.close_campaign(campaign_id, current_user)
    except ValueError as exc:
        detail = str(exc) or "Donation failed"
        logger.warning("Donation failed: %s", detail)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from exc

    return {"success": success}


# ---------------------------------------------------------------------------
# Donation endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/donate",
    response_model=DonationResponse,
    summary="Submit a donation with UPI screenshot",
)
async def donate(
    request: Request,
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_COMPLAINT)
    ),
):
    """
    Submit a donation to a ward campaign.

    Request (multipart/form-data):
    - campaign_id    (str, required)
    - amount         (float, required)
    - transaction_id (str, required)
    - screenshot     (file, recommended — JPG or PNG)

    Fraud Detection (automatic):
    1. Duplicate transaction_id check
    2. Duplicate screenshot detection via image hash
    3. OCR verification of amount and transaction ID from screenshot

    Status after submission:
    - approved       — no fraud flags detected
    - pending_review — one or more fraud flags triggered (Corporator reviews manually)

    Access:
    - All authenticated users (Voter, Leader, Corporator, OPS)
    """
    content_type = request.headers.get("content-type", "")
    upload_file = None
    data: dict = {}

    if "multipart/form-data" in content_type:
        form = await request.form()
        for key, value in form.multi_items():
            if key in ("screenshot", "file", "image", "attachment"):
                upload_file = value
                continue
            if value is None:
                continue
            if isinstance(value, str):
                if value.strip():
                    data[key] = value.strip()
                continue
            # Accept non-string form values (web FormData may pass numbers)
            data[key] = str(value)

        for field in ("amount",):
            if field in data:
                try:
                    data[field] = float(data[field])
                except (ValueError, TypeError):
                    pass
    else:
        data = await request.json()

    try:
        payload = DonationCreateRequest(**data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    service = CampaignService()
    try:
        return await service.process_donation(payload, current_user, screenshot=upload_file)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get(
    "/{campaign_id}/donations",
    response_model=PaginatedResponse[DonationResponse],
    summary="List donations for a campaign",
)
async def list_donations(
    campaign_id: str = Path(...),
    donation_status: Optional[str] = Query(
        None,
        alias="status",
        description="Filter: pending | approved | rejected | pending_review",
    ),
    pagination: tuple = Depends(get_paginated_params),
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_COMPLAINT)
    ),
):
    """
    List donations for a specific campaign.

    Visibility:
    - VOTER: only their own donations
    - CORPORATOR / OPS: all donations (can filter by status)
    - LEADER: only their own donations

    Access:
    - All authenticated users
    """
    skip, limit = pagination
    service = CampaignService()
    return await service.list_donations(
        current_user=current_user,
        campaign_id=campaign_id,
        status=donation_status,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/donations/me",
    response_model=PaginatedResponse[DonationResponse],
    summary="List my donation history",
)
async def list_my_donations(
    pagination: tuple = Depends(get_paginated_params),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    List donation history for the current user.
    """
    skip, limit = pagination
    service = CampaignService()
    return await service.list_user_donations(
        current_user=current_user,
        skip=skip,
        limit=limit,
    )


@router.patch(
    "/donations/{donation_id}/review",
    summary="Review a pending_review donation (Corporator only)",
)
async def review_donation(
    donation_id: str = Path(...),
    payload: DonationReviewRequest = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Corporator manually approves or rejects a flagged donation.

    When approved:
    - Campaign total_raised is updated
    - donation_count is incremented

    When rejected:
    - Campaign totals are NOT updated
    - Donation is marked rejected with review notes

    Access:
    - CORPORATOR
    - OPS

    Requirements:
    - Donation must be in pending or pending_review status
    """
    if current_user.role not in (UserRole.CORPORATOR, UserRole.OPS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Corporators or OPS can review donations",
        )

    service = CampaignService()
    try:
        success = await service.review_donation(donation_id, payload, current_user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return {"success": success}
