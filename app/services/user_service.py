"""
User Service Module
===================
Business logic for user management, profile updates, and territory assignments.
Enforces hierarchy: Corporator → Leader → Voter

CRITICAL SECURITY:
- Leaders can only interact with users in their assigned territory
- Voter identity fields are never exposed to Leaders
- Geographic scoping enforced at service layer

Author: Political Communication Platform Team
"""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
import logging
from bson import ObjectId

from app.db.mongodb import get_database
from app.core.roles import UserRole
from app.core.security import hash_password
from app.utils.helpers import validate_email, validate_mobile_number, utc_now
from app.utils.enums import EngagementLevel
from app.utils.geo import LocationHierarchy, build_location_filter
from app.schemas.user_schema import (
    UserCreateRequest,
    UserUpdateRequest,
    VoterDemographicsRequest,
    VoterProfileUpdateRequest,
    LeaderAssignmentRequest,
    NotificationPreferencesRequest,
)

logger = logging.getLogger(__name__)


class UserService:
    """
    User management service enforcing role hierarchy and geographic scoping.
    """
    
    @staticmethod
    async def create_user(
        request: UserCreateRequest,
        created_by: str
    ) -> Dict[str, Any]:
        """
        Create a new user (Corporator/Ops only).
        SECURITY: Only allows creation of LEADER or VOTER roles by admins.
        
        Args:
            request: User creation details
            created_by: ID of user creating this account
            
        Returns:
            Created user document
            
        Raises:
            ValueError: If validation fails
        """
        # FIX: Validate that only LEADER or VOTER can be created via this endpoint
        # CORPORATOR and OPS must be created through separate admin process
        if request.role not in [UserRole.LEADER, UserRole.VOTER]:
            raise ValueError("Can only create LEADER or VOTER accounts through this endpoint")
        
        db = get_database()
        
        # Check if user already exists
        existing_user = await db.users.find_one({
            "$or": [
                {"email": request.email.lower()},
                {"mobile_number": request.mobile_number}
            ]
        })
        
        if existing_user:
            raise ValueError("Email or mobile number already registered")
        
        # Create user document
        user_doc = {
            "email": request.email.lower(),
            "mobile_number": request.mobile_number,
            "password_hash": hash_password(request.password),
            "full_name": request.full_name,
            "role": request.role.value,
            "location": request.location.dict(),
            "language_preference": request.language_preference,
            "is_active": True,
            "is_verified": False,
            "is_mobile_verified": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "created_by": created_by,
            "notification_preferences": {
                "email": True,
                "sms": True,
                "push": True
            }
        }
        
        # Add role-specific fields
        if request.role == UserRole.VOTER:
            user_doc["engagement"] = {
                "level": EngagementLevel.PASSIVE.value,
                "issues_of_interest": [],
                "last_active_date": None,
                "total_complaints": 0,
                "total_polls_participated": 0,
                "total_feedback_given": 0
            }
            user_doc["assigned_leader_id"] = None
        
        elif request.role == UserRole.LEADER:
            user_doc["assigned_territory"] = request.location.dict()  # CRITICAL: Store assigned territory
            user_doc["territory"] = {
                "assigned_areas": [],
                "assigned_wards": [],
                "total_voters_assigned": 0
            }
            user_doc["performance"] = {
                "messages_shared": 0,
                "complaints_followed_up": 0,
                "complaints_handled": 0,
                "complaints_resolved": 0,
                "events_participated": 0,
                "voter_interactions": 0,
                "poll_responses": 0,
                "poll_response_rate": 0.0,
                "engagement_level": "low",
                "average_response_time_hours": 0.0,
                "rating": 0.0,
                "tasks_assigned": 0,
                "tasks_completed": 0,
                "ground_verifications_completed": 0
            }
            user_doc["assigned_by"] = created_by
            user_doc["leader_responsibilities"] = []
        
        result = await db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        
        logger.info(f"User created: {user_id} ({request.role.value}) by {created_by}")
        
        return await UserService.get_user_by_id(user_id)
    
    @staticmethod
    async def get_user_by_id(
        user_id: str,
        requesting_user_id: Optional[str] = None,
        requesting_user_role: Optional[UserRole] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get user by ID (sanitized response - no password hash).
        
        CRITICAL SECURITY:
        - If requester is a Leader, verify target user is in Leader's territory
        - Sanitize voter identity fields for Leaders
        
        Args:
            user_id: User ID to fetch
            requesting_user_id: ID of user making the request
            requesting_user_role: Role of user making the request
            
        Returns:
            User document without sensitive fields
            
        Raises:
            ValueError: If Leader tries to access user outside territory
        """
        db = get_database()
        
        try:
            user = await db.users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None
        
        if not user:
            return None
        
        # CRITICAL: If requester is a Leader, enforce territory boundaries
        if requesting_user_role == UserRole.LEADER and requesting_user_id != user_id:
            requester = await db.users.find_one({"_id": ObjectId(requesting_user_id)})
            if not requester:
                raise ValueError("Requesting user not found")
            
            leader_territory = requester.get("assigned_territory", {})
            user_location = user.get("location", {})
            
            # Check if user is in Leader's territory
            if not UserService._is_in_territory(user_location, leader_territory):
                raise ValueError("User not in your assigned territory")
        
        # Remove sensitive fields
        user.pop("password_hash", None)
        user = UserService._serialize_doc(user)

        # PRIVACY: Sanitize voter-specific sensitive fields if requester is Leader
        if requesting_user_role == UserRole.LEADER and user.get("role") == UserRole.VOTER.value:
            user = UserService._sanitize_voter_fields_for_leader(user)
        else:
            if user.get("role") == UserRole.VOTER.value:
                voter_lookup = await db.voter_lookups.find_one({"user_id": user_id})
                if voter_lookup:
                    voter_lookup.pop("_id", None)
                    voter_lookup.pop("epic_encrypted", None)
                    user["voter_lookup"] = UserService._serialize_doc(voter_lookup)

        return user
    
    @staticmethod
    def _is_in_territory(user_location: dict, leader_territory: dict) -> bool:
        """
        Check if user's location falls within leader's assigned territory.
        
        Matching logic (hierarchical):
        - If leader_territory specifies 'area', user must match area
        - If leader_territory specifies 'ward', user must match ward
        - If leader_territory specifies 'city', user must match city
        - If leader_territory specifies 'state', user must match state
        
        Args:
            user_location: User's location dict
            leader_territory: Leader's assigned territory dict
            
        Returns:
            bool: True if user is in territory
        """
        if not leader_territory:
            return False
        
        # Match from most specific (area) to least specific (state)
        for field in ["area", "ward", "city", "state"]:
            territory_value = leader_territory.get(field, "").lower().strip()
            user_value = user_location.get(field, "").lower().strip()
            
            if territory_value:
                if territory_value != user_value:
                    return False
        
        return True
    
    @staticmethod
    def _sanitize_voter_fields_for_leader(user: dict) -> dict:
        """
        Remove/mask sensitive voter identity fields when accessed by Leader.
        
        Leaders should NOT see:
        - Email address (privacy)
        - Mobile number (privacy)
        - Demographics (religion, caste, etc.)
        - Exact location details (only area-level)
        
        Args:
            user: User document
            
        Returns:
            Sanitized user document
        """
        # Mask email and mobile
        if "email" in user:
            user["email"] = "***@***.***"  # Fully masked
        if "mobile_number" in user:
            user["mobile_number"] = "**********"  # Fully masked
        
        # Remove demographics
        user.pop("demographics", None)
        
        # Keep only aggregated engagement metrics (no individual identifiers)
        if "engagement" in user:
            engagement = user["engagement"]
            user["engagement"] = {
                "level": engagement.get("level"),
                "total_complaints": engagement.get("total_complaints", 0),
                "total_polls_participated": engagement.get("total_polls_participated", 0),
                "total_feedback_given": engagement.get("total_feedback_given", 0),
                # DO NOT expose: issues_of_interest (can identify individuals)
            }
        
        logger.debug(f"Sanitized voter profile for Leader access: {user.get('_id')}")
        return user
    
    @staticmethod
    async def update_user(
        user_id: str,
        request: UserUpdateRequest
    ) -> Dict[str, Any]:
        """
        Update user profile.
        
        Args:
            user_id: User ID to update
            request: Fields to update
            
        Returns:
            Updated user document
        """
        db = get_database()
        
        # Build update document (only include non-None fields)
        update_fields = {}
        
        if request.full_name is not None:
            update_fields["full_name"] = request.full_name
        if request.profile_photo_url is not None:
            update_fields["profile_photo_url"] = request.profile_photo_url
        if request.location is not None:
            update_fields["location"] = request.location.dict()
        if request.language_preference is not None:
            update_fields["language_preference"] = request.language_preference
        
        if not update_fields:
            raise ValueError("No fields to update")
        
        update_fields["updated_at"] = utc_now()
        
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_fields}
        )
        
        return await UserService.get_user_by_id(user_id)
    
    @staticmethod
    async def update_voter_demographics(
        user_id: str,
        request: VoterDemographicsRequest
    ) -> Dict[str, Any]:
        """
        Update voter demographics (voter only).
        
        Args:
            user_id: Voter user ID
            request: Demographics data
            
        Returns:
            Updated user document
        """
        db = get_database()
        
        demographics = {}
        if request.voting_location is not None:
            demographics["voting_location"] = request.voting_location
        if request.age_group:
            demographics["age_group"] = request.age_group.value
        if request.gender:
            demographics["gender"] = request.gender.value
        if request.occupation:
            demographics["occupation"] = request.occupation.value
        if request.profession:
            demographics["profession"] = request.profession
        if request.education:
            demographics["education"] = request.education.value
        if request.family_adults is not None:
            demographics["family_adults"] = request.family_adults
        if request.family_kids is not None:
            demographics["family_kids"] = request.family_kids
        if request.annual_income_range:
            demographics["annual_income_range"] = request.annual_income_range.value
        if request.religion:
            demographics["religion"] = request.religion
        
        update_fields = {
            "demographics": demographics,
            "engagement.issues_of_interest": request.issues_of_interest,
            "updated_at": utc_now()
        }
        
        await db.users.update_one(
            {"_id": ObjectId(user_id), "role": UserRole.VOTER.value},
            {"$set": update_fields}
        )
        
        return await UserService.get_user_by_id(user_id)

    @staticmethod
    async def update_voter_profile(
        user_id: str,
        request: VoterProfileUpdateRequest
    ) -> Dict[str, Any]:
        """
        Update voter profile fields (voter only).
        Allows partial updates without clearing existing demographics.
        """
        db = get_database()

        update_fields: Dict[str, Any] = {"updated_at": utc_now()}
        demographics: Dict[str, Any] = {}

        if request.voting_location is not None:
            demographics["voting_location"] = request.voting_location
        if request.age_group:
            demographics["age_group"] = request.age_group.value
        if request.gender:
            demographics["gender"] = request.gender.value
        if request.occupation:
            demographics["occupation"] = request.occupation.value
        if request.profession:
            demographics["profession"] = request.profession
        if request.education:
            demographics["education"] = request.education.value
        if request.family_adults is not None:
            demographics["family_adults"] = request.family_adults
        if request.family_kids is not None:
            demographics["family_kids"] = request.family_kids
        if request.annual_income_range:
            demographics["annual_income_range"] = request.annual_income_range.value
        if request.religion:
            demographics["religion"] = request.religion

        if demographics:
            update_fields["demographics"] = demographics
        if request.issues_of_interest is not None:
            update_fields["engagement.issues_of_interest"] = request.issues_of_interest
        if request.profile_photo_url is not None:
            update_fields["profile_photo_url"] = request.profile_photo_url

        if len(update_fields) == 1:
            raise ValueError("No fields to update")

        await db.users.update_one(
            {"_id": ObjectId(user_id), "role": UserRole.VOTER.value},
            {"$set": update_fields}
        )

        return await UserService.get_user_by_id(user_id)
    
    @staticmethod
    async def assign_leader_territory(
        request: LeaderAssignmentRequest,
        assigned_by: str
    ) -> Dict[str, str]:
        """
        Assign territory to a leader with STRICT validation.
        Enforces that leader can only be assigned to areas within corporator's constituency.
        
        Args:
            request: Leader assignment details
            assigned_by: Corporator ID doing the assignment
            
        Returns:
            Assignment result
            
        Raises:
            ValueError: If leader doesn't exist or is not a leader role
        """
        db = get_database()
        
        # SECURITY FIX: Verify leader exists and has LEADER role
        leader = await db.users.find_one({
            "_id": ObjectId(request.leader_id),
            "role": UserRole.LEADER.value,
            "is_active": True
        })
        
        if not leader:
            raise ValueError("Leader not found or not active")
        
        # SECURITY FIX: Verify corporator exists and has permission
        corporator = await db.users.find_one({
            "_id": ObjectId(assigned_by),
            "role": {"$in": [UserRole.CORPORATOR.value, UserRole.OPS.value]},
            "is_active": True
        })
        
        if not corporator:
            raise ValueError("Unauthorized to assign territory")
        
        # CRITICAL: Build assigned_territory from first assigned area
        # This becomes the Leader's geographic scope
        assigned_territory = leader.get("location", {})
        if request.assigned_areas:
            # Update territory to first assigned area for geographic filtering
            assigned_territory["area"] = request.assigned_areas[0]
        
        # Update leader's territory assignment
        await db.users.update_one(
            {"_id": ObjectId(request.leader_id)},
            {
                "$set": {
                    "assigned_territory": assigned_territory,  # CRITICAL: Geographic scope
                    "territory.assigned_areas": request.assigned_areas,
                    "territory.assigned_wards": request.assigned_wards,
                    "territory.total_voters_assigned": request.total_voters,
                    "assigned_by": assigned_by,
                    "leader_responsibilities": request.responsibilities or [],
                    "updated_at": utc_now()
                }
            }
        )
        
        # Update voters in the assigned territory to link them to this leader
        area_filter = {"location.area": {"$in": request.assigned_areas}}
        
        await db.users.update_many(
            {**area_filter, "role": UserRole.VOTER.value},
            {"$set": {"assigned_leader_id": request.leader_id}}
        )
        
        logger.info(f"Leader {request.leader_id} assigned to areas {request.assigned_areas} by {assigned_by}")
        
        return {
            "success": True,
            "leader_id": request.leader_id,
            "assigned_areas": request.assigned_areas,
            "message": "Territory assigned successfully"
        }
    
    @staticmethod
    async def log_leader_activity(
        leader_id: str,
        activity_type: str,
        increment_amount: int = 1
    ) -> Dict[str, Any]:
        """
        Log leader activity and increment performance metrics.
        
        Args:
            leader_id: Leader user ID
            activity_type: Type of activity to log
            increment_amount: How much to increment (default 1)
            
        Returns:
            Updated performance metrics
            
        Raises:
            ValueError: If leader not found or activity_type invalid
        """
        db = get_database()
        
        # Validate leader exists
        leader = await db.users.find_one({
            "_id": ObjectId(leader_id),
            "role": UserRole.LEADER.value,
            "is_active": True
        })
        
        if not leader:
            raise ValueError("Leader not found or inactive")
        
        # Map activity type to performance field
        activity_map = {
            'message': 'performance.messages_shared',
            'event': 'performance.events_participated',
            'voter_interaction': 'performance.voter_interactions',
            'poll_response': 'performance.poll_responses',
            'complaint_followup': 'performance.complaints_followed_up',
            'complaint_handled': 'performance.complaints_handled',
            'complaint_resolved': 'performance.complaints_resolved'
        }
        
        if activity_type not in activity_map:
            raise ValueError(f"Invalid activity_type: {activity_type}. Must be one of {list(activity_map.keys())}")
        
        field_path = activity_map[activity_type]
        
        # Increment the metric
        await db.users.update_one(
            {"_id": ObjectId(leader_id)},
            {
                "$inc": {field_path: increment_amount},
                "$set": {"updated_at": utc_now()}
            }
        )
        
        # Return updated performance
        updated_leader = await db.users.find_one({"_id": ObjectId(leader_id)})
        return updated_leader.get("performance", {})

    @staticmethod
    async def log_leader_response_time(
        leader_id: str,
        hours: float
    ) -> Dict[str, Any]:
        """
        Update leader's average response time.
        
        Args:
            leader_id: Leader user ID
            hours: Response time in hours
            
        Returns:
            Updated performance metrics
        """
        db = get_database()
        
        leader = await db.users.find_one({
            "_id": ObjectId(leader_id),
            "role": UserRole.LEADER.value
        })
        
        if not leader:
            raise ValueError("Leader not found")
        
        performance = leader.get("performance", {})
        
        # Calculate running average
        old_avg = performance.get("average_response_time_hours", 0.0)
        new_avg = (old_avg + hours) / 2
        
        await db.users.update_one(
            {"_id": ObjectId(leader_id)},
            {
                "$set": {
                    "performance.average_response_time_hours": round(new_avg, 2),
                    "updated_at": utc_now()
                }
            }
        )
        
        updated_leader = await db.users.find_one({"_id": ObjectId(leader_id)})
        return updated_leader.get("performance", {})

    @staticmethod
    async def update_leader_rating(
        leader_id: str,
        rating: float
    ) -> Dict[str, Any]:
        """
        Update leader's rating.
        
        Args:
            leader_id: Leader user ID
            rating: Rating value (1-5)
            
        Returns:
            Updated performance metrics
        """
        db = get_database()
        
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        
        leader = await db.users.find_one({
            "_id": ObjectId(leader_id),
            "role": UserRole.LEADER.value
        })
        
        if not leader:
            raise ValueError("Leader not found")
        
        performance = leader.get("performance", {})
        old_rating = performance.get("rating", 0.0)
        new_rating = (old_rating + rating) / 2
        
        await db.users.update_one(
            {"_id": ObjectId(leader_id)},
            {
                "$set": {
                    "performance.rating": round(new_rating, 2),
                    "updated_at": utc_now()
                }
            }
        )
        
        logger.info(f"Leader {leader_id} rating updated to {new_rating}")
        updated_leader = await db.users.find_one({"_id": ObjectId(leader_id)})
        return updated_leader.get("performance", {})

    @staticmethod
    async def update_task_completion(
        leader_id: str,
        task_id: str,
        completed: bool = True,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark a task as completed or incomplete for a leader.
        
        Args:
            leader_id: Leader user ID
            task_id: Task ID to update
            completed: Whether task is completed
            notes: Optional completion notes
            
        Returns:
            Updated leader document
        """
        db = get_database()
        
        leader = await db.users.find_one({
            "_id": ObjectId(leader_id),
            "role": UserRole.LEADER.value
        })
        
        if not leader:
            raise ValueError("Leader not found")
        
        if completed:
            await db.users.update_one(
                {"_id": ObjectId(leader_id)},
                {
                    "$inc": {"performance.tasks_completed": 1},
                    "$set": {"updated_at": utc_now()}
                }
            )
            logger.info(f"Leader {leader_id} completed task {task_id}")
        else:
            await db.users.update_one(
                {"_id": ObjectId(leader_id)},
                {
                    "$inc": {"performance.tasks_completed": -1},
                    "$set": {"updated_at": utc_now()}
                }
            )
            logger.info(f"Leader {leader_id} marked task {task_id} as incomplete")
        
        return await UserService.get_user_by_id(leader_id)

    @staticmethod
    async def log_ground_verification(
        leader_id: str,
        verification_location: LocationHierarchy,
        verification_photos: List[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Log a ground verification completed by a leader.
        
        Args:
            leader_id: Leader user ID
            verification_location: Where verification was done
            verification_photos: URLs of verification photos
            notes: Any notes about the verification
            
        Returns:
            Updated leader document
        """
        db = get_database()
        
        leader = await db.users.find_one({
            "_id": ObjectId(leader_id),
            "role": UserRole.LEADER.value,
            "is_active": True
        })
        
        if not leader:
            raise ValueError("Leader not found or inactive")
        
        # Create verification record
        verification_record = {
            "leader_id": leader_id,
            "location": verification_location.dict(),
            "completed_at": utc_now(),
            "photos": verification_photos or [],
            "notes": notes
        }
        
        # Store in ground_verifications collection
        await db.ground_verifications.insert_one(verification_record)
        
        # Increment counter on leader profile
        await db.users.update_one(
            {"_id": ObjectId(leader_id)},
            {
                "$inc": {"performance.ground_verifications_completed": 1},
                "$set": {"updated_at": utc_now()}
            }
        )
        
        logger.info(f"Leader {leader_id} completed ground verification at {verification_location.area}")
        
        return await UserService.get_user_by_id(leader_id)

    @staticmethod
    async def get_leader_activity_history(
        leader_id: str,
        days: int = 30,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get detailed activity history for a leader.
        
        Args:
            leader_id: Leader user ID
            days: Look back N days
            skip: Pagination skip
            limit: Pagination limit
            
        Returns:
            Activity history with pagination
        """
        db = get_database()
        
        leader = await db.users.find_one({
            "_id": ObjectId(leader_id),
            "role": UserRole.LEADER.value
        })
        
        if not leader:
            raise ValueError("Leader not found")
        
        since = datetime.utcnow() - timedelta(days=days)
        
        # Query activity logs
        try:
            cursor = db.activity_logs.find({
                "leader_id": leader_id,
                "timestamp": {"$gte": since}
            }).skip(skip).limit(limit).sort("timestamp", -1)
            
            activities = await cursor.to_list(length=limit)
            total = await db.activity_logs.count_documents({
                "leader_id": leader_id,
                "timestamp": {"$gte": since}
            })
        except Exception:
            activities = []
            total = 0
        
        return {
            "leader_id": leader_id,
            "period_days": days,
            "activities": activities,
            "total": total,
            "skip": skip,
            "limit": limit
        }
    
    @staticmethod
    async def list_users(
        filters: Dict[str, Any],
        skip: int,
        limit: int,
        requesting_user_id: Optional[str] = None,
        requesting_user_role: Optional[UserRole] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List users with filters and pagination.
        
        CRITICAL SECURITY:
        - If requester is Leader, only return users in Leader's assigned territory
        - Sanitize voter fields for Leader access
        
        Args:
            filters: MongoDB query filters
            skip: Number of documents to skip
            limit: Maximum documents to return
            requesting_user_id: ID of user making the request
            requesting_user_role: Role of user making the request
            
        Returns:
            Tuple of (users list, total count)
        """
        db = get_database()
        
        # Build query
        query = {}
        
        if "role" in filters:
            query["role"] = filters["role"].value if hasattr(filters["role"], "value") else filters["role"]
        if "is_active" in filters:
            query["is_active"] = filters["is_active"]
        
        # Geographic filters
        for geo_field in ["location.state", "location.city", "location.ward", "location.area"]:
            if geo_field in filters:
                query[geo_field] = filters[geo_field]
        
        # CRITICAL: If requester is Leader, enforce territory restrictions
        if requesting_user_role == UserRole.LEADER:
            requester = await db.users.find_one({"_id": ObjectId(requesting_user_id)})
            if not requester:
                raise ValueError("Requesting user not found")
            
            leader_territory = requester.get("assigned_territory", {})
            
            # Add territory filters to query
            for field in ["area", "ward", "city", "state"]:
                territory_value = leader_territory.get(field)
                if territory_value:
                    query[f"location.{field}"] = territory_value
                    break  # Stop at first specified level (most specific)
            
            logger.debug(f"Leader {requesting_user_id} territory filter: {query}")
        
        # Execute query
        cursor = db.users.find(query).skip(skip).limit(limit).sort("created_at", -1)
        
        users = []
        async for user in cursor:
            user.pop("password_hash", None)
            user = UserService._serialize_doc(user)
            
            # PRIVACY: Sanitize voter fields if requester is Leader
            if requesting_user_role == UserRole.LEADER and user.get("role") == UserRole.VOTER.value:
                user = UserService._sanitize_voter_fields_for_leader(user)
            
            users.append(user)
        
        total = await db.users.count_documents(query)
        
        return (users, total)

    @staticmethod
    def _serialize_doc(value: Any) -> Any:
        """
        Recursively serialize MongoDB/Pydantic-unfriendly types.
        - ObjectId -> str
        - datetime -> ISO string
        """
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return [UserService._serialize_doc(v) for v in value]
        if isinstance(value, dict):
            return {k: UserService._serialize_doc(v) for k, v in value.items()}
        return value
    
    @staticmethod
    async def get_leader_performance(leader_id: str) -> Dict[str, Any]:
        """
        Get leader performance metrics.
        
        Args:
            leader_id: Leader user ID
            
        Returns:
            Performance metrics
        """
        db = get_database()
        
        leader = await db.users.find_one({
            "_id": ObjectId(leader_id),
            "role": UserRole.LEADER.value
        })
        
        if not leader:
            raise ValueError("Leader not found")
        
        performance = leader.get("performance", {})
        engagement_level = UserService._compute_engagement_level(performance)
        performance_score = UserService._compute_performance_score(performance)
        
        return {
            "leader_id": leader_id,
            "full_name": leader.get("full_name"),
            "location": leader.get("location"),
            **performance,
            "engagement_level": engagement_level,
            "performance_score": performance_score,
        }

    @staticmethod
    def _compute_engagement_level(performance: Dict[str, Any]) -> str:
        score = 0
        score += performance.get("messages_shared", 0)
        score += performance.get("complaints_followed_up", 0)
        score += performance.get("events_participated", 0)
        score += performance.get("voter_interactions", 0)
        score += performance.get("poll_response_rate", 0) / 10
        if score >= 30:
            return "high"
        if score >= 10:
            return "medium"
        return "low"

    @staticmethod
    def _compute_performance_score(performance: Dict[str, Any]) -> float:
        score = 0.0
        score += performance.get("messages_shared", 0)
        score += performance.get("complaints_followed_up", 0)
        score += performance.get("complaints_resolved", 0) * 2
        score += performance.get("events_participated", 0)
        score += performance.get("voter_interactions", 0)
        score += performance.get("poll_response_rate", 0) / 2
        return round(score, 2)
    
    @staticmethod
    async def get_voter_engagement(voter_id: str) -> Dict[str, Any]:
        """
        Get voter engagement metrics.
        
        Args:
            voter_id: Voter user ID
            
        Returns:
            Engagement metrics
        """
        db = get_database()
        
        voter = await db.users.find_one({
            "_id": ObjectId(voter_id),
            "role": UserRole.VOTER.value
        })
        
        if not voter:
            raise ValueError("Voter not found")
        
        engagement = voter.get("engagement", {})
        
        return {
            "user_id": voter_id,
            "engagement_level": engagement.get("level"),
            "issues_of_interest": engagement.get("issues_of_interest", []),
            "total_complaints": engagement.get("total_complaints", 0),
            "total_polls_participated": engagement.get("total_polls_participated", 0),
            "total_feedback_given": engagement.get("total_feedback_given", 0),
            "last_active_date": engagement.get("last_active_date"),
            "engagement_score": 0.0
        }
    
    @staticmethod
    async def update_notification_preferences(
        user_id: str,
        request: NotificationPreferencesRequest
    ) -> Dict[str, Any]:
        """
        Update user notification preferences.
        
        Args:
            user_id: User ID
            request: Notification preferences
            
        Returns:
            Updated user document
        """
        db = get_database()
        
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "notification_preferences": request.dict(),
                "updated_at": utc_now()
            }}
        )
        
        return await UserService.get_user_by_id(user_id)
    
    @staticmethod
    async def deactivate_user(user_id: str) -> bool:
        """
        Deactivate a user account.
        
        Args:
            user_id: User ID to deactivate
            
        Returns:
            True if deactivated
        """
        db = get_database()
        
        result = await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "is_active": False,
                "updated_at": utc_now()
            }}
        )
        
        if result.matched_count == 0:
            raise ValueError("User not found")
        
        logger.info(f"User {user_id} deactivated")
        return True

    @staticmethod
    async def get_user_insights(user_id: str) -> Dict[str, Any]:
        """
        Get current user's insights/stats based on their role.
        
        For LEADER:
        - Number of voters in their ward/area
        - Number of complaints acknowledged
        
        For CORPORATOR:
        - Number of complaints resolved
        - Number of active leaders
        
        Args:
            user_id: Current user ID
            
        Returns:
            User insights/stats
        """
        db = get_database()
        
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise ValueError("User not found")
        
        role = user.get("role")
        location = user.get("location", {})
        
        if role == UserRole.LEADER.value:
            # Get voters in same ward/area
            ward = location.get("ward")
            area = location.get("area")
            
            voter_filter = {
                "role": UserRole.VOTER.value,
                "is_active": True,
                "location.ward": ward,
                "location.area": area
            }
            
            voters_count = await db.users.count_documents(voter_filter)
            
            # Get complaints acknowledged by this leader
            acknowledged_complaints = await db.complaints.count_documents({
                "assigned_to": ObjectId(user_id),
                "acknowledged_at": {"$exists": True, "$ne": None}
            })
            
            return {
                "role": role,
                "full_name": user.get("full_name"),
                "location": location,
                "voters_in_ward": voters_count,
                "complaints_acknowledged": acknowledged_complaints,
                "reach": voters_count,  # Alias for voters in ward
                "performance": user.get("performance", {}),
            }
        
        elif role == UserRole.CORPORATOR.value:
            # Get complaints resolved in corporator's territory
            city = location.get("city")
            state = location.get("state")
            
            resolved_filter = {
                "location.city": city,
                "location.state": state,
                "status": "resolved"
            }
            
            resolved_complaints = await db.complaints.count_documents(resolved_filter)
            
            # Get active leaders in territory
            leaders_filter = {
                "role": UserRole.LEADER.value,
                "is_active": True,
                "location.city": city,
                "location.state": state
            }
            
            active_leaders = await db.users.count_documents(leaders_filter)
            
            return {
                "role": role,
                "full_name": user.get("full_name"),
                "location": location,
                "complaints_resolved": resolved_complaints,
                "active_leaders": active_leaders,
                "territory": f"{city}, {state}",
            }
        
        else:
            # Voter or other role
            return {
                "role": role,
                "full_name": user.get("full_name"),
                "location": location,
            }
