"""
Complaint Service
=================
Service layer for complaint lifecycle management with RBAC enforcement.

Author: Political Communication Platform Team
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from bson import ObjectId
from app.db.mongodb import get_database
from app.utils.enums import ComplaintStatus
from app.utils.pagination import create_paginated_response
from app.utils.enums import NotificationType
from app.services.notification_service import NotificationService
from app.schemas.complaint_schema import ComplaintResponse
from app.core.roles import UserRole
from app.api.dependencies import CurrentUser
from uuid import uuid4
from pathlib import Path
from fastapi import UploadFile
import logging

logger = logging.getLogger(__name__)

_COMPLAINT_ALLOWED_EXTENSIONS = {
    "jpg":  "image",
    "jpeg": "image",
    "png":  "image",
    "mp4":  "video",
    "mov":  "video",
    "pdf":  "document",
    "doc":  "document",
    "docx": "document",
}

_COMPLAINT_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

try:
    from fastapi import HTTPException, status
except Exception:  # pragma: no cover - optional import for runtime safety
    HTTPException = None
    status = None


class ComplaintService:
    """Complaint lifecycle service with RBAC enforcement."""

    def __init__(self):
        self.db = get_database()
        self.collection = self.db.complaints
        self.users_collection = self.db.users

    async def create_complaint(self, payload, current_user, upload_file: UploadFile | None = None):
        """Create a complaint (Voter) or on behalf of assigned voter (Leader)."""
        created_by = current_user.user_id

        if current_user.role == UserRole.LEADER:
            if not payload.on_behalf_of_voter_id:
                raise ValueError("Leader must provide on_behalf_of_voter_id")

            voter = await self.users_collection.find_one({"_id": ObjectId(payload.on_behalf_of_voter_id)})
            if not voter or voter.get("role") != UserRole.VOTER.value:
                raise ValueError("Voter not found")

            assigned_leader_id = voter.get("assigned_leader_id")
            if assigned_leader_id != current_user.user_id:
                raise ValueError("Leader can only create complaints for assigned voters")

            created_by = payload.on_behalf_of_voter_id

        count = await self.collection.count_documents({})
        complaint_id = f"COMP-{datetime.utcnow().year}-{count + 1:04d}"

        now = datetime.utcnow()

        file_url = None
        file_type = None
        file_name = None
        file_uploaded_at = None

        if upload_file is not None:
            file_url, file_type, file_name = await self._save_complaint_file(upload_file)
            file_uploaded_at = datetime.utcnow()

        image_url = None
        image_uploaded_at = None
        if file_type == "image" and file_url:
            image_url = file_url
            image_uploaded_at = file_uploaded_at

        # AUTO-ASSIGNMENT: Find and assign to leader in the same ward/area
        complaint_location = payload.location.dict() if hasattr(payload.location, "dict") else payload.location
        assigned_to = None
        assigned_at = None
        assigned_by = None
        
        try:
            # Query for leaders in the same ward/area
            leader_query = {
                "role": UserRole.LEADER.value,
                "is_active": True,
                "location.ward": complaint_location.get("ward"),
                "location.area": complaint_location.get("area"),
            }
            
            # Find first available leader in the same territory
            leader = await self.users_collection.find_one(leader_query)
            if leader:
                assigned_to = str(leader["_id"])
                assigned_at = now
                assigned_by = "system"  # Auto-assignment by system
                logger.info(f"Auto-assigned complaint {complaint_id} to leader {assigned_to}")
        except Exception as e:
            logger.warning(f"Auto-assignment failed: {str(e)}")

        doc = {
            "complaint_id": complaint_id,
            "created_by": created_by,
            "created_at": now,
            "title": payload.title,
            "description": payload.description,
            "category": payload.category.value if hasattr(payload.category, "value") else payload.category,
            "priority": payload.priority.value if hasattr(payload.priority, "value") else payload.priority,
            "location": complaint_location,
            "status": ComplaintStatus.PENDING.value,
            "status_updated_at": now,
            "assigned_to": assigned_to,
            "assigned_at": assigned_at,
            "assigned_by": assigned_by,
            "resolved_by": None,
            "resolved_at": None,
            "resolution_notes": None,
            "attachment_urls": payload.attachment_urls or [],
            "image_urls": payload.image_urls or [],
            "file_url": file_url,
            "file_type": file_type,
            "file_name": file_name,
            "file_uploaded_at": file_uploaded_at,
            "image_url": image_url,
            "image_uploaded_at": image_uploaded_at,
            "notes": [],
            "audit_trail": [],
            "is_escalated": False,
            "escalated_at": None,
            "escalation_reason": None,
            "decline_reason": None,
            "declined_by": None,
            "declined_at": None,
            "voter_satisfaction_rating": None,
            "voter_feedback": None,
            "feedback_given_at": None,
            "sentiment": None,
            "verification_requested_at": None,
            "verified_by_corporator": False,
            "voter_feedback_rating": None,
            "voter_feedback_comment": None,
            "performance_score_updated": False,
            "estimated_resolution_date": None,
            "tags": [],
            "is_public": False,
        }

        result = await self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return ComplaintResponse(**self._normalize_doc(doc))

    async def get_complaints(
        self,
        current_user,
        skip: int = 0,
        limit: int = 20,
        status=None,
        category: str | None = None,
        priority: str | None = None,
        location_filters: dict | None = None,
    ):
        """List complaints with role-based visibility and filters."""
        query = {}

        if status:
            query["status"] = status.value if hasattr(status, "value") else status
        if category:
            query["category"] = category
        if priority:
            query["priority"] = priority
        if location_filters:
            query.update(location_filters)

        if current_user.role == UserRole.VOTER:
            query["created_by"] = current_user.user_id
        elif current_user.role == UserRole.LEADER:
            # Leader sees:
            # 1. Complaints explicitly assigned to them
            # 2. Complaints created by voters assigned to them
            # 3. BOTH must be within their assigned territory (if territory is set)
            
            leader = None
            if ObjectId.is_valid(current_user.user_id):
                leader = await self.users_collection.find_one({"_id": ObjectId(current_user.user_id)})
            
            # Find voters assigned to this leader
            assigned_voter_ids = await self.users_collection.distinct(
                "_id", {"assigned_leader_id": current_user.user_id}
            )
            voter_id_strings = [str(vid) for vid in assigned_voter_ids]
            
            # Build visibility condition:
            # - Assigned to this leader
            # - OR Created by a voter assigned to this leader
            # - OR Unassigned (so leader can see new issues in territory)
            visibility_filter = {
                "$or": [
                    {"assigned_to": current_user.user_id},
                    {"created_by": {"$in": voter_id_strings}},
                    {"assigned_to": None}
                ]
            }
            
            # Combine with territory filters
            territory = leader.get("assigned_territory", {}) if leader else {}
            territory_filter = {}
            for key in ("state", "city", "ward", "area"):
                value = territory.get(key)
                if value:
                    territory_filter[f"location.{key}"] = value
            
            if territory_filter:
                # If leader has a territory, they see (Assigned to them OR Unassigned) AND Territory Match
                # OR they see complaints from their assigned voters (even if territory differs)
                query = {
                    "$or": [
                        {"$and": [
                            {"$or": [{"assigned_to": current_user.user_id}, {"assigned_to": None}]},
                            territory_filter
                        ]},
                        {"created_by": {"$in": voter_id_strings}}
                    ]
                }
            else:
                # If leader has no territory limits, they see what's assigned to them or their voters
                query = visibility_filter
        # Corporator / OPS: no extra filter

        total = await self.collection.count_documents(query)
        cursor = (
            self.collection
            .find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

        items = []
        async for doc in cursor:
            items.append(ComplaintResponse(**self._normalize_doc(doc)))

        page = (skip // limit) + 1 if limit else 1
        return create_paginated_response(items=items, total=total, page=page, page_size=limit)

    async def assign_complaint(self, complaint_id: str, leader_id: str, current_user) -> bool:
        complaint = await self._get_complaint(complaint_id)

        leader = await self.users_collection.find_one({"_id": ObjectId(leader_id)})
        if not leader or leader.get("role") != UserRole.LEADER.value:
            raise ValueError("Leader not found")

        if not self._is_within_territory(complaint.get("location", {}), leader.get("assigned_territory", {})):
            raise ValueError("Complaint is outside leader's assigned territory")

        now = datetime.utcnow()
        audit = self._audit_entry(complaint.get("status"), ComplaintStatus.ACKNOWLEDGED.value, current_user.user_id, "Assigned to leader")

        result = await self.collection.update_one(
            {"_id": complaint["_id"]},
            {
                "$set": {
                    "assigned_to": leader_id,
                    "assigned_at": now,
                    "assigned_by": current_user.user_id,
                    "status": ComplaintStatus.ACKNOWLEDGED.value,
                    "status_updated_at": now,
                },
                "$push": {"audit_trail": audit},
            },
        )
        return result.modified_count > 0

    async def acknowledge_complaint(self, complaint_id: str, payload, current_user) -> bool:
        complaint = await self._get_complaint(complaint_id)

        if complaint.get("assigned_to") != current_user.user_id:
            raise ValueError("Complaint not assigned to this leader")

        now = datetime.utcnow()
        updates = {
            "acknowledged_by_leader": current_user.user_id,
            "acknowledged_at": now,
            "status_updated_at": now,
        }
        if payload.expected_visit_date:
            updates["expected_visit_date"] = payload.expected_visit_date

        notes = []
        if payload.acknowledgment_notes:
            notes.append({
                "added_by": current_user.user_id,
                "content": payload.acknowledgment_notes,
                "added_at": now,
                "is_internal": True,
                "note_type": "field_observation",
            })

        update_doc = {"$set": updates}
        if notes:
            update_doc["$push"] = {"notes": {"$each": notes}}

        result = await self.collection.update_one(
            {"_id": complaint["_id"]},
            update_doc,
        )
        return result.modified_count > 0

    async def update_complaint_status(self, complaint_id: str, payload, current_user) -> bool:
        complaint = await self._get_complaint(complaint_id)

        new_status = payload.status.value if hasattr(payload.status, "value") else payload.status

        if current_user.role == UserRole.LEADER:
            if complaint.get("assigned_to") != current_user.user_id:
                raise ValueError("Complaint not assigned to this leader")
            if new_status in [ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value]:
                raise ValueError("Leaders cannot resolve or close complaints")

        now = datetime.utcnow()
        audit = self._audit_entry(complaint.get("status"), new_status, current_user.user_id, payload.notes)
        update_doc = {
            "status": new_status,
            "status_updated_at": now,
        }
        if payload.estimated_resolution_date:
            update_doc["estimated_resolution_date"] = payload.estimated_resolution_date

        # FIXED: Handle resolution fields when status is 'resolved'
        if new_status == ComplaintStatus.RESOLVED.value:
            update_doc["resolved_by"] = current_user.user_id
            update_doc["resolved_at"] = now
            if payload.notes and payload.notes.strip():
                update_doc["resolution_notes"] = payload.notes.strip()

        result = await self.collection.update_one(
            {"_id": complaint["_id"]},
            {"$set": update_doc, "$push": {"audit_trail": audit}},
        )

        # Increment leader performance metric when complaint is resolved
        if result.modified_count > 0 and new_status == ComplaintStatus.RESOLVED.value and complaint.get("assigned_to"):
            await self._increment_leader_metric(complaint.get("assigned_to"), "performance.complaints_resolved")

        return result.modified_count > 0

    async def resolve_complaint(self, complaint_id: str, payload, current_user) -> bool:
        complaint = await self._get_complaint(complaint_id)

        now = datetime.utcnow()
        audit = self._audit_entry(complaint.get("status"), ComplaintStatus.RESOLVED.value, current_user.user_id, payload.resolution_notes)

        update_doc = {
            "status": ComplaintStatus.RESOLVED.value,
            "status_updated_at": now,
            "resolved_by": current_user.user_id,
            "resolved_at": now,
            "resolution_notes": payload.resolution_notes,
            "attachment_urls": payload.attachment_urls or complaint.get("attachment_urls", []),
        }

        result = await self.collection.update_one(
            {"_id": complaint["_id"]},
            {"$set": update_doc, "$push": {"audit_trail": audit}},
        )

        if result.modified_count > 0 and complaint.get("assigned_to"):
            await self._increment_leader_metric(complaint.get("assigned_to"), "performance.complaints_resolved")

        return result.modified_count > 0

    async def add_note(self, complaint_id: str, payload, current_user) -> bool:
        complaint = await self._get_complaint(complaint_id)

        if current_user.role == UserRole.LEADER and complaint.get("assigned_to") != current_user.user_id:
            raise ValueError("Complaint not assigned to this leader")

        now = datetime.utcnow()
        note_type = payload.note_type
        is_internal = payload.is_internal
        if current_user.role == UserRole.LEADER:
            note_type = "field_observation"
            is_internal = True

        note = {
            "added_by": current_user.user_id,
            "content": payload.content,
            "added_at": now,
            "is_internal": is_internal,
            "note_type": note_type,
        }

        update_doc = {"$push": {"notes": note}}
        set_fields = {}

        if current_user.role == UserRole.LEADER and not complaint.get("first_field_visit_at"):
            set_fields["first_field_visit_at"] = now
            await self._increment_leader_metric(current_user.user_id, "performance.complaints_followed_up")

        if set_fields:
            update_doc["$set"] = set_fields

        result = await self.collection.update_one({"_id": complaint["_id"]}, update_doc)
        return result.modified_count > 0

    async def add_voter_feedback(self, complaint_id: str, payload, current_user) -> bool:
        complaint = await self._get_complaint(complaint_id)

        if complaint.get("created_by") != current_user.user_id:
            raise ValueError("Complaint not accessible")

        if complaint.get("status") not in [ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value]:
            raise ValueError("Feedback allowed only on resolved/closed complaints")

        now = datetime.utcnow()
        result = await self.collection.update_one(
            {"_id": complaint["_id"]},
            {
                "$set": {
                    "voter_satisfaction_rating": payload.satisfaction_rating,
                    "voter_feedback": payload.feedback,
                    "feedback_given_at": now,
                }
            },
        )
        return result.modified_count > 0

    async def escalate(self, complaint_id: str, payload, current_user) -> bool:
        complaint = await self._get_complaint(complaint_id)

        if current_user.role == UserRole.LEADER and complaint.get("assigned_to") != current_user.user_id:
            raise ValueError("Complaint not assigned to this leader")

        now = datetime.utcnow()
        audit = self._audit_entry(complaint.get("status"), complaint.get("status"), current_user.user_id, payload.reason)

        result = await self.collection.update_one(
            {"_id": complaint["_id"]},
            {
                "$set": {
                    "is_escalated": True,
                    "escalated_at": now,
                    "escalation_reason": payload.reason,
                },
                "$push": {"audit_trail": audit},
            },
        )
        return result.modified_count > 0

    async def decline_complaint(self, complaint_id: str, payload, current_user) -> bool:
        complaint = await self._get_complaint(complaint_id)

        if complaint.get("status") in [ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value]:
            raise ValueError("Cannot decline a resolved complaint")

        now = datetime.utcnow()
        reason = payload.decline_reason if payload.decline_reason else None
        audit = self._audit_entry(complaint.get("status"), ComplaintStatus.REJECTED.value, current_user.user_id, reason)

        result = await self.collection.update_one(
            {"_id": complaint["_id"]},
            {
                "$set": {
                    "status": ComplaintStatus.REJECTED.value,
                    "status_updated_at": now,
                    "decline_reason": reason,
                    "decline_category": payload.decline_category,
                    "declined_by": current_user.user_id,
                    "declined_at": now,
                },
                "$push": {"audit_trail": audit},
            },
        )

        return result.modified_count > 0

    async def request_verification(self, complaint_id: str, payload, current_user) -> bool:
        complaint = await self._get_complaint(complaint_id)

        if complaint.get("status") != ComplaintStatus.RESOLVED.value:
            raise ValueError("Only resolved complaints can be verified")

        now = datetime.utcnow()
        result = await self.collection.update_one(
            {"_id": complaint["_id"]},
            {
                "$set": {
                    "verification_requested_at": now,
                    "verified_by_corporator": True,
                }
            },
        )

        if result.modified_count > 0:
            await self._notify_voter(
                complaint.get("created_by"),
                "Complaint Verification Requested",
                payload.notes or "Please verify the resolution and provide feedback.",
                complaint.get("complaint_id"),
            )

        return result.modified_count > 0

    async def submit_verification_feedback(self, complaint_id: str, payload, current_user) -> bool:
        complaint = await self._get_complaint(complaint_id)

        if complaint.get("created_by") != current_user.user_id:
            raise ValueError("Complaint not accessible")

        if not complaint.get("verification_requested_at"):
            raise ValueError("Verification not requested for this complaint")

        if complaint.get("voter_feedback_rating") is not None:
            raise ValueError("Verification feedback already submitted")

        now = datetime.utcnow()
        updates = {
            "voter_feedback_rating": payload.rating,
            "voter_feedback_comment": payload.comment,
        }

        audit = None
        if payload.rating < 3:
            updates["status"] = ComplaintStatus.IN_PROGRESS.value
            updates["status_updated_at"] = now
            audit = self._audit_entry(complaint.get("status"), ComplaintStatus.IN_PROGRESS.value, current_user.user_id, "Reopened after low verification rating")

        result = await self.collection.update_one(
            {"_id": complaint["_id"]},
            {"$set": updates, **({"$push": {"audit_trail": audit}} if audit else {})},
        )

        if result.modified_count > 0 and payload.rating >= 3 and complaint.get("assigned_to") and not complaint.get("performance_score_updated"):
            await self._increment_leader_metric(complaint.get("assigned_to"), "performance.complaints_resolved")
            await self.collection.update_one(
                {"_id": complaint["_id"]},
                {"$set": {"performance_score_updated": True}},
            )

        return result.modified_count > 0

    async def _get_complaint(self, complaint_id: str) -> dict:
        query = {"complaint_id": complaint_id}
        if ObjectId.is_valid(complaint_id):
            query = {"$or": [{"_id": ObjectId(complaint_id)}, {"complaint_id": complaint_id}]}
        complaint = await self.collection.find_one(query)
        if not complaint:
            raise ValueError("Complaint not found")
        return complaint

    async def complaints_analytics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        state: Optional[str] = None,
        city: Optional[str] = None,
        ward: Optional[str] = None,
        area: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
        assigned_to: Optional[str] = None,
        sla_hours: int = 72,
    ) -> Dict[str, Any]:
        match: Dict[str, Any] = {}
        if start_date or end_date:
            date_filter: Dict[str, Any] = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            match["created_at"] = date_filter
        if state:
            match["location.state"] = state
        if city:
            match["location.city"] = city
        if ward:
            match["location.ward"] = ward
        if area:
            match["location.area"] = area
        if category:
            match["category"] = category
        if status:
            match["status"] = status
        if assigned_to:
            match["assigned_to"] = assigned_to

        match_stage = {"$match": match} if match else {"$match": {}}

        def _date_group(field: str, fmt: str):
            return {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": fmt, "date": f"${field}"}}
                    },
                    "count": {"$sum": 1},
                }
            }

        facet = {
            "status_counts": [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ],
            "status_trends": [
                _date_group("created_at", "%Y-%m-%d"),
                {"$sort": {"_id.date": 1}},
            ],
            "status_transitions": [
                {"$unwind": {"path": "$audit_trail", "preserveNullAndEmptyArrays": False}},
                {"$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$audit_trail.changed_at"}},
                        "status": "$audit_trail.status_to",
                    },
                    "count": {"$sum": 1},
                }},
                {"$sort": {"_id.date": 1}},
            ],
            "daily_trend": [
                _date_group("created_at", "%Y-%m-%d"),
                {"$sort": {"_id.date": 1}},
            ],
            "weekly_trend": [
                _date_group("created_at", "%G-W%V"),
                {"$sort": {"_id.date": 1}},
            ],
            "monthly_trend": [
                _date_group("created_at", "%Y-%m"),
                {"$sort": {"_id.date": 1}},
            ],
            "resolution_trend": [
                {"$match": {"resolved_at": {"$ne": None}}},
                _date_group("resolved_at", "%Y-%m-%d"),
                {"$sort": {"_id.date": 1}},
            ],
            "avg_resolution_time_trend": [
                {"$match": {"resolved_at": {"$ne": None}}},
                {"$project": {
                    "resolved_at": 1,
                    "resolution_hours": {
                        "$divide": [{"$subtract": ["$resolved_at", "$created_at"]}, 3600000]
                    },
                }},
                {"$group": {
                    "_id": {"date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$resolved_at"}}},
                    "avg_hours": {"$avg": "$resolution_hours"},
                }},
                {"$sort": {"_id.date": 1}},
            ],
            "peak_hours": [
                {"$group": {"_id": {"$hour": "$created_at"}, "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ],
            "peak_days": [
                {"$group": {"_id": {"$dayOfWeek": "$created_at"}, "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ],
            "area_distribution": [
                {"$group": {"_id": "$location.area", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ],
            "ward_distribution": [
                {"$group": {"_id": "$location.ward", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ],
            "region_distribution": [
                {"$group": {"_id": "$location.city", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ],
            "area_resolution_rate": [
                {"$group": {
                    "_id": "$location.area",
                    "total": {"$sum": 1},
                    "resolved": {"$sum": {"$cond": [{"$eq": ["$status", "resolved"]}, 1, 0]}},
                }},
                {"$project": {
                    "rate": {
                        "$cond": [
                            {"$gt": ["$total", 0]},
                            {"$multiply": [{"$divide": ["$resolved", "$total"]}, 100]},
                            0,
                        ]
                    }
                }},
                {"$sort": {"rate": -1}},
            ],
            "category_distribution": [
                {"$group": {"_id": "$category", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ],
            "category_resolution_time": [
                {"$match": {"resolved_at": {"$ne": None}}},
                {"$project": {
                    "category": 1,
                    "resolution_hours": {
                        "$divide": [{"$subtract": ["$resolved_at", "$created_at"]}, 3600000]
                    },
                }},
                {"$group": {"_id": "$category", "avg_hours": {"$avg": "$resolution_hours"}}},
                {"$sort": {"avg_hours": -1}},
            ],
            "user_complaints": [
                {"$group": {"_id": "$created_by", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ],
            "assignee_distribution": [
                {"$group": {"_id": "$assigned_to", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ],
            "assignee_resolution_rate": [
                {"$group": {
                    "_id": "$assigned_to",
                    "total": {"$sum": 1},
                    "resolved": {"$sum": {"$cond": [{"$eq": ["$status", "resolved"]}, 1, 0]}},
                }},
                {"$project": {
                    "rate": {
                        "$cond": [
                            {"$gt": ["$total", 0]},
                            {"$multiply": [{"$divide": ["$resolved", "$total"]}, 100]},
                            0,
                        ]
                    }
                }},
                {"$sort": {"rate": -1}},
            ],
            "pending_backlog_trend": [
                {"$match": {"status": {"$in": ["pending", "in_progress", "acknowledged"]}}},
                _date_group("created_at", "%Y-%m-%d"),
                {"$sort": {"_id.date": 1}},
            ],
            "resolution_time_avg": [
                {"$match": {"resolved_at": {"$ne": None}}},
                {"$project": {
                    "resolution_hours": {
                        "$divide": [{"$subtract": ["$resolved_at", "$created_at"]}, 3600000]
                    },
                }},
                {"$group": {"_id": None, "avg_hours": {"$avg": "$resolution_hours"}}},
            ],
            "handling_time_avg": [
                {"$project": {
                    "handling_hours": {
                        "$divide": [{"$subtract": ["$status_updated_at", "$created_at"]}, 3600000]
                    },
                }},
                {"$group": {"_id": None, "avg_hours": {"$avg": "$handling_hours"}}},
            ],
            "heatmap": [
                {"$group": {"_id": {"ward": "$location.ward", "area": "$location.area"}, "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
            ],
        }

        result = await self.collection.aggregate([match_stage, {"$facet": facet}]).to_list(None)
        data = result[0] if result else {}

        status_counts = data.get("status_counts", [])
        total_complaints = sum(item.get("count", 0) for item in status_counts)

        status_map = {str(i.get("_id") or "unknown"): int(i.get("count", 0)) for i in status_counts}
        resolved_count = status_map.get("resolved", 0)

        resolution_time_avg_rows = data.get("resolution_time_avg", [])
        avg_resolution_time_hours = float(resolution_time_avg_rows[0].get("avg_hours", 0.0)) if resolution_time_avg_rows else 0.0

        handling_time_avg_rows = data.get("handling_time_avg", [])
        avg_handling_time_hours = float(handling_time_avg_rows[0].get("avg_hours", 0.0)) if handling_time_avg_rows else 0.0

        resolution_rate_pct = round((resolved_count / total_complaints) * 100, 2) if total_complaints else 0.0

        status_distribution = [
            {
                "label": k,
                "count": v,
                "percent": round((v / total_complaints) * 100, 2) if total_complaints else 0.0,
            }
            for k, v in status_map.items()
        ]

        def _time_list(key: str, value_field: str = "count"):
            items = data.get(key, [])
            return [
                {"date": i["_id"]["date"], "value": float(i.get(value_field, 0))}
                for i in items
            ]

        status_transitions = [
            {"date": i["_id"]["date"], "status": i["_id"]["status"], "value": i["count"]}
            for i in data.get("status_transitions", [])
        ]

        def _distribution_list(key: str):
            return [{"label": i.get("_id") or "unknown", "value": int(i.get("count", 0))} for i in data.get(key, [])]

        area_distribution = _distribution_list("area_distribution")
        ward_distribution = _distribution_list("ward_distribution")
        region_distribution = _distribution_list("region_distribution")
        top_problem_areas = area_distribution[:10]

        area_resolution_rate = [
            {"label": i.get("_id") or "unknown", "value": round(float(i.get("rate", 0.0)), 2)}
            for i in data.get("area_resolution_rate", [])
        ]

        category_distribution = _distribution_list("category_distribution")
        category_resolution_time = [
            {"label": i.get("_id") or "unknown", "value": round(float(i.get("avg_hours", 0.0)), 2)}
            for i in data.get("category_resolution_time", [])
        ]

        user_rows = data.get("user_complaints", [])
        user_complaints = [
            {"id": str(i.get("_id")), "label": str(i.get("_id")), "value": int(i.get("count", 0))}
            for i in user_rows
        ]
        top_complainants = user_complaints[:10]
        repeat_complainants = len([u for u in user_rows if int(u.get("count", 0)) > 1])

        assignee_rows = data.get("assignee_distribution", [])
        assignee_distribution = [
            {"id": str(i.get("_id")), "label": str(i.get("_id")), "value": int(i.get("count", 0)), "resolution_rate_pct": 0.0}
            for i in assignee_rows
        ]

        assignee_resolution_rate = [
            {"id": str(i.get("_id")), "label": str(i.get("_id")), "value": int(i.get("total", 0)), "resolution_rate_pct": round(float(i.get("rate", 0.0)), 2)}
            for i in data.get("assignee_resolution_rate", [])
        ]

        workload_distribution = assignee_distribution

        heatmap = [
            {
                "ward": i.get("_id", {}).get("ward") or "",
                "area": i.get("_id", {}).get("area") or "",
                "count": int(i.get("count", 0)),
            }
            for i in data.get("heatmap", [])
        ]

        now = datetime.utcnow()
        sla_ms = sla_hours * 3600000
        sla_breach_count = await self.collection.count_documents({
            **match,
            "$or": [
                {
                    "resolved_at": {"$ne": None},
                    "$expr": {"$gt": [{"$subtract": ["$resolved_at", "$created_at"]}, sla_ms]},
                },
                {
                    "resolved_at": None,
                    "$expr": {"$gt": [{"$subtract": [now, "$created_at"]}, sla_ms]},
                },
            ],
        })

        resolved_within_sla = await self.collection.count_documents({
            **match,
            "resolved_at": {"$ne": None},
            "$expr": {"$lte": [{"$subtract": ["$resolved_at", "$created_at"]}, sla_ms]},
        })
        resolution_efficiency_pct = round((resolved_within_sla / resolved_count) * 100, 2) if resolved_count else 0.0

        return {
            "summary": {
                "total_complaints": total_complaints,
                "pending": status_map.get("pending", 0),
                "in_progress": status_map.get("in_progress", 0),
                "resolved": status_map.get("resolved", 0),
                "rejected": status_map.get("rejected", 0),
                "closed": status_map.get("closed", 0),
                "acknowledged": status_map.get("acknowledged", 0),
                "resolution_rate_pct": resolution_rate_pct,
                "avg_resolution_time_hours": round(avg_resolution_time_hours, 2),
            },
            "status_counts": status_distribution,
            "status_transitions": status_transitions,
            "complaints_over_time_daily": _time_list("daily_trend"),
            "complaints_over_time_weekly": _time_list("weekly_trend"),
            "complaints_over_time_monthly": _time_list("monthly_trend"),
            "resolution_trend": _time_list("resolution_trend"),
            "avg_resolution_time_trend": [
                {"date": i["_id"]["date"], "value": float(i.get("avg_hours", 0.0))}
                for i in data.get("avg_resolution_time_trend", [])
            ],
            "peak_hours": [{"label": str(i.get("_id")), "value": int(i.get("count", 0))} for i in data.get("peak_hours", [])],
            "peak_days": [{"label": str(i.get("_id")), "value": int(i.get("count", 0))} for i in data.get("peak_days", [])],
            "area_distribution": area_distribution,
            "ward_distribution": ward_distribution,
            "region_distribution": region_distribution,
            "top_problem_areas": top_problem_areas,
            "area_resolution_rate": area_resolution_rate,
            "category_distribution": category_distribution,
            "category_resolution_time": category_resolution_time,
            "user_complaints": user_complaints,
            "top_complainants": top_complainants,
            "repeat_complainants": repeat_complainants,
            "complaint_frequency_trend": _time_list("daily_trend"),
            "avg_handling_time_hours": round(avg_handling_time_hours, 2),
            "resolution_efficiency_pct": resolution_efficiency_pct,
            "pending_backlog_trend": _time_list("pending_backlog_trend"),
            "sla_breach_count": sla_breach_count,
            "assignee_distribution": assignee_distribution,
            "assignee_resolution_rate": assignee_resolution_rate,
            "workload_distribution": workload_distribution,
            "heatmap": heatmap,
        }

    async def _notify_voter(self, user_id: str, title: str, message: str, complaint_id: str) -> None:
        if not user_id or not ObjectId.is_valid(user_id):
            return
        notifier = NotificationService()
        await notifier.notify(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=NotificationType.COMPLAINT_UPDATE.value,
            related_resource_id=complaint_id,
            related_resource_type="complaint",
        )

    async def _increment_leader_metric(self, leader_id: str, field: str) -> None:
        if not ObjectId.is_valid(leader_id):
            return
        await self.users_collection.update_one(
            {"_id": ObjectId(leader_id)},
            {"$inc": {field: 1}},
        )

    @staticmethod
    def _audit_entry(status_from: str, status_to: str, changed_by: str, reason: str | None = None) -> dict:
        return {
            "status_from": status_from,
            "status_to": status_to,
            "changed_by": changed_by,
            "reason": reason,
            "changed_at": datetime.utcnow(),
        }

    @staticmethod
    def _is_within_territory(location: dict, territory: dict) -> bool:
        if not territory:
            return True
        for key in ("state", "city", "ward", "area"):
            t_val = territory.get(key)
            l_val = location.get(key)
            if t_val and l_val:
                # Normalize: lowercase and remove "ward-" prefix for comparison
                t_norm = str(t_val).lower().replace("ward-", "").strip()
                l_norm = str(l_val).lower().replace("ward-", "").strip()
                if t_norm != l_norm:
                    return False
        return True

    async def _save_complaint_file(self, upload_file: UploadFile):
        if not upload_file.filename:
            raise ValueError("File must have a filename")

        filename = upload_file.filename
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in _COMPLAINT_ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(_COMPLAINT_ALLOWED_EXTENSIONS.keys()))
            raise ValueError(
                f"File type '.{ext}' is not allowed. Allowed types: {allowed}"
            )

        content = await upload_file.read()
        await upload_file.close()

        if not content:
            raise ValueError("File is empty")
        if len(content) > _COMPLAINT_MAX_FILE_SIZE:
            raise ValueError("File size exceeds 10MB limit")

        app_dir = Path(__file__).resolve().parents[1]
        upload_dir = app_dir / "static" / "complaints"
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid4().hex}.{ext}"
        file_path = upload_dir / safe_name
        file_path.write_bytes(content)

        file_url = f"/static/complaints/{safe_name}"
        file_type = _COMPLAINT_ALLOWED_EXTENSIONS[ext]
        return file_url, file_type, filename

    @staticmethod
    def _normalize_doc(doc: dict) -> dict:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])

        date_fields = [
            "created_at",
            "assigned_at",
            "acknowledged_at",
            "first_field_visit_at",
            "resolved_at",
            "escalated_at",
            "image_uploaded_at",
            "file_uploaded_at",
            "declined_at",
            "verification_requested_at",
            "status_updated_at",
            "feedback_given_at",
        ]
        for field in date_fields:
            value = doc.get(field)
            if isinstance(value, datetime):
                doc[field] = value.isoformat()

        if "notes" in doc and isinstance(doc["notes"], list):
            for note in doc["notes"]:
                if isinstance(note.get("added_at"), datetime):
                    note["added_at"] = note["added_at"].isoformat()

        if "audit_trail" in doc and isinstance(doc["audit_trail"], list):
            for entry in doc["audit_trail"]:
                if isinstance(entry.get("changed_at"), datetime):
                    entry["changed_at"] = entry["changed_at"].isoformat()

        return doc
