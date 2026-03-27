"""
User Routes Module
==================
API endpoints for user management operations.
Handles user CRUD, profile updates, leader assignments, and user analytics.

Author: Political Communication Platform Team
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional, List
import logging

from app.schemas.user_schema import (
    UserCreateRequest,
    UserProfileResponse,
    UserUpdateRequest,
    VoterDemographicsRequest,
    LeaderAssignmentRequest,
    UserListResponse,
    LeaderPerformanceResponse,
    VoterEngagementResponse,
    NotificationPreferencesRequest,
    GroundVerificationRequest,
    UserDirectoryResponse,
)
from app.db.mongodb import get_database
from app.services.user_service import UserService
from app.api.dependencies import (
    get_current_user,
    require_role,
    require_roles,
    require_permission,
    CurrentUser,
    get_paginated_params,
)
from app.core.roles import UserRole
from app.core.permissions import Permission
from app.utils.helpers import utc_now


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users")


@router.post("/", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreateRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.CREATE_USER))
) -> UserProfileResponse:
    """
    Create a new user (Corporator/Ops only).
    
    Args:
        request (UserCreateRequest): User creation details
        current_user (CurrentUser): Authenticated corporator/ops
        
    Returns:
        UserProfileResponse: Created user profile
        
    Raises:
        HTTPException: If validation fails or user already exists
    """
    try:
        user = await UserService.create_user(request, created_by=current_user.user_id)
        logger.info(f"User created: {user['id']} by {current_user.user_id}")
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"User creation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User creation failed"
        )


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: CurrentUser = Depends(get_current_user)
) -> UserProfileResponse:
    """
    Get current user's profile.
    
    Args:
        current_user (CurrentUser): Authenticated user
        
    Returns:
        UserProfileResponse: User profile
    """
    try:
        user = await UserService.get_user_by_id(current_user.user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch profile"
        )


@router.get("/me/insights")
async def get_my_insights(
    current_user: CurrentUser = Depends(get_current_user)
) -> dict:
    """
    Get current user's insights/stats based on role.
    
    For LEADER:
    - Number of voters in their ward/area
    - Number of complaints acknowledged
    
    For CORPORATOR:
    - Number of complaints resolved
    - Number of active leaders
    
    Args:
        current_user (CurrentUser): Authenticated user
        
    Returns:
        dict: User insights and stats
    """
    try:
        insights = await UserService.get_user_insights(current_user.user_id)
        return {
            "success": True,
            "data": insights
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching user insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch insights"
        )


@router.get("/directory", response_model=UserDirectoryResponse)
async def get_users_directory(
    current_user: CurrentUser = Depends(get_current_user)
) -> UserDirectoryResponse:
    """
    Get a public directory of Leaders and Corporators.
    Accessible to all authenticated roles (including voters).
    Returns only non-PII data: id, full_name, role, location (area/ward/city).
    Used by voters to browse and select a leader/corporator for booking appointments.
    """
    try:
        db = get_database()

        cursor = db.users.find(
            {"role": {"$in": ["leader", "corporator"]}, "is_active": True},
            {
                "_id": 1,
                "full_name": 1,
                "role": 1,
                "location": 1,
            }
        ).sort("full_name", 1)

        users = []
        async for user in cursor:
            users.append({
                "id": str(user["_id"]),
                "full_name": user.get("full_name", "Unknown"),
                "role": user.get("role", ""),
                "location": {
                    "area": user.get("location", {}).get("area", ""),
                    "ward": user.get("location", {}).get("ward", ""),
                    "city": user.get("location", {}).get("city", ""),
                },
            })

        return UserDirectoryResponse(success=True, data=users, total=len(users))
    except Exception as e:
        logger.error(f"Error fetching user directory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch directory"
        )


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user(
    user_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW_USER))
) -> UserProfileResponse:
    """
    Get user by ID (requires VIEW_USER permission).
    
    SECURITY ENFORCEMENT:
    - Voter profiles are always private
    - Leaders can only view users in their assigned territory
    - Corporators and OPS can view all users
    
    Args:
        user_id (str): User ID to fetch
        current_user (CurrentUser): Authenticated user
        
    Returns:
        UserProfileResponse: User profile
    """
    try:
        # CRITICAL: Pass current user context for territory enforcement
        user = await UserService.get_user_by_id(
            user_id,
            requesting_user_id=current_user.user_id,
            requesting_user_role=current_user.role
        )
        
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        # PRIVACY: Voter profiles are always private (even to Leaders in same territory)
        if user.get("role") == UserRole.VOTER.value and user_id != current_user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Voter profiles are private"
            )
        
        return user
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user"
        )


@router.patch("/me", response_model=UserProfileResponse)
async def update_my_profile(
    request: UserUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user)
) -> UserProfileResponse:
    """
    Update current user's profile.
    
    Args:
        request (UserUpdateRequest): Fields to update
        current_user (CurrentUser): Authenticated user
        
    Returns:
        UserProfileResponse: Updated user profile
    """
    try:
        user = await UserService.update_user(current_user.user_id, request)
        logger.info(f"User {current_user.user_id} updated profile")
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Profile update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed"
        )


@router.patch("/{user_id}", response_model=UserProfileResponse)
async def update_user(
    user_id: str,
    request: UserUpdateRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.UPDATE_USER))
) -> UserProfileResponse:
    """
    Update user by ID (Corporator/Ops only).
    
    Args:
        user_id (str): User ID to update
        request (UserUpdateRequest): Fields to update
        current_user (CurrentUser): Authenticated corporator/ops
        
    Returns:
        UserProfileResponse: Updated user profile
    """
    try:
        user = await UserService.update_user(user_id, request)
        logger.info(f"User {user_id} updated by {current_user.user_id}")
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"User update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User update failed"
        )


@router.post("/me/demographics", response_model=UserProfileResponse)
async def update_demographics(
    request: VoterDemographicsRequest,
    current_user: CurrentUser = Depends(require_role(UserRole.VOTER))
) -> UserProfileResponse:
    """
    Update voter demographics (voter only).
    
    Args:
        request (VoterDemographicsRequest): Demographics data
        current_user (CurrentUser): Authenticated voter
        
    Returns:
        UserProfileResponse: Updated user profile
    """
    try:
        user = await UserService.update_voter_demographics(current_user.user_id, request)
        logger.info(f"Voter {current_user.user_id} updated demographics")
        return user
    except Exception as e:
        logger.error(f"Demographics update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Demographics update failed"
        )


@router.post("/leaders/assign", status_code=status.HTTP_200_OK)
async def assign_leader(
    request: LeaderAssignmentRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.ASSIGN_LEADER_TERRITORY))
) -> dict:
    """
    Assign territory to a leader (Corporator only).
    
    Args:
        request (LeaderAssignmentRequest): Leader assignment details
        current_user (CurrentUser): Authenticated corporator
        
    Returns:
        dict: Assignment result
    """
    try:
        result = await UserService.assign_leader_territory(
            request, assigned_by=current_user.user_id
        )
        logger.info(f"Leader {request.leader_id} assigned territory by {current_user.user_id}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Leader assignment failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Leader assignment failed"
        )





@router.get("", response_model=UserListResponse)
@router.get("/", response_model=UserListResponse)
async def list_users(
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    state: Optional[str] = Query(None, description="Filter by state"),
    city: Optional[str] = Query(None, description="Filter by city"),
    ward: Optional[str] = Query(None, description="Filter by ward"),
    area: Optional[str] = Query(None, description="Filter by area"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    pagination: tuple = Depends(get_paginated_params),
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW_USER))
) -> UserListResponse:
    """
    List users with filters and pagination.
    
    CRITICAL SECURITY:
    - Voter profiles are NEVER listed (privacy protection)
    - Leaders can only see users in their assigned territory
    - Corporators and OPS can see all users
    
    Args:
        role: Filter by role
        state: Filter by state
        city: Filter by city
        ward: Filter by ward
        area: Filter by area
        is_active: Filter by active status
        pagination: Page and page_size
        current_user: Authenticated user
        
    Returns:
        UserListResponse: Paginated list of users
    """
    try:
        skip, limit = pagination
        page = (skip // limit) + 1
        
        # PRIVACY: Voter profiles are always private via standard listing
        # but Leaders/Corporators/OPS can see them in their scoped territory
        # with sanitization applied in the service layer.
        if role is not None and role == UserRole.VOTER:
             if current_user.role not in [UserRole.LEADER, UserRole.CORPORATOR, UserRole.OPS]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Voter profiles are private"
                )

        # Build base filters
        filters = {}
        if role:
            filters["role"] = role
        if state:
            filters["location.state"] = state
        if city:
            filters["location.city"] = city
        if ward:
            filters["location.ward"] = ward
        if area:
            filters["location.area"] = area
        if is_active is not None:
            filters["is_active"] = is_active
        
        # CRITICAL: Pass current user context for territory enforcement
        users, total = await UserService.list_users(
            filters,
            skip,
            limit,
            requesting_user_id=current_user.user_id,
            requesting_user_role=current_user.role
        )
        
        return UserListResponse(
            total=total,
            page=page,
            page_size=limit,
            total_pages=(total + limit - 1) // limit,
            items=users
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@router.get("/leaders/performance/{leader_id}", response_model=LeaderPerformanceResponse)
async def get_leader_performance(
    leader_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW_LEADER_PERFORMANCE))
) -> LeaderPerformanceResponse:
    """
    Get leader performance metrics (Corporator/Ops only).
    
    Args:
        leader_id (str): Leader user ID
        current_user (CurrentUser): Authenticated corporator/ops
        
    Returns:
        LeaderPerformanceResponse: Leader performance data
    """
    try:
        performance = await UserService.get_leader_performance(leader_id)
        return performance
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching leader performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch leader performance"
        )


@router.get("/voters/engagement/{voter_id}", response_model=VoterEngagementResponse)
async def get_voter_engagement(
    voter_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW_USER_ANALYTICS))
) -> VoterEngagementResponse:
    """
    Get voter engagement metrics (Corporator/Ops only).
    
    Args:
        voter_id (str): Voter user ID
        current_user (CurrentUser): Authenticated corporator/ops
        
    Returns:
        VoterEngagementResponse: Voter engagement data
    """
    try:
        engagement = await UserService.get_voter_engagement(voter_id)
        return engagement
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching voter engagement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch voter engagement"
        )


@router.patch("/me/notification-preferences", response_model=UserProfileResponse)
async def update_notification_preferences(
    request: NotificationPreferencesRequest,
    current_user: CurrentUser = Depends(get_current_user)
) -> UserProfileResponse:
    """
    Update notification preferences.
    
    Args:
        request (NotificationPreferencesRequest): Notification preferences
        current_user (CurrentUser): Authenticated user
        
    Returns:
        UserProfileResponse: Updated user profile
    """
    try:
        user = await UserService.update_notification_preferences(
            current_user.user_id, request
        )
        logger.info(f"User {current_user.user_id} updated notification preferences")
        return user
    except Exception as e:
        logger.error(f"Notification preferences update failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification preferences"
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: str,
    current_user: CurrentUser = Depends(require_permission(Permission.DELETE_USER))
):
    """
    Deactivate user account (Corporator/Ops only).
    
    Args:
        user_id (str): User ID to deactivate
        current_user (CurrentUser): Authenticated corporator/ops
    """
    try:
        await UserService.deactivate_user(user_id)
        logger.info(f"User {user_id} deactivated by {current_user.user_id}")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"User deactivation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User deactivation failed"
        )


# ============================================================================
# PHASE 6: LEADER ACTIVITY TRACKING ENDPOINTS
# ============================================================================

@router.post("/leaders/{leader_id}/activity", status_code=status.HTTP_200_OK)
async def log_leader_activity_endpoint(
    leader_id: str,
    activity_type: str = Query(
        ...,
        description="Activity type: message, event, voter_interaction, poll_response, complaint_followup, complaint_handled, complaint_resolved"
    ),
    increment_amount: int = Query(1, ge=1, description="Amount to increment by"),
    current_user: CurrentUser = Depends(require_permission(Permission.UPDATE_USER))
) -> dict:
    """
    Log leader activity (e.g., message shared, event attended).
    Increments performance metrics.
    
    Args:
        leader_id: Leader user ID
        activity_type: Type of activity
        increment_amount: How much to increment
        current_user: Authenticated corporator/ops
        
    Returns:
        Updated performance metrics
    """
    try:
        performance = await UserService.log_leader_activity(
            leader_id, activity_type, increment_amount
        )
        logger.info(f"Leader {leader_id} activity logged: {activity_type} (+{increment_amount}) by {current_user.user_id}")
        return {
            "success": True,
            "leader_id": leader_id,
            "activity_type": activity_type,
            "increment_amount": increment_amount,
            "performance": performance
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error logging leader activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log activity"
        )


@router.put("/leaders/{leader_id}/response-time", status_code=status.HTTP_200_OK)
async def update_leader_response_time(
    leader_id: str,
    hours: float = Query(..., ge=0, description="Response time in hours"),
    current_user: CurrentUser = Depends(require_permission(Permission.UPDATE_USER))
) -> dict:
    """
    Update leader's average response time.
    
    Args:
        leader_id: Leader user ID
        hours: Response time in hours
        current_user: Authenticated corporator/ops
        
    Returns:
        Updated performance metrics
    """
    try:
        performance = await UserService.log_leader_response_time(leader_id, hours)
        logger.info(f"Leader {leader_id} response time updated to {hours}h by {current_user.user_id}")
        return {
            "success": True,
            "leader_id": leader_id,
            "response_time_hours": hours,
            "performance": performance
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating response time: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update response time"
        )


@router.put("/leaders/{leader_id}/rating", status_code=status.HTTP_200_OK)
async def update_leader_rating_endpoint(
    leader_id: str,
    rating: float = Query(..., ge=1, le=5, description="Rating 1-5"),
    current_user: CurrentUser = Depends(require_permission(Permission.UPDATE_USER))
) -> dict:
    """
    Update leader's rating (from voter feedback).
    
    Args:
        leader_id: Leader user ID
        rating: Rating value 1-5
        current_user: Authenticated corporator/ops
        
    Returns:
        Updated performance metrics
    """
    try:
        performance = await UserService.update_leader_rating(leader_id, rating)
        logger.info(f"Leader {leader_id} rating updated to {rating} by {current_user.user_id}")
        return {
            "success": True,
            "leader_id": leader_id,
            "rating": rating,
            "performance": performance
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating rating: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update rating"
        )


@router.post("/leaders/{leader_id}/tasks/{task_id}/complete", status_code=status.HTTP_200_OK)
async def complete_leader_task(
    leader_id: str,
    task_id: str,
    completed: bool = Query(True, description="Mark as completed or incomplete"),
    notes: str = Query(None, description="Optional completion notes"),
    current_user: CurrentUser = Depends(require_permission(Permission.UPDATE_USER))
) -> dict:
    """
    Mark a task as completed for a leader.
    
    Args:
        leader_id: Leader user ID
        task_id: Task ID to mark complete
        completed: Whether to mark as complete (True) or incomplete (False)
        notes: Optional notes
        current_user: Authenticated corporator/ops
        
    Returns:
        Updated leader document
    """
    try:
        user = await UserService.update_task_completion(leader_id, task_id, completed, notes)
        logger.info(f"Leader {leader_id} task {task_id} marked {'complete' if completed else 'incomplete'} by {current_user.user_id}")
        return {
            "success": True,
            "leader_id": leader_id,
            "task_id": task_id,
            "completed": completed,
            "tasks_completed": user.get("performance", {}).get("tasks_completed", 0),
            "tasks_assigned": user.get("performance", {}).get("tasks_assigned", 0)
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error marking task complete: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update task"
        )


@router.post("/leaders/{leader_id}/ground-verification", status_code=status.HTTP_201_CREATED)
async def log_ground_verification_endpoint(
    leader_id: str,
    request: GroundVerificationRequest,
    current_user: CurrentUser = Depends(require_permission(Permission.UPDATE_USER))
) -> dict:
    """
    Log a ground verification completed by a leader.
    
    Args:
        leader_id: Leader user ID
        request: Verification details
        current_user: Authenticated leader/corporator/ops
        
    Returns:
        Updated leader document
    """
    try:
        # Check if current user is the leader or has permission
        if current_user.role == UserRole.LEADER and current_user.user_id != leader_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Leaders can only log their own verifications"
            )
        
        user = await UserService.log_ground_verification(
            leader_id,
            request.location,
            request.photos,
            request.notes
        )
        logger.info(f"Ground verification logged for leader {leader_id} by {current_user.user_id}")
        return {
            "success": True,
            "leader_id": leader_id,
            "verification_count": user.get("performance", {}).get("ground_verifications_completed", 0),
            "verified_at": utc_now().isoformat()
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error logging ground verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log verification"
        )


@router.get("/leaders/{leader_id}/activity-history")
async def get_leader_activity_history_endpoint(
    leader_id: str,
    days: int = Query(30, ge=1, le=365, description="Look back N days"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW_USER))
) -> dict:
    """
    Get activity history for a leader.
    
    Args:
        leader_id: Leader user ID
        days: Number of days to look back
        page: Pagination page
        page_size: Items per page
        current_user: Authenticated user
        
    Returns:
        Activity history with pagination
    """
    try:
        skip = (page - 1) * page_size
        history = await UserService.get_leader_activity_history(
            leader_id, days, skip, page_size
        )
        return history
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching activity history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch activity history"
        )
