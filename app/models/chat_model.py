"""
Chat Model Module
=================
Defines enums and helpers for the chat and messaging system.
Also contains chat-specific MongoDB index creation.

Author: Political Communication Platform Team
"""

from enum import Enum
import logging
from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.errors import OperationFailure

logger = logging.getLogger(__name__)


class ChatType(str, Enum):
    """Types of chats"""
    DIRECT = "direct"
    BROADCAST = "broadcast"


class MessageStatus(str, Enum):
    """Delivery/read status for messages"""
    SENT = "sent"
    DELIVERED = "delivered"
    SEEN = "seen"


class ReactionType(str, Enum):
    """Supported reaction types"""
    LIKE = "like"
    LOVE = "love"
    LAUGH = "laugh"
    WOW = "wow"
    SAD = "sad"
    ANGRY = "angry"
    EMOJI = "emoji"


class SharePlatform(str, Enum):
    """Supported share platforms"""
    WHATSAPP = "whatsapp"
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    TELEGRAM = "telegram"
    SMS = "sms"
    EMAIL = "email"
    COPY_LINK = "copy_link"
    OTHER = "other"


class MessageSentiment(str, Enum):
    """Sentiment classification for feedback"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


async def create_chat_indexes(db) -> None:
    """
    Create chat-specific indexes for chats and messages collections.
    Called during application startup.
    """
    try:
        # ====================
        # CHATS COLLECTION
        # ====================
        await db.chats.create_index([("chat_type", ASCENDING)])
        await db.chats.create_index([("participants", ASCENDING)])
        await db.chats.create_index([("created_by", ASCENDING)])
        await db.chats.create_index([("last_message_at", DESCENDING)])
        await db.chats.create_index([("is_active", ASCENDING)])
        await db.chats.create_index([("broadcast_to", ASCENDING)])

        logger.info("? Chats collection indexes created")

        # ====================
        # MESSAGES COLLECTION
        # ====================
        await db.messages.create_index([("chat_id", ASCENDING)])
        await db.messages.create_index([("sender_id", ASCENDING)])
        await db.messages.create_index([("created_at", DESCENDING)])
        await db.messages.create_index([("status", ASCENDING)])
        await db.messages.create_index([("is_deleted", ASCENDING)])
        await db.messages.create_index([("deleted_for_users", ASCENDING)])

        # Embedded arrays for analytics/filters
        await db.messages.create_index([("reactions.user_id", ASCENDING)])
        await db.messages.create_index([("share_logs.user_id", ASCENDING)])
        await db.messages.create_index([("feedback.user_id", ASCENDING)])
        await db.messages.create_index([("feedback.sentiment", ASCENDING)])
        await db.messages.create_index([("feedback.rating", DESCENDING)])

        # Text search on content
        try:
            await db.messages.create_index(
                [("content", TEXT)],
                name="message_text_search",
            )
        except OperationFailure as exc:
            if getattr(exc, "code", None) == 85 or "IndexOptionsConflict" in str(exc):
                logger.info("✓ Messages text index already exists; skipping")
            else:
                raise

        logger.info("? Messages collection indexes created")
        logger.info("? Chat indexes created successfully")

    except Exception as exc:
        logger.error(f"? Error creating chat indexes: {exc}")
        raise
