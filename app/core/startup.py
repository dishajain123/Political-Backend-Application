"""
Application Startup / Shutdown Module
=====================================
Defines the FastAPI lifespan context manager.

Author: Political Communication Platform Team
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.db.mongodb import connect_to_mongo, close_mongo_connection, get_database
from app.db.indexes import create_indexes
from app.models.chat_model import create_chat_indexes
from app.services.help_number_service import HelpNumberService


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Handles startup and shutdown events.
    """
    logger.info("Starting up application...")
    await connect_to_mongo()

    logger.info("Creating database indexes...")
    await create_indexes()

    # Create chat-specific indexes (chats + messages collections)
    logger.info("Creating chat indexes...")
    await create_chat_indexes(get_database())

    # Seed help numbers data
    logger.info("Seeding help numbers...")
    await HelpNumberService().seed_initial_data()

    logger.info("Application startup complete!")

    yield  # Control back to FastAPI

    logger.info("Shutting down application...")
    await close_mongo_connection()
    logger.info("Application shutdown complete!")
