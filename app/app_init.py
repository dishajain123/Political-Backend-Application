"""
Application Initialization Module
==================================
Thin compatibility wrapper for app creation and import path fixes.

Author: Political Communication Platform Team
"""

import sys
from pathlib import Path

# --- Ensure project root is in sys.path for Windows/uvicorn reload ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.app_factory import create_application

# --- Create the FastAPI app instance ---
app = create_application()
