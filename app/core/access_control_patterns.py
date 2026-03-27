"""
Service-Layer Access Control Patterns
======================================
Implements data isolation and ownership verification for VOTER and OPS roles.
These patterns MUST be applied in service layers beyond permission-based checks.

Author: Political Communication Platform Team
"""

from typing import Optional, List
from bson import ObjectId
from app.core.roles import UserRole
from app.db.mongodb import get_database
import logging

logger = logging.getLogger(__name__)


class VoterAccessControl:
    """
    Data isolation patterns for VOTER role.
    Voters can only access their own complaints, appointments, and feedback.
    """
    
    @staticmethod
    async def verify_complaint_ownership(
        voter_user_id: str,
        complaint_id: str,
        db=None
    ) -> bool:
        """
        Verify that a voter owns a complaint before allowing view/update.
        
        Args:
            voter_user_id: The voter's user ID
            complaint_id: The complaint ObjectId to check
            db: Database connection
            
        Returns:
            bool: True if voter created this complaint, False otherwise
        """
        if not db:
            db = get_database()
            
        try:
            complaint = await db.complaints.find_one({
                "_id": ObjectId(complaint_id),
                "created_by": ObjectId(voter_user_id)
            })
            return complaint is not None
        except Exception as e:
            logger.error(f"Error verifying complaint ownership: {e}")
            return False
    
    
    @staticmethod
    async def verify_appointment_ownership(
        voter_user_id: str,
        appointment_id: str,
        db=None
    ) -> bool:
        """
        Verify that a voter owns an appointment before allowing view/update.
        
        Args:
            voter_user_id: The voter's user ID
            appointment_id: The appointment ObjectId to check
            db: Database connection
            
        Returns:
            bool: True if voter requested this appointment, False otherwise
        """
        if not db:
            db = get_database()
            
        try:
            appointment = await db.appointments.find_one({
                "_id": ObjectId(appointment_id),
                "requested_by": ObjectId(voter_user_id)
            })
            return appointment is not None
        except Exception as e:
            logger.error(f"Error verifying appointment ownership: {e}")
            return False
    
    
    @staticmethod
    async def verify_feedback_ownership(
        voter_user_id: str,
        feedback_id: str,
        db=None
    ) -> bool:
        """
        Verify that a voter owns feedback before allowing view.
        
        Args:
            voter_user_id: The voter's user ID
            feedback_id: The feedback ObjectId to check
            db: Database connection
            
        Returns:
            bool: True if voter created this feedback, False otherwise
        """
        if not db:
            db = get_database()
            
        try:
            feedback = await db.feedback.find_one({
                "_id": ObjectId(feedback_id),
                "created_by": ObjectId(voter_user_id)
            })
            return feedback is not None
        except Exception as e:
            logger.error(f"Error verifying feedback ownership: {e}")
            return False
    
    
    @staticmethod
    async def get_voter_complaints(
        voter_user_id: str,
        db=None,
        skip: int = 0,
        limit: int = 20
    ) -> List:
        """
        Retrieve all complaints created by a voter.
        Service should use this for pagination in voter-scoped endpoints.
        
        Args:
            voter_user_id: The voter's user ID
            db: Database connection
            skip: Pagination skip
            limit: Pagination limit
            
        Returns:
            List of complaint documents owned by this voter
        """
        if not db:
            db = get_database()
            
        try:
            complaints = await db.complaints.find({
                "created_by": ObjectId(voter_user_id)
            }).skip(skip).limit(limit).to_list(length=limit)
            return complaints
        except Exception as e:
            logger.error(f"Error retrieving voter complaints: {e}")
            return []
    
    
    @staticmethod
    async def get_voter_appointments(
        voter_user_id: str,
        db=None,
        skip: int = 0,
        limit: int = 20
    ) -> List:
        """
        Retrieve all appointments requested by a voter.
        
        Args:
            voter_user_id: The voter's user ID
            db: Database connection
            skip: Pagination skip
            limit: Pagination limit
            
        Returns:
            List of appointment documents requested by this voter
        """
        if not db:
            db = get_database()
            
        try:
            appointments = await db.appointments.find({
                "requested_by": ObjectId(voter_user_id)
            }).skip(skip).limit(limit).to_list(length=limit)
            return appointments
        except Exception as e:
            logger.error(f"Error retrieving voter appointments: {e}")
            return []


class LeaderAccessControl:
    """
    Data isolation patterns for LEADER role.
    Leaders can only access complaints and feedback from their assigned territory.
    """
    
    @staticmethod
    async def get_leader_territory(
        leader_user_id: str,
        db=None
    ) -> Optional[str]:
        """
        Retrieve the territory assigned to a leader.
        
        Args:
            leader_user_id: The leader's user ID
            db: Database connection
            
        Returns:
            Territory ID if assigned, None otherwise
        """
        if not db:
            db = get_database()
            
        try:
            leader = await db.users.find_one({
                "_id": ObjectId(leader_user_id),
                "role": "leader"
            })
            return leader.get("assigned_territory") if leader else None
        except Exception as e:
            logger.error(f"Error retrieving leader territory: {e}")
            return None
    
    
    @staticmethod
    async def verify_territory_access(
        leader_user_id: str,
        territory_id: str,
        db=None
    ) -> bool:
        """
        Verify that a leader can access resources in a specific territory.
        
        Args:
            leader_user_id: The leader's user ID
            territory_id: The territory to check
            db: Database connection
            
        Returns:
            bool: True if leader is assigned to this territory
        """
        assigned_territory = await LeaderAccessControl.get_leader_territory(
            leader_user_id, db
        )
        return assigned_territory == territory_id if assigned_territory else False
    
    
    @staticmethod
    async def get_leader_complaints(
        leader_user_id: str,
        db=None,
        skip: int = 0,
        limit: int = 20
    ) -> List:
        """
        Retrieve complaints from a leader's assigned territory.
        
        Args:
            leader_user_id: The leader's user ID
            db: Database connection
            skip: Pagination skip
            limit: Pagination limit
            
        Returns:
            List of complaints from assigned territory
        """
        if not db:
            db = get_database()
        
        territory = await LeaderAccessControl.get_leader_territory(leader_user_id, db)
        if not territory:
            return []
        
        try:
            complaints = await db.complaints.find({
                "territory": territory
            }).skip(skip).limit(limit).to_list(length=limit)
            return complaints
        except Exception as e:
            logger.error(f"Error retrieving leader complaints: {e}")
            return []


class OpsAccessControl:
    """
    Data isolation and audit patterns for OPS role.
    OPS has comprehensive read/update access but no create/delete.
    All modifications must be logged for audit trails.
    """
    
    @staticmethod
    async def log_ops_action(
        ops_user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        changes: dict = None,
        db=None
    ) -> bool:
        """
        Log all OPS modifications for audit trail.
        
        Args:
            ops_user_id: The OPS user making the change
            action: Action performed (e.g., "UPDATE_STATUS", "ASSIGN", "RESOLVE")
            resource_type: Type of resource (e.g., "complaint", "appointment")
            resource_id: ID of the resource modified
            changes: Dictionary of fields changed
            db: Database connection
            
        Returns:
            bool: True if logged successfully
        """
        if not db:
            db = get_database()
        
        try:
            await db.audit_logs.insert_one({
                "ops_user_id": ObjectId(ops_user_id),
                "action": action,
                "resource_type": resource_type,
                "resource_id": ObjectId(resource_id),
                "changes": changes or {},
                "timestamp": __import__("datetime").datetime.utcnow()
            })
            logger.info(
                f"Audit logged: OPS {ops_user_id} performed {action} "
                f"on {resource_type} {resource_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Error logging OPS action: {e}")
            return False
    
    
    @staticmethod
    async def get_ops_complaints(
        status_filter: Optional[str] = None,
        db=None,
        skip: int = 0,
        limit: int = 20
    ) -> List:
        """
        Retrieve complaints visible to OPS console (all complaints).
        Optionally filter by status.
        
        Args:
            status_filter: Optional status filter (e.g., "open", "resolved", "pending")
            db: Database connection
            skip: Pagination skip
            limit: Pagination limit
            
        Returns:
            List of complaints matching criteria
        """
        if not db:
            db = get_database()
        
        query = {}
        if status_filter:
            query["status"] = status_filter
        
        try:
            complaints = await db.complaints.find(query).skip(skip).limit(limit).to_list(length=limit)
            return complaints
        except Exception as e:
            logger.error(f"Error retrieving OPS complaints: {e}")
            return []
    
    
    @staticmethod
    async def get_ops_appointments(
        status_filter: Optional[str] = None,
        db=None,
        skip: int = 0,
        limit: int = 20
    ) -> List:
        """
        Retrieve all appointments visible to OPS console.
        
        Args:
            status_filter: Optional status filter
            db: Database connection
            skip: Pagination skip
            limit: Pagination limit
            
        Returns:
            List of appointments matching criteria
        """
        if not db:
            db = get_database()
        
        query = {}
        if status_filter:
            query["status"] = status_filter
        
        try:
            appointments = await db.appointments.find(query).skip(skip).limit(limit).to_list(length=limit)
            return appointments
        except Exception as e:
            logger.error(f"Error retrieving OPS appointments: {e}")
            return []


# Route-level usage patterns
"""
EXAMPLE: Voter complaint retrieval

from fastapi import APIRouter, Depends
from app.api.dependencies import get_current_user, require_permission, get_paginated_params
from app.core.permissions import Permission
from app.services.access_control import VoterAccessControl

router = APIRouter()

@router.get("/complaints")
async def get_my_complaints(
    current_user: CurrentUser = Depends(require_permission(Permission.VIEW_COMPLAINT)),
    paginated = Depends(get_paginated_params),
    db = Depends(get_database)
):
    # current_user is already verified to have VIEW_COMPLAINT permission
    # Service layer applies voter-specific scoping
    skip, limit = paginated
    complaints = await VoterAccessControl.get_voter_complaints(
        current_user.user_id, db, skip, limit
    )
    return {"data": complaints}


EXAMPLE: OPS complaint status update with audit logging

@router.patch("/complaints/{complaint_id}/status")
async def update_complaint_status(
    complaint_id: str,
    new_status: str,
    current_user: CurrentUser = Depends(require_permission(Permission.UPDATE_COMPLAINT_STATUS)),
    db = Depends(get_database)
):
    # current_user is already verified to have UPDATE_COMPLAINT_STATUS permission
    # OPS role has this permission; voters/leaders do not
    
    # Update complaint
    result = await db.complaints.update_one(
        {"_id": ObjectId(complaint_id)},
        {"$set": {"status": new_status}}
    )
    
    # Log the action for audit trail
    await OpsAccessControl.log_ops_action(
        current_user.user_id,
        action="UPDATE_STATUS",
        resource_type="complaint",
        resource_id=complaint_id,
        changes={"status": new_status},
        db=db
    )
    
    return {"success": result.modified_count > 0}
"""