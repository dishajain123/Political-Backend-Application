"""
Areas Routes Module
===================
API endpoints for geographic area management.
Handles area CRUD operations for OPS console.

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
router = APIRouter(prefix="/areas")


class AreaCreateRequest(BaseModel):
    """Request to create a new area."""
    name: str = Field(..., min_length=1, max_length=200)
    state: str = Field(..., min_length=1, max_length=100)
    city: str = Field(..., min_length=1, max_length=100)
    ward: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=1000)


class AreaResponse(BaseModel):
    """Area response schema."""
    id: str = Field(..., alias="_id")
    name: str
    state: str
    city: str
    ward: Optional[str] = None
    description: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        populate_by_name = True


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_area(
    request: AreaCreateRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.CREATE_USER))
) -> dict:
    """
    Create a new geographic area.
    
    Args:
        request: Area creation details
        current_user: Authenticated OPS user
        
    Returns:
        Created area document
        
    Raises:
        HTTPException: If area creation fails
    """
    try:
        logger.info(f"[CREATE_AREA] Creating area: {request.name} in {request.city}, {request.state}")
        
        db = get_database()
        
        # Check if area already exists
        logger.debug(f"[CREATE_AREA] Checking for duplicate area: {request.name} in {request.city}")
        existing_area = await db.areas.find_one({
            "name": request.name.lower(),
            "city": request.city.lower(),
            "state": request.state.lower()
        })
        
        if existing_area:
            logger.warning(f"[CREATE_AREA] Area already exists: {request.name}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Area with this name already exists in this city"
            )
        
        # Create area document
        logger.debug(f"[CREATE_AREA] Building area document...")
        area_doc = {
            "name": request.name,
            "name_lower": request.name.lower(),
            "state": request.state,
            "state_lower": request.state.lower(),
            "city": request.city,
            "city_lower": request.city.lower(),
            "ward": request.ward,
            "ward_lower": request.ward.lower() if request.ward else None,
            "description": request.description,
            "created_by": current_user.user_id,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "is_active": True
        }
        
        logger.debug(f"[CREATE_AREA] Inserting area document...")
        result = await db.areas.insert_one(area_doc)
        area_id = str(result.inserted_id)
        logger.info(f"[CREATE_AREA] Area created successfully: {area_id}")
        
        # Return created area
        area_doc["_id"] = area_id
        area_doc.pop("_id", None) if "_id" in area_doc and area_doc["_id"] != area_id else None
        
        return {
            "id": area_id,
            "name": area_doc["name"],
            "state": area_doc["state"],
            "city": area_doc["city"],
            "ward": area_doc.get("ward"),
            "description": area_doc.get("description"),
            "created_at": area_doc["created_at"].isoformat() if hasattr(area_doc["created_at"], 'isoformat') else str(area_doc["created_at"]),
            "updated_at": area_doc["updated_at"].isoformat() if hasattr(area_doc["updated_at"], 'isoformat') else str(area_doc["updated_at"])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CREATE_AREA] Error creating area: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create area: {str(e)}"
        )


@router.get("", response_model=dict, status_code=status.HTTP_200_OK)
async def list_areas(
    state: Optional[str] = None,
    city: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user)
) -> dict:
    """
    List all areas with optional filters.
    
    Args:
        state: Filter by state (optional)
        city: Filter by city (optional)
        current_user: Authenticated user
        
    Returns:
        List of areas
    """
    try:
        logger.debug(f"[LIST_AREAS] Fetching areas, state={state}, city={city}")
        
        db = get_database()
        
        # Build filter
        filter_dict = {"is_active": True}
        if state:
            filter_dict["state_lower"] = state.lower()
        if city:
            filter_dict["city_lower"] = city.lower()
        
        logger.debug(f"[LIST_AREAS] Query filter: {filter_dict}")
        
        # Fetch areas
        cursor = db.areas.find(filter_dict)
        areas = await cursor.to_list(None)
        
        logger.info(f"[LIST_AREAS] Found {len(areas)} areas")
        
        # Format response
        formatted_areas = []
        for area in areas:
            formatted_areas.append({
                "id": str(area.get("_id")),
                "name": area.get("name"),
                "state": area.get("state"),
                "city": area.get("city"),
                "ward": area.get("ward"),
                "description": area.get("description"),
                "created_at": area.get("created_at").isoformat() if hasattr(area.get("created_at"), 'isoformat') else str(area.get("created_at")),
                "updated_at": area.get("updated_at").isoformat() if hasattr(area.get("updated_at"), 'isoformat') else str(area.get("updated_at"))
            })
        
        return {
            "total": len(formatted_areas),
            "areas": formatted_areas
        }
        
    except Exception as e:
        logger.error(f"[LIST_AREAS] Error fetching areas: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch areas: {str(e)}"
        )
