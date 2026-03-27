from fastapi import APIRouter, Depends, Path, Body, HTTPException, status
from typing import List

from app.api.dependencies import get_current_user, require_permission
from app.core.permissions import Permission
from app.core.roles import UserRole
from app.schemas.help_number_schema import (
    HelpNumberCreate,
    HelpNumberUpdate,
    HelpNumberResponse,
    HelpNumberListResponse,
)
from app.api.dependencies import CurrentUser
from app.services.help_number_service import HelpNumberService

router = APIRouter(prefix="/help-numbers", tags=["Help Numbers"])


@router.get(
    "",
    response_model=HelpNumberListResponse,
    summary="Get all active help numbers",
)
@router.get(
    "/",
    response_model=HelpNumberListResponse,
    summary="Get all active help numbers",
)
async def get_help_numbers(
    current_user: CurrentUser = Depends(get_current_user),
):
    service = HelpNumberService()
    items = await service.get_all_help_numbers()
    return HelpNumberListResponse(total=len(items), items=items)


@router.post(
    "",
    response_model=HelpNumberResponse,
    summary="Create help number (Corporator only)",
)
@router.post(
    "/",
    response_model=HelpNumberResponse,
    summary="Create help number (Corporator only)",
)
async def create_help_number(
    payload: HelpNumberCreate = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    if current_user.role != UserRole.CORPORATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Corporator can create help numbers",
        )
    service = HelpNumberService()
    try:
        return await service.create_help_number(payload, current_user)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put(
    "/{help_number_id}",
    response_model=HelpNumberResponse,
    summary="Update help number (Corporator only)",
)
async def update_help_number(
    help_number_id: str = Path(...),
    payload: HelpNumberUpdate = Body(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    if current_user.role != UserRole.CORPORATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Corporator can update help numbers",
        )
    service = HelpNumberService()
    try:
        return await service.update_help_number(help_number_id, payload, current_user)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete(
    "/{help_number_id}",
    summary="Delete help number (Corporator only)",
)
async def delete_help_number(
    help_number_id: str = Path(...),
    current_user: CurrentUser = Depends(get_current_user),
):
    if current_user.role != UserRole.CORPORATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Corporator can delete help numbers",
        )
    service = HelpNumberService()
    try:
        success = await service.delete_help_number(help_number_id, current_user)
        return {"success": success}
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc