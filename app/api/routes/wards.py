"""
Wards Routes Module
===================
API endpoints for geographic ward management.
Handles ward CRUD operations for OPS console.

Author: Political Communication Platform Team
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
import logging
from datetime import datetime

from app.db.mongodb import get_database
from app.api.dependencies import (
    get_current_user,
    require_permission,
    CurrentUser,
)
from app.core.permissions import Permission
from app.utils.helpers import utc_now
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/wards")


class WardCreateRequest(BaseModel):
    """Request to create a new ward."""
    name: str = Field(..., min_length=1, max_length=200)
    ward_number: Optional[str] = Field(default=None, max_length=50)
    state: str = Field(..., min_length=1, max_length=100)
    city: str = Field(..., min_length=1, max_length=100)
    area_id: Optional[str] = Field(default=None, description="ID of the parent area")
    description: Optional[str] = Field(default=None, max_length=1000)


class WardResponse(BaseModel):
    """Ward response schema."""
    id: str = Field(..., alias="_id")
    name: str
    ward_number: Optional[str] = None
    state: str
    city: str
    area_id: Optional[str] = None
    description: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        populate_by_name = True


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_ward(
    request: WardCreateRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.CREATE_USER))
) -> dict:
    """
    Create a new geographic ward.
    
    Args:
        request: Ward creation details
        current_user: Authenticated OPS user
        
    Returns:
        Created ward document
        
    Raises:
        HTTPException: If ward creation fails
    """
    try:
        logger.info(f"[CREATE_WARD] Creating ward: {request.name} in {request.city}, {request.state}")
        
        db = get_database()
        
        # Check if ward already exists
        logger.debug(f"[CREATE_WARD] Checking for duplicate ward: {request.name} in {request.city}")
        existing_ward = await db.wards.find_one({
            "name": request.name.lower(),
            "city": request.city.lower(),
            "state": request.state.lower()
        })
        
        if existing_ward:
            logger.warning(f"[CREATE_WARD] Ward already exists: {request.name}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ward with this name already exists in this city"
            )
        
        # Create ward document
        logger.debug(f"[CREATE_WARD] Building ward document...")
        ward_doc = {
            "name": request.name,
            "name_lower": request.name.lower(),
            "ward_number": request.ward_number,
            "state": request.state,
            "state_lower": request.state.lower(),
            "city": request.city,
            "city_lower": request.city.lower(),
            "area_id": request.area_id,
            "description": request.description,
            "created_by": current_user.user_id,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "is_active": True
        }
        
        logger.debug(f"[CREATE_WARD] Inserting ward document...")
        result = await db.wards.insert_one(ward_doc)
        ward_id = str(result.inserted_id)
        logger.info(f"[CREATE_WARD] Ward created successfully: {ward_id}")
        
        # Return created ward
        ward_doc["_id"] = ward_id
        
        return {
            "id": ward_id,
            "name": ward_doc["name"],
            "ward_number": ward_doc.get("ward_number"),
            "state": ward_doc["state"],
            "city": ward_doc["city"],
            "area_id": ward_doc.get("area_id"),
            "description": ward_doc.get("description"),
            "created_at": ward_doc["created_at"].isoformat() if hasattr(ward_doc["created_at"], 'isoformat') else str(ward_doc["created_at"]),
            "updated_at": ward_doc["updated_at"].isoformat() if hasattr(ward_doc["updated_at"], 'isoformat') else str(ward_doc["updated_at"])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CREATE_WARD] Error creating ward: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create ward: {str(e)}"
        )


@router.get("", response_model=dict, status_code=status.HTTP_200_OK)
async def list_wards(
    state: Optional[str] = None,
    city: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user)
) -> dict:
    """
    List all wards with optional filters.
    
    Args:
        state: Filter by state (optional)
        city: Filter by city (optional)
        current_user: Authenticated user
        
    Returns:
        List of wards
    """
    try:
        logger.debug(f"[LIST_WARDS] Fetching wards, state={state}, city={city}")
        
        db = get_database()
        
        # Build filter
        filter_dict = {"is_active": True}
        if state:
            filter_dict["state_lower"] = state.lower()
        if city:
            filter_dict["city_lower"] = city.lower()
        
        logger.debug(f"[LIST_WARDS] Query filter: {filter_dict}")
        
        # Fetch wards
        cursor = db.wards.find(filter_dict)
        wards = await cursor.to_list(None)
        
        logger.info(f"[LIST_WARDS] Found {len(wards)} wards")
        
        # Format response
        formatted_wards = []
        for ward in wards:
            formatted_wards.append({
                "id": str(ward.get("_id")),
                "name": ward.get("name"),
                "ward_number": ward.get("ward_number"),
                "state": ward.get("state"),
                "city": ward.get("city"),
                "description": ward.get("description"),
                "created_at": ward.get("created_at").isoformat() if hasattr(ward.get("created_at"), 'isoformat') else str(ward.get("created_at")),
                "updated_at": ward.get("updated_at").isoformat() if hasattr(ward.get("updated_at"), 'isoformat') else str(ward.get("updated_at"))
            })
        
        return {
            "total": len(formatted_wards),
            "wards": formatted_wards
        }
        
    except Exception as e:
        logger.error(f"[LIST_WARDS] Error fetching wards: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch wards: {str(e)}"
        )
