from fastapi import APIRouter, Depends, Query
from app.services.feedback_service import FeedbackService
from app.schemas.feedback_schema import FeedbackCreate, FeedbackListResponse
from app.api.dependencies import require_permission, get_current_user, CurrentUser
from app.core.permissions import Permission

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("")
async def submit(
    payload: FeedbackCreate,
    user=Depends(require_permission(Permission.CREATE_FEEDBACK)),
):
    service = FeedbackService()
    return await service.submit(payload, user)


@router.get("", response_model=FeedbackListResponse)
async def list_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _=Depends(require_permission(Permission.VIEW_ALL_FEEDBACK)),
):
    service = FeedbackService()
    return await service.list_all(page=page, page_size=page_size)


@router.get("/me", response_model=FeedbackListResponse)
async def list_my_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW_FEEDBACK)),
):
    service = FeedbackService()
    return await service.list_for_user(
        user_id=current_user.user_id,
        page=page,
        page_size=page_size,
    )
