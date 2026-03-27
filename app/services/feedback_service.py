"""
Feedback Service
================
Handles structured feedback and sentiment capture with proper data isolation.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional
from bson import ObjectId
from app.db.mongodb import get_database
from app.schemas.feedback_schema import (
    FeedbackCreate,
    FeedbackResponse,
    FeedbackListResponse,
)
from app.api.dependencies import CurrentUser
from app.utils.sentiment import analyze_sentiment, extract_keywords
import math
import logging

logger = logging.getLogger(__name__)


class FeedbackService:
    """Feedback logic with data isolation"""

    def __init__(self):
        self.collection = get_database().feedback

    async def submit(
        self, payload: FeedbackCreate, user: CurrentUser
    ) -> FeedbackResponse:
        """Submit feedback (Voter/Leader)."""
        count = await self.collection.count_documents({})
        feedback_id = f"FB-{datetime.utcnow().year}-{count + 1:04d}"
        sentiment = analyze_sentiment(payload.content).value
        keywords = extract_keywords(payload.content)
        
        doc = {
            **payload.dict(),
            "feedback_id": feedback_id,
            "created_by": user.user_id,
            "created_at": datetime.utcnow(),
            "sentiment": sentiment,
            "keywords": keywords,
            "is_reviewed": False,
        }
        
        result = await self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        
        logger.info(f"Feedback created: {feedback_id} by user {user.user_id}")
        return FeedbackResponse(**self._normalize_doc(doc))

    async def list_all(self, page: int, page_size: int) -> FeedbackListResponse:
        """
        List all feedback for corporator/ops oversight.
        
        Access: Corporator, OPS only
        """
        skip = (page - 1) * page_size
        cursor = self.collection.find({}).sort("created_at", -1).skip(skip).limit(page_size)
        items = []
        async for doc in cursor:
            items.append(FeedbackResponse(**self._normalize_doc(doc)))
        
        total = await self.collection.count_documents({})
        total_pages = math.ceil(total / page_size) if page_size else 0
        
        return FeedbackListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        )

    async def list_for_user(
        self, user_id: str, page: int, page_size: int
    ) -> FeedbackListResponse:
        """
        List feedback created by a specific user.
        
        VOTER DATA ISOLATION:
        - Users can only view their own feedback
        - Query includes user_id filter at database level
        - Cannot be bypassed by client manipulation
        
        Access: User viewing own feedback
        """
        # Validate user_id format
        if not ObjectId.is_valid(user_id):
            logger.warning(f"Invalid user_id format in list_for_user: {user_id}")
            return FeedbackListResponse(
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0,
                items=[],
            )
        
        skip = (page - 1) * page_size
        # CRITICAL: Scope query by user_id - cannot be bypassed
        query = {"created_by": user_id}
        
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)
        items = []
        async for doc in cursor:
            items.append(FeedbackResponse(**self._normalize_doc(doc)))
        
        total = await self.collection.count_documents(query)
        total_pages = math.ceil(total / page_size) if page_size else 0

        logger.debug(f"Listed {len(items)} feedback items for user {user_id}")
        
        return FeedbackListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        )

    async def get_by_id(self, feedback_id: str, user_id: str) -> FeedbackResponse:
        """
        Get specific feedback by ID with ownership verification.
        
        VOTER DATA ISOLATION:
        - Users can only view their own feedback
        - Ownership verified at query level
        """
        query = {}
        
        # Match by _id or feedback_id
        if ObjectId.is_valid(feedback_id):
            query = {"$or": [
                {"_id": ObjectId(feedback_id), "created_by": user_id},
                {"feedback_id": feedback_id, "created_by": user_id}
            ]}
        else:
            query = {"feedback_id": feedback_id, "created_by": user_id}
        
        doc = await self.collection.find_one(query)
        
        if not doc:
            logger.warning(
                f"Unauthorized feedback access attempt: user {user_id} "
                f"tried to access feedback {feedback_id}"
            )
            raise ValueError("Feedback not found")
        
        return FeedbackResponse(**self._normalize_doc(doc))

    @staticmethod
    def _normalize_doc(doc: dict) -> dict:
        """Normalize Mongo document for Pydantic response."""
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("created_at"), datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        return doc