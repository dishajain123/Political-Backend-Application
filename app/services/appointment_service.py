"""
Appointment Service
===================
Business logic for complete appointment lifecycle with notifications and RBAC enforcement.

CRITICAL VOTER RULES:
- Voters can ONLY view their own appointments (as requester or requested)
- Voters can REQUEST appointments but NOT approve
- Voters can CANCEL their own appointments (as requester only)
- Voters CANNOT reschedule, complete, or view others' appointments
- Voters CANNOT see corporator calendar

CRITICAL OPS RULES:
- OPS can view all appointments (like Corporator)
- OPS can approve, reject, reschedule, complete appointments
- OPS has same permissions as Corporator for appointment management

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional
from bson import ObjectId
from app.db.mongodb import get_database
from app.schemas.appointment_schema import (
    AppointmentCreate,
    AppointmentUpdate,
    AppointmentResponse,
    AppointmentListResponse,
    AppointmentApproveRequest,
)
from app.api.dependencies import CurrentUser
from app.utils.enums import AppointmentStatus, AppointmentReason
from app.core.roles import UserRole
from app.services.notification_service import NotificationService
from app.utils.enums import NotificationType
import math
import logging

logger = logging.getLogger(__name__)


class AppointmentService:
    """Handles complete appointment lifecycle with notifications and data isolation"""

    def __init__(self):
        self.collection = get_database().appointments
        self.users_collection = get_database().users

    async def create(
        self, payload: AppointmentCreate, user: CurrentUser
    ) -> AppointmentResponse:
        """
        Create an appointment request (Voter/Leader).
        
        CRITICAL VALIDATIONS:
        - Appointment date must be in future
        - Requested user must exist
        - Check for duplicate pending requests
        """
        # VALIDATE: Appointment date is in future
        now = datetime.utcnow()
        if payload.appointment_date <= now:
            raise ValueError("Appointment date must be in the future")
        
        # VALIDATE: Requested user exists
        requested_with = await self.users_collection.find_one(
            {"_id": ObjectId(payload.requested_with)}
        )
        if not requested_with:
            raise ValueError("Requested user not found")
        if requested_with.get("role") not in [UserRole.LEADER.value, UserRole.CORPORATOR.value]:
            raise ValueError("Appointments can only be requested with leaders or corporators")
        
        # PREVENT DUPLICATES: Check for pending request from same users
        existing = await self.collection.find_one({
            "requested_by": user.user_id,
            "requested_with": payload.requested_with,
            "status": {"$in": [AppointmentStatus.REQUESTED.value, AppointmentStatus.APPROVED.value]},
        })
        if existing:
            raise ValueError("You already have a pending appointment with this user")
        
        # CREATE: Generate appointment ID
        count = await self.collection.count_documents({})
        appointment_id = f"APPT-{datetime.utcnow().year}-{count + 1:04d}"
        
        doc = {
            "appointment_id": appointment_id,
            "requested_by": user.user_id,
            "requested_with": payload.requested_with,
            "reason": payload.reason.value if hasattr(payload.reason, 'value') else payload.reason,
            "description": payload.description,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "appointment_date": payload.appointment_date,
            "duration_minutes": payload.duration_minutes,
            "location": payload.location,
            "urgency_level": payload.urgency_level if hasattr(payload, "urgency_level") else "normal",
            "status": AppointmentStatus.REQUESTED.value,
            "status_updated_at": datetime.utcnow(),
            "approved_or_rejected_by": None,
            "approved_or_rejected_at": None,
            "rejection_reason": None,
            "reschedule_count": 0,
            "new_appointment_date": None,
            "reschedule_reason": None,
            "completed_at": None,
            "attendees": [],
            "meeting_notes": None,
            "cancelled_at": None,
            "cancelled_by": None,
            "cancellation_reason": None,
            "feedback": None,
            "reminder_sent": False,
            "reminder_sent_at": None,
            "is_priority": payload.is_priority if hasattr(payload, 'is_priority') else False,
            "tags": payload.tags if hasattr(payload, 'tags') else [],
            "linked_complaint_id": payload.linked_complaint_id if hasattr(payload, 'linked_complaint_id') else None,
        }
        
        result = await self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        # 4. Trigger Notifications
        # Notify the Leader/Corporator (requested_with)
        await self._notify(
            user_id=payload.requested_with,
            title="New Appointment Request",
            message=f"You have a new appointment request ({doc['appointment_id']}).",
        )
        # Notify the Requester (voter - confirmation)
        await self._notify(
            user_id=user.user_id,
            title="Appointment Request Sent",
            message=f"Your appointment request ({doc['appointment_id']}) has been sent successfully.",
        )
        
        logger.info(f"Appointment created: {appointment_id} by user {user.user_id}")
        doc = await self._attach_user_names(doc)
        return AppointmentResponse(**self._normalize_doc(doc))

    async def approve(
        self, 
        appointment_id: str, 
        user: CurrentUser,
        payload: Optional[AppointmentApproveRequest] = None
    ) -> AppointmentResponse:
        """
        Approve an appointment request with optional refinements.
        """
        appointment = await self._get_appointment(appointment_id)
        
        # VALIDATE: Only requested_with (Leader/Corporator) can approve
        if appointment["requested_with"] != user.user_id:
            logger.warning(
                f"Unauthorized approve attempt: user {user.user_id} "
                f"tried to approve appointment {appointment_id} "
                f"(requested with {appointment['requested_with']})"
            )
            # Exception for OPS/Corporator?
            if user.role not in [UserRole.CORPORATOR.value, UserRole.OPS.value]:
                raise ValueError("Unauthorized to approve this appointment")
        
        # VALIDATE: Status must be requested
        if appointment["status"] != AppointmentStatus.REQUESTED.value:
            raise ValueError(f"Only appointments in {AppointmentStatus.REQUESTED.value} status can be approved")
        
        # PREPARE UPDATE
        update_data = {
            "status": AppointmentStatus.APPROVED.value,
            "approved_or_rejected_by": user.user_id,
            "approved_or_rejected_at": datetime.utcnow(),
            "status_updated_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
        
        # Optional modifications during approval
        message_extras = ""
        if payload:
            if payload.appointment_date:
                update_data["appointment_date"] = payload.appointment_date
                message_extras += f" (New slot: {payload.appointment_date.isoformat()})"
            if payload.location:
                update_data["location"] = payload.location
                message_extras += f" (Location: {payload.location})"
            if payload.notes:
                update_data["notes"] = payload.notes
        
        # UPDATE
        await self.collection.update_one(
            {"_id": appointment["_id"]},
            {"$set": update_data}
        )
        
        # NOTIFY
        # Notify the Requester
        await self._notify(
            user_id=appointment["requested_by"],
            title="Appointment Approved",
            message=(
                f"Your appointment request ({appointment['appointment_id']}) has been approved "
                f"by {user.full_name}.{message_extras}"
            ),
        )
        
        logger.info(f"Appointment {appointment_id} approved by {user.user_id}")
        appointment.update(update_data)
        appointment = await self._attach_user_names(appointment)
        return AppointmentResponse(**self._normalize_doc(appointment))
        
    async def reject(
        self, appointment_id: str, rejection_reason: str, user: CurrentUser
    ) -> AppointmentResponse:
        """
        Reject an appointment request with reason.
        
        CRITICAL:
        - Only requested_with user can reject
        - Must provide rejection reason
        """
        appointment = await self._get_appointment(appointment_id)
        
        # VALIDATE: Only requested_with can reject (Corporator/OPS can manage all)
        if user.role not in [UserRole.CORPORATOR, UserRole.OPS] and appointment["requested_with"] != user.user_id:
            logger.warning(
                f"Unauthorized rejection attempt: user {user.user_id} "
                f"tried to reject appointment {appointment_id}"
            )
            raise ValueError("Only the requested user can reject this appointment")
        
        # VALIDATE: Status is REQUESTED
        if appointment["status"] != AppointmentStatus.REQUESTED.value:
            raise ValueError(f"Cannot reject appointment with status: {appointment['status']}")
        
        # VALIDATE: Rejection reason provided
        if not rejection_reason or len(rejection_reason.strip()) == 0:
            raise ValueError("Rejection reason is required")
        
        # REJECT: Update status
        result = await self.collection.find_one_and_update(
            {"appointment_id": appointment_id},
            {
                "$set": {
                    "status": "rejected",
                    "approved_or_rejected_by": user.user_id,
                    "approved_or_rejected_at": datetime.utcnow(),
                    "rejection_reason": rejection_reason,
                    "status_updated_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
            return_document=True,
        )
        
        # TRIGGER: Send notification to requester with reason
        await self._notify(
            user_id=appointment["requested_by"],
            title="Appointment Rejected",
            message=f"Your appointment {appointment_id} was rejected: {rejection_reason}",
        )
        
        logger.info(f"Appointment {appointment_id} rejected by {user.user_id}")
        result = await self._attach_user_names(result)
        return AppointmentResponse(**self._normalize_doc(result))

    async def reschedule(
        self, appointment_id: str, new_date: datetime, reason: Optional[str], user: CurrentUser
    ) -> AppointmentResponse:
        """
        Reschedule an approved appointment.
        
        CRITICAL:
        - Only requested_with user can reschedule
        - VOTERS CANNOT reschedule
        - New date must be in future
        """
        appointment = await self._get_appointment(appointment_id)
        
        # VALIDATE: Can reschedule only REQUESTED/APPROVED/RESCHEDULED appointments
        if appointment["status"] not in {
            AppointmentStatus.REQUESTED.value,
            AppointmentStatus.APPROVED.value,
            AppointmentStatus.RESCHEDULED.value,
        }:
            raise ValueError("Can only reschedule requested or approved appointments")
        
        # CRITICAL: Only requested_with can reschedule (Corporator/OPS can manage all)
        if user.role not in [UserRole.CORPORATOR, UserRole.OPS] and appointment["requested_with"] != user.user_id:
            logger.warning(
                f"Unauthorized reschedule attempt: user {user.user_id} "
                f"tried to reschedule appointment {appointment_id}"
            )
            raise ValueError("Only the requested user can reschedule this appointment")
        
        # VALIDATE: New date is in future
        if new_date <= datetime.utcnow():
            raise ValueError("New appointment date must be in the future")
        
        clean_reason = reason.strip() if isinstance(reason, str) and reason.strip() else None
        # RESCHEDULE: Update with new date
        result = await self.collection.find_one_and_update(
            {"appointment_id": appointment_id},
            {
                "$set": {
                    "status": AppointmentStatus.RESCHEDULED.value,
                    "appointment_date": new_date,
                    "new_appointment_date": new_date,
                    "reschedule_reason": clean_reason,
                    "reschedule_count": appointment.get("reschedule_count", 0) + 1,
                    "status_updated_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
            return_document=True,
        )
        
        # TRIGGER: Send notification to requester
        note = f" Note: {clean_reason}" if clean_reason else ""
        await self._notify(
            user_id=appointment["requested_by"],
            title="Appointment Rescheduled",
            message=f"Appointment {appointment_id} was rescheduled to {new_date.isoformat()}.{note}",
        )
        
        logger.info(f"Appointment {appointment_id} rescheduled by {user.user_id}")
        result = await self._attach_user_names(result)
        return AppointmentResponse(**self._normalize_doc(result))

    async def complete(
        self, appointment_id: str, attendees: list, meeting_notes: str, user: CurrentUser
    ) -> AppointmentResponse:
        """
        Mark appointment as completed (after meeting).
        
        CRITICAL:
        - Only requested_with can mark complete
        - Record attendees and notes
        """
        appointment = await self._get_appointment(appointment_id)
        
        # CRITICAL: Only requested_with can mark complete (Corporator/OPS can manage all)
        if user.role not in [UserRole.CORPORATOR, UserRole.OPS] and appointment["requested_with"] != user.user_id:
            logger.warning(
                f"Unauthorized complete attempt: user {user.user_id} "
                f"tried to mark appointment {appointment_id} as complete"
            )
            raise ValueError("Only the appointed user can mark appointment as complete")
        
        # COMPLETE: Update status and details
        result = await self.collection.find_one_and_update(
            {"appointment_id": appointment_id},
            {
                "$set": {
                    "status": AppointmentStatus.COMPLETED.value,
                    "completed_at": datetime.utcnow(),
                    "attendees": attendees,
                    "meeting_notes": meeting_notes,
                    "status_updated_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
            return_document=True,
        )
        
        other_user = appointment["requested_by"]
        await self._notify(
            user_id=other_user,
            title="Appointment Completed",
            message=f"Appointment {appointment_id} has been marked completed.",
        )
        
        logger.info(f"Appointment {appointment_id} completed by {user.user_id}")
        result = await self._attach_user_names(result)
        return AppointmentResponse(**self._normalize_doc(result))

    async def cancel(
        self, appointment_id: str, cancellation_reason: str, user: CurrentUser
    ) -> AppointmentResponse:
        """
        Cancel an appointment.
        
        CRITICAL VOTER ISOLATION:
        - VOTERS can only cancel their OWN appointments (as requester)
        - Requested_with can cancel any appointment
        - Must provide reason
        - Cannot cancel completed appointments
        """
        appointment = await self._get_appointment(appointment_id)
        
        # VOTER DATA ISOLATION: Voters can only cancel their own appointments
        if user.role == UserRole.VOTER:
            if appointment["requested_by"] != user.user_id:
                logger.warning(
                    f"Unauthorized cancellation attempt: voter {user.user_id} "
                    f"tried to cancel appointment {appointment_id} they didn't request"
                )
                raise ValueError("You can only cancel appointments you requested")
        else:
            # Leader/Corporator/OPS: Can cancel if they are one of the participants
            if user.user_id not in [appointment["requested_by"], appointment["requested_with"]]:
                raise ValueError("Only appointment participants can cancel")
        
        # VALIDATE: Cannot cancel completed
        if appointment["status"] == AppointmentStatus.COMPLETED.value:
            raise ValueError("Cannot cancel completed appointment")
        
        # VALIDATE: Reason provided
        if not cancellation_reason or len(cancellation_reason.strip()) == 0:
            raise ValueError("Cancellation reason is required")
        
        # CANCEL: Update status
        result = await self.collection.find_one_and_update(
            {"appointment_id": appointment_id},
            {
                "$set": {
                    "status": AppointmentStatus.CANCELLED.value,
                    "cancelled_at": datetime.utcnow(),
                    "cancelled_by": user.user_id,
                    "cancellation_reason": cancellation_reason,
                    "status_updated_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
            return_document=True,
        )
        
        other_user = appointment["requested_with"] if appointment["requested_by"] == user.user_id else appointment["requested_by"]
        await self._notify(
            user_id=other_user,
            title="Appointment Cancelled",
            message=f"Appointment {appointment_id} was cancelled: {cancellation_reason}",
        )
        
        logger.info(f"Appointment {appointment_id} cancelled by {user.user_id}")
        result = await self._attach_user_names(result)
        return AppointmentResponse(**self._normalize_doc(result))

    async def list(
        self,
        user: CurrentUser,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> AppointmentListResponse:
        """
        List appointments with RBAC enforcement.
        
        CRITICAL PRIVACY:
        - VOTER: sees own appointments only (as requester or requested)
        - LEADER: sees appointments where they are requested_with
        - CORPORATOR/OPS: sees all appointments
        """
        query = {}
        
        # RBAC: Build query based on role
        # Using string comparison for robustness across different object types
        role_str = str(user.role).lower()
        
        if role_str == UserRole.VOTER.value:
            # CRITICAL: Voters see ONLY their own appointments
            query = {
                "$or": [
                    {"requested_by": user.user_id},
                    {"requested_with": user.user_id},
                ]
            }
            logger.debug(f"Voter {user.user_id} listing own appointments")
        
        elif role_str == UserRole.LEADER.value:
            # Leader: sees appointments where they are either requested_with (as leader)
            # OR requested_by (acting as a voter/requester)
            query = {
                "$or": [
                    {"requested_with": user.user_id},
                    {"requested_by": user.user_id},
                ]
            }
        
        # Corporator and OPS see all (no filter)
        
        # Status filter
        if status:
            try:
                query["status"] = AppointmentStatus(status).value
            except ValueError:
                pass

        # Reason filter
        if reason:
            try:
                query["reason"] = AppointmentReason(reason).value
            except ValueError:
                pass
        
        # Pagination
        skip = (page - 1) * page_size
        
        # Count
        total = await self.collection.count_documents(query)
        
        # Fetch
        cursor = self.collection.find(query).sort("appointment_date", 1).skip(skip).limit(page_size)
        
        docs = []
        async for doc in cursor:
            docs.append(doc)

        if docs:
            user_ids = set()
            for doc in docs:
                requested_by = doc.get("requested_by")
                requested_with = doc.get("requested_with")
                if requested_by:
                    user_ids.add(requested_by)
                if requested_with:
                    user_ids.add(requested_with)

            user_map = await self._get_user_map(user_ids)
            for doc in docs:
                requested_by = doc.get("requested_by")
                requested_with = doc.get("requested_with")
                if requested_by in user_map:
                    doc["requested_by_name"] = user_map[requested_by].get("full_name")
                if requested_with in user_map:
                    doc["requested_with_name"] = user_map[requested_with].get("full_name")

        items = [AppointmentResponse(**self._normalize_doc(doc)) for doc in docs]
        
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0
        
        return AppointmentListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items,
        )

    async def _get_appointment(self, appointment_id: str) -> dict:
        """Helper: Get appointment by ID."""
        query = {"appointment_id": appointment_id}
        if ObjectId.is_valid(appointment_id):
            query = {"$or": [{"appointment_id": appointment_id}, {"_id": ObjectId(appointment_id)}]}
        appointment = await self.collection.find_one(query)
        if not appointment:
            raise ValueError("Appointment not found")
        return appointment

    async def get_by_id(self, appointment_id: str, user: CurrentUser) -> AppointmentResponse:
        """
        Get appointment with privacy enforcement.
        
        VOTER DATA ISOLATION:
        - Voters can only view their own appointments
        """
        appointment = await self._get_appointment(appointment_id)
        
        # CRITICAL: Voters can only view their own appointments
        if user.role == UserRole.VOTER:
            if user.user_id not in [appointment["requested_by"], appointment["requested_with"]]:
                logger.warning(
                    f"Unauthorized access attempt: voter {user.user_id} "
                    f"tried to access appointment {appointment_id}"
                )
                raise ValueError("Appointment not accessible")
        
        # Corporator/OPS can view all
        # Leader can view if involved
        elif user.role == UserRole.LEADER:
            if user.user_id not in [appointment["requested_by"], appointment["requested_with"]]:
                raise ValueError("Appointment not accessible")
        
        appointment = await self._attach_user_names(appointment)
        return AppointmentResponse(**self._normalize_doc(appointment))

    async def _notify(self, user_id: str, title: str, message: str) -> None:
        """Send notification to user about appointment."""
        notifier = NotificationService()
        await notifier.notify(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=NotificationType.APPOINTMENT_UPDATE.value,
        )

    async def _get_user_map(self, user_ids: set) -> dict:
        """Fetch user records and build id -> user map."""
        if not user_ids:
            return {}
        object_ids = [ObjectId(uid) for uid in user_ids if ObjectId.is_valid(uid)]
        if not object_ids:
            return {}
        cursor = self.users_collection.find(
            {"_id": {"$in": object_ids}},
            {"full_name": 1},
        )
        user_map = {}
        async for user in cursor:
            user_map[str(user["_id"])] = user
        return user_map

    async def _attach_user_names(self, doc: dict) -> dict:
        """Attach requester/recipient names to appointment doc."""
        requested_by = doc.get("requested_by")
        requested_with = doc.get("requested_with")
        user_ids = {uid for uid in (requested_by, requested_with) if uid}
        user_map = await self._get_user_map(user_ids)
        if requested_by in user_map:
            doc["requested_by_name"] = user_map[requested_by].get("full_name")
        if requested_with in user_map:
            doc["requested_with_name"] = user_map[requested_with].get("full_name")
        return doc

    @staticmethod
    def _normalize_doc(doc: dict) -> dict:
        """Normalize Mongo document for response."""
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        for key in ("appointment_date", "new_appointment_date", "created_at", "updated_at", "status_updated_at", "approved_or_rejected_at", "completed_at", "cancelled_at", "reminder_sent_at"):
            value = doc.get(key)
            if isinstance(value, datetime):
                doc[key] = value.isoformat()
        return doc
