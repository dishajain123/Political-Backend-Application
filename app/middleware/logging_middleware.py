"""
Logging Middleware Module
=========================
Middleware for request/response logging and performance monitoring.

Author: Political Communication Platform Team
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import logging
import time
import json
from typing import Callable


logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all HTTP requests and responses.
    Tracks request duration, status codes, and provides request/response details.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Log request details, process request, and log response.
        
        Args:
            request (Request): Incoming HTTP request
            call_next (Callable): Next middleware/route handler
            
        Returns:
            Response: HTTP response
        """
        # Skip OPTIONS requests (CORS preflight) - don't log them
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Record request start time
        start_time = time.time()
        
        # Log request details
        request_id = self._generate_request_id()
        request.state.request_id = request_id
        
        self._log_request(request, request_id)
        
        try:
            # Process request through next middleware/route
            response = await call_next(request)
        except Exception as e:
            # Log unhandled exceptions
            duration = time.time() - start_time
            logger.error(
                f"[{request_id}] Unhandled exception in {request.method} {request.url.path}",
                exc_info=e,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration * 1000,
                }
            )
            raise
        
        # Calculate response time
        duration = time.time() - start_time
        
        # Log response details
        self._log_response(request, response, duration, request_id)
        
        # Add timing header
        response.headers["X-Process-Time"] = str(duration)
        response.headers["X-Request-ID"] = request_id
        
        return response
    
    @staticmethod
    def _generate_request_id() -> str:
        """
        Generate unique request ID for tracking.
        
        Returns:
            str: Unique request ID
        """
        import uuid
        return str(uuid.uuid4())[:8]
    
    @staticmethod
    def _log_request(request: Request, request_id: str) -> None:
        """
        Log incoming request details.
        
        Args:
            request (Request): HTTP request
            request_id (str): Unique request ID
        """
        # Extract user info if available
        user_id = getattr(request.state, "user_id", None)
        user_role = getattr(request.state, "user_role", None)
        
        # Build log message
        user_info = f" [user: {user_id}, role: {user_role}]" if user_id else ""
        
        # Log request details
        logger.info(
            f"[{request_id}] {request.method} {request.url.path}{user_info}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params) if request.query_params else {},
                "user_id": user_id,
                "user_role": user_role,
                "client_host": request.client.host if request.client else None,
            }
        )
    
    @staticmethod
    def _log_response(
        request: Request,
        response: Response,
        duration: float,
        request_id: str
    ) -> None:
        """
        Log response details and request performance.
        
        Args:
            request (Request): HTTP request
            response (Response): HTTP response
            duration (float): Request duration in seconds
            request_id (str): Unique request ID
        """
        # Determine log level based on status code
        status_code = response.status_code
        
        if status_code >= 500:
            log_level = logger.error
            level_name = "ERROR"
        elif status_code >= 400:
            log_level = logger.warning
            level_name = "WARNING"
        elif status_code >= 300:
            log_level = logger.info
            level_name = "INFO"
        else:
            log_level = logger.info
            level_name = "INFO"
        
        duration_ms = duration * 1000
        
        # Log response details
        log_level(
            f"[{request_id}] {level_name} {request.method} {request.url.path} "
            f"{status_code} ({duration_ms:.2f}ms)",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "user_id": getattr(request.state, "user_id", None),
            }
        )


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add request context for correlation and tracking.
    Helps in distributed tracing and debugging.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Add request context to all requests.
        
        Args:
            request (Request): Incoming HTTP request
            call_next (Callable): Next middleware/route handler
            
        Returns:
            Response: HTTP response
        """
        # Add request metadata to state
        request.state.request_method = request.method
        request.state.request_path = request.url.path
        request.state.request_query = dict(request.query_params)
        
        # Call next middleware
        response = await call_next(request)
        
        # Add context headers to response
        if hasattr(request.state, "request_id"):
            response.headers["X-Request-ID"] = request.state.request_id
        
        return response