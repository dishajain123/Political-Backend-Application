"""
Application Factory Module
==========================
Creates and configures the FastAPI application instance.

Author: Political Communication Platform Team
"""

import logging
from pathlib import Path
from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.startup import lifespan
from app.core.routes import register_routers
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.logging_middleware import LoggingMiddleware


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("app.app_init")


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def create_application() -> FastAPI:
    """
    Factory function to create and configure the FastAPI application.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        description="Role-based Political Communication & Intelligence Platform",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan
    )

    # --- Static Files (uploads) ---
    static_dir = PROJECT_ROOT / "app" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # --- Favicon (avoid 405 noise from browser) ---
    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon():
        return Response(status_code=204)

    # --- CORS Configuration ---
    # Add CORS before other middleware so it executes first in the request pipeline
    # This must be done at application initialization, not as middleware wrapping
    from starlette.middleware.cors import CORSMiddleware as CORS
    app.add_middleware(
        CORS,
        allow_origins=["*"],  # Allow all origins for development/mobile
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Custom Middleware (Auth & Logging) ---
    # Added after CORS is configured
    app.add_middleware(AuthMiddleware)
    app.add_middleware(LoggingMiddleware)

    # --- Routers ---
    register_routers(app)

    # --- Health Check ---
    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "app_name": settings.APP_NAME, "version": "1.0.0"}

    # --- CORS Handler for OPTIONS requests ---
    # Explicitly handle all OPTIONS requests for CORS preflight
    @app.options("/{full_path:path}", include_in_schema=False)
    async def cors_preflight_handler(full_path: str):
        """Handle CORS preflight OPTIONS requests"""
        from starlette.responses import Response
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )

    logger.info(f"Application '{settings.APP_NAME}' initialized successfully")
    return app
