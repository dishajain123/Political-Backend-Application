"""
Permission Management Module
===========================
Defines granular permissions for each role across all features.
This module implements the role-based access control (RBAC) rules.

Author: Political Communication Platform Team
"""

from typing import Set, Dict, Union
from app.core.roles import UserRole


class Permission:
    """
    Permission constants for all system actions.
    Each permission represents a specific action in the system.
    """
    
    # Announcement permissions
    CREATE_ANNOUNCEMENT = "create_announcement"
    VIEW_ANNOUNCEMENT = "view_announcement"
    UPDATE_ANNOUNCEMENT = "update_announcement"
    DELETE_ANNOUNCEMENT = "delete_announcement"
    
    # Poll permissions
    CREATE_POLL = "create_poll"
    VIEW_POLL = "view_poll"
    PARTICIPATE_POLL = "participate_poll"
    VIEW_POLL_RESULTS = "view_poll_results"
    CLOSE_POLL = "close_poll"
    
    # Complaint permissions
    CREATE_COMPLAINT = "create_complaint"
    VIEW_COMPLAINT = "view_complaint"
    ASSIGN_COMPLAINT = "assign_complaint"
    UPDATE_COMPLAINT_STATUS = "update_complaint_status"
    ADD_COMPLAINT_NOTE = "add_complaint_note"
    RESOLVE_COMPLAINT = "resolve_complaint"
    VIEW_ALL_COMPLAINTS = "view_all_complaints"
    
    # Appointment permissions
    REQUEST_APPOINTMENT = "request_appointment"
    VIEW_APPOINTMENT = "view_appointment"
    APPROVE_APPOINTMENT = "approve_appointment"
    RESCHEDULE_APPOINTMENT = "reschedule_appointment"
    CANCEL_APPOINTMENT = "cancel_appointment"
    
    # Event permissions
    CREATE_EVENT = "create_event"
    VIEW_EVENT = "view_event"
    UPDATE_EVENT = "update_event"
    DELETE_EVENT = "delete_event"
    ASSIGN_EVENT_LEADER = "assign_event_leader"
    TRACK_EVENT_PARTICIPATION = "track_event_participation"
    
    # Feedback permissions
    CREATE_FEEDBACK = "create_feedback"
    VIEW_FEEDBACK = "view_feedback"
    VIEW_ALL_FEEDBACK = "view_all_feedback"
    
    # User management permissions
    CREATE_USER = "create_user"
    VIEW_USER = "view_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    ASSIGN_LEADER_TERRITORY = "assign_leader_territory"
    VIEW_USER_ANALYTICS = "view_user_analytics"
    
    # Notification permissions
    SEND_NOTIFICATION = "send_notification"
    VIEW_NOTIFICATION = "view_notification"
    
    # Analytics permissions
    VIEW_BASIC_ANALYTICS = "view_basic_analytics"
    VIEW_ADVANCED_ANALYTICS = "view_advanced_analytics"
    VIEW_VOTER_INTELLIGENCE = "view_voter_intelligence"
    VIEW_LEADER_PERFORMANCE = "view_leader_performance"
    VIEW_SENTIMENT_ANALYSIS = "view_sentiment_analysis"
    
    # Chat analytics permissions
    VIEW_CHAT_ANALYTICS = "view_chat_analytics"
    VIEW_BROADCAST_PERFORMANCE = "view_broadcast_performance"


# Role-Permission mapping
ROLE_PERMISSIONS: Dict[UserRole, Set[str]] = {
    
    # CORPORATOR: Top authority with strategic control
    UserRole.CORPORATOR: {
        # Announcements
        Permission.CREATE_ANNOUNCEMENT,
        Permission.VIEW_ANNOUNCEMENT,
        Permission.UPDATE_ANNOUNCEMENT,
        Permission.DELETE_ANNOUNCEMENT,
        
        # Polls
        Permission.CREATE_POLL,
        Permission.VIEW_POLL,
        Permission.VIEW_POLL_RESULTS,
        Permission.CLOSE_POLL,
        
        # Complaints (oversight)
        Permission.VIEW_ALL_COMPLAINTS,
        Permission.VIEW_COMPLAINT,
        Permission.ASSIGN_COMPLAINT,
        Permission.UPDATE_COMPLAINT_STATUS,
        Permission.RESOLVE_COMPLAINT,
        
        # Appointments
        Permission.VIEW_APPOINTMENT,
        Permission.APPROVE_APPOINTMENT,
        Permission.RESCHEDULE_APPOINTMENT,
        Permission.CANCEL_APPOINTMENT,
        
        # Events
        Permission.CREATE_EVENT,
        Permission.VIEW_EVENT,
        Permission.UPDATE_EVENT,
        Permission.DELETE_EVENT,
        Permission.ASSIGN_EVENT_LEADER,
        Permission.TRACK_EVENT_PARTICIPATION,
        
        # Feedback
        Permission.VIEW_ALL_FEEDBACK,
        Permission.VIEW_FEEDBACK,
        
        # User management
        Permission.CREATE_USER,
        Permission.VIEW_USER,
        Permission.UPDATE_USER,
        Permission.DELETE_USER,
        Permission.ASSIGN_LEADER_TERRITORY,
        
        # Notifications
        Permission.SEND_NOTIFICATION,
        Permission.VIEW_NOTIFICATION,
        
        # Analytics
        Permission.VIEW_BASIC_ANALYTICS,
        Permission.VIEW_ADVANCED_ANALYTICS,
        Permission.VIEW_VOTER_INTELLIGENCE,
        Permission.VIEW_LEADER_PERFORMANCE,
        Permission.VIEW_SENTIMENT_ANALYSIS,
        
        # Chat analytics
        Permission.VIEW_CHAT_ANALYTICS,
        Permission.VIEW_BROADCAST_PERFORMANCE,
    },
    
    # LEADER: Field execution with limited authority
    UserRole.LEADER: {
        # Announcements (share + local context)
        Permission.CREATE_ANNOUNCEMENT,
        Permission.VIEW_ANNOUNCEMENT,
        
        # Polls (can participate and view)
        Permission.VIEW_POLL,
        Permission.PARTICIPATE_POLL,
        Permission.VIEW_POLL_RESULTS,
        
        # Complaints (limited handling)
        Permission.CREATE_COMPLAINT,  # On behalf of assigned voters only (service-enforced)
        Permission.VIEW_COMPLAINT,  # Only assigned to them
        Permission.ADD_COMPLAINT_NOTE,
        Permission.UPDATE_COMPLAINT_STATUS,  # Limited status updates
        
        # Appointments
        Permission.REQUEST_APPOINTMENT,
        Permission.VIEW_APPOINTMENT,
        Permission.APPROVE_APPOINTMENT,
        Permission.RESCHEDULE_APPOINTMENT,
        
        # Events (view and participate)
        Permission.VIEW_EVENT,
        
        # Feedback
        Permission.CREATE_FEEDBACK,
        Permission.VIEW_FEEDBACK,
        
        # User management (limited)
        Permission.VIEW_USER,
        
        # Notifications
        Permission.VIEW_NOTIFICATION,
        
        # Analytics (basic only)
    },
    
    # VOTER: Citizens with participation rights
    UserRole.VOTER: {
        # Announcements (view only)
        Permission.VIEW_ANNOUNCEMENT,
        
        # Polls (participate)
        Permission.VIEW_POLL,
        Permission.PARTICIPATE_POLL,
        
        # Complaints (create and track own)
        Permission.CREATE_COMPLAINT,
        Permission.VIEW_COMPLAINT,  # Own complaints only (service-enforced)
        
        # Appointments (request)
        Permission.REQUEST_APPOINTMENT,
        Permission.VIEW_APPOINTMENT,  # Own appointments only (service-enforced)
        
        # Events (view)
        Permission.VIEW_EVENT,
        
        # Feedback (create)
        Permission.CREATE_FEEDBACK,
        Permission.VIEW_FEEDBACK,  # Own feedback only (service-enforced)
        
        # Notifications
        Permission.VIEW_NOTIFICATION,
    },
    
    # OPS: Operations and analytics console
    # NOTE: OPS role is NOT part of the political hierarchy (see roles.py)
    # OPS users access operations endpoints via permission-based checks only.
    # OPS has LIMITED CREATE/DELETE operations - can create users/corporators for system management.
    UserRole.OPS: {
        # Complaints (full management - read/update only, no delete)
        Permission.VIEW_ALL_COMPLAINTS,
        Permission.VIEW_COMPLAINT,
        Permission.ASSIGN_COMPLAINT,
        Permission.UPDATE_COMPLAINT_STATUS,
        Permission.RESOLVE_COMPLAINT,
        Permission.ADD_COMPLAINT_NOTE,
        
        # Feedback (full view - no modification)
        Permission.VIEW_ALL_FEEDBACK,
        Permission.VIEW_FEEDBACK,
        
        # Appointments (management)
        Permission.VIEW_APPOINTMENT,
        Permission.APPROVE_APPOINTMENT,
        Permission.RESCHEDULE_APPOINTMENT,
        
        # User management (create users/corporators, view and analytics)
        Permission.CREATE_USER,
        Permission.VIEW_USER,
        Permission.VIEW_USER_ANALYTICS,
        
        # Analytics (comprehensive access)
        Permission.VIEW_BASIC_ANALYTICS,
        Permission.VIEW_ADVANCED_ANALYTICS,
        Permission.VIEW_VOTER_INTELLIGENCE,
        Permission.VIEW_LEADER_PERFORMANCE,
        Permission.VIEW_SENTIMENT_ANALYSIS,
        
        # Chat analytics
        Permission.VIEW_CHAT_ANALYTICS,
        Permission.VIEW_BROADCAST_PERFORMANCE,
        
        # Notifications (view only)
        Permission.VIEW_NOTIFICATION,
    },
}


def has_permission(user_role: Union[UserRole, str], permission: str) -> bool:
    """
    Check if a role has a specific permission.
    
    Args:
        user_role (UserRole): The user's role
        permission (str): The permission to check
        
    Returns:
        bool: True if role has the permission
        
    Example:
        >>> has_permission(UserRole.CORPORATOR, Permission.CREATE_POLL)
        True
        >>> has_permission(UserRole.VOTER, Permission.CREATE_POLL)
        False
    """
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            return False

    return permission in ROLE_PERMISSIONS.get(user_role, set())


def get_role_permissions(user_role: Union[UserRole, str]) -> Set[str]:
    """
    Get all permissions for a specific role.
    
    Args:
        user_role (UserRole): The user's role
        
    Returns:
        Set[str]: Set of all permissions for the role
    """
    if isinstance(user_role, str):
        try:
            user_role = UserRole(user_role)
        except ValueError:
            return set()

    return ROLE_PERMISSIONS.get(user_role, set())
