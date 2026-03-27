"""
Authentication Middleware Module
================================
Middleware for token validation and user context enrichment.

Author: Political Communication Platform Team
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import logging
from typing import Callable

from app.core.security import decode_token


logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate JWT tokens and add user context to requests.
    Tokens are extracted from Authorization header and validated.
    """
    
    # Public endpoints that don't require authentication
    PUBLIC_ENDPOINTS = [
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/refresh",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/verify-email",
        "/api/v1/auth/verify-mobile",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request, validate token if required, and add user context.
        
        Args:
            request (Request): Incoming HTTP request
            call_next (Callable): Next middleware/route handler
            
        Returns:
            Response: HTTP response
        """
        # Skip OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Check if endpoint is public
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        # Extract token from Authorization header
        token = self._extract_token(request)
        
        if not token:
            # Endpoint requires auth but no token provided
            # Will be handled by route dependency injection
            logger.debug(f"No token provided for {request.url.path}")
            return await call_next(request)
        
        # Validate token and add user context to request
        try:
            payload = decode_token(token)
            
            if payload:
                # Add user context to request state
                request.state.user_id = payload.get("sub")
                request.state.user_role = payload.get("role")
                request.state.token_type = payload.get("type")
                
                logger.debug(f"Token validated for user {request.state.user_id}")
            else:
                logger.warning(f"Invalid token provided for {request.url.path}")
        
        except Exception as e:
            logger.error(f"Error validating token: {e}")
        
        # Continue to next middleware/route
        return await call_next(request)
    
    @staticmethod
    def _extract_token(request: Request) -> str | None:
        """
        Extract JWT token from Authorization header.
        
        Expected format: "Bearer <token>"
        
        Args:
            request (Request): HTTP request
            
        Returns:
            str | None: JWT token or None if not found
        """
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return None
        
        # Check for Bearer scheme
        parts = auth_header.split()
        
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.warning("Invalid Authorization header format")
            return None
        
        return parts[1]
    
    @staticmethod
    def _is_public_endpoint(path: str) -> bool:
        """
        Check if endpoint is public (doesn't require authentication).
        
        Args:
            path (str): Request path
            
        Returns:
            bool: True if endpoint is public
        """
        # Exact matches
        if path in AuthMiddleware.PUBLIC_ENDPOINTS:
            return True
        
        # Prefix matches
        public_prefixes = [
            "/health",
            "/api/v1/auth/",
            "/docs",
            "/redoc",
            "/openapi",
        ]
        
        for prefix in public_prefixes:
            if path.startswith(prefix):
                return True
        
        return False