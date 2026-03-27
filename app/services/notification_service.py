"""
Notification Service
====================
Stores and retrieves in-app notifications with proper data isolation.

Responsibilities:
- Create notifications (for system, announcements, updates)
- Fetch notifications for a specific user (scoped by user_id)
- Mark notifications as read
- Delete/dismiss notifications
- Data isolation: Users cannot access other users' notifications

Security:
- All queries include user_id filter (data isolation)
- ObjectId validation prevents injection
- Service layer enforces ownership before any operation

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List
from bson import ObjectId
from app.db.mongodb import get_database
from app.schemas.notification_schema import NotificationResponse, NotificationListResponse
import math
import logging

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Notification service with strict data isolation.
    
    CRITICAL: All methods enforce user_id filtering at query level.
    Users cannot see, read, or modify other users' notifications.
    """

    def __init__(self):
        self.collection = get_database().notifications

    async def notify(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: str,
        sender_id: Optional[str] = None,
        action_url: Optional[str] = None,
        related_resource_id: Optional[str] = None,
        related_resource_type: Optional[str] = None,
        priority: str = "normal",
        delivery_channels: Optional[dict] = None,
    ) -> str:
        """
        Create a new notification.

        Args:
            user_id: Recipient user ID
            title: Notification title
            message: Notification message
            notification_type: Type (e.g., "announcement", "complaint_update", "event")
            sender_id: Optional sender user ID (system or admin)
            action_url: Optional URL for action button
            related_resource_id: Optional related resource (complaint ID, etc.)
            related_resource_type: Optional resource type
            priority: Priority level (normal, high, urgent)
            delivery_channels: Delivery preferences

        Returns:
            str: notification_id for tracking

        Raises:
            ValueError: If user_id is invalid
        """
        try:
            # Validate user_id is valid ObjectId
            if not ObjectId.is_valid(user_id):
                raise ValueError(f"Invalid user_id format: {user_id}")

            # Generate notification_id
            count = await self.collection.count_documents({})
            notification_id = f"NOT-{datetime.utcnow().year}-{count + 1:05d}"

            # Prepare document
            notification_doc = {
                "notification_id": notification_id,
                "user_id": ObjectId(user_id),  # Store as ObjectId for efficient queries
                "notification_type": notification_type,
                "title": title,
                "message": message,
                "priority": priority,
                "is_read": False,
                "read_at": None,
                "delivery_channels": delivery_channels or {
                    "in_app": True,
                    "push": False,
                    "email": False,
                    "sms": False
                },
                "sender_id": ObjectId(sender_id) if sender_id else None,
                "action_url": action_url,
                "related_resource_id": related_resource_id,
                "related_resource_type": related_resource_type,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }

            result = await self.collection.insert_one(notification_doc)

            logger.info(
                f"Notification created: {notification_id} for user {user_id}"
            )
            return notification_id

        except ValueError as e:
            logger.error(f"Invalid input for notification: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            raise


    async def list_for_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
        is_read_filter: Optional[bool] = None,
    ) -> NotificationListResponse:
        """
        Fetch notifications for a specific user (paginated).

        CRITICAL DATA ISOLATION:
        - Query includes user_id filter at database level
        - Users can ONLY see their own notifications
        - Cannot bypass this scoping

        Args:
            user_id: The user whose notifications to retrieve
            skip: Pagination skip
            limit: Pagination limit (1-100)
            is_read_filter: Optional filter by read status

        Returns:
            NotificationListResponse with paginated items
        """
        try:
            # Build query with user_id filter (CRITICAL)
            # Accept both ObjectId and string user_id formats for compatibility
            if ObjectId.is_valid(user_id):
                query = {"user_id": {"$in": [ObjectId(user_id), user_id]}}
            else:
                query = {"user_id": user_id}
            
            # Optional read status filter
            if is_read_filter is not None:
                query["is_read"] = is_read_filter

            # Count total for pagination
            total = await self.collection.count_documents(query)
            unread_count = await self.collection.count_documents({
                **query,
                "is_read": False
            })

            # Fetch paginated results
            cursor = (
                self.collection
                .find(query)
                .skip(skip)
                .limit(limit)
                .sort("created_at", -1)
            )

            items = []
            async for doc in cursor:
                try:
                    items.append(
                        NotificationResponse(**self._normalize_doc(doc))
                    )
                except Exception as e:
                    logger.error(f"Error normalizing notification document: {e}")
                    continue

            # Calculate pagination
            page = (skip // limit) + 1 if limit else 1
            total_pages = math.ceil(total / limit) if limit else 0

            return NotificationListResponse(
                total=total,
                page=page,
                page_size=limit,
                total_pages=total_pages,
                unread_count=unread_count,
                items=items,
            )

        except Exception as e:
            logger.error(f"Error listing notifications for user {user_id}: {e}")
            raise


    async def get_by_id(
        self,
        notification_id: str,
        user_id: str,
    ) -> Optional[NotificationResponse]:
        """
        Get a specific notification by ID with ownership verification.

        CRITICAL: Query includes both notification_id AND user_id
        - Cannot retrieve another user's notification
        - Returns None if user_id doesn't match

        Args:
            notification_id: The notification ID (or _id)
            user_id: The current user's ID

        Returns:
            NotificationResponse if found and belongs to user, None otherwise
        """
        try:
            if not ObjectId.is_valid(user_id):
                logger.warning(f"Invalid user_id format: {user_id}")
                return None

            # Build query with BOTH filters (CRITICAL)
            query = {"user_id": ObjectId(user_id)}

            # Try to match by _id (ObjectId) or notification_id (string)
            if ObjectId.is_valid(notification_id):
                query["_id"] = ObjectId(notification_id)
            else:
                query["notification_id"] = notification_id

            # This query will NOT find the notification if user_id doesn't match
            doc = await self.collection.find_one(query)

            if doc:
                return NotificationResponse(**self._normalize_doc(doc))
            
            return None

        except Exception as e:
            logger.error(f"Error retrieving notification {notification_id}: {e}")
            return None


    async def mark_as_read(
        self,
        notification_id: str,
        user_id: str,
    ) -> bool:
        """
        Mark a notification as read.

        CRITICAL OWNERSHIP CHECK:
        - Query requires both user_id AND notification_id
        - Cannot mark another user's notification as read

        Args:
            notification_id: The notification ID
            user_id: The current user's ID

        Returns:
            bool: True if marked, False if not found or not owned by user
        """
        try:
            if not ObjectId.is_valid(user_id):
                logger.warning(f"Invalid user_id format: {user_id}")
                return False

            # Build query with BOTH filters (CRITICAL)
            query = {"user_id": ObjectId(user_id)}

            if ObjectId.is_valid(notification_id):
                query["_id"] = ObjectId(notification_id)
            else:
                query["notification_id"] = notification_id

            # Update only if user_id matches
            result = await self.collection.update_one(
                query,
                {
                    "$set": {
                        "is_read": True,
                        "read_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            if result.modified_count > 0:
                logger.debug(f"Notification {notification_id} marked as read for user {user_id}")
                return True

            # Not found or already read
            return False

        except Exception as e:
            logger.error(f"Error marking notification {notification_id} as read: {e}")
            return False


    async def mark_all_as_read(
        self,
        user_id: str,
    ) -> int:
        """
        Mark all unread notifications as read for a user.

        CRITICAL: Only affects notifications belonging to user_id

        Args:
            user_id: The user's ID

        Returns:
            int: Number of notifications marked as read
        """
        try:
            if not ObjectId.is_valid(user_id):
                logger.warning(f"Invalid user_id format: {user_id}")
                return 0

            # Query scoped to user_id only
            result = await self.collection.update_many(
                {
                    "user_id": ObjectId(user_id),
                    "is_read": False
                },
                {
                    "$set": {
                        "is_read": True,
                        "read_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            logger.info(f"Marked {result.modified_count} notifications as read for user {user_id}")
            return result.modified_count

        except Exception as e:
            logger.error(f"Error marking all notifications as read for user {user_id}: {e}")
            return 0


    async def delete(
        self,
        notification_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete/dismiss a notification.

        CRITICAL OWNERSHIP CHECK:
        - Query requires both user_id AND notification_id
        - Cannot delete another user's notification

        Args:
            notification_id: The notification ID
            user_id: The current user's ID

        Returns:
            bool: True if deleted, False if not found or not owned by user
        """
        try:
            if not ObjectId.is_valid(user_id):
                logger.warning(f"Invalid user_id format: {user_id}")
                return False

            # Build query with BOTH filters (CRITICAL)
            query = {"user_id": ObjectId(user_id)}

            if ObjectId.is_valid(notification_id):
                query["_id"] = ObjectId(notification_id)
            else:
                query["notification_id"] = notification_id

            # Delete only if user_id matches
            result = await self.collection.delete_one(query)

            if result.deleted_count > 0:
                logger.info(f"Notification {notification_id} deleted for user {user_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error deleting notification {notification_id}: {e}")
            return False


    async def get_notification_preferences(
        self,
        user_id: str,
    ) -> dict:
        """
        Get notification preferences for a user.

        Args:
            user_id: The user's ID

        Returns:
            dict: User's notification preferences
        """
        try:
            if not ObjectId.is_valid(user_id):
                return {}

            # Preferences stored in users collection
            db = get_database()
            user_doc = await db.users.find_one(
                {"_id": ObjectId(user_id)},
                {"notification_preferences": 1}
            )

            if user_doc:
                return user_doc.get("notification_preferences", {})

            return {}

        except Exception as e:
            logger.error(f"Error retrieving notification preferences for user {user_id}: {e}")
            return {}


    @staticmethod
    def _normalize_doc(doc: dict) -> dict:
        """
        Normalize MongoDB document for Pydantic response model.

        Converts ObjectId fields to strings, datetime to ISO format.
        """
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        
        if "user_id" in doc and isinstance(doc["user_id"], ObjectId):
            doc["user_id"] = str(doc["user_id"])
        
        if "sender_id" in doc and isinstance(doc["sender_id"], ObjectId):
            doc["sender_id"] = str(doc["sender_id"])
        
        if isinstance(doc.get("created_at"), datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        
        if isinstance(doc.get("read_at"), datetime) and doc.get("read_at"):
            doc["read_at"] = doc["read_at"].isoformat()
        
        if isinstance(doc.get("updated_at"), datetime):
            doc["updated_at"] = doc["updated_at"].isoformat()
        
        return doc
