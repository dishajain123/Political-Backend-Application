"""
Common Enumerations Module
=========================
Defines all enums used across the application for consistent status values,
categories, and types.

Author: Political Communication Platform Team
"""

from enum import Enum


class ComplaintStatus(str, Enum):
    """Status values for complaints throughout their lifecycle"""
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"
    REJECTED = "rejected"


class ComplaintCategory(str, Enum):
    """Categories for complaint classification"""
    INFRASTRUCTURE = "infrastructure"
    WATER_SUPPLY = "water_supply"
    ELECTRICITY = "electricity"
    SANITATION = "sanitation"
    ROADS = "roads"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    SAFETY = "safety"
    CORRUPTION = "corruption"
    OTHER = "other"


class ComplaintPriority(str, Enum):
    """Priority levels for complaints"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AppointmentStatus(str, Enum):
    """Status values for appointments"""
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    RESCHEDULED = "rescheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AppointmentReason(str, Enum):
    """Reasons for appointment requests"""
    PERSONAL_ISSUE = "personal_issue"
    COMMUNITY_ISSUE = "community_issue"
    FEEDBACK = "feedback"
    COMPLAINT_FOLLOWUP = "complaint_followup"
    GENERAL_MEETING = "general_meeting"
    OTHER = "other"


class EventType(str, Enum):
    """Types of events"""
    RALLY = "rally"
    PUBLIC_MEETING = "public_meeting"
    TOWN_HALL = "town_hall"
    CAMPAIGN = "campaign"
    CELEBRATION = "celebration"
    AWARENESS = "awareness"
    OTHER = "other"


class EventStatus(str, Enum):
    """Status of events"""
    SCHEDULED = "scheduled"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"


class PollStatus(str, Enum):
    """Status of polls"""
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class AnnouncementStatus(str, Enum):
    """Status of announcements"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AnnouncementPriority(str, Enum):
    """Priority levels for announcements"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class AnnouncementCategory(str, Enum):
    """
    CRITICAL: Categories for announcements
    These are the 5 mandatory types for Communication & Promotion
    """
    ANNOUNCEMENT = "announcement"
    POLICY = "policy"
    SCHEME = "scheme"
    ACHIEVEMENT = "achievement"
    PARTY_MESSAGE = "party_message"


class FeedbackCategory(str, Enum):
    """Categories for feedback"""
    GENERAL = "general"
    SERVICE_QUALITY = "service_quality"
    LEADER_PERFORMANCE = "leader_performance"
    POLICY_FEEDBACK = "policy_feedback"
    EVENT_FEEDBACK = "event_feedback"
    APP_FEEDBACK = "app_feedback"
    OTHER = "other"


class SentimentType(str, Enum):
    """Sentiment analysis results"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class NotificationType(str, Enum):
    """Types of notifications"""
    ANNOUNCEMENT = "announcement"
    POLL = "poll"
    EVENT = "event"
    COMPLAINT_UPDATE = "complaint_update"
    APPOINTMENT_UPDATE = "appointment_update"
    SYSTEM = "system"
    GENERAL = "general"


class Gender(str, Enum):
    """Gender options"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class AgeGroup(str, Enum):
    """Age group categories for analytics"""
    BELOW_18 = "below_18"
    AGE_18_25 = "18_25"
    AGE_26_35 = "26_35"
    AGE_36_45 = "36_45"
    AGE_46_60 = "46_60"
    ABOVE_60 = "above_60"


class EducationLevel(str, Enum):
    """Education level categories"""
    NO_FORMAL = "no_formal"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    HIGHER_SECONDARY = "higher_secondary"
    GRADUATE = "graduate"
    POST_GRADUATE = "post_graduate"
    DOCTORATE = "doctorate"


class OccupationCategory(str, Enum):
    """Occupation categories"""
    STUDENT = "student"
    EMPLOYED_PRIVATE = "employed_private"
    EMPLOYED_GOVERNMENT = "employed_government"
    SELF_EMPLOYED = "self_employed"
    BUSINESS = "business"
    UNEMPLOYED = "unemployed"
    RETIRED = "retired"
    HOMEMAKER = "homemaker"
    OTHER = "other"


class EngagementLevel(str, Enum):
    """User engagement levels"""
    ACTIVE = "active"
    PASSIVE = "passive"
    SILENT = "silent"


class AnnualIncomeRange(str, Enum):
    """Annual income range categories (INR)"""
    LT_2L = "lt_2l"
    FROM_2_5L = "2_5l"
    FROM_5_15L = "5_15l"
    FROM_15_40L = "15_40l"
    GT_40L = "gt_40l"
