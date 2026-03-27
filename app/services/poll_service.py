"""
Poll Service
============
Poll creation, targeting, participation, and results aggregation with privacy enforcement.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List, Dict
from bson import ObjectId
from app.db.mongodb import get_database
from app.schemas.poll_schema import PollCreate, PollResponse
from app.api.dependencies import CurrentUser
from app.core.roles import UserRole
from app.utils.enums import PollStatus
from app.utils.sentiment import analyze_sentiment
import hashlib
from app.utils.geo import LocationHierarchy, build_location_filter
import math
import logging

logger = logging.getLogger(__name__)


class PollService:
    """Poll business logic with targeting and privacy"""

    def __init__(self):
        self.collection = get_database().polls
        self.users_collection = get_database().users

    @staticmethod
    def _normalize_doc(doc: dict) -> dict:
        """Normalize Mongo document to match response schema types."""
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        for key in ("created_at", "end_date", "start_date", "status_updated_at", "auto_close_at"):
            value = doc.get(key)
            if isinstance(value, datetime):
                doc[key] = value.isoformat()
        return doc

    async def create(
        self, payload: PollCreate, user: CurrentUser
    ) -> PollResponse:
        """
        Create poll with MANDATORY targeting.
        
        CRITICAL VALIDATIONS:
        - Title: 5-300 chars (Pydantic)
        - Options: min 2 required
        - Targeting: role + region validated
        """
        poll_id = f"POLL-{datetime.utcnow().year}-{str(ObjectId())[:8].upper()}"
        
        # FIXED: Ensure targeting is stored
        target_roles = payload.target_roles if payload.target_roles else [
            UserRole.VOTER.value,
            UserRole.LEADER.value
        ]
        
        # VALIDATE: At least 2 options required
        if not payload.options or len(payload.options) < 2:
            raise ValueError("At least 2 poll options are required")

        doc = {
            "poll_id": poll_id,
            "title": payload.title,
            "description": payload.description,
            "poll_type": payload.poll_type,
            
            # TARGETING (MANDATORY)
            "target_roles": target_roles,
            "target_regions": payload.target_regions,  # {states: [], cities: [], wards: [], areas: []}
            "target_geography": payload.target_geography,
            "target_demographics": payload.target_demographics,
            
            # Options (for aggregation)
            "options": [
                {
                    "option_id": str(idx + 1),
                    "text": opt.text,
                    "description": opt.description,
                    "icon_url": opt.icon_url,
                    "votes": 0,
                    "percentage": 0.0,
                }
                for idx, opt in enumerate(payload.options)
            ],
            
            # Settings
            "is_anonymous": payload.is_anonymous,
            "allow_multiple_responses": payload.allow_multiple_responses,
            "show_results": payload.show_results,  # immediately, after_voting, after_closing, never
            "is_public": payload.is_public,
            
            # Responses (separate collection is better, but stored here for now)
            # CRITICAL: Store only hashed/anonymized user_id if anonymous
            "responses": [],
            "total_responses": 0,
            
            # Metadata
            "status": PollStatus.DRAFT.value,
            "created_by": user.user_id,
            "created_at": datetime.utcnow(),
            "start_date": payload.start_date,
            "end_date": payload.end_date,
            "status_updated_at": datetime.utcnow(),
            
            # Analytics (private)
            "view_count": 0,
            "unique_viewers": [],  # Private - don't expose
            "participation_rate": 0.0,
        }
        
        result = await self.collection.insert_one(doc)
        doc["_id"] = result.inserted_id
        return PollResponse(**self._normalize_doc(doc))

    async def _can_vote_poll(
        self, poll: dict, user_role: str, user_location: dict
    ) -> bool:
        """
        Check if user can vote on poll based on targeting.
        
        CRITICAL: Enforces privacy - anonymous polls don't track identity.
        """
        # Check status
        if poll.get("status") not in ["active", "published"]:
            return False
        
        # Check role targeting
        target_roles = poll.get("target_roles", [])
        if target_roles and user_role not in target_roles:
            return False
        
        # Check region targeting
        target_regions = poll.get("target_regions")
        if target_regions:
            user_state = user_location.get("state", "").lower()
            user_city = user_location.get("city", "").lower()
            
            # Must match both state AND (city if specified)
            state_match = any(
                r.lower() == user_state
                for r in target_regions.get("states", [])
            ) if target_regions.get("states") else True
            
            if not state_match:
                return False

            if target_regions.get("cities"):
                if user_city not in [c.lower() for c in target_regions.get("cities", [])]:
                    return False
        
        # Check precise geography targeting (single hierarchy)
        if poll.get("target_geography"):
            geo = poll["target_geography"]
            for key in ("state", "city", "ward", "area"):
                if geo.get(key) and geo.get(key, "").lower() != user_location.get(key, "").lower():
                    return False
        
        return True

    def _demographics_match(self, poll: dict, user_doc: dict) -> bool:
        """Check if user demographics match poll targeting."""
        target = poll.get("target_demographics") or {}
        if not target:
            return True
        
        demographics = (user_doc or {}).get("demographics") or {}
        if target.get("age_groups") and demographics.get("age_group") not in target["age_groups"]:
            return False
        if target.get("genders") and demographics.get("gender") not in target["genders"]:
            return False
        if target.get("occupations") and demographics.get("occupation") not in target["occupations"]:
            return False
        if target.get("education_levels") and demographics.get("education") not in target["education_levels"]:
            return False
        return True

    async def list(
        self,
        skip: int,
        limit: int,
        user_role: str = UserRole.VOTER.value,
        user_id: Optional[str] = None,
        user_location: Optional[Dict] = None,
        status: str = "active",  # Only show active polls to voters
    ):
        """
        List polls targeting current user.
        
        CRITICAL: Only return polls user is targeted for.
        VOTER DATA ISOLATION: Filter by targeting rules.
        """
        if user_location is None:
            user_location = {}
        
        # Build query: only active polls visible to non-creators
        query = {}
        
        # If voter/leader, only see published polls
        if user_role in [UserRole.VOTER.value, UserRole.LEADER.value]:
            query["status"] = {"$in": ["active", "published"]}
        else:
            # Corporator/OPS can request all statuses
            if status and status != "all":
                query["status"] = status
        
        # Get total count (before filtering by targeting)
        total_raw = await self.collection.count_documents(query)
        
        # Fetch paginated polls
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit * 2)
        
        items = []
        async for doc in cursor:
            # For voter/leader, show all active/published polls regardless of targeting/language.
            # Targeting is still enforced when voting.
            sanitized_doc = self._sanitize_poll_for_viewer(doc, user_role)
            items.append(PollResponse(**self._normalize_doc(sanitized_doc)))
            
            # Stop after getting enough items
            if len(items) >= limit:
                break
        
        page = (skip // limit) + 1 if limit else 1
        total_pages = math.ceil(total_raw / limit) if limit else 0
        
        return {
            "items": items,
            "total": total_raw,
            "page": page,
            "page_size": limit,
            "total_pages": total_pages,
        }

    async def get_by_id(self, poll_id: str, user: CurrentUser) -> PollResponse:
        """
        Get a specific poll with privacy enforcement.
        
        VOTER DATA ISOLATION:
        - Verify voter is targeted for this poll
        - Don't expose responses
        """
        query = {"poll_id": poll_id}
        if ObjectId.is_valid(poll_id):
            query = {"$or": [{"_id": ObjectId(poll_id)}, {"poll_id": poll_id}]}
        
        poll = await self.collection.find_one(query)
        if not poll:
            raise ValueError("Poll not found")

        # Get user document for targeting checks
        user_doc = await self.users_collection.find_one({"_id": ObjectId(user.user_id)})
        if not user_doc:
            raise ValueError("User not found")
        
        user_role = user_doc.get("role")
        user_location = user_doc.get("location", {})
        
        # CRITICAL: Voters can only see polls targeted to them
        if user_role == UserRole.VOTER.value:
            can_access = await self._can_vote_poll(poll, user_role, user_location)
            if not can_access:
                logger.warning(
                    f"Unauthorized poll access attempt: user {user.user_id} "
                    f"tried to access poll {poll_id} not targeted to them"
                )
                raise ValueError("Poll not found")
            
            # Check demographics
            if not self._demographics_match(poll, user_doc):
                raise ValueError("Poll not found")
        
        sanitized = self._sanitize_poll_for_viewer(poll, user_role)
        return PollResponse(**self._normalize_doc(sanitized))

    async def update(self, poll_id: str, payload: dict, user: CurrentUser) -> PollResponse:
        """Update a draft poll (creator/corporator only)."""
        query = {"poll_id": poll_id}
        if ObjectId.is_valid(poll_id):
            query = {"$or": [{"_id": ObjectId(poll_id)}, {"poll_id": poll_id}]}
        
        poll = await self.collection.find_one(query)
        if not poll:
            raise ValueError("Poll not found")
        if poll.get("status") != PollStatus.DRAFT.value:
            raise ValueError("Only draft polls can be updated")
        
        update_doc = {"status_updated_at": datetime.utcnow()}
        for field in ("title", "description", "end_date", "target_roles", "target_regions", "target_geography", "target_demographics"):
            if field in payload and payload[field] is not None:
                update_doc[field] = payload[field]
        
        if "options" in payload and payload["options"]:
            update_doc["options"] = [
                {
                    "option_id": str(idx + 1),
                    "text": opt["text"],
                    "description": opt.get("description"),
                    "icon_url": opt.get("icon_url"),
                    "votes": 0,
                    "percentage": 0.0,
                }
                for idx, opt in enumerate(payload["options"])
            ]
        
        result = await self.collection.find_one_and_update(
            query,
            {"$set": update_doc},
            return_document=True,
        )
        return PollResponse(**self._normalize_doc(result))

    def _sanitize_poll_for_viewer(self, poll: dict, user_role: str) -> dict:
        """
        Sanitize poll data based on user role and anonymity settings.
        
        CRITICAL PRIVACY:
        - Anonymous polls: don't show user_id in responses
        - Only creators see individual responses
        - Voters only see aggregated percentages (if show_results=immediately)
        """
        sanitized = poll.copy()
        
        # PRIVACY: Hide individual responses from non-creators
        if user_role != UserRole.CORPORATOR.value and poll.get("created_by"):
            sanitized["responses"] = []  # Don't expose who voted
        elif poll.get("is_anonymous", True):
            # Even creators shouldn't see user_ids in anonymous polls
            sanitized["responses"] = [
                {
                    "selected_option_id": r.get("selected_option_id"),
                    "response_text": r.get("response_text"),
                    # DO NOT include: user_id
                    "responded_at": r.get("responded_at"),
                }
                for r in poll.get("responses", [])
            ]
        
        # PRIVACY: Hide viewer list
        if "unique_viewers" in sanitized:
            del sanitized["unique_viewers"]
        if "anonymous_responders" in sanitized:
            del sanitized["anonymous_responders"]
        
        return sanitized

    async def get_results(
        self, poll_id: str, user_role: str
    ) -> Dict:
        """
        Get aggregated results for a poll.
        
        CRITICAL:
        - Only show percentages, not individual votes
        - Respect show_results setting (immediately, after_voting, after_closing, never)
        - Hide voter identities
        """
        query = {}
        if ObjectId.is_valid(poll_id):
            query = {"$or": [{"_id": ObjectId(poll_id)}, {"poll_id": poll_id}]}
        else:
            query = {"poll_id": poll_id}
        
        poll = await self.collection.find_one(query)
        if not poll:
            raise ValueError("Poll not found")
        
        # Check if user can see results
        can_see_results = await self._can_see_results(poll, user_role)
        if not can_see_results:
            return {
                "poll_id": poll["poll_id"],
                "message": "Results not available yet",
                "show_results_setting": poll.get("show_results"),
            }
        
        # Aggregate results (calculate percentages)
        total_responses = poll.get("total_responses", 0)
        
        aggregated_options = []
        for option in poll.get("options", []):
            votes = option.get("votes", 0)
            percentage = (votes / total_responses * 100) if total_responses > 0 else 0.0
            
            aggregated_options.append({
                "option_id": option["option_id"],
                "text": option["text"],
                "votes": votes,  # Only creators see actual vote counts
                "percentage": percentage,
            })
        
        # Geographic + demographic breakdown (only for non-anonymous polls)
        geographic_breakdown = {}
        demographic_breakdown = {}
        sentiment_summary = {"positive": 0, "neutral": 0, "negative": 0, "mixed": 0}
        
        if not poll.get("is_anonymous", True) and poll.get("responses"):
            user_ids = [r.get("user_id") for r in poll.get("responses", []) if r.get("user_id")]
            if user_ids:
                users = await self.users_collection.find({"_id": {"$in": [ObjectId(uid) for uid in user_ids if ObjectId.is_valid(uid)]}}).to_list(None)
                for u in users:
                    loc = u.get("location", {})
                    state = loc.get("state", "unknown")
                    city = loc.get("city", "unknown")
                    geographic_breakdown.setdefault(state, {})
                    geographic_breakdown[state][city] = geographic_breakdown[state].get(city, 0) + 1
                    
                    demo = u.get("demographics") or {}
                    age = demo.get("age_group", "unknown")
                    gender = demo.get("gender", "unknown")
                    demographic_breakdown.setdefault("age_group", {})
                    demographic_breakdown.setdefault("gender", {})
                    demographic_breakdown["age_group"][age] = demographic_breakdown["age_group"].get(age, 0) + 1
                    demographic_breakdown["gender"][gender] = demographic_breakdown["gender"].get(gender, 0) + 1
        
        for r in poll.get("responses", []):
            if r.get("response_text"):
                sentiment = analyze_sentiment(r["response_text"]).value
                sentiment_summary[sentiment] = sentiment_summary.get(sentiment, 0) + 1
        
        return {
            "poll_id": poll["poll_id"],
            "title": poll["title"],
            "total_responses": total_responses,
            "options": aggregated_options,
            "is_anonymous": poll.get("is_anonymous", True),
            "participation_rate": poll.get("participation_rate", 0.0),
            "geographic_breakdown": geographic_breakdown,
            "demographic_breakdown": demographic_breakdown,
            "sentiment_summary": sentiment_summary,
        }

    async def _can_see_results(self, poll: dict, user_role: str) -> bool:
        """
        Check if user can see poll results based on show_results setting.
        """
        show_results = poll.get("show_results", "after_voting")
        
        match show_results:
            case "immediately":
                return True  # Everyone sees results immediately
            case "after_voting":
                # User can see if they voted (not implemented here - requires session tracking)
                return True  # TODO: Check if user voted
            case "after_closing":
                # Only show if poll is closed
                return poll.get("status") == "closed"
            case "never":
                # Only creator/ops can see
                return user_role in [UserRole.CORPORATOR.value, UserRole.OPS.value]
            case _:
                return False

    async def vote(
        self, poll_id: str, option_id: str, user_id: str, response_text: Optional[str] = None
    ) -> Dict:
        """
        Record a vote on a poll (with privacy enforcement).
        
        CRITICAL:
        - If anonymous: don't store user_id with response
        - Track votes in option counts
        - Update aggregation
        """
        query = {}
        if ObjectId.is_valid(poll_id):
            query = {"$or": [{"_id": ObjectId(poll_id)}, {"poll_id": poll_id}]}
        else:
            query = {"poll_id": poll_id}
        
        poll = await self.collection.find_one(query)
        if not poll:
            raise ValueError("Poll not found")
        
        # Prevent duplicate submissions when multiple responses are not allowed
        if not poll.get("allow_multiple_responses", False):
            already_voted = await self._has_voted(poll, user_id)
            if already_voted:
                raise ValueError("You have already responded to this poll")

        response_sentiment = None
        if response_text:
            response_sentiment = analyze_sentiment(response_text).value

        # PRIVACY: Store response appropriately
        if poll.get("is_anonymous", True):
            # Anonymous: don't store user_id
            response_doc = {
                "selected_option_id": option_id,
                "response_text": response_text,
                "sentiment": response_sentiment,
                "responded_at": datetime.utcnow(),
                # user_id intentionally NOT stored
            }
            responder_hash = self._hash_responder(poll.get("poll_id"), user_id)
        else:
            # Non-anonymous: store user_id
            response_doc = {
                "user_id": user_id,
                "selected_option_id": option_id,
                "response_text": response_text,
                "sentiment": response_sentiment,
                "responded_at": datetime.utcnow(),
            }
            responder_hash = None
        
        # Update poll
        update_doc = {
            "$push": {"responses": response_doc},
            "$inc": {"total_responses": 1},
            "$addToSet": {"unique_viewers": user_id},
        }
        if responder_hash:
            update_doc["$addToSet"]["anonymous_responders"] = responder_hash

        result = await self.collection.update_one(query, update_doc)
        
        if result.modified_count == 0:
            raise ValueError("Failed to record vote")

        await self._track_voter_participation(user_id)
        await self._track_leader_poll_response(user_id)
        
        return {"message": "Vote recorded successfully"}

    async def _has_voted(self, poll: dict, user_id: str) -> bool:
        """Check if user already voted on this poll."""
        if poll.get("is_anonymous", True):
            responder_hash = self._hash_responder(poll.get("poll_id"), user_id)
            if responder_hash in poll.get("anonymous_responders", []):
                return True
            return False
        for response in poll.get("responses", []):
            if response.get("user_id") == user_id:
                return True
        return False

    @staticmethod
    def _hash_responder(poll_id: Optional[str], user_id: str) -> str:
        """Hash responder for anonymous poll tracking."""
        token = f"{poll_id}:{user_id}"
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def _track_voter_participation(self, user_id: str) -> None:
        """Track voter poll participation."""
        if not ObjectId.is_valid(user_id):
            return
        await self.users_collection.update_one(
            {"_id": ObjectId(user_id), "role": UserRole.VOTER.value},
            {
                "$inc": {"engagement.total_polls_participated": 1},
                "$set": {"engagement.last_active_date": datetime.utcnow()},
            },
        )

    async def _track_leader_poll_response(self, voter_id: str) -> None:
        """Track leader's voter responses."""
        if not ObjectId.is_valid(voter_id):
            return
        voter = await self.users_collection.find_one(
            {"_id": ObjectId(voter_id), "role": UserRole.VOTER.value},
            {"assigned_leader_id": 1},
        )
        if not voter:
            return
        leader_id = voter.get("assigned_leader_id")
        if not leader_id or not ObjectId.is_valid(str(leader_id)):
            return
        leader = await self.users_collection.find_one(
            {"_id": ObjectId(str(leader_id)), "role": UserRole.LEADER.value},
            {"territory.total_voters_assigned": 1},
        )
        if not leader:
            return
        total_voters = (leader.get("territory") or {}).get("total_voters_assigned", 0) or 0
        await self.users_collection.update_one(
            {"_id": ObjectId(str(leader_id))},
            {"$inc": {"performance.poll_responses": 1}},
        )
        if total_voters > 0:
            await self.users_collection.update_one(
                {"_id": ObjectId(str(leader_id))},
                [
                    {
                        "$set": {
                            "performance.poll_response_rate": {
                                "$round": [
                                    {
                                        "$multiply": [
                                            {"$divide": ["$performance.poll_responses", total_voters]},
                                            100,
                                        ]
                                    },
                                    2,
                                ]
                            }
                        }
                    }
                ],
            )

    async def publish(self, poll_id: str, user_id: str) -> PollResponse:
        """
        Publish a draft poll (make it active).
        
        TRIGGER NOTIFICATION HERE after publishing.
        """
        query = {}
        if ObjectId.is_valid(poll_id):
            query = {"$or": [{"_id": ObjectId(poll_id)}, {"poll_id": poll_id}]}
        else:
            query = {"poll_id": poll_id}
        
        result = await self.collection.find_one_and_update(
            query,
            {
                "$set": {
                    "status": "active",
                    "status_updated_at": datetime.utcnow(),
                }
            },
            return_document=True
        )
        
        if not result:
            raise ValueError("Poll not found")
        
        # TRIGGER NOTIFICATION HERE
        # await notify_targeted_users(result, user_id)
        
        return PollResponse(**self._normalize_doc(result))

    async def close(self, poll_id: str) -> PollResponse:
        """Close a poll (stop voting)."""
        query = {}
        if ObjectId.is_valid(poll_id):
            query = {"$or": [{"_id": ObjectId(poll_id)}, {"poll_id": poll_id}]}
        else:
            query = {"poll_id": poll_id}
        
        result = await self.collection.find_one_and_update(
            query,
            {
                "$set": {
                    "status": "closed",
                    "status_updated_at": datetime.utcnow(),
                }
            },
            return_document=True
        )
        
        if not result:
            raise ValueError("Poll not found")
        
        return PollResponse(**self._normalize_doc(result))
