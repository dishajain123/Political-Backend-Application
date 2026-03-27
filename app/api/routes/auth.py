"""
Authentication Routes Module
=============================
API endpoints for authentication operations.
Thin controller layer that delegates to AuthService.

Author: Political Communication Platform Team
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import Optional
import logging

from app.schemas.auth_schema import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    ChangePasswordRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    AuthResponse,
    VoterRegistrationRequest,
    LeaderRegistrationRequest,
    CorporatorRegistrationRequest,
)
from app.schemas.user_schema import UserCreateRequest
from ...services.auth_service import AuthService
from app.api.dependencies import (
    get_current_user,
    CurrentUser,
)
from app.core.security import create_user_tokens, get_user_id_from_token
from app.core.roles import UserRole


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth")


@router.post("/register-voter", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_voter(request: VoterRegistrationRequest) -> AuthResponse:
    """
    Register a new voter with full profile data.
    
    Args:
        request (VoterRegistrationRequest): Voter registration details
        
    Returns:
        AuthResponse: User info with access and refresh tokens
        
    Raises:
        HTTPException: If validation fails or user already exists
        
    Flow:
        1. Validate voter registration inputs
        2. Check if email/phone already registered
        3. Hash password and create voter user document
        4. Store demographics and family data
        5. Generate JWT tokens
        6. Return user info and tokens
    """
    try:
        result = await AuthService.register_voter(
            email=request.email,
            mobile_number=request.mobile_number,
            password=request.password,
            full_name=request.full_name,
            location=request.location.dict(),
            language_preference=request.language_preference,
            family_adults=request.family_adults,
            family_kids=request.family_kids,
            demographics=request.demographics.model_dump(),
        )
        
        logger.info(f"New voter registered: {result['user_id']}")
        
        return AuthResponse(
            success=True,
            message="Voter registration successful",
            data=result
        )
    
    except ValueError as e:
        logger.warning(f"Voter registration validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Voter registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Voter registration failed"
        )


@router.post("/register-leader", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_leader(request: LeaderRegistrationRequest) -> AuthResponse:
    """
    Register a new leader.
    Territory will be assigned by administrators after registration.
    
    Args:
        request (LeaderRegistrationRequest): Leader registration details
        
    Returns:
        AuthResponse: User info with access and refresh tokens
        
    Raises:
        HTTPException: If validation fails or user already exists
        
    Flow:
        1. Validate leader registration inputs
        2. Check if email/phone already registered
        3. Hash password and create leader user document
        4. Initialize performance tracking fields
        5. Generate JWT tokens
        6. Return user info and tokens
    """
    try:
        result = await AuthService.register_leader(
            email=request.email,
            mobile_number=request.mobile_number,
            password=request.password,
            full_name=request.full_name,
            location=request.location.dict(),
            language_preference=request.language_preference,
        )
        
        logger.info(f"New leader registered: {result['user_id']}")
        
        return AuthResponse(
            success=True,
            message="Leader registration successful",
            data=result
        )
    
    except ValueError as e:
        logger.warning(f"Leader registration validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Leader registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Leader registration failed"
        )


@router.post("/register-corporator", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register_corporator(request: CorporatorRegistrationRequest) -> AuthResponse:
    """
    Register a new corporator.
    Corporators are municipal representatives with oversight authority.
    Account approval may be required by administrators.
    
    Args:
        request (CorporatorRegistrationRequest): Corporator registration details
        
    Returns:
        AuthResponse: User info with access and refresh tokens
        
    Raises:
        HTTPException: If validation fails or user already exists
        
    Flow:
        1. Validate corporator registration inputs
        2. Check if email/phone already registered
        3. Hash password and create corporator user document
        4. Store demographics if provided
        5. Generate JWT tokens
        6. Return user info and tokens
    """
    try:
        result = await AuthService.register_corporator(
            email=request.email,
            mobile_number=request.mobile_number,
            password=request.password,
            full_name=request.full_name,
            location=request.location.dict(),
            language_preference=request.language_preference,
            demographics=request.demographics,
        )
        
        logger.info(f"New corporator registered: {result['user_id']}")
        
        return AuthResponse(
            success=True,
            message="Corporator registration successful",
            data=result
        )
    
    except ValueError as e:
        logger.warning(f"Corporator registration validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Corporator registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Corporator registration failed"
        )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: UserCreateRequest) -> AuthResponse:
    """
    Register a new user account (generic endpoint).
    SECURITY: Only allows VOTER role for public registration.
    Other roles must be created through admin panel.
    
    Args:
        request (UserCreateRequest): Registration details
        
    Returns:
        AuthResponse: User info with access and refresh tokens
        
    Raises:
        HTTPException: If validation fails or user already exists
        
    Flow:
        1. Validate registration inputs
        2. Check if email/phone already registered
        3. Hash password and create user document
        4. Generate JWT tokens
        5. Return user info and tokens
    """
    try:
        result = await AuthService.register_user(
            email=request.email,
            mobile_number=request.mobile_number,
            password=request.password,
            full_name=request.full_name,
            role=request.role,
            location=request.location.dict(),
            language_preference=request.language_preference
        )
        
        logger.info(f"New user registered: {result['user_id']}")
        
        return AuthResponse(
            success=True,
            message="Registration successful",
            data=result
        )
    
    except ValueError as e:
        logger.warning(f"Registration validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest) -> AuthResponse:
    """
    Authenticate user and generate tokens.
    
    Args:
        request (LoginRequest): Login credentials (email or mobile + password)
        
    Returns:
        AuthResponse: User info with access and refresh tokens
        
    Raises:
        HTTPException: If credentials are invalid
        
    Flow:
        1. Validate login request
        2. Find user by email or mobile number
        3. Verify password
        4. Update last login time
        5. Generate and return tokens
    """
    try:
        result = await AuthService.login_user(
            email=request.email,
            mobile_number=request.mobile_number,
            password=request.password
        )
        
        logger.info(f"User logged in: {result['user_id']}")
        
        return AuthResponse(
            success=True,
            message="Login successful",
            data=result
        )
    
    except ValueError as e:
        logger.warning(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/phone or password"
        )
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(request: RefreshTokenRequest) -> AuthResponse:
    """
    Refresh expired access token using refresh token.
    
    Args:
        request (RefreshTokenRequest): Contains refresh token
        
    Returns:
        AuthResponse: New access token
        
    Raises:
        HTTPException: If refresh token is invalid or expired
        
    Flow:
        1. Validate refresh token
        2. Extract user ID and role
        3. Generate new access token
        4. Return new token pair
    """
    try:
        # Decode refresh token
        from app.core.security import decode_token
        payload = decode_token(request.refresh_token)
        
        if not payload or payload.get("type") != "refresh":
            raise ValueError("Invalid refresh token")
        
        user_id = payload.get("sub")
        role_str = payload.get("role")
        
        if not user_id or not role_str:
            raise ValueError("Invalid token payload")
        
        # Create new tokens
        role = UserRole(role_str)
        tokens = create_user_tokens(user_id, role)
        
        logger.info(f"Token refreshed for user {user_id}")
        
        return AuthResponse(
            success=True,
            message="Token refreshed successfully",
            data=tokens
        )
    
    except ValueError as e:
        logger.warning(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/change-password", response_model=AuthResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user)
) -> AuthResponse:
    """
    Change user's password.
    
    Args:
        request (ChangePasswordRequest): Old and new passwords
        current_user (CurrentUser): Authenticated user
        
    Returns:
        AuthResponse: Success message
        
    Raises:
        HTTPException: If old password is incorrect or validation fails
        
    Flow:
        1. Authenticate user with old password
        2. Validate new password strength
        3. Update password in database
        4. Return success
    """
    try:
        await AuthService.change_password(
            user_id=current_user.user_id,
            old_password=request.old_password,
            new_password=request.new_password
        )
        
        logger.info(f"Password changed for user {current_user.user_id}")
        
        return AuthResponse(
            success=True,
            message="Password changed successfully"
        )
    
    except ValueError as e:
        logger.warning(f"Password change failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.post("/forgot-password", response_model=AuthResponse)
async def forgot_password(request: PasswordResetRequest) -> AuthResponse:
    """
    Initiate password reset process.
    Sends reset link to email or SMS.
    
    Args:
        request (PasswordResetRequest): Email or mobile number
        
    Returns:
        AuthResponse: Confirmation message
        
    Note:
        Returns generic message for security (doesn't reveal if user exists)
    """
    try:
        result = await AuthService.request_password_reset(
            email=request.email,
            mobile_number=request.mobile_number
        )
        
        logger.info("Password reset requested")
        
        return AuthResponse(
            success=True,
            message=result.get("message", "If user exists, reset link will be sent")
        )
    
    except Exception as e:
        logger.error(f"Password reset request error: {e}")
        # Return generic message for security
        return AuthResponse(
            success=True,
            message="If user exists, reset link will be sent"
        )


@router.post("/reset-password", response_model=AuthResponse)
async def reset_password(request: PasswordResetConfirm) -> AuthResponse:
    """
    Confirm password reset with token from email/SMS.
    
    Args:
        request (PasswordResetConfirm): Reset token and new password
        
    Returns:
        AuthResponse: Success message
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        await AuthService.confirm_password_reset(
            reset_token=request.reset_token,
            new_password=request.new_password
        )
        
        logger.info("Password reset completed")
        
        return AuthResponse(
            success=True,
            message="Password reset successfully"
        )
    
    except ValueError as e:
        logger.warning(f"Password reset failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )


@router.get("/me", response_model=AuthResponse)
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user)
) -> AuthResponse:
    """
    Get current authenticated user's information.
    
    Args:
        current_user (CurrentUser): Authenticated user
        
    Returns:
        AuthResponse: Current user info
    """
    return AuthResponse(
        success=True,
        message="User information retrieved",
        data={
            "user_id": current_user.user_id,
            "role": current_user.role.value
        }
    )


@router.post("/logout", response_model=AuthResponse)
async def logout(
    current_user: CurrentUser = Depends(get_current_user)
) -> AuthResponse:
    """
    Logout current user.
    In JWT-based auth, logout is client-side (token deletion).
    
    Args:
        current_user (CurrentUser): Authenticated user
        
    Returns:
        AuthResponse: Logout confirmation
    """
    logger.info(f"User logged out: {current_user.user_id}")
    
    return AuthResponse(
        success=True,
        message="Logged out successfully",
        data={"user_id": current_user.user_id}
    )
