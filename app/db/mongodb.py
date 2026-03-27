"""
MongoDB Connection Module
========================
Manages MongoDB database connections and provides database instance access.
Uses Motor for async MongoDB operations.

Author: Political Communication Platform Team
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging

from app.core.config import settings


logger = logging.getLogger(__name__)


class MongoDB:
    """
    MongoDB connection manager.
    Implements singleton pattern for database connection.
    """
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None


async def connect_to_mongo() -> None:
    """
    Establish connection to MongoDB.
    Called during application startup.
    
    Raises:
        Exception: If connection fails
    """
    try:
        logger.info(f"Connecting to MongoDB at {settings.MONGODB_URL}")
        
        # Create async MongoDB client
        MongoDB.client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            maxPoolSize=10,
            minPoolSize=1,
            serverSelectionTimeoutMS=5000
        )
        
        # Get database instance
        MongoDB.db = MongoDB.client[settings.MONGODB_DB_NAME]
        
        # Test connection
        await MongoDB.client.admin.command('ping')
        
        logger.info(f"Successfully connected to MongoDB database: {settings.MONGODB_DB_NAME}")
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


async def close_mongo_connection() -> None:
    """
    Close MongoDB connection.
    Called during application shutdown.
    """
    try:
        if MongoDB.client:
            MongoDB.client.close()
            logger.info("MongoDB connection closed")
    except Exception as e:
        logger.error(f"Error closing MongoDB connection: {e}")


def get_database() -> AsyncIOMotorDatabase:
    """
    Get the MongoDB database instance.
    
    Returns:
        AsyncIOMotorDatabase: The active database instance
        
    Raises:
        RuntimeError: If database is not connected
        
    Example:
        >>> db = get_database()
        >>> users_collection = db["users"]
    """
    if MongoDB.db is None:
        raise RuntimeError("Database is not connected. Call connect_to_mongo() first.")
    return MongoDB.db


# Convenience function to get collections
def get_collection(collection_name: str):
    """
    Get a specific collection from the database.
    
    Args:
        collection_name (str): Name of the collection
        
    Returns:
        AsyncIOMotorCollection: The requested collection
        
    Example:
        >>> users = get_collection("users")
        >>> user = await users.find_one({"email": "test@example.com"})
    """
    db = get_database()
    return db[collection_name]