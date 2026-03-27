"""
Chat Service Compatibility Wrapper
==================================
Provides backward-compatible import path for ChatService.

Author: Political Communication Platform Team
"""

from app.services.chat import ChatService

__all__ = ["ChatService"]
