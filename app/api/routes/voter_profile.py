"""
Voter Profile Routes
====================
Voter-only profile endpoints for demographic updates, profile retrieval,
and ECI voter lookup (captcha proxy, EPIC search, detail search, save).

Author: Political Communication Platform Team
"""

from fastapi import APIRouter, HTTPException, status, Depends
import logging

from app.schemas.user_schema import UserProfileResponse, VoterProfileUpdateRequest
from app.schemas.voter_lookup_schema import (
    CaptchaResponse,
    VoterSearchByEpicRequest,
    VoterSearchByDetailsRequest,
    VoterSearchResult,
    VoterSaveRequest,
    VoterSaveResponse,
)
from app.services.user_service import UserService
from app.services.voter_lookup_service import VoterLookupService
from app.api.dependencies import require_role, CurrentUser
from app.core.roles import UserRole

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voter")


# ---------------------------------------------------------------------------
# Existing voter profile endpoints (unchanged)
# ---------------------------------------------------------------------------

@router.get("/profile", response_model=UserProfileResponse)
async def get_voter_profile(
    current_user: CurrentUser = Depends(require_role(UserRole.VOTER))
) -> UserProfileResponse:
    """
    Get current voter profile (voter only).
    """
    try:
        user = await UserService.get_user_by_id(current_user.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching voter profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch voter profile"
        )


@router.post("/profile/update", response_model=UserProfileResponse)
async def update_voter_profile(
    request: VoterProfileUpdateRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.VOTER))
) -> UserProfileResponse:
    """
    Update voter profile fields (voter only).
    """
    try:
        user = await UserService.update_voter_profile(current_user.user_id, request)
        logger.info(f"Voter {current_user.user_id} updated profile")
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Voter profile update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed"
        )


# ---------------------------------------------------------------------------
# ECI Voter Lookup endpoints
# ---------------------------------------------------------------------------

@router.get("/captcha", response_model=CaptchaResponse)
async def get_captcha(
    current_user: CurrentUser = Depends(require_role(UserRole.VOTER))
) -> CaptchaResponse:
    """
    Create an ECI session and return a base64-encoded captcha image.
    The returned session_id must be supplied in subsequent search calls.
    Captcha expires in 120 seconds.
    """
    try:
        result = await VoterLookupService.get_captcha()
        return CaptchaResponse(**result)
    except RuntimeError as e:
        logger.error(f"Captcha fetch failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch captcha from ECI portal"
        )
    except Exception as e:
        logger.error(f"Unexpected error in get_captcha: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Captcha service error"
        )


@router.post("/search-epic", response_model=VoterSearchResult)
async def search_by_epic(
    request: VoterSearchByEpicRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.VOTER))
) -> VoterSearchResult:
    """
    Search for a voter by EPIC number via ECI portal proxy.
    Requires a valid session_id obtained from GET /voter/captcha.
    Rate limited to 5 searches per minute per session.
    """
    try:
        result = await VoterLookupService.search_epic(request)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No voter record found for the provided EPIC number"
            )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        logger.error(f"ECI EPIC search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ECI portal request failed"
        )
    except Exception as e:
        logger.error(f"Unexpected error in search_by_epic: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Voter search service error"
        )


@router.post("/search-details", response_model=VoterSearchResult)
async def search_by_details(
    request: VoterSearchByDetailsRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.VOTER))
) -> VoterSearchResult:
    """
    Search for a voter by personal details via ECI portal proxy.
    Requires a valid session_id obtained from GET /voter/captcha.
    Rate limited to 5 searches per minute per session.
    """
    try:
        result = await VoterLookupService.search_details(request)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No voter record found for the provided details"
            )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        logger.error(f"ECI details search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ECI portal request failed"
        )
    except Exception as e:
        logger.error(f"Unexpected error in search_by_details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Voter search service error"
        )


@router.post("/save", response_model=VoterSaveResponse)
async def save_voter_profile(
    request: VoterSaveRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.VOTER))
) -> VoterSaveResponse:
    """
    Save a verified voter profile (EPIC + constituency/polling station) for a user.
    The EPIC number is encrypted before storage.
    """
    try:
        result = await VoterLookupService.save_voter_profile(request)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Save voter profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save voter profile"
        )