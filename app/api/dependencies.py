"""
API Dependencies Module
=======================
FastAPI dependencies for authentication, authorization, and role-based access control.
Used as dependency injections in route handlers.

Author: Political Communication Platform Team
"""

from fastapi import Depends, HTTPException, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Tuple
import logging
from bson import ObjectId

from app.core.security import get_user_id_from_token, get_role_from_token, decode_token
from app.core.roles import UserRole, has_higher_or_equal_role
from app.core.permissions import has_permission
from app.db.mongodb import get_database

logger = logging.getLogger(__name__)
security = HTTPBearer()


class CurrentUser:
    """
    Represents the currently authenticated user.
    Contains user_id, role, and token for authorization checks.
    """
    def __init__(self, user_id: str, role: UserRole, token: str):
        self.user_id = user_id
        self.role = role
        self.token = token

    def __repr__(self):
        return f"CurrentUser(user_id={self.user_id}, role={self.role.value})"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> CurrentUser:
    """
    Validate JWT token and return current user with DB verification.
    """
    token = credentials.credentials

    # Step 0: Ensure token is an access token (refresh tokens must not authorize APIs)
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        logger.warning("Non-access token used for API authentication")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Step 1: Decode token and extract user_id
    user_id = get_user_id_from_token(token)
    if not user_id:
        logger.warning("Invalid token attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Step 2: Extract role from token (FIXED: convert to UserRole)
    token_role_raw = get_role_from_token(token)
    if not token_role_raw:
        logger.warning(f"Invalid role in token for user {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing role",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token_role = UserRole(token_role_raw)
    except ValueError:
        logger.error(f"Invalid role value in token: {token_role_raw}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token role"
        )

    # Step 3: Validate against database
    db = get_database()
    try:
        user_doc = await db.users.find_one({"_id": ObjectId(user_id)})
    except Exception as e:
        logger.error(f"Database error during user lookup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )

    if not user_doc:
        logger.warning(f"Token used for non-existent user: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user_doc.get("is_active", False):
        logger.warning(f"Token used for inactive user: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    db_role = UserRole(user_doc.get("role"))

    # Step 4: Role mismatch protection
    if db_role != token_role:
        logger.error(
            f"SECURITY ALERT: Role mismatch for user {user_id}. "
            f"Token role: {token_role.value}, DB role: {db_role.value}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token role mismatch. Please login again."
        )

    logger.debug(f"User authenticated: {user_id} ({db_role.value})")

    return CurrentUser(user_id=user_id, role=db_role, token=token)


def require_role(required_role: UserRole):
    """
    Dependency to enforce a minimum role level.
    Uses role hierarchy for political roles (Voter < Leader < Corporator).
    OPS role cannot use this - use require_permission() instead.
    
    Args:
        required_role: The minimum required role level
        
    Returns:
        Dependency function
    """
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if not has_higher_or_equal_role(current_user.role, required_role):
            logger.warning(
                f"Role check failed: user {current_user.user_id} "
                f"({current_user.role.value}) requires {required_role.value}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires {required_role.value} role or higher"
            )
        return current_user
    return role_checker


def require_roles(*allowed_roles: UserRole):
    """
    Dependency to enforce exact role membership.
    User must be one of the specified roles (order-agnostic).
    
    Args:
        *allowed_roles: One or more allowed roles
        
    Returns:
        Dependency function
    """
    async def role_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            logger.warning(
                f"Role check failed: user {current_user.user_id} "
                f"({current_user.role.value}) not in allowed roles: "
                f"{[r.value for r in allowed_roles]}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of: "
                       f"{', '.join(r.value for r in allowed_roles)}"
            )
        return current_user
    return role_checker


def require_ops():
    """
    Dependency to enforce OPS role (operations console access).
    Use this for endpoints that should ONLY be accessible to OPS users.
    
    Returns:
        Dependency function that checks for OPS role
        
    Example:
        @router.get("/ops/exclusive-endpoint")
        async def exclusive_endpoint(_=Depends(require_ops())):
            ...
    """
    async def ops_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if current_user.role != UserRole.OPS:
            logger.warning(
                f"OPS access denied: user {current_user.user_id} "
                f"({current_user.role.value}) is not OPS role"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This action requires OPS role"
            )
        return current_user
    return ops_checker


def require_permission(permission: str):
    """
    Dependency to enforce a specific permission.
    Used for granular access control (recommended for OPS endpoints).
    
    Args:
        permission: Permission constant from Permission class
        
    Returns:
        Dependency function
    """
    async def permission_checker(
        current_user: CurrentUser = Depends(get_current_user)
    ) -> CurrentUser:
        if not has_permission(current_user.role, permission):
            logger.warning(
                f"Permission check failed: user {current_user.user_id} "
                f"({current_user.role.value}) lacks '{permission}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have permission to perform this action: {permission}"
            )
        return current_user
    return permission_checker


def get_paginated_params(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page")
) -> Tuple[int, int]:
    """
    Extract pagination parameters from query string.
    
    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        
    Returns:
        Tuple of (skip, limit) for database queries
    """
    skip = (page - 1) * page_size
    limit = page_size
    return skip, limit