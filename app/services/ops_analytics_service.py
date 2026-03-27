"""
OPS Analytics Service Compatibility Wrapper
===========================================
Provides backward-compatible import path for OpsAnalyticsService.
"""

from app.services.analytics import OpsAnalyticsService

__all__ = ["OpsAnalyticsService"]
