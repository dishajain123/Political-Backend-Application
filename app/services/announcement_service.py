"""
Announcement Service
====================
Handles announcements with role-based targeting and privacy enforcement.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional
from bson import ObjectId
from app.db.mongodb import get_database
from app.schemas.announcement_schema import (
    AnnouncementCreateRequest,
    AnnouncementUpdateRequest,
    AnnouncementResponse,
    AnnouncementListResponse,
    AnnouncementPublishRequest,
    AnnouncementAcknowledgeRequest,
    AnnouncementTargetRequest,
)
from app.core.roles import UserRole
from app.utils.enums import AnnouncementStatus, AnnouncementPriority, AnnouncementCategory
from app.api.dependencies import CurrentUser
from app.services.notification_service import NotificationService
from app.utils.enums import NotificationType
import math


class AnnouncementService:
    """Announcement business logic with targeting and privacy enforcement"""

    def __init__(self):
        self.collection = get_database().announcements
        self.users_collection = get_database().users

    async def create(
        self, payload: AnnouncementCreateRequest, user_id: str
    ) -> AnnouncementResponse:
        """
        Create announcement with MANDATORY fields and targeting.
        
        CRITICAL VALIDATIONS:
        - Title: mandatory, 5-300 chars
        - Content: mandatory, 20+ chars
        - Category: mandatory (5 enum values enforced by Pydantic)
        - Target: targeting rules validated by role
        
        LEADER-SPECIFIC RULES:
        - MUST provide parent_announcement_id (reference to Corporator announcement)
        - MUST have "create_announcements" in leader_responsibilities
        - Automatically geo-restricted to assigned territory
        - Cannot create global announcements
        """
        user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise ValueError("User not found")
        
        user_role = user.get("role")
        is_leader = user_role == UserRole.LEADER.value
        
        # LEADER-SPECIFIC VALIDATION
        if is_leader:
            # Check delegation
            responsibilities = user.get("leader_responsibilities", []) or []
            if "create_announcements" not in responsibilities:
                raise ValueError("Leader not delegated to create announcements")
            
            # CRITICAL: Leader MUST reference parent announcement
            if not payload.parent_announcement_id:
                raise ValueError(
                    "Leaders must reference a parent Corporator announcement. "
                    "Please provide parent_announcement_id to add local context."
                )
            
            # Validate parent announcement exists and is published
            parent_id = (payload.parent_announcement_id or "").strip()
            if not parent_id:
                raise ValueError(
                    "Leaders must reference a parent Corporator announcement. "
                    "Please provide parent_announcement_id to add local context."
                )
            # Prefer a published corporator announcement to avoid matching drafts.
            parent_match = {
                "is_leader_message": False,
                "$or": [
                    {"status": AnnouncementStatus.PUBLISHED.value},
                    {"published_at": {"$ne": None}},
                ],
            }
            if ObjectId.is_valid(parent_id):
                parent_match["$or"].append({"_id": ObjectId(parent_id)})
                parent_match["$or"].append({"announcement_id": parent_id})
            else:
                parent_match["$or"].append({"announcement_id": parent_id})
            
            parent = await self.collection.find_one(parent_match)
            if not parent:
                raise ValueError("Parent announcement must be published before adding local context")
            
            # Verify parent was created by Corporator
            parent_creator = await self.users_collection.find_one({"_id": ObjectId(parent.get("created_by"))})
            if not parent_creator or parent_creator.get("role") != UserRole.CORPORATOR.value:
                raise ValueError("Parent announcement must be created by Corporator")
            
            # ENFORCE: Leader announcement automatically restricted to assigned territory
            leader_territory = user.get("assigned_territory", {})
            if not leader_territory:
                raise ValueError("Leader must have assigned territory to create announcements")
            
            # Override any target provided - enforce geo-restriction
            payload.target = AnnouncementTargetRequest(
                roles=[UserRole.VOTER.value],  # Leaders communicate to voters in their territory
                geography=leader_territory,
                regions=None,
                issue_categories=payload.target.issue_categories if payload.target else None,
                specific_users=None,
            )

        # CORPORATOR: Can create without parent (global announcements)
        elif user_role == UserRole.CORPORATOR.value:
            # Corporators can create standalone announcements
            if payload.parent_announcement_id:
                raise ValueError("Corporators create global announcements - do not provide parent_announcement_id")

        # Generate unique announcement_id
        count = await self.collection.count_documents({})
        
        # Different ID prefix for Leader messages
        if is_leader:
            announcement_id = f"LEADER-ANN-{datetime.utcnow().year}-{count + 1:04d}"
        else:
            announcement_id = f"ANN-{datetime.utcnow().year}-{count + 1:04d}"
        
        # Extract enum values with validation
        category_value = payload.category.value if isinstance(payload.category, AnnouncementCategory) else payload.category
        priority_value = payload.priority.value if isinstance(payload.priority, AnnouncementPriority) else payload.priority
        
        doc = {
            "announcement_id": announcement_id,
            "title": payload.title,
            "content": payload.content,
            "summary": payload.summary,
            "priority": priority_value,
            "status": AnnouncementStatus.DRAFT.value,  # Always draft on creation
            "category": category_value,  # MANDATORY field
            
            # TARGETING - stored for filtering
            "target": payload.target.dict() if payload.target else {
                "roles": [UserRole.VOTER.value, UserRole.LEADER.value],  # Default: all
                "geography": None,
                "regions": None,
                "issue_categories": [],
                "specific_users": [],
            },
            
            # Media
            "featured_image_url": payload.featured_image_url,
            "banner_url": payload.banner_url,
            "attachment_urls": payload.attachment_urls or [],
            "tags": payload.tags or [],
            
            # Settings
            "require_acknowledgment": payload.require_acknowledgment,
            "enable_comments": payload.enable_comments,
            "is_public": payload.is_public,
            "is_pinned": False,
            "scheduled_publish_at": payload.scheduled_publish_at,
            "expiry_date": payload.expiry_date,
            "content_language": (
                payload.content_language
                if isinstance(payload.content_language, str)
                else None
            ),
            
            # LEADER-SPECIFIC FIELDS
            "parent_announcement_id": payload.parent_announcement_id if is_leader else None,
            "local_context": payload.local_context if is_leader else None,
            "is_leader_message": is_leader,
            
            # Audit
            "created_by": user_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "published_at": None,
            
            # Metrics (private - not visible to viewers)
            "metrics": {
                "view_count": 0,
                "unique_viewers": [],  # Track viewer IDs for analytics (private)
                "share_count": 0,
                "reaction_count": 0,
                "comment_count": 0,
                "acknowledgment_count": 0,
                "acknowledgment_users": [],  # Private - who acknowledged (not public)
            },
        }
        # Keep content_language only if valid
        if not isinstance(doc.get("content_language"), str):
            doc.pop("content_language", None)
        
        result = await self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        
        return AnnouncementResponse(
            _id=doc["_id"],
            announcement_id=doc["announcement_id"],
            title=doc["title"],
            content=doc.get("content"),
            summary=doc.get("summary"),
            priority=doc["priority"],
            status=doc["status"],
            category=doc["category"],
            created_by=doc["created_by"],
            created_at=doc["created_at"].isoformat(),
            published_at=doc["published_at"].isoformat() if doc.get("published_at") else None,
            expiry_date=doc["expiry_date"].isoformat() if doc.get("expiry_date") else None,
            is_public=doc["is_public"],
            is_pinned=doc["is_pinned"],
            metrics=doc["metrics"],
            parent_announcement_id=doc.get("parent_announcement_id"),
            local_context=doc.get("local_context"),
            is_leader_message=doc.get("is_leader_message", False),
        )

    async def _can_view_announcement(
        self,
        announcement: dict,
        user_role: str,
        user_location: dict,
        user_id: Optional[str] = None,
        user_issues: Optional[list] = None,
        user_language: Optional[str] = None,
    ) -> bool:
        """
        Check if user can view announcement based on targeting rules.
        
        CRITICAL: Enforces privacy - viewers don't see who else viewed/acknowledged.
        """
        # OPS cannot view announcements
        if user_role == UserRole.OPS.value:
            return False

        status = announcement.get("status")

        # Non-published announcements are only visible to corporators.
        if status != AnnouncementStatus.PUBLISHED.value:
            return user_role == UserRole.CORPORATOR.value

        # Published announcements:
        # - If public, visible to all (except OPS).
        # - If private, enforce targeting below.
        if announcement.get("is_public", True):
            return True

        target = announcement.get("target", {})
        
        # Check specific user targeting (overrides other target filters)
        if target.get("specific_users"):
            return user_id in target.get("specific_users", [])

        # Check role targeting
        if target.get("roles"):
            if user_role not in target["roles"]:
                return False
        
        # If user has no location data, skip location-based targeting
        user_state = user_location.get("state", "").lower()
        user_city = user_location.get("city", "").lower()
        user_ward = user_location.get("ward", "").lower()
        user_area = user_location.get("area", "").lower()
        has_location = any([user_state, user_city, user_ward, user_area])

        # Check region targeting (list)
        if has_location and target.get("regions"):
            regions = target["regions"]
            state_match = any(
                r.get("state", "").lower() == user_state 
                for r in regions
            )
            
            if not state_match:
                return False
        
        # Check single geography targeting
        if has_location and target.get("geography"):
            geo = target["geography"]
            
            if geo.get("state") and geo.get("state", "").lower() != user_state:
                return False
            if geo.get("city") and geo.get("city", "").lower() != user_city:
                return False
            if geo.get("ward") and geo.get("ward", "").lower() != user_ward:
                return False
            if geo.get("area") and geo.get("area", "").lower() != user_area:
                return False
        
        # Check issue category targeting
        if target.get("issue_categories") and user_issues:
            if not set(target.get("issue_categories", [])) & set(user_issues):
                return False

        # Language filtering disabled for announcements:
        # published announcements should be visible regardless of user language.
        
        return True

    async def list(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        is_public: Optional[bool] = None,
        user_id: Optional[str] = None,
        user_role: str = UserRole.VOTER.value,
        user_location: Optional[dict] = None,
        user_issues: Optional[list] = None,
        user_language: Optional[str] = None,
    ) -> AnnouncementListResponse:
        """
        List announcements with targeting enforcement.
        
        CRITICAL CHANGES:
        - Only return announcements user is TARGETED to see
        - Filter by role + location
        - DON'T leak viewer/acknowledgment data
        """
        if user_location is None:
            user_location = {}
        
        # Build filter query
        query = {}
        
        if status:
            query["status"] = status
        
        if priority:
            query["priority"] = priority
        
        if category:
            try:
                AnnouncementCategory(category)
                query["category"] = category
            except ValueError:
                pass
        
        if is_public is not None:
            query["is_public"] = is_public
        
        # IMPORTANT: Only published announcements visible to voters.
        if user_role in [UserRole.VOTER.value, UserRole.LEADER.value]:
            query["status"] = AnnouncementStatus.PUBLISHED.value
        
        # Calculate skip
        skip = (page - 1) * page_size
        
        # Get total count
        total = await self.collection.count_documents(query)
        
        # Get paginated items
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(page_size)
        
        items = []
        async for doc in cursor:
            # CRITICAL: Check targeting for each announcement
            can_view = await self._can_view_announcement(
                doc,
                user_role,
                user_location,
                user_id=user_id,
                user_issues=user_issues,
                user_language=user_language,
            )
            
            if not can_view:
                continue
            
            # PRIVACY: Sanitize metrics before returning
            metrics = doc.get("metrics", {})
            sanitized_metrics = {
                "view_count": metrics.get("view_count", 0),
                "share_count": metrics.get("share_count", 0),
                "reaction_count": metrics.get("reaction_count", 0),
                "comment_count": metrics.get("comment_count", 0),
                "acknowledgment_count": metrics.get("acknowledgment_count", 0),
                # DO NOT expose: unique_viewers, acknowledgment_users
            }
            
            items.append(
                AnnouncementResponse(
                    _id=str(doc["_id"]),
                    announcement_id=doc["announcement_id"],
                    title=doc["title"],
                    content=doc.get("content"),
                    summary=doc.get("summary"),
                    banner_url=doc.get("banner_url"),
                    priority=doc["priority"],
                    status=doc["status"],
                    category=doc.get("category", "announcement"),
                    created_by=doc["created_by"],
                    created_at=doc["created_at"].isoformat(),
                    published_at=doc["published_at"].isoformat() if doc.get("published_at") else None,
                    expiry_date=doc["expiry_date"].isoformat() if doc.get("expiry_date") else None,
                    is_public=doc.get("is_public", True),
                    is_pinned=doc.get("is_pinned", False),
                    metrics=sanitized_metrics,
                    parent_announcement_id=doc.get("parent_announcement_id"),
                    local_context=doc.get("local_context"),
                    is_leader_message=doc.get("is_leader_message", False),
                )
            )
        
        # Calculate total pages
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0
        
        return AnnouncementListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        )

    async def get_by_id(
        self,
        announcement_id: str,
        user_role: str,
        user_location: dict,
        user_id: Optional[str] = None,
        user_issues: Optional[list] = None,
        user_language: Optional[str] = None,
    ) -> AnnouncementResponse:
        """Get announcement by ID with targeting and privacy enforcement."""
        query = {}
        
        if ObjectId.is_valid(announcement_id):
            query = {"$or": [{"_id": ObjectId(announcement_id)}, {"announcement_id": announcement_id}]}
        else:
            query = {"announcement_id": announcement_id}
        
        doc = await self.collection.find_one(query)
        
        if not doc:
            raise ValueError("Announcement not found")

        # Voters and Leaders can only access published announcements.
        if user_role in [UserRole.VOTER.value, UserRole.LEADER.value]:
            if doc.get("status") != AnnouncementStatus.PUBLISHED.value:
                raise ValueError("Announcement not accessible")

        # Enforce targeting for non-corporator users
        if user_role != UserRole.CORPORATOR.value:
            can_view = await self._can_view_announcement(
                doc,
                user_role,
                user_location,
                user_id=user_id,
                user_issues=user_issues,
                user_language=user_language,
            )
            if not can_view:
                raise ValueError("Announcement not accessible")
        
        # Increment view count safely (private metric)
        if user_id:
            await self.collection.update_one(
                {"_id": doc["_id"]},
                {
                    "$inc": {"metrics.view_count": 1},
                    "$addToSet": {"metrics.unique_viewers": user_id}
                }
            )
        
        # PRIVACY: Sanitize metrics
        metrics = doc.get("metrics", {})
        sanitized_metrics = {
            "view_count": metrics.get("view_count", 0),
            "share_count": metrics.get("share_count", 0),
            "reaction_count": metrics.get("reaction_count", 0),
            "comment_count": metrics.get("comment_count", 0),
            "acknowledgment_count": metrics.get("acknowledgment_count", 0),
        }
        
        return AnnouncementResponse(
            _id=str(doc["_id"]),
            announcement_id=doc["announcement_id"],
            title=doc["title"],
            content=doc.get("content"),
            summary=doc.get("summary"),
            banner_url=doc.get("banner_url"),
            priority=doc["priority"],
            status=doc["status"],
            category=doc.get("category", "announcement"),
            created_by=doc["created_by"],
            created_at=doc["created_at"].isoformat(),
            published_at=doc["published_at"].isoformat() if doc.get("published_at") else None,
            expiry_date=doc["expiry_date"].isoformat() if doc.get("expiry_date") else None,
            is_public=doc.get("is_public", True),
            is_pinned=doc.get("is_pinned", False),
            metrics=sanitized_metrics,
            parent_announcement_id=doc.get("parent_announcement_id"),
            local_context=doc.get("local_context"),
            is_leader_message=doc.get("is_leader_message", False),
        )

    async def update(
        self, announcement_id: str, payload: AnnouncementUpdateRequest, user_id: str
    ) -> AnnouncementResponse:
        """
        Update announcement (creator only).
        
        Leaders can update their local_context field.
        """
        # Find announcement first
        query = {}
        if ObjectId.is_valid(announcement_id):
            query = {"$or": [{"_id": ObjectId(announcement_id)}, {"announcement_id": announcement_id}]}
        else:
            query = {"announcement_id": announcement_id}
        
        existing = await self.collection.find_one(query)
        if not existing:
            raise ValueError("Announcement not found")
        
        # Verify ownership
        if existing.get("created_by") != user_id:
            raise ValueError("Only creator can update announcement")
        
        update_doc = {"updated_at": datetime.utcnow()}
        
        if payload.title:
            update_doc["title"] = payload.title
        if payload.content:
            update_doc["content"] = payload.content
        if payload.summary is not None:
            update_doc["summary"] = payload.summary
        if payload.priority:
            update_doc["priority"] = payload.priority.value if isinstance(payload.priority, AnnouncementPriority) else payload.priority
        if payload.category:
            update_doc["category"] = payload.category.value if isinstance(payload.category, AnnouncementCategory) else payload.category
        if payload.featured_image_url is not None:
            update_doc["featured_image_url"] = payload.featured_image_url
        if payload.tags is not None:
            update_doc["tags"] = payload.tags
        if payload.is_pinned is not None:
            update_doc["is_pinned"] = payload.is_pinned
        
        # LEADER-SPECIFIC: Allow updating local_context
        if payload.local_context is not None:
            if existing.get("is_leader_message"):
                update_doc["local_context"] = payload.local_context
        
        result = await self.collection.find_one_and_update(
            {"_id": existing["_id"]},
            {"$set": update_doc},
            return_document=True
        )
        
        if not result:
            raise ValueError("Announcement not found")
        
        metrics = result.get("metrics", {})
        sanitized_metrics = {
            "view_count": metrics.get("view_count", 0),
            "share_count": metrics.get("share_count", 0),
            "reaction_count": metrics.get("reaction_count", 0),
            "comment_count": metrics.get("comment_count", 0),
            "acknowledgment_count": metrics.get("acknowledgment_count", 0),
        }
        
        return AnnouncementResponse(
            _id=str(result["_id"]),
            announcement_id=result["announcement_id"],
            title=result["title"],
            content=result.get("content"),
            summary=result.get("summary"),
            banner_url=result.get("banner_url"),
            priority=result["priority"],
            status=result["status"],
            category=result.get("category", "announcement"),
            created_by=result["created_by"],
            created_at=result["created_at"].isoformat(),
            published_at=result["published_at"].isoformat() if result.get("published_at") else None,
            expiry_date=result["expiry_date"].isoformat() if result.get("expiry_date") else None,
            is_public=result.get("is_public", True),
            is_pinned=result.get("is_pinned", False),
            metrics=sanitized_metrics,
            parent_announcement_id=result.get("parent_announcement_id"),
            local_context=result.get("local_context"),
            is_leader_message=result.get("is_leader_message", False),
        )

    async def publish(
        self, announcement_id: str, payload: AnnouncementPublishRequest, user_id: str
    ) -> AnnouncementResponse:
        """Publish a draft announcement."""
        update_doc = {
            "status": AnnouncementStatus.PUBLISHED.value,
            "published_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        if payload.scheduled_publish_at:
            update_doc["scheduled_publish_at"] = payload.scheduled_publish_at
        
        query = {}
        if ObjectId.is_valid(announcement_id):
            query = {"$or": [{"_id": ObjectId(announcement_id)}, {"announcement_id": announcement_id}]}
        else:
            query = {"announcement_id": announcement_id}
        
        result = await self.collection.find_one_and_update(
            query,
            {"$set": update_doc},
            return_document=True
        )
        
        if not result:
            raise ValueError("Announcement not found")
        
        # TRIGGER IN-APP NOTIFICATIONS for targeted users
        await self._notify_targeted_users(result)
        
        # Track leader communications
        await self._track_leader_message_shared(user_id)
        
        metrics = result.get("metrics", {})
        sanitized_metrics = {
            "view_count": metrics.get("view_count", 0),
            "share_count": metrics.get("share_count", 0),
            "reaction_count": metrics.get("reaction_count", 0),
            "comment_count": metrics.get("comment_count", 0),
            "acknowledgment_count": metrics.get("acknowledgment_count", 0),
        }
        
        return AnnouncementResponse(
            _id=str(result["_id"]),
            announcement_id=result["announcement_id"],
            title=result["title"],
            content=result.get("content"),
            summary=result.get("summary"),
            banner_url=result.get("banner_url"),
            priority=result["priority"],
            status=result["status"],
            category=result.get("category", "announcement"),
            created_by=result["created_by"],
            created_at=result["created_at"].isoformat(),
            published_at=result["published_at"].isoformat() if result.get("published_at") else None,
            expiry_date=result["expiry_date"].isoformat() if result.get("expiry_date") else None,
            is_public=result.get("is_public", True),
            is_pinned=result.get("is_pinned", False),
            metrics=sanitized_metrics,
            parent_announcement_id=result.get("parent_announcement_id"),
            local_context=result.get("local_context"),
            is_leader_message=result.get("is_leader_message", False),
        )

    async def acknowledge(
        self, announcement_id: str, user_id: str, payload: AnnouncementAcknowledgeRequest
    ) -> None:
        """Acknowledge announcement receipt (private tracking)."""
        query = {}
        if ObjectId.is_valid(announcement_id):
            query = {"$or": [{"_id": ObjectId(announcement_id)}, {"announcement_id": announcement_id}]}
        else:
            query = {"announcement_id": announcement_id}
        
        result = await self.collection.update_one(
            query,
            {
                "$inc": {"metrics.acknowledgment_count": 1},
                "$addToSet": {"metrics.acknowledgment_users": user_id}
            }
        )
        
        if result.matched_count == 0:
            raise ValueError("Announcement not found")

    async def delete(self, announcement_id: str, user_id: str) -> None:
        """Soft delete announcement (archive)."""
        query = {}
        if ObjectId.is_valid(announcement_id):
            query = {"$or": [{"_id": ObjectId(announcement_id)}, {"announcement_id": announcement_id}]}
        else:
            query = {"announcement_id": announcement_id}
        
        result = await self.collection.update_one(
            query,
            {
                "$set": {
                    "status": AnnouncementStatus.ARCHIVED.value,
                    "updated_at": datetime.utcnow(),
                }
            }
        )
        
        if result.matched_count == 0:
            raise ValueError("Announcement not found")

    async def _notify_targeted_users(self, announcement: dict) -> None:
        """Create in-app notifications for targeted users."""
        target = announcement.get("target") or {}

        # If specific_users are provided, notify only those users
        specific_users = target.get("specific_users") or []
        if specific_users:
            user_ids = [uid for uid in specific_users if ObjectId.is_valid(uid)]
        else:
            query = {"is_active": True}

            roles = target.get("roles") or []
            if roles and "all" not in roles:
                query["role"] = {"$in": roles}

            # Geographic targeting (single hierarchy)
            geo = target.get("geography") or {}
            for key in ("state", "city", "ward", "area", "building", "booth_number"):
                if geo.get(key):
                    query[f"location.{key}"] = geo.get(key)

            # Region targeting (list of hierarchies)
            regions = target.get("regions") or []
            if regions:
                region_filters = []
                for region in regions:
                    region_filter = {}
                    for key in ("state", "city", "ward", "area", "building", "booth_number"):
                        if region.get(key):
                            region_filter[f"location.{key}"] = region.get(key)
                    if region_filter:
                        region_filters.append(region_filter)
                if region_filters:
                    query["$or"] = region_filters

            # Issue-category targeting
            issue_categories = target.get("issue_categories") or []
            if issue_categories:
                query["engagement.issues_of_interest"] = {"$in": issue_categories}

            cursor = self.users_collection.find(query, {"_id": 1})
            user_ids = [str(doc["_id"]) async for doc in cursor]

        if not user_ids:
            return

        notifier = NotificationService()
        for uid in user_ids:
            await notifier.notify(
                user_id=uid,
                title=announcement.get("title", "New Announcement"),
                message=announcement.get("summary") or announcement.get("title", ""),
                notification_type=NotificationType.ANNOUNCEMENT.value,
                delivery_channels={
                    "in_app": True,
                    "push": True,
                    "email": False,
                    "sms": False
                },
            )

    async def _track_leader_message_shared(self, user_id: str) -> None:
        """Track Leader performance metric when publishing announcement."""
        if not ObjectId.is_valid(user_id):
            return
        user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
        if not user or user.get("role") != UserRole.LEADER.value:
            return
        await self.users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"performance.messages_shared": 1}},
        )
