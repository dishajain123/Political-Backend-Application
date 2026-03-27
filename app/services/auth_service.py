"""
Authentication Service Module
=============================
Business logic for authentication operations.
Handles user registration, login, token management, password reset.

Author: Political Communication Platform Team
"""

from typing import Optional, Dict, Any
from datetime import datetime
import logging
from bson import ObjectId

from app.db.mongodb import get_database
from app.core.security import (
    hash_password,
    verify_password,
    create_user_tokens,
)
from app.core.roles import UserRole
from app.utils.helpers import (
    validate_email,
    validate_mobile_number,
    utc_now,
)
from app.utils.enums import EngagementLevel


logger = logging.getLogger(__name__)


class AuthService:
    """
    Authentication service for user registration, login, and token management.
    
    Workflow Example:
        1. User registers with email, password, phone
        2. Service validates inputs and creates user document
        3. User logs in with email/phone and password
        4. Service verifies credentials and returns access + refresh tokens
        5. User can refresh token when it expires
    """
    
    @staticmethod
    async def register_voter(
        email: str,
        mobile_number: str,
        password: str,
        full_name: str,
        location: Dict[str, Any],
        language_preference: str = "en",
        family_adults: Optional[int] = None,
        family_kids: Optional[int] = None,
        demographics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Register a new voter with full profile data.
        
        Args:
            email (str): User's email address
            mobile_number (str): User's mobile number
            password (str): Plain text password
            full_name (str): User's full name
            location (Dict): Location information
            language_preference (str): Language preference
            family_adults (Optional[int]): Number of adults in family
            family_kids (Optional[int]): Number of kids in family
            demographics (Optional[Dict]): Demographic data (education, occupation, etc.)
            
        Returns:
            Dict[str, Any]: User document with tokens
            
        Raises:
            ValueError: If validation fails or user already exists
        """
        # Validate email format
        if not validate_email(email):
            raise ValueError("Invalid email format")
        
        # Validate mobile number format
        if not validate_mobile_number(mobile_number):
            raise ValueError("Invalid mobile number format")
        
        # Validate password strength
        AuthService._validate_password_strength(password)
        
        db = get_database()
        
        # Check if user already exists
        existing_user = await db.users.find_one({
            "$or": [
                {"email": email.lower()},
                {"mobile_number": mobile_number}
            ]
        })
        
        if existing_user:
            logger.warning(f"Registration failed: email or phone already exists")
            raise ValueError("Email or mobile number already registered")
        
        # Create user document
        user_doc = {
            "email": email.lower(),
            "mobile_number": mobile_number,
            "password_hash": hash_password(password),
            "full_name": full_name,
            "role": UserRole.VOTER.value,
            "location": location,
            "language_preference": language_preference,
            "is_active": True,
            "is_verified": False,
            "is_mobile_verified": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "last_login": None,
            "notification_preferences": {
                "email": True,
                "sms": True,
                "push": True
            }
        }
        
        # Add voter-specific fields
        user_doc["engagement"] = {
            "level": EngagementLevel.PASSIVE.value,
            "issues_of_interest": [],
            "last_active_date": None,
            "total_complaints": 0,
            "total_polls_participated": 0,
            "total_feedback_given": 0
        }
        user_doc["assigned_leader_id"] = None
        
        # Add demographics (required on API, still guard here)
        user_doc["demographics"] = demographics or {}
        
        # Add family data
        if family_adults is not None:
            user_doc["demographics"]["family_adults"] = family_adults
        
        if family_kids is not None:
            user_doc["demographics"]["family_kids"] = family_kids
        
        # Insert user into database
        result = await db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        
        logger.info(f"Voter registered successfully: {user_id}")
        
        # Generate tokens
        tokens = create_user_tokens(user_id, UserRole.VOTER)
        
        return {
            "user_id": user_id,
            "email": email,
            "full_name": full_name,
            "role": UserRole.VOTER.value,
            **tokens
        }
    
    @staticmethod
    async def register_leader(
        email: str,
        mobile_number: str,
        password: str,
        full_name: str,
        location: Dict[str, Any],
        language_preference: str = "en",
    ) -> Dict[str, Any]:
        """
        Register a new leader with basic profile data.
        Territory will be assigned by administrators later.
        
        Args:
            email (str): User's email address
            mobile_number (str): User's mobile number
            password (str): Plain text password
            full_name (str): User's full name
            location (Dict): Location information
            language_preference (str): Language preference
            
        Returns:
            Dict[str, Any]: User document with tokens
            
        Raises:
            ValueError: If validation fails or user already exists
        """
        # Validate email format
        if not validate_email(email):
            raise ValueError("Invalid email format")
        
        # Validate mobile number format
        if not validate_mobile_number(mobile_number):
            raise ValueError("Invalid mobile number format")
        
        # Validate password strength
        AuthService._validate_password_strength(password)
        
        db = get_database()
        
        # Check if user already exists
        existing_user = await db.users.find_one({
            "$or": [
                {"email": email.lower()},
                {"mobile_number": mobile_number}
            ]
        })
        
        if existing_user:
            logger.warning(f"Registration failed: email or phone already exists")
            raise ValueError("Email or mobile number already registered")
        
        # Create user document
        user_doc = {
            "email": email.lower(),
            "mobile_number": mobile_number,
            "password_hash": hash_password(password),
            "full_name": full_name,
            "role": UserRole.LEADER.value,
            "location": location,
            "language_preference": language_preference,
            "is_active": True,
            "is_verified": False,
            "is_mobile_verified": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "last_login": None,
            "notification_preferences": {
                "email": True,
                "sms": True,
                "push": True
            }
        }
        
        # Add leader-specific fields
        user_doc["territory"] = {
            "assigned_areas": [],
            "assigned_wards": [],
            "total_voters_assigned": 0
        }
        user_doc["assigned_territory"] = location  # Will be updated when territory is assigned
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
        user_doc["assigned_by"] = None  # Will be set when corporator assigns territory
        user_doc["leader_responsibilities"] = []
        
        # Insert user into database
        result = await db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        
        logger.info(f"Leader registered successfully: {user_id}")
        
        # Generate tokens
        tokens = create_user_tokens(user_id, UserRole.LEADER)
        
        return {
            "user_id": user_id,
            "email": email,
            "full_name": full_name,
            "role": UserRole.LEADER.value,
            **tokens
        }
    
    @staticmethod
    async def register_corporator(
        email: str,
        mobile_number: str,
        password: str,
        full_name: str,
        location: Dict[str, Any],
        language_preference: str = "en",
        demographics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Register a new corporator with basic profile data.
        Corporators are municipal representatives with oversight authority.
        Account approval may be required by administrators.
        
        Args:
            email (str): User's email address
            mobile_number (str): User's mobile number
            password (str): Plain text password
            full_name (str): User's full name
            location (Dict): Location information
            language_preference (str): Language preference
            demographics (Optional[Dict]): Demographic data (gender, etc.)
            
        Returns:
            Dict[str, Any]: User document with tokens
            
        Raises:
            ValueError: If validation fails or user already exists
        """
        # Validate email format
        if not validate_email(email):
            raise ValueError("Invalid email format")
        
        # Validate mobile number format
        if not validate_mobile_number(mobile_number):
            raise ValueError("Invalid mobile number format")
        
        # Validate password strength
        AuthService._validate_password_strength(password)
        
        db = get_database()
        
        # Check if user already exists
        existing_user = await db.users.find_one({
            "$or": [
                {"email": email.lower()},
                {"mobile_number": mobile_number}
            ]
        })
        
        if existing_user:
            logger.warning(f"Registration failed: email or phone already exists")
            raise ValueError("Email or mobile number already registered")
        
        # Create user document
        user_doc = {
            "email": email.lower(),
            "mobile_number": mobile_number,
            "password_hash": hash_password(password),
            "full_name": full_name,
            "role": UserRole.CORPORATOR.value,
            "location": location,
            "language_preference": language_preference,
            "is_active": True,
            "is_verified": False,
            "is_mobile_verified": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "last_login": None,
            "notification_preferences": {
                "email": True,
                "sms": True,
                "push": True
            }
        }
        
        # Add corporator-specific fields
        user_doc["corporator_info"] = {
            "ward_number": None,
            "municipality_id": None,
            "is_approved": False,
            "approval_date": None,
            "approval_by": None
        }
        user_doc["assigned_territory"] = location
        user_doc["performance"] = {
            "complaints_handled": 0,
            "complaints_resolved": 0,
            "leaders_managed": 0,
            "events_organized": 0,
            "rating": 0.0,
            "total_interactions": 0
        }
        
        # Add demographics (optional)
        user_doc["demographics"] = demographics or {}
        
        # Insert user into database
        result = await db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        
        logger.info(f"Corporator registered successfully: {user_id}")
        
        # Generate tokens
        tokens = create_user_tokens(user_id, UserRole.CORPORATOR)
        
        return {
            "user_id": user_id,
            "email": email,
            "full_name": full_name,
            "role": UserRole.CORPORATOR.value,
            **tokens
        }
    
    @staticmethod
    async def register_user(
        email: str,
        mobile_number: str,
        password: str,
        full_name: str,
        role: UserRole,
        location: Dict[str, Any],
        language_preference: str = "en"
    ) -> Dict[str, Any]:
        """
        Register a new user in the system (generic method).
        SECURITY FIX: Only allow VOTER role for public registration
        Other roles (CORPORATOR, LEADER, OPS) must be created by admins through admin panel
        
        Args:
            email (str): User's email address
            mobile_number (str): User's mobile number
            password (str): Plain text password
            full_name (str): User's full name
            role (UserRole): User's role
            location (Dict): Location information
            language_preference (str): Language preference
            
        Returns:
            Dict[str, Any]: User document with tokens
            
        Raises:
            ValueError: If validation fails or user already exists
        """
        # SECURITY FIX: Only allow VOTER role for public registration
        if role != UserRole.VOTER:
            logger.error(f"Unauthorized registration attempt with role: {role.value}")
            raise ValueError("Public registration is only allowed for voters. Contact administrator for other roles.")
        
        # Validate email format
        if not validate_email(email):
            raise ValueError("Invalid email format")
        
        # Validate mobile number format
        if not validate_mobile_number(mobile_number):
            raise ValueError("Invalid mobile number format")
        
        # Validate password strength
        AuthService._validate_password_strength(password)
        
        db = get_database()
        
        # Check if user already exists
        existing_user = await db.users.find_one({
            "$or": [
                {"email": email.lower()},
                {"mobile_number": mobile_number}
            ]
        })
        
        if existing_user:
            logger.warning(f"Registration failed: email or phone already exists")
            raise ValueError("Email or mobile number already registered")
        
        # Create user document
        user_doc = {
            "email": email.lower(),
            "mobile_number": mobile_number,
            "password_hash": hash_password(password),
            "full_name": full_name,
            "role": role.value,
            "location": location,
            "language_preference": language_preference,
            "is_active": True,
            "is_verified": False,
            "is_mobile_verified": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "last_login": None,
            "notification_preferences": {
                "email": True,
                "sms": True,
                "push": True
            }
        }
        
        # Add role-specific fields (only VOTER is allowed via this endpoint)
        user_doc["engagement"] = {
            "level": EngagementLevel.PASSIVE.value,
            "issues_of_interest": [],
            "last_active_date": None,
            "total_complaints": 0,
            "total_polls_participated": 0,
            "total_feedback_given": 0
        }
        user_doc["assigned_leader_id"] = None
        user_doc["demographics"] = None
        
        # Insert user into database
        result = await db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)
        
        logger.info(f"User registered successfully: {user_id} ({role.value})")
        
        # Generate tokens
        tokens = create_user_tokens(user_id, role)
        
        return {
            "user_id": user_id,
            "email": email,
            "full_name": full_name,
            "role": role.value,
            **tokens
        }
    
    @staticmethod
    async def login_user(
        email: Optional[str] = None,
        mobile_number: Optional[str] = None,
        password: str = None
    ) -> Dict[str, Any]:
        """
        Authenticate user and generate tokens.
        
        Args:
            email (Optional[str]): User's email
            mobile_number (Optional[str]): User's mobile number
            password (str): Plain text password
            
        Returns:
            Dict[str, Any]: User info with access and refresh tokens
            
        Raises:
            ValueError: If credentials are invalid
        """
        if not email and not mobile_number:
            raise ValueError("Either email or mobile_number must be provided")
        
        if not password:
            raise ValueError("Password is required")
        
        db = get_database()
        
        # Find user by email or mobile
        query = {}
        if email:
            query["email"] = email.lower()
        elif mobile_number:
            query["mobile_number"] = mobile_number
        
        user = await db.users.find_one(query)
        
        if not user:
            logger.warning(f"Login failed: user not found")
            raise ValueError("Invalid email/phone or password")
        
        # Check if user is active
        if not user.get("is_active"):
            logger.warning(f"Login failed: user {user['_id']} is inactive")
            raise ValueError("User account is inactive")
        
        # Verify password
        if not verify_password(password, user.get("password_hash", "")):
            logger.warning(f"Login failed: invalid password for user {user['_id']}")
            raise ValueError("Invalid email/phone or password")
        
        # Update last login time
        user_id = str(user["_id"])
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login": utc_now()}}
        )
        
        # Extract role
        role = UserRole(user["role"])
        
        # Generate tokens
        tokens = create_user_tokens(user_id, role)
        
        logger.info(f"User logged in successfully: {user_id}")
        
        return {
            "user_id": user_id,
            "email": user["email"],
            "full_name": user["full_name"],
            "role": role.value,
            **tokens
        }
    
    @staticmethod
    async def change_password(
        user_id: str,
        old_password: str,
        new_password: str
    ) -> bool:
        """
        Change user's password.
        
        Args:
            user_id (str): User's ID
            old_password (str): Current password
            new_password (str): New password
            
        Returns:
            bool: True if password changed successfully
            
        Raises:
            ValueError: If old password is incorrect or new password is invalid
        """
        db = get_database()
        
        # Get user
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise ValueError("User not found")
        
        # Verify old password
        if not verify_password(old_password, user.get("password_hash", "")):
            logger.warning(f"Password change failed: invalid old password for {user_id}")
            raise ValueError("Current password is incorrect")
        
        # Validate new password
        AuthService._validate_password_strength(new_password)
        
        # Update password
        await db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "password_hash": hash_password(new_password),
                "updated_at": utc_now()
            }}
        )
        
        logger.info(f"Password changed successfully for user {user_id}")
        return True
    
    @staticmethod
    async def request_password_reset(
        email: Optional[str] = None,
        mobile_number: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Initiate password reset process.
        
        Args:
            email (Optional[str]): User's email
            mobile_number (Optional[str]): User's mobile number
            
        Returns:
            Dict[str, str]: Reset token and delivery method
            
        Raises:
            ValueError: If user not found
            
        Note:
            In production, send reset token via email/SMS to user.
            This is a simplified implementation.
        """
        if not email and not mobile_number:
            raise ValueError("Either email or mobile_number must be provided")
        
        db = get_database()
        
        # Find user
        query = {}
        if email:
            query["email"] = email.lower()
        elif mobile_number:
            query["mobile_number"] = mobile_number
        
        user = await db.users.find_one(query)
        
        if not user:
            logger.warning("Password reset requested for non-existent user")
            # Return generic message for security
            return {"message": "If user exists, reset link will be sent"}
        
        # Generate reset token
        import secrets
        reset_token = secrets.token_urlsafe(32)
        
        # Store reset token with expiry (valid for 1 hour)
        from datetime import timedelta
        reset_token_expiry = utc_now() + timedelta(hours=1)
        
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "reset_token": reset_token,
                "reset_token_expiry": reset_token_expiry
            }}
        )
        
        logger.info(f"Password reset requested for user {user['_id']}")
        
        # In production: send email/SMS with reset link
        return {
            "message": "Reset link sent to registered email/phone",
            "reset_token": reset_token  # Return for development (remove in production)
        }
    
    @staticmethod
    async def confirm_password_reset(
        reset_token: str,
        new_password: str
    ) -> bool:
        """
        Confirm password reset with token.
        
        Args:
            reset_token (str): Reset token from email/SMS
            new_password (str): New password
            
        Returns:
            bool: True if password reset successfully
            
        Raises:
            ValueError: If token is invalid or expired
        """
        db = get_database()
        
        # Find user with valid reset token
        user = await db.users.find_one({
            "reset_token": reset_token,
            "reset_token_expiry": {"$gt": utc_now()}
        })
        
        if not user:
            logger.warning("Password reset failed: invalid or expired token")
            raise ValueError("Invalid or expired reset token")
        
        # Validate new password
        AuthService._validate_password_strength(new_password)
        
        # Update password and clear reset token
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {
                "password_hash": hash_password(new_password),
                "updated_at": utc_now()
            },
            "$unset": {
                "reset_token": "",
                "reset_token_expiry": ""
            }}
        )
        
        logger.info(f"Password reset completed for user {user['_id']}")
        return True
    
    @staticmethod
    def _validate_password_strength(password: str) -> None:
        """
        Validate password meets security requirements.
        
        Requirements:
        - Minimum 8 characters
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        
        Args:
            password (str): Password to validate
            
        Raises:
            ValueError: If password doesn't meet requirements
        """
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        if not any(c.isupper() for c in password):
            raise ValueError("Password must contain at least one uppercase letter")
        
        if not any(c.islower() for c in password):
            raise ValueError("Password must contain at least one lowercase letter")
        
        if not any(c.isdigit() for c in password):
            raise ValueError("Password must contain at least one digit")
        
        special_chars = "!@#$%^&*(),.?\":{}|<>"
        if not any(c in special_chars for c in password):
            raise ValueError("Password must contain at least one special character")
