"""
Role Definitions Module
======================
Defines all user roles in the system as enums and constants.
These roles form the basis of the role-based access control (RBAC) system.

Author: Political Communication Platform Team
"""

from enum import Enum


class UserRole(str, Enum):
    """
    Enumeration of all user roles in the platform.
    Each role has specific permissions defined in permissions.py
    """

    CORPORATOR = "corporator"  # Top authority (MLA/MP/Party Head)
    LEADER = "leader"          # Field representatives
    VOTER = "voter"            # Citizens/followers
    OPS = "ops"                # Operations console users (admin/analyst)


# Role hierarchy (higher index = more authority)
# IMPORTANT: This hierarchy applies to route-level access control ONLY.
# OPS is intentionally EXCLUDED because it operates on a separate permission system
# (analytics/operations, not political authority).
# Corporator > Leader > Voter in political chain of command.
ROLE_HIERARCHY = {
    UserRole.VOTER: 0,
    UserRole.LEADER: 1,
    UserRole.CORPORATOR: 2,
}


def has_higher_or_equal_role(user_role: UserRole, required_role: UserRole) -> bool:
    """
    Check if user role has equal or higher authority than required role.
    
    IMPORTANT: OPS role is not part of the hierarchy and returns False
    for any hierarchy-based checks. OPS users must use permission-based checks instead.

    Args:
        user_role (UserRole): The user's current role
        required_role (UserRole): The minimum required role (from VOTER -> LEADER -> CORPORATOR)

    Returns:
        bool: True if user has sufficient authority in the political chain
              False if OPS role is involved (use permission-based access instead)

    Example:
        >>> has_higher_or_equal_role(UserRole.CORPORATOR, UserRole.LEADER)
        True
        >>> has_higher_or_equal_role(UserRole.VOTER, UserRole.LEADER)
        False
        >>> has_higher_or_equal_role(UserRole.OPS, UserRole.LEADER)
        False
    """

    # OPS is not part of political hierarchy - must use permission-based access
    if user_role == UserRole.OPS or required_role == UserRole.OPS:
        return False

    # Fail-safe: unknown roles should not get access
    if user_role not in ROLE_HIERARCHY or required_role not in ROLE_HIERARCHY:
        return False

    return ROLE_HIERARCHY[user_role] >= ROLE_HIERARCHY[required_role]


# Role display names for UI
ROLE_DISPLAY_NAMES = {
    UserRole.CORPORATOR: "Corporator/Head",
    UserRole.LEADER: "Leader",
    UserRole.VOTER: "Voter",
    UserRole.OPS: "Operations",
}


# Default role for new users
DEFAULT_ROLE = UserRole.VOTER