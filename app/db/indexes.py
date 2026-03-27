"""
Database Index Definitions
==========================
Defines and creates all MongoDB indexes for optimal query performance.
Indexes are created during application startup.

Author: Political Communication Platform Team
"""

import logging
from app.db.mongodb import get_database
from pymongo import ASCENDING, DESCENDING, TEXT


logger = logging.getLogger(__name__)


async def create_indexes() -> None:
    """
    Create all database indexes for collections.
    This function is called during application startup.
    
    Indexes improve query performance for frequently accessed fields.
    """
    db = get_database()
    
    try:
        # ====================
        # USERS COLLECTION
        # ====================
        await db.users.create_index([("email", ASCENDING)], unique=True)
        await db.users.create_index(
            [("mobile_number", ASCENDING)],
            unique=True,
            partialFilterExpression={"mobile_number": {"$type": "string"}},
        )
        await db.users.create_index([("role", ASCENDING)])
        await db.users.create_index([("is_active", ASCENDING)])
        
        # Geographic indexes for location-based queries
        await db.users.create_index([("location.state", ASCENDING)])
        await db.users.create_index([("location.city", ASCENDING)])
        await db.users.create_index([("location.ward", ASCENDING)])
        await db.users.create_index([("location.area", ASCENDING)])
        await db.users.create_index([("location.booth_number", ASCENDING)])
        
        # Engagement analytics indexes
        await db.users.create_index([("engagement.level", ASCENDING)])
        await db.users.create_index([("engagement.last_active_date", DESCENDING)])
        await db.users.create_index([("engagement.total_polls_participated", DESCENDING)])
        await db.users.create_index([("engagement.total_feedback_given", DESCENDING)])
        await db.users.create_index([("engagement.total_complaints", DESCENDING)])
        
        # Demographics analytics indexes
        await db.users.create_index([("demographics.age_group", ASCENDING)])
        await db.users.create_index([("demographics.gender", ASCENDING)])
        await db.users.create_index([("demographics.occupation", ASCENDING)])
        await db.users.create_index([("demographics.education", ASCENDING)])
        
        # Leader assignment index
        await db.users.create_index([("assigned_leader_id", ASCENDING)])
        
        logger.info("✓ Users collection indexes created")
        
        # ====================
        # ANNOUNCEMENTS COLLECTION
        # ====================
        await db.announcements.create_index([("created_by", ASCENDING)])
        await db.announcements.create_index([("created_at", DESCENDING)])
        await db.announcements.create_index([("status", ASCENDING)])
        await db.announcements.create_index([("priority", DESCENDING)])
        
        # Text search on title and content
        await db.announcements.create_index([("title", TEXT), ("content", TEXT)])
        
        # Target audience indexes
        await db.announcements.create_index([("target.roles", ASCENDING)])
        await db.announcements.create_index([("target.geography.state", ASCENDING)])
        await db.announcements.create_index([("target.geography.city", ASCENDING)])
        
        logger.info("✓ Announcements collection indexes created")
        
        # ====================
        # POLLS COLLECTION
        # ====================
        await db.polls.create_index([("created_by", ASCENDING)])
        await db.polls.create_index([("created_at", DESCENDING)])
        await db.polls.create_index([("status", ASCENDING)])
        await db.polls.create_index([("end_date", ASCENDING)])
        
        # Poll responses (embedded)
        await db.polls.create_index([("responses.user_id", ASCENDING)])
        
        logger.info("✓ Polls collection indexes created")
        
        # ====================
        # COMPLAINTS COLLECTION
        # ====================
        await db.complaints.create_index([("created_by", ASCENDING)])
        await db.complaints.create_index([("assigned_to", ASCENDING)])
        await db.complaints.create_index([("status", ASCENDING)])
        await db.complaints.create_index([("priority", DESCENDING)])
        await db.complaints.create_index([("category", ASCENDING)])
        await db.complaints.create_index([("created_at", DESCENDING)])
        await db.complaints.create_index([("assigned_at", DESCENDING)])
        await db.complaints.create_index([("resolved_at", DESCENDING)])
        await db.complaints.create_index([("status_updated_at", DESCENDING)])
        await db.complaints.create_index([("is_escalated", ASCENDING)])
        await db.complaints.create_index([("voter_satisfaction_rating", DESCENDING)])
        
        # Location-based complaint queries
        await db.complaints.create_index([("location.state", ASCENDING)])
        await db.complaints.create_index([("location.city", ASCENDING)])
        await db.complaints.create_index([("location.ward", ASCENDING)])
        await db.complaints.create_index([("location.area", ASCENDING)])
        
        # Text search on description
        await db.complaints.create_index([("title", TEXT), ("description", TEXT)])
        
        # Compound index for analytics
        await db.complaints.create_index([
            ("status", ASCENDING),
            ("category", ASCENDING),
            ("created_at", DESCENDING)
        ])
        
        logger.info("✓ Complaints collection indexes created")
        
        # ====================
        # APPOINTMENTS COLLECTION
        # ====================
        await db.appointments.create_index([("requested_by", ASCENDING)])
        await db.appointments.create_index([("requested_with", ASCENDING)])
        await db.appointments.create_index([("status", ASCENDING)])
        await db.appointments.create_index([("appointment_date", ASCENDING)])
        await db.appointments.create_index([("created_at", DESCENDING)])
        
        # Compound index for calendar views
        await db.appointments.create_index([
            ("requested_with", ASCENDING),
            ("appointment_date", ASCENDING),
            ("status", ASCENDING)
        ])
        
        logger.info("✓ Appointments collection indexes created")
        
        # ====================
        # EVENTS COLLECTION
        # ====================
        await db.events.create_index([("created_by", ASCENDING)])
        await db.events.create_index([("event_date", ASCENDING)])
        await db.events.create_index([("status", ASCENDING)])
        await db.events.create_index([("event_type", ASCENDING)])
        await db.events.create_index([("created_at", DESCENDING)])
        
        # Location indexes for events
        await db.events.create_index([("location.city", ASCENDING)])
        await db.events.create_index([("location.area", ASCENDING)])
        
        # Assigned leaders index
        await db.events.create_index([("assigned_leaders", ASCENDING)])
        
        logger.info("✓ Events collection indexes created")
        
        # ====================
        # FEEDBACK COLLECTION
        # ====================
        await db.feedback.create_index([("created_by", ASCENDING)])
        await db.feedback.create_index([("created_at", DESCENDING)])
        await db.feedback.create_index([("rating", DESCENDING)])
        await db.feedback.create_index([("category", ASCENDING)])
        await db.feedback.create_index([("sentiment", ASCENDING)])
        await db.feedback.create_index([("reaction", ASCENDING)])
        
        # Text search on feedback content
        await db.feedback.create_index([("content", TEXT)])
        
        logger.info("✓ Feedback collection indexes created")
        
        # ====================
        # NOTIFICATIONS COLLECTION
        # ====================
        await db.notifications.create_index([("user_id", ASCENDING)])
        await db.notifications.create_index([("is_read", ASCENDING)])
        await db.notifications.create_index([("created_at", DESCENDING)])
        await db.notifications.create_index([("notification_type", ASCENDING)])
        
        # Compound index for unread notifications
        await db.notifications.create_index([
            ("user_id", ASCENDING),
            ("is_read", ASCENDING),
            ("created_at", DESCENDING)
        ])
        
        logger.info("✓ Notifications collection indexes created")

        # ====================
        # CAMPAIGNS COLLECTION
        # ====================
        await db.campaigns.create_index([("campaign_id", ASCENDING)], unique=True)
        await db.campaigns.create_index([("created_by", ASCENDING)])
        await db.campaigns.create_index([("created_at", DESCENDING)])
        await db.campaigns.create_index([("is_active", ASCENDING)])
        await db.campaigns.create_index([("category", ASCENDING)])

        # Location-based campaign queries
        await db.campaigns.create_index([("ward", ASCENDING)])
        await db.campaigns.create_index([("city", ASCENDING)])
        await db.campaigns.create_index([("state", ASCENDING)])

        # Text search on title and description
        await db.campaigns.create_index([("title", TEXT), ("description", TEXT)])

        # Compound index: active campaigns by ward for quick home-screen queries
        await db.campaigns.create_index([
            ("is_active", ASCENDING),
            ("ward", ASCENDING),
            ("created_at", DESCENDING),
        ])

        logger.info("✓ Campaigns collection indexes created")

        # ====================
        # DONATIONS COLLECTION
        # ====================
        await db.donations.create_index([("donation_id", ASCENDING)], unique=True)

        # Fraud detection — both must be fast lookups
        await db.donations.create_index(
            [("transaction_id", ASCENDING)],
            unique=True,
            partialFilterExpression={"transaction_id": {"$type": "string"}},
        )
        await db.donations.create_index([("image_hash", ASCENDING)])

        # Relational lookups
        await db.donations.create_index([("campaign_id", ASCENDING)])
        await db.donations.create_index([("user_id", ASCENDING)])

        # Status-based filtering
        await db.donations.create_index([("status", ASCENDING)])
        await db.donations.create_index([("created_at", DESCENDING)])
        await db.donations.create_index([("status_updated_at", DESCENDING)])

        # Compound: Corporator reviews pending_review donations per campaign
        await db.donations.create_index([
            ("campaign_id", ASCENDING),
            ("status", ASCENDING),
            ("created_at", DESCENDING),
        ])

        # Compound: voter's own donations history
        await db.donations.create_index([
            ("user_id", ASCENDING),
            ("created_at", DESCENDING),
        ])

        logger.info("✓ Donations collection indexes created")

        logger.info("✅ All database indexes created successfully!")
        
    except Exception as e:
        logger.error(f"❌ Error creating indexes: {e}")
        raise
