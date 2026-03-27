"""
Event Service
=============
Handles events, campaigns, and participation tracking with leader assignment and metrics.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List, Dict
from bson import ObjectId
from app.db.mongodb import get_database
from app.schemas.event_schema import (
    EventCreate,
    EventResponse,
    EventListResponse,
    EventUpdateRequest,
    EventStatusUpdateRequest,
)
from app.api.dependencies import CurrentUser
from app.core.roles import UserRole
from app.utils.enums import EventStatus, EventType
import math


class EventService:
    """Event business logic with validation, leader assignment, and metrics"""

    def __init__(self):
        self.collection = get_database().events
        self.users_collection = get_database().users

    async def create(
        self, payload: EventCreate, user: CurrentUser
    ) -> EventResponse:
        """
        Create an event with MANDATORY validations.
        
        CRITICAL VALIDATIONS:
        - Title: 5-300 chars (Pydantic validates)
        - Description: 10-3000 chars (Pydantic validates)
        - Type: EventType enum enforced
        - Location: state + city required
        - Date: must be future date
        """
        # VALIDATE: Event date must be in future
        now = datetime.utcnow()
        if payload.event_date <= now:
            raise ValueError("Event date must be in the future")
        
        # VALIDATE: Location must have state and city
        if not payload.location:
            raise ValueError("Event location must include state and city")
        if isinstance(payload.location, dict):
            if not payload.location.get("state") or not payload.location.get("city"):
                raise ValueError("Event location must include state and city")
        else:
            if not getattr(payload.location, "state", None) or not getattr(payload.location, "city", None):
                raise ValueError("Event location must include state and city")
        
        # Generate unique event_id
        count = await self.collection.count_documents({})
        event_id = f"EVT-{datetime.utcnow().year}-{count + 1:04d}"
        
        doc = {
            "event_id": event_id,
            "title": payload.title,
            "description": payload.description,
            "event_type": payload.event_type.value if isinstance(payload.event_type, EventType) else payload.event_type,
            "created_by": user.user_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            
            # Scheduling
            "event_date": payload.event_date,
            "end_date": payload.end_date,
            "duration_hours": payload.duration_hours,
            
            # Location
            "location": payload.location.dict() if hasattr(payload.location, 'dict') else payload.location,
            "venue_name": payload.venue_name,
            "venue_address": payload.venue_address,
            
            # Status
            "status": EventStatus.SCHEDULED.value,
            "status_updated_at": datetime.utcnow(),
            
            # Management
            "assigned_leaders": [],  # Empty initially
            "estimated_attendees": payload.estimated_attendees,
            "max_capacity": payload.max_capacity,
            
            # Content
            "agenda": payload.agenda or [],
            "speakers": payload.speakers or [],
            
            # Media
            "banner_url": payload.banner_url,
            "poster_url": payload.poster_url,
            "document_urls": payload.document_urls or [],
            "media_urls": payload.media_urls or [],
            
            # Participation
            "registrations": [],
            "registration_open": True,
            "registration_deadline": payload.registration_deadline,
            
            # Visibility
            "is_public": True if user.role == UserRole.CORPORATOR else payload.is_public,
            "is_featured": False,
            "visibility_level": "public",
            
            # Metadata
            "tags": payload.tags or [],
            "hashtags": payload.hashtags or [],
            "priority": 0,
            "content_language": getattr(payload, "content_language", None),
            
            # Metrics (private)
            "actual_attendees": 0,
            "participation_rate": 0.0,
            "actual_expense": None,
        }
        
        result = await self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        
        return EventResponse(**self._normalize_doc(doc))

    async def assign_leader(
        self, event_id: str, leader_id: str, user: CurrentUser
    ) -> bool:
        """
        Assign a leader to an event.
        
        CRITICAL:
        - Only corporator or event creator can assign
        - Leader must exist
        - Leader role must be validated
        """
        # VALIDATE: User is corporator or event creator
        event = await self.collection.find_one({"event_id": event_id})
        if not event:
            raise ValueError("Event not found")
        
        if user.role.value != UserRole.CORPORATOR.value and event["created_by"] != user.user_id:
            raise ValueError("Only corporator or event creator can assign leaders")
        
        # VALIDATE: Leader exists
        leader = await self.users_collection.find_one(
            {"_id": ObjectId(leader_id), "role": UserRole.LEADER.value}
        )
        if not leader:
            raise ValueError("Leader not found or user is not a leader")
        
        # ASSIGN: Add leader to assigned_leaders list (no duplicates)
        result = await self.collection.update_one(
            {"event_id": event_id},
            {"$addToSet": {"assigned_leaders": leader_id}},
        )
        
        return result.modified_count == 1

    async def reassign_leader(
        self, event_id: str, old_leader_id: str, new_leader_id: str, user: CurrentUser
    ) -> bool:
        """
        Reassign a leader to another leader.
        
        CRITICAL:
        - Remove old leader
        - Assign new leader
        - Track leadership changes
        """
        # VALIDATE: Event exists
        event = await self.collection.find_one({"event_id": event_id})
        if not event:
            raise ValueError("Event not found")
        
        # VALIDATE: User is corporator or event creator
        if user.role.value != UserRole.CORPORATOR.value and event["created_by"] != user.user_id:
            raise ValueError("Only corporator or event creator can reassign leaders")
        
        # VALIDATE: New leader exists
        leader = await self.users_collection.find_one(
            {"_id": ObjectId(new_leader_id), "role": UserRole.LEADER.value}
        )
        if not leader:
            raise ValueError("New leader not found or user is not a leader")
        
        # REASSIGN: Remove old, add new
        result = await self.collection.update_one(
            {"event_id": event_id},
            {
                "$pull": {"assigned_leaders": old_leader_id},
                "$addToSet": {"assigned_leaders": new_leader_id},
            },
        )
        
        return result.modified_count == 1

    async def remove_leader(
        self, event_id: str, leader_id: str, user: CurrentUser
    ) -> bool:
        """Remove a leader from an event."""
        # VALIDATE: Event exists
        event = await self.collection.find_one({"event_id": event_id})
        if not event:
            raise ValueError("Event not found")
        
        # VALIDATE: User is corporator or event creator
        if user.role.value != UserRole.CORPORATOR.value and event["created_by"] != user.user_id:
            raise ValueError("Only corporator or event creator can remove leaders")
        
        result = await self.collection.update_one(
            {"event_id": event_id},
            {"$pull": {"assigned_leaders": leader_id}},
        )
        
        return result.modified_count == 1

    async def register_participant(
        self, event_id: str, user_id: str
    ) -> bool:
        """
        Register a participant for an event.
        
        CRITICAL:
        - Check registration is open
        - Check not already registered
        - Track registration timestamp
        """
        event = await self.collection.find_one({"event_id": event_id})
        if not event and ObjectId.is_valid(event_id):
            event = await self.collection.find_one({"_id": ObjectId(event_id)})
        if not event:
            raise ValueError("Event not found")

        now = datetime.utcnow()

        # Do not allow registration for cancelled events
        if event.get("status") == EventStatus.CANCELLED.value:
            raise ValueError("Registration is closed for this event")

        # Enforce registration deadline if provided
        deadline = event.get("registration_deadline")
        if isinstance(deadline, datetime) and now > deadline:
            raise ValueError("Registration is closed for this event")

        # Enforce max capacity if set
        registrations = event.get("registrations", [])
        max_capacity = event.get("max_capacity")
        if isinstance(max_capacity, int) and max_capacity > 0:
            if len(registrations) >= max_capacity:
                raise ValueError("Event is at full capacity")

        # If registration_open is explicitly False, respect it unless we can safely reopen
        if event.get("registration_open") is False:
            reopen_allowed = False
            if isinstance(deadline, datetime) and now <= deadline:
                reopen_allowed = True
            else:
                event_date = event.get("event_date")
                if isinstance(event_date, datetime) and event_date > now:
                    # No deadline set but event is in the future → allow reopening
                    reopen_allowed = True
            if reopen_allowed:
                await self.collection.update_one(
                    {"event_id": event.get("event_id")},
                    {"$set": {"registration_open": True, "updated_at": now}},
                )
            else:
                raise ValueError("Registration is closed for this event")

        # If already registered, treat as success (idempotent)
        for registration in registrations:
            if registration.get("user_id") == user_id:
                return True
        
        # Add registration
        result = await self.collection.update_one(
            {"event_id": event_id},
            {
                "$push": {
                    "registrations": {
                        "user_id": user_id,
                        "registered_at": datetime.utcnow(),
                        "attended": False,
                    }
                }
            },
        )
        
        return result.matched_count == 1

    async def mark_attendance(
        self, event_id: str, user_id: str, attended: bool = True
    ) -> bool:
        """
        Mark participant as attended/not attended.
        
        CRITICAL:
        - Update attendance status
        - Recalculate participation metrics
        """
        event = await self.collection.find_one({"event_id": event_id})
        if not event:
            raise ValueError("Event not found")

        prior_attended = None
        for registration in event.get("registrations", []):
            if registration.get("user_id") == user_id:
                prior_attended = registration.get("attended", False)
                break

        result = await self.collection.update_one(
            {"event_id": event_id, "registrations.user_id": user_id},
            {"$set": {"registrations.$.attended": attended}},
        )
        
        if result.modified_count > 0:
            # Recalculate metrics
            await self._recalculate_metrics(event_id)
            await self._track_leader_event_participation(user_id, prior_attended, attended)
        
        return result.modified_count == 1

    async def _recalculate_metrics(self, event_id: str) -> None:
        """
        Recalculate participation metrics.
        
        CRITICAL METRICS:
        - Total registrations
        - Actual attendees
        - Participation rate (attended / registered)
        """
        event = await self.collection.find_one({"event_id": event_id})
        if not event:
            return
        
        registrations = event.get("registrations", [])
        total_registered = len(registrations)
        attended = sum(1 for r in registrations if r.get("attended", False))
        
        participation_rate = (attended / total_registered * 100) if total_registered > 0 else 0.0
        
        await self.collection.update_one(
            {"event_id": event_id},
            {
                "$set": {
                    "actual_attendees": attended,
                    "participation_rate": participation_rate,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    async def _track_leader_event_participation(
        self,
        user_id: str,
        prior_attended: Optional[bool],
        attended: bool,
    ) -> None:
        if not ObjectId.is_valid(user_id):
            return
        user = await self.users_collection.find_one(
            {"_id": ObjectId(user_id), "role": UserRole.LEADER.value}
        )
        if not user:
            return
        if prior_attended is False and attended is True:
            await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"performance.events_participated": 1}},
            )
        if prior_attended is True and attended is False:
            await self.users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"performance.events_participated": -1}},
            )

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        event_type: Optional[str] = None,
        user_role: Optional[str] = None,
        user_id: Optional[str] = None,
        user_location: Optional[dict] = None,
        user_language: Optional[str] = None,
    ) -> EventListResponse:
        """
        List events with filtering.
        
        CRITICAL FILTERS:
        - Public events visible to all
        - Leaders see assigned events
        - Corporator sees all
        """
        query = {}
        
        # Status filter
        if status:
            try:
                query["status"] = EventStatus(status).value
            except ValueError:
                pass

        # Event type filter
        if event_type:
            try:
                query["event_type"] = EventType(event_type).value
            except ValueError:
                pass
        
        # Role-based visibility
        if user_role == UserRole.LEADER.value and user_id:
            # Leaders see: public events + events they're assigned to
            query = {
                "$and": [
                    query,
                    {
                        "$or": [
                            {"is_public": True},
                            {"assigned_leaders": user_id},
                        ]
                    },
                ]
            }
        elif user_role == UserRole.VOTER.value:
            # Voters see: public events only
            query["is_public"] = True
        
        # Calculate skip
        skip = (page - 1) * page_size
        
        # Get total count
        total = await self.collection.count_documents(query)
        
        # Get paginated items
        cursor = self.collection.find(query).sort("event_date", 1).skip(skip).limit(page_size)
        
        items = []
        async for doc in cursor:
            summary = await self._registration_summary(doc.get("registrations", []), user_id)
            doc.update(summary)
            items.append(EventResponse(**self._normalize_doc(doc)))
        
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0
        
        return EventListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        )

    async def get_by_id(self, event_id: str, user_role: str, user_id: str) -> EventResponse:
        """Get event by ID with visibility checks."""
        event = await self.collection.find_one({"event_id": event_id})
        if not event:
            raise ValueError("Event not found")
        
        if user_role == UserRole.VOTER.value and not event.get("is_public", True):
            raise ValueError("Event not accessible")
        if user_role == UserRole.LEADER.value:
            if not event.get("is_public", True) and user_id not in event.get("assigned_leaders", []):
                raise ValueError("Event not accessible")
        
        summary = await self._registration_summary(event.get("registrations", []), user_id)
        event.update(summary)
        return EventResponse(**self._normalize_doc(event))

    @staticmethod
    def _matches_location(event_location: dict, user_location: dict) -> bool:
        if not event_location or not user_location:
            return True
        for key in ("state", "city", "ward", "area"):
            event_val = (event_location.get(key) or "").lower()
            user_val = (user_location.get(key) or "").lower()
            if event_val and event_val != user_val:
                return False
        return True

    async def _registration_summary(self, registrations: list, user_id: Optional[str]) -> Dict[str, object]:
        user_ids = [r.get("user_id") for r in registrations if r.get("user_id")]
        is_registered = bool(user_id and user_id in user_ids)
        role_counts = {
            UserRole.VOTER.value: 0,
            UserRole.LEADER.value: 0,
        }

        object_ids = [ObjectId(uid) for uid in user_ids if ObjectId.is_valid(uid)]
        if object_ids:
            cursor = self.users_collection.find({"_id": {"$in": object_ids}}, {"role": 1})
            async for user in cursor:
                role = user.get("role")
                if role in role_counts:
                    role_counts[role] += 1

        registrations_count = role_counts[UserRole.VOTER.value] + role_counts[UserRole.LEADER.value]
        return {
            "registrations_count": registrations_count,
            "registrations_by_role": role_counts,
            "is_registered": is_registered,
        }

    async def update(
        self, event_id: str, payload: EventUpdateRequest, user: CurrentUser
    ) -> EventResponse:
        """Update an event (creator or corporator)."""
        event = await self.collection.find_one({"event_id": event_id})
        if not event:
            raise ValueError("Event not found")
        
        if user.role.value != UserRole.CORPORATOR.value and event.get("created_by") != user.user_id:
            raise ValueError("Only corporator or creator can update event")
        
        update_doc = {"updated_at": datetime.utcnow()}
        for field in (
            "title", "description", "event_date", "end_date", "venue_name",
            "venue_address", "speakers", "agenda", "estimated_attendees", "organizer_notes"
        ):
            value = getattr(payload, field, None)
            if value is not None:
                update_doc[field] = value
        
        result = await self.collection.find_one_and_update(
            {"event_id": event_id},
            {"$set": update_doc},
            return_document=True,
        )
        return EventResponse(**self._normalize_doc(result))

    async def update_status(
        self, event_id: str, payload: EventStatusUpdateRequest, user: CurrentUser
    ) -> EventResponse:
        """Update event status (creator or corporator)."""
        event = await self.collection.find_one({"event_id": event_id})
        if not event:
            raise ValueError("Event not found")

        if user.role.value != UserRole.CORPORATOR.value and event.get("created_by") != user.user_id:
            raise ValueError("Only corporator or creator can update event status")

        status_value = payload.status.value if hasattr(payload.status, "value") else payload.status

        update_doc = {
            "status": status_value,
            "status_updated_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

        if status_value == EventStatus.POSTPONED.value:
            if payload.postponed_to:
                update_doc["postponed_to"] = payload.postponed_to
                update_doc["event_date"] = payload.postponed_to
            if payload.reason:
                update_doc["postponement_reason"] = payload.reason
        elif status_value == EventStatus.SCHEDULED.value:
            update_doc["postponed_to"] = None
            update_doc["postponement_reason"] = None

        result = await self.collection.find_one_and_update(
            {"event_id": event_id},
            {"$set": update_doc},
            return_document=True,
        )
        return EventResponse(**self._normalize_doc(result))

    async def delete(self, event_id: str, user: CurrentUser) -> None:
        """Soft delete event (set status to cancelled)."""
        event = await self.collection.find_one({"event_id": event_id})
        if not event:
            raise ValueError("Event not found")
        if user.role.value != UserRole.CORPORATOR.value and event.get("created_by") != user.user_id:
            raise ValueError("Only corporator or creator can delete event")
        
        await self.collection.update_one(
            {"event_id": event_id},
            {"$set": {
                "status": EventStatus.CANCELLED.value,
                "status_updated_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }}
        )

    async def get_metrics(self, event_id: str) -> dict:
        """
        Get participation and engagement metrics for an event.
        
        RETURNS:
        - Total registrations
        - Actual attendees
        - Participation rate
        - Leadership assignments
        """
        event = await self.collection.find_one({"event_id": event_id})
        if not event:
            raise ValueError("Event not found")
        
        registrations = event.get("registrations", [])
        assigned_leaders = event.get("assigned_leaders", [])
        
        return {
            "event_id": event_id,
            "title": event.get("title"),
            "total_registrations": len(registrations),
            "actual_attendees": event.get("actual_attendees", 0),
            "participation_rate": event.get("participation_rate", 0.0),
            "reach": len(registrations),
            "engagement_score": event.get("participation_rate", 0.0),
            "assigned_leaders_count": len(assigned_leaders),
            "event_status": event.get("status"),
        }

    @staticmethod
    def _normalize_doc(doc: dict) -> dict:
        """Normalize Mongo document for response."""
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        for key in ("event_date", "end_date", "created_at", "updated_at", "status_updated_at", "registration_deadline"):
            value = doc.get(key)
            if isinstance(value, datetime):
                doc[key] = value.isoformat()
        return doc
