"""
Security Module
==============
Handles all security-related functionality including:
- Password hashing and verification
- JWT token creation and validation
- Security utilities

Author: Political Communication Platform Team
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
import logging  # FIX: Added missing import

from app.core.config import settings
from app.core.roles import UserRole


logger = logging.getLogger(__name__)  # FIX: Added logger initialization

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.
    
    Args:
        password (str): Plain text password
        
    Returns:
        str: Hashed password
        
    Example:
        >>> hashed = hash_password("mypassword123")
        >>> len(hashed) > 0
        True
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.
    
    Args:
        plain_password (str): Plain text password to verify
        hashed_password (str): Hashed password to compare against
        
    Returns:
        bool: True if password matches
        
    Example:
        >>> hashed = hash_password("mypassword123")
        >>> verify_password("mypassword123", hashed)
        True
        >>> verify_password("wrongpassword", hashed)
        False
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.
    
    Args:
        data (Dict[str, Any]): Data to encode in the token (typically user_id, role)
        expires_delta (Optional[timedelta]): Custom expiration time
        
    Returns:
        str: Encoded JWT token
        
    Example:
        >>> token = create_access_token({"sub": "user123", "role": "voter"})
        >>> len(token) > 0
        True
    """
    to_encode = data.copy()
    
    # Set expiration time
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    
    # Add standard JWT claims
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    
    # Encode the token
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT refresh token with longer expiration.
    
    Args:
        data (Dict[str, Any]): Data to encode in the token
        
    Returns:
        str: Encoded JWT refresh token
    """
    to_encode = data.copy()
    
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.
    
    Args:
        token (str): JWT token to decode
        
    Returns:
        Optional[Dict[str, Any]]: Decoded token payload or None if invalid
        
    Example:
        >>> token = create_access_token({"sub": "user123"})
        >>> payload = decode_token(token)
        >>> payload["sub"] == "user123"
        True
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[str]:
    """
    Extract user ID from a JWT token.
    
    Args:
        token (str): JWT token
        
    Returns:
        Optional[str]: User ID if valid, None otherwise
    """
    payload = decode_token(token)
    if payload:
        return payload.get("sub")
    return None


def get_role_from_token(token: str) -> Optional[UserRole]:
    """
    Extract user role from a JWT token.
    
    Args:
        token (str): JWT token
        
    Returns:
        Optional[UserRole]: User role if valid, None otherwise
    """
    payload = decode_token(token)
    if not payload:
        return None
    role_str = payload.get("role")
    if not role_str:
        return None
    try:
        return UserRole(role_str)
    except ValueError:
        logger.warning(f"Invalid role value in token: {role_str}")
        return None


def create_user_tokens(user_id: str, role: UserRole) -> Dict[str, str]:
    """
    Create both access and refresh tokens for a user.
    
    Args:
        user_id (str): User's unique identifier
        role (UserRole): User's role
        
    Returns:
        Dict[str, str]: Dictionary with access_token and refresh_token
        
    Example:
        >>> tokens = create_user_tokens("user123", UserRole.VOTER)
        >>> "access_token" in tokens and "refresh_token" in tokens
        True
    """
    token_data = {
        "sub": user_id,
        "role": role.value
    }
    
    return {
        "access_token": create_access_token(token_data),
        "refresh_token": create_refresh_token(token_data),
        "token_type": "bearer"
    }