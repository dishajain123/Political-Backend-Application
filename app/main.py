"""
Main Application Entry Point
============================
This is the entry point for the FastAPI application.
It imports the configured app from app_init and runs it with uvicorn.

Usage:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Author: Political Communication Platform Team
"""

from app.app_init import app

# This allows running the app directly with: python -m app.main
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )