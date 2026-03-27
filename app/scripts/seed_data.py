"""
Seed Data Script (Full Dataset)
==============================
Generates realistic demo data for all collections.
Run: python app/scripts/seed_data.py
"""

import asyncio
import logging
import random
import string
from datetime import datetime, timedelta
from typing import List, Dict, Any
from uuid import uuid4

from bson import ObjectId

from app.db.mongodb import connect_to_mongo, close_mongo_connection, get_database
from app.core.security import hash_password
from app.core.roles import UserRole
from app.utils.enums import (
    AnnouncementPriority,
    AnnouncementStatus,
    AnnouncementCategory,
    AppointmentReason,
    AppointmentStatus,
    ComplaintCategory,
    ComplaintPriority,
    ComplaintStatus,
    EventStatus,
    EventType,
    FeedbackCategory,
    NotificationType,
    PollStatus,
    SentimentType,
    EngagementLevel,
    Gender,
    AgeGroup,
    EducationLevel,
    OccupationCategory,
    AnnualIncomeRange,
)

# ==========================
# LOGGING SETUP
# ==========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("seed_data")

# ==========================
# CONFIGURATION
# ==========================
CORPORATORS = 1
LEADERS = 20
VOTERS = 1000
OPS_USERS = 5

COMPLAINTS = 200
EVENTS = 10
POLLS = 5
ANNOUNCEMENTS = 10
APPOINTMENTS = 30
FEEDBACK = 40
NOTIFICATIONS = 60

CAMPAIGNS = 8
DONATIONS_MIN = 100
DONATIONS_MAX = 250

HELP_NUMBERS = 8
CHATS = 12

DEFAULT_PASSWORD = "Test@123"

BASE_LOCATION = {
    "state": "Maharashtra",
    "city": "Mumbai",
}

WARDS = ["Ward-A", "Ward-B", "Ward-C", "Ward-D", "Ward-E", "Ward-F"]
AREAS = [
    "Andheri East",
    "Andheri West",
    "Kandivali East",
    "Kandivali West",
    "Borivali East",
    "Borivali West",
    "Malad East",
    "Malad West",
    "Goregaon East",
    "Goregaon West",
]
BUILDINGS = [
    "Sapphire Heights",
    "Prakash Towers",
    "Sea Breeze",
    "Silver Residency",
    "Green Meadows",
    "Laxmi Niwas",
    "Shivaji Plaza",
]

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Vihaan", "Reyansh", "Mohit", "Rohan",
    "Prakash", "Sanjay", "Rahul", "Amit", "Vishal", "Neha", "Ananya", "Kavya",
    "Shruti", "Pooja", "Ritu", "Nisha", "Meera", "Isha", "Sonal", "Radhika",
]
LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Mehta", "Deshmukh", "Kulkarni", "Jadhav", "Pillai",
    "Khan", "Singh", "Gupta", "Nair", "Reddy", "Shinde", "Sawant", "Yadav",
]

# NOTE: MongoDB's text-index "language override" only supports a specific set of
# language codes (en, fr, de, es, pt, ru, etc.).  "hi" and "mr" are NOT supported,
# so we must NOT store them in a field literally called `language`.
# We use `content_language` throughout all document inserts instead.
LANGUAGES = ["en", "hi", "mr"]

RELIGIONS = ["Hindu", "Muslim", "Buddhist", "Sikh", "Christian", "Jain"]
COMPLAINT_TITLES = [
    "Pothole on main road",
    "Water leakage near society",
    "Drainage blockage",
    "Garbage overflow",
    "Street light not working",
    "Road markings faded",
    "Open manhole",
    "Illegal dumping site",
]

COMPLAINT_DESCRIPTIONS = [
    "Large potholes causing accidents and traffic slowdown.",
    "Continuous water leakage leading to wastage and road damage.",
    "Drainage is blocked and overflowing during rains.",
    "Garbage has not been collected for several days.",
    "Street lights are not working, area unsafe at night.",
    "Road markings are faded, causing confusion for vehicles.",
    "Open manhole is dangerous for pedestrians.",
    "Illegal dumping is causing foul smell and health issues.",
]

EVENT_TITLES = [
    "Free Health Camp for Senior Citizens",
    "Public Town Hall Meeting",
    "Women Empowerment Workshop",
    "Environment Awareness Rally",
    "Youth Skill Development Drive",
    "Road Safety Campaign",
    "Community Cleanliness Drive",
    "Blood Donation Camp",
    "Water Conservation Workshop",
    "Traffic Awareness Program",
]

POLL_QUESTIONS = [
    "Should Ward A receive a new community park?",
    "Which civic service needs the most improvement in your area?",
    "Do you support a monthly cleanliness drive in your ward?",
    "Should the ward allocate more budget to street lighting?",
    "How satisfied are you with local water supply?",
]

CAMPAIGN_TITLES = [
    "Drainage Improvement Before Monsoon",
    "Ward Road Repair Drive",
    "School Classroom Renovation",
    "Community Center Repairs",
    "Street Light Replacement",
    "Local Park Restoration",
    "Senior Citizen Clinic Fund",
    "Drinking Water Pipeline Fix",
]

HELP_SERVICES = [
    ("Police", "100", "Emergency"),
    ("Fire Brigade", "101", "Emergency"),
    ("Ambulance", "102", "Emergency"),
    ("Women Helpline", "1091", "Helpline"),
    ("Child Helpline", "1098", "Helpline"),
    ("Municipal Corporation", "1916", "Civic"),
    ("Electricity Helpline", "1912", "Utilities"),
    ("Water Supply Helpline", "1910", "Utilities"),
]

# ==========================
# HELPERS
# ==========================

def utc_now() -> datetime:
    return datetime.utcnow()


def random_past_date(days: int = 60) -> datetime:
    return utc_now() - timedelta(days=random.randint(1, days), hours=random.randint(0, 23))


def random_future_date(days: int = 30) -> datetime:
    return utc_now() + timedelta(days=random.randint(1, days), hours=random.randint(0, 23))


def random_phone() -> str:
    return "+91" + "".join(random.choice(string.digits) for _ in range(10))


def random_name() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_location() -> Dict[str, str]:
    return {
        "state": "Maharashtra",
        "city": "Mumbai",
        "ward": random.choice(WARDS),
        "area": random.choice(AREAS),
        "building": random.choice(BUILDINGS),
        "booth_number": str(random.randint(1, 300)),
    }


def random_demographics() -> Dict[str, Any]:
    return {
        "voting_location": f"{random.choice(WARDS)} - {random.choice(AREAS)}",
        "age_group": random.choice(list(AgeGroup)).value,
        "gender": random.choice(list(Gender)).value,
        "religion": random.choice(RELIGIONS),
        "occupation": random.choice(list(OccupationCategory)).value,
        "profession": random.choice(["Teacher", "Driver", "Engineer", "Vendor", "Student"]),
        "education": random.choice(list(EducationLevel)).value,
        "family_adults": random.randint(1, 4),
        "family_kids": random.randint(0, 3),
        "annual_income_range": random.choice(list(AnnualIncomeRange)).value,
    }


def random_engagement() -> Dict[str, Any]:
    return {
        "level": random.choice(list(EngagementLevel)).value,
        "issues_of_interest": random.sample(
            ["roads", "water_supply", "drainage", "education", "healthcare"],
            k=random.randint(1, 3),
        ),
        "last_active_date": random_past_date(30),
        "total_complaints": random.randint(0, 5),
        "total_polls_participated": random.randint(0, 10),
        "total_feedback_given": random.randint(0, 5),
    }


def notification_prefs() -> Dict[str, bool]:
    return {
        "email": True,
        "sms": True,
        "push": True,
        "receive_announcements": True,
        "receive_polls": True,
        "receive_events": True,
        "receive_updates": True,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
    }

# ==========================
# USER CREATION
# ==========================

async def create_corporator(db) -> ObjectId:
    log.info("Creating corporator user …")
    now = utc_now()
    doc = {
        "email": "corporator@test.com",
        "mobile_number": random_phone(),
        "password_hash": hash_password(DEFAULT_PASSWORD),
        "full_name": "Prakash Deshmukh",
        "profile_photo_url": "https://example.com/corporator.jpg",
        "role": UserRole.CORPORATOR.value,
        "location": random_location(),
        "is_active": True,
        "is_verified": True,
        "is_mobile_verified": True,
        "created_at": now,
        "updated_at": now,
        "last_login": random_past_date(5),
        "designation": "MLA",
        "constituency": "Mumbai North",
        "language_preference": random.choice(LANGUAGES),
        "notification_preferences": notification_prefs(),
        "leader_responsibilities": [],
    }
    result = await db.users.insert_one(doc)
    log.info("  ✔ Corporator created  id=%s", result.inserted_id)
    return result.inserted_id


async def create_ops_users(db) -> List[ObjectId]:
    log.info("Creating %d ops users …", OPS_USERS)
    ids = []
    for i in range(OPS_USERS):
        now = utc_now()
        doc = {
            "email": f"ops{i+1}@test.com",
            "mobile_number": random_phone(),
            "password_hash": hash_password(DEFAULT_PASSWORD),
            "full_name": f"Ops User {i+1}",
            "profile_photo_url": "https://example.com/ops.jpg",
            "role": UserRole.OPS.value,
            "location": random_location(),
            "is_active": True,
            "is_verified": True,
            "is_mobile_verified": True,
            "created_at": now,
            "updated_at": now,
            "last_login": random_past_date(7),
            "language_preference": random.choice(LANGUAGES),
            "notification_preferences": notification_prefs(),
        }
        result = await db.users.insert_one(doc)
        ids.append(result.inserted_id)
    log.info("  ✔ %d ops users created", len(ids))
    return ids


async def create_leaders(db, corporator_id: ObjectId) -> List[ObjectId]:
    log.info("Creating %d leaders …", LEADERS)
    ids = []
    for i in range(LEADERS):
        now = utc_now()
        doc = {
            "email": f"leader{i+1}@test.com",
            "mobile_number": random_phone(),
            "password_hash": hash_password(DEFAULT_PASSWORD),
            "full_name": f"{random_name()}",
            "profile_photo_url": "https://example.com/leader.jpg",
            "role": UserRole.LEADER.value,
            "location": random_location(),
            "is_active": True,
            "is_verified": True,
            "is_mobile_verified": True,
            "created_at": now,
            "updated_at": now,
            "last_login": random_past_date(10),
            "language_preference": random.choice(LANGUAGES),
            "notification_preferences": notification_prefs(),
            "assigned_by": corporator_id,
            "leader_responsibilities": ["complaint_followups", "event_coordination"],
            "territory": {
                "assigned_areas": random.sample(AREAS, k=2),
                "assigned_wards": random.sample(WARDS, k=1),
                "total_voters_assigned": random.randint(30, 150),
            },
            "performance": {
                "messages_shared": random.randint(20, 200),
                "complaints_followed_up": random.randint(5, 50),
                "complaints_handled": random.randint(5, 50),
                "complaints_resolved": random.randint(5, 50),
                "events_participated": random.randint(1, 10),
                "voter_interactions": random.randint(20, 200),
                "poll_responses": random.randint(5, 40),
                "poll_response_rate": round(random.uniform(10, 80), 2),
                "engagement_level": random.choice(["low", "medium", "high"]),
                "average_response_time_hours": round(random.uniform(1, 24), 2),
                "rating": round(random.uniform(3.0, 5.0), 1),
                "tasks_assigned": random.randint(5, 30),
                "tasks_completed": random.randint(5, 30),
                "ground_verifications_completed": random.randint(0, 5),
            },
        }
        result = await db.users.insert_one(doc)
        ids.append(result.inserted_id)
    log.info("  ✔ %d leaders created", len(ids))
    return ids


async def create_voters(db, leader_ids: List[ObjectId]) -> List[ObjectId]:
    log.info("Creating %d voters …", VOTERS)
    ids = []
    for i in range(VOTERS):
        now = utc_now()
        assigned_leader = random.choice(leader_ids)
        doc = {
            "email": f"voter{i+1}@test.com",
            "mobile_number": random_phone(),
            "password_hash": hash_password(DEFAULT_PASSWORD),
            "full_name": f"{random_name()}",
            "profile_photo_url": "https://example.com/voter.jpg",
            "role": UserRole.VOTER.value,
            "location": random_location(),
            "is_active": True,
            "is_verified": True,
            "is_mobile_verified": True,
            "created_at": now,
            "updated_at": now,
            "last_login": random_past_date(15),
            "assigned_leader_id": assigned_leader,
            "language_preference": random.choice(LANGUAGES),
            "notification_preferences": notification_prefs(),
            "demographics": random_demographics(),
            "engagement": random_engagement(),
        }
        result = await db.users.insert_one(doc)
        ids.append(result.inserted_id)
    log.info("  ✔ %d voters created", len(ids))
    return ids

# ==========================
# COMPLAINTS
# ==========================

async def create_complaints(db, voter_ids: List[ObjectId], leader_ids: List[ObjectId], corporator_id: ObjectId) -> List[str]:
    log.info("Creating %d complaints …", COMPLAINTS)
    complaints = []
    complaint_ids = []
    statuses = [
        ComplaintStatus.PENDING.value,
        ComplaintStatus.ACKNOWLEDGED.value,
        ComplaintStatus.IN_PROGRESS.value,
        ComplaintStatus.RESOLVED.value,
        ComplaintStatus.CLOSED.value,
        ComplaintStatus.REJECTED.value,
    ]

    for i in range(COMPLAINTS):
        status = random.choice(statuses)
        created_at = random_past_date(60)
        assigned_to = random.choice(leader_ids)
        resolved = status in [ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value]
        rejected = status == ComplaintStatus.REJECTED.value

        complaint_id = f"COMP-2026-{i + 1:04d}"
        complaint = {
            "complaint_id": complaint_id,
            "created_by": str(random.choice(voter_ids)),
            "created_at": created_at,
            "title": random.choice(COMPLAINT_TITLES),
            "description": random.choice(COMPLAINT_DESCRIPTIONS),
            "category": random.choice(list(ComplaintCategory)).value,
            "priority": random.choice(list(ComplaintPriority)).value,
            "location": random_location(),
            "status": status,
            "status_updated_at": random_past_date(30),
            "assigned_to": str(assigned_to),
            "assigned_at": random_past_date(20),
            "assigned_by": str(corporator_id),
            "resolved_by": str(assigned_to) if resolved else None,
            "resolved_at": random_past_date(10) if resolved else None,
            "resolution_notes": "Issue resolved after field inspection." if resolved else None,
            "attachment_urls": ["https://example.com/complaint-doc.pdf"],
            "image_urls": ["https://example.com/complaint-photo.jpg"],
            "voice_note_url": "https://example.com/voice-note.mp3",
            "image_url": "https://example.com/primary-image.jpg",
            "image_uploaded_at": random_past_date(25),
            "notes": [{
                "added_by": str(assigned_to),
                "content": "Initial assessment completed.",
                "added_at": random_past_date(15),
                "is_internal": True,
            }],
            "audit_trail": [{
                "status_from": ComplaintStatus.PENDING.value,
                "status_to": status,
                "changed_by": str(assigned_to),
                "reason": "Auto update by leader",
                "changed_at": random_past_date(12),
            }],
            "is_escalated": random.choice([True, False]),
            "escalated_at": random_past_date(10),
            "escalation_reason": "High impact issue",
            "decline_reason": "Insufficient evidence" if rejected else None,
            "declined_by": str(assigned_to) if rejected else None,
            "declined_at": random_past_date(10) if rejected else None,
            "voter_satisfaction_rating": random.randint(3, 5) if resolved else None,
            "voter_feedback": "Good response and quick action" if resolved else None,
            "feedback_given_at": random_past_date(5) if resolved else None,
            "sentiment": random.choice([s.value for s in SentimentType]),
            "verification_requested_at": random_past_date(7),
            "verified_by_corporator": True,
            "voter_feedback_rating": random.randint(3, 5),
            "voter_feedback_comment": "Verified resolution",
            "performance_score_updated": True,
            "estimated_resolution_date": random_future_date(7),
            "tags": random.sample(["urgent", "infrastructure", "public_safety", "maintenance"], k=2),
            "is_public": True,
        }
        complaints.append(complaint)
        complaint_ids.append(complaint_id)

    if complaints:
        await db.complaints.insert_many(complaints)
    log.info("  ✔ %d complaints inserted", len(complaints))
    return complaint_ids

# ==========================
# EVENTS
# ==========================

async def create_events(db, corporator_id: ObjectId, leader_ids: List[ObjectId], voter_ids: List[ObjectId]) -> None:
    log.info("Creating %d events …", EVENTS)
    events = []
    for i in range(EVENTS):
        created_at = random_past_date(60)
        event_date = random_future_date(20)
        status = random.choice(list(EventStatus)).value
        event = {
            "event_id": f"EVT-2026-{i + 1:04d}",
            "title": EVENT_TITLES[i % len(EVENT_TITLES)],
            "description": f"{EVENT_TITLES[i % len(EVENT_TITLES)]} for local citizens.",
            "event_type": random.choice(list(EventType)).value,
            "created_by": str(corporator_id),
            "created_at": created_at,
            "event_date": event_date,
            "end_date": event_date + timedelta(hours=3),
            "duration_hours": 3.0,
            "location": random_location(),
            "venue_name": "Community Hall",
            "venue_address": "Ward Office Road, Mumbai",
            "status": status,
            "status_updated_at": random_past_date(10),
            "estimated_attendees": random.randint(100, 1000),
            "actual_attendees": random.randint(50, 500),
            "participation_rate": round(random.uniform(20, 80), 2),
            "max_capacity": 1000,
            "assigned_leaders": [str(random.choice(leader_ids))],
            "organizer_notes": "Ensure registration desk available",
            "agenda": ["Welcome", "Keynote", "Q&A"],
            "speakers": ["Dr. Mehta", "Sarpanch Rao"],
            "banner_url": "https://example.com/event-banner.jpg",
            "poster_url": "https://example.com/event-poster.jpg",
            "document_urls": ["https://example.com/event-doc.pdf"],
            "media_urls": ["https://example.com/event-video.mp4"],
            "registrations": [{
                "user_id": str(random.choice(voter_ids)),
                "registered_at": random_past_date(5),
                "attended": True,
                "feedback_rating": random.randint(3, 5),
                "feedback_comment": "Great event",
            }],
            "registration_open": True,
            "registration_deadline": random_future_date(5),
            "cancelled_at": None,
            "cancellation_reason": None,
            "postponed_to": None,
            "postponement_reason": None,
            "estimated_budget": random.randint(5000, 20000),
            "actual_expense": random.randint(4000, 15000),
            "budget_notes": "Within planned budget",
            "is_public": True,
            "is_featured": random.choice([True, False]),
            "visibility_level": "public",
            "tags": ["community", "awareness"],
            "hashtags": ["#Mumbai", "#Civic"],
            "priority": random.randint(0, 5),
            # FIX: renamed from `language` → `content_language` to avoid
            # MongoDB text-index "language override" error for unsupported
            # locale codes such as "hi" and "mr".
            "content_language": random.choice(LANGUAGES),
        }
        events.append(event)
    if events:
        await db.events.insert_many(events)
    log.info("  ✔ %d events inserted", len(events))

# ==========================
# POLLS
# ==========================

async def create_polls(db, corporator_id: ObjectId, voter_ids: List[ObjectId]) -> List[str]:
    log.info("Creating %d polls …", POLLS)
    polls = []
    poll_ids = []
    for i in range(POLLS):
        poll_id = f"POLL-2026-{i + 1:04d}"
        options = [
            {"option_id": "1", "text": "Yes", "votes": random.randint(10, 200), "percentage": 0.0},
            {"option_id": "2", "text": "No", "votes": random.randint(5, 150), "percentage": 0.0},
        ]
        total_votes = sum(o["votes"] for o in options)
        for o in options:
            o["percentage"] = round((o["votes"] / total_votes) * 100, 2) if total_votes else 0.0

        responses = [
            {
                "user_id": str(random.choice(voter_ids)),
                "selected_option_id": random.choice(["1", "2"]),
                "response_text": None,
                "sentiment": random.choice([s.value for s in SentimentType]),
                "responded_at": random_past_date(10),
            }
            for _ in range(random.randint(10, 50))
        ]

        poll = {
            "poll_id": poll_id,
            "title": POLL_QUESTIONS[i % len(POLL_QUESTIONS)],
            "description": "Citizen opinion poll",
            "created_by": str(corporator_id),
            "created_at": random_past_date(30),
            "poll_type": "yes_no",
            "status": random.choice(list(PollStatus)).value,
            "status_updated_at": random_past_date(10),
            "start_date": random_past_date(20),
            "end_date": random_future_date(10),
            "options": options,
            "allow_other": True,
            "other_option_responses": ["Maybe"],
            "responses": responses,
            "total_responses": len(responses),
            "target_roles": ["voter"],
            "target_regions": {"wards": WARDS},
            "target_geography": random_location(),
            "target_demographics": {"age_groups": [AgeGroup.AGE_18_25.value]},
            "is_anonymous": True,
            "allow_multiple_responses": False,
            "show_results": "after_voting",
            "is_public": True,
            "is_featured": random.choice([True, False]),
            "view_count": random.randint(100, 500),
            "unique_responders": random.randint(50, 200),
            "participation_rate": round(random.uniform(10, 80), 2),
            "anonymous_responders": [],
            "banner_url": "https://example.com/poll-banner.jpg",
            "attachments": ["https://example.com/poll-attachment.pdf"],
            "auto_close_at": random_future_date(15),
            "is_auto_closed": False,
            "tags": ["civic", "survey"],
            "category": "Policy",
            "priority": random.randint(0, 5),
            "notes": "Demo poll notes",
        }
        polls.append(poll)
        poll_ids.append(poll_id)

    if polls:
        await db.polls.insert_many(polls)
    log.info("  ✔ %d polls inserted", len(polls))
    return poll_ids

# ==========================
# ANNOUNCEMENTS
# ==========================

async def create_announcements(db, corporator_id: ObjectId) -> None:
    log.info("Creating %d announcements …", ANNOUNCEMENTS)
    announcements = []
    for i in range(ANNOUNCEMENTS):
        created_at = random_past_date(30)
        status = random.choice(list(AnnouncementStatus)).value
        announcement = {
            "announcement_id": f"ANN-2026-{i + 1:04d}",
            "created_by": str(corporator_id),
            "created_at": created_at,
            "title": f"Announcement {i + 1}",
            "content": "Important civic announcement for residents.",
            "summary": "Short summary of announcement",
            "status": status,
            "status_updated_at": random_past_date(5),
            "priority": random.choice(list(AnnouncementPriority)).value,
            "published_at": random_past_date(3),
            "scheduled_publish_at": None,
            "expiry_date": random_future_date(15),
            "expires_on": None,
            "target": {
                "roles": ["voter", "leader"],
                "geography": random_location(),
                "regions": [random_location()],
                "issue_categories": ["roads", "water_supply"],
                "specific_users": [],
            },
            # FIX: renamed from `language` → `content_language` to avoid
            # MongoDB text-index "language override" error for unsupported
            # locale codes such as "hi" and "mr".
            "content_language": random.choice(LANGUAGES),
            "featured_image_url": "https://example.com/announcement.jpg",
            "banner_url": "https://example.com/announcement-banner.jpg",
            "attachment_urls": ["https://example.com/announcement-doc.pdf"],
            "video_urls": ["https://example.com/announcement-video.mp4"],
            "media_gallery": ["https://example.com/announcement-gallery.jpg"],
            "tags": ["civic", "update"],
            "category": random.choice(list(AnnouncementCategory)).value,
            "hashtags": ["#Mumbai", "#WardUpdate"],
            "authority_level": "corporator",
            "verified_by": str(corporator_id),
            "verified_at": random_past_date(2),
            "metrics": {
                "view_count": random.randint(100, 500),
                "unique_viewers": [],
                "share_count": random.randint(5, 50),
                "reaction_count": random.randint(10, 100),
                "comment_count": random.randint(2, 30),
                "acknowledgment_count": random.randint(0, 100),
                "acknowledgment_users": [],
            },
            "is_pinned": random.choice([True, False]),
            "pin_until": random_future_date(7),
            "enable_comments": True,
            "enable_sharing": True,
            "require_acknowledgment": random.choice([True, False]),
            "acknowledgment_count": random.randint(0, 100),
            "update_history": [],
            "related_announcement_ids": [],
            "related_event_ids": [],
            "related_poll_ids": [],
            "visibility": "public",
            "urgency": random.choice(["normal", "important", "urgent"]),
            "requires_action": random.choice([True, False]),
            "action_required_by": random_future_date(5),
        }
        announcements.append(announcement)
        log.debug("  Prepared announcement %d  status=%s", i + 1, status)

    if announcements:
        await db.announcements.insert_many(announcements)
    log.info("  ✔ %d announcements inserted", len(announcements))

# ==========================
# APPOINTMENTS
# ==========================

async def create_appointments(db, voter_ids: List[ObjectId], leader_ids: List[ObjectId], corporator_id: ObjectId) -> None:
    log.info("Creating %d appointments …", APPOINTMENTS)
    appointments = []
    for i in range(APPOINTMENTS):
        created_at = random_past_date(30)
        appointment_date = random_future_date(15)
        status = random.choice(list(AppointmentStatus)).value
        requested_with = str(random.choice(leader_ids + [corporator_id]))
        appointment = {
            "appointment_id": f"APPT-2026-{i + 1:04d}",
            "requested_by": str(random.choice(voter_ids)),
            "requested_with": requested_with,
            "reason": random.choice(list(AppointmentReason)).value,
            "description": "Discussion on civic issues",
            "created_at": created_at,
            "appointment_date": appointment_date,
            "duration_minutes": random.choice([30, 45, 60]),
            "location": "Community Center",
            "urgency_level": random.choice(["low", "normal", "high"]),
            "status": status,
            "status_updated_at": random_past_date(5),
            "approved_or_rejected_by": requested_with,
            "approved_or_rejected_at": random_past_date(4),
            "rejection_reason": "Schedule conflict" if status == AppointmentStatus.REJECTED.value else None,
            "reschedule_count": random.randint(0, 2),
            "new_appointment_date": random_future_date(20),
            "reschedule_reason": "Leader unavailable" if random.random() > 0.5 else None,
            "completed_at": random_past_date(1) if status == AppointmentStatus.COMPLETED.value else None,
            "attendees": [requested_with],
            "meeting_notes": "Meeting concluded with action items",
            "cancelled_at": None,
            "cancelled_by": None,
            "cancellation_reason": None,
            "feedback": {
                "rating": random.randint(3, 5),
                "comments": "Good discussion",
                "given_by": requested_with,
                "given_at": random_past_date(1),
            },
            "reminder_sent": True,
            "reminder_sent_at": random_past_date(2),
            "is_priority": random.choice([True, False]),
            "tags": ["civic", "meeting"],
            "linked_complaint_id": None,
        }
        appointments.append(appointment)
    if appointments:
        await db.appointments.insert_many(appointments)
    log.info("  ✔ %d appointments inserted", len(appointments))

# ==========================
# FEEDBACK
# ==========================

async def create_feedback(db, voter_ids: List[ObjectId], leader_ids: List[ObjectId], poll_ids: List[str], complaint_ids: List[str]) -> None:
    log.info("Creating %d feedback records …", FEEDBACK)
    feedbacks = []
    for i in range(FEEDBACK):
        created_at = random_past_date(30)
        feedback = {
            "feedback_id": f"FB-2026-{i + 1:04d}",
            "created_by": str(random.choice(voter_ids)),
            "created_at": created_at,
            "category": random.choice(list(FeedbackCategory)).value,
            "title": "Feedback on civic service",
            "content": "The issue was resolved satisfactorily.",
            "rating": random.randint(3, 5),
            "related_to": str(random.choice(leader_ids)),
            "related_event_id": None,
            "related_poll_id": random.choice(poll_ids) if poll_ids else None,
            "related_complaint_id": random.choice(complaint_ids) if complaint_ids else None,
            "sentiment": random.choice(list(SentimentType)).value,
            "sentiment_score": round(random.uniform(-1, 1), 2),
            "keywords": ["service", "response"],
            "attachment_urls": ["https://example.com/feedback.pdf"],
            "is_reviewed": True,
            "reviewed_by": str(random.choice(leader_ids)),
            "review_notes": "Reviewed by leader",
            "reviewed_at": random_past_date(5),
            "action_taken": True,
            "action_description": "Escalated to ops",
            "action_taken_by": str(random.choice(leader_ids)),
            "action_taken_at": random_past_date(3),
            "is_public": random.choice([True, False]),
            "is_featured": random.choice([True, False]),
            "reaction": random.choice(["agree", "disagree", "confused"]),
            "emoji": "??",
            "is_anonymous": False,
            "requires_followup": False,
            "followup_due_date": None,
            "tags": ["service"],
            "priority": random.randint(0, 3),
            "response_required": False,
        }
        feedbacks.append(feedback)
    if feedbacks:
        await db.feedback.insert_many(feedbacks)
    log.info("  ✔ %d feedback records inserted", len(feedbacks))

# ==========================
# NOTIFICATIONS
# ==========================

async def create_notifications(db, user_ids: List[ObjectId]) -> None:
    log.info("Creating %d notifications …", NOTIFICATIONS)
    notifications = []
    for i in range(NOTIFICATIONS):
        created_at = random_past_date(15)
        notification = {
            "notification_id": f"NOT-2026-{i + 1:04d}",
            "user_id": str(random.choice(user_ids)),
            "notification_type": random.choice(list(NotificationType)).value,
            "title": "Notification Update",
            "message": "A new update is available for your ward.",
            "body": "Detailed notification message body",
            "icon_url": "https://example.com/notification-icon.png",
            "image_url": "https://example.com/notification-image.png",
            "action_url": "https://example.com/action",
            "action_label": "View",
            "related_resource_id": "RES-001",
            "related_resource_type": "announcement",
            "is_read": random.choice([True, False]),
            "read_at": random_past_date(2),
            "priority": random.choice(["low", "normal", "high", "urgent"]),
            "created_at": created_at,
            "sent_at": created_at,
            "delivery_channels": {"in_app": True, "push": True, "email": False, "sms": False},
            "in_app_status": "sent",
            "push_status": "sent",
            "email_status": "not_sent",
            "sms_status": "not_sent",
            "delivery_error": None,
            "retry_count": 0,
            "last_retry_at": None,
            "expires_at": random_future_date(7),
            "is_expired": False,
            "clicked": random.choice([True, False]),
            "clicked_at": random_past_date(1),
            "dismissed": False,
            "dismissed_at": None,
            "respects_quiet_hours": True,
            "force_send": False,
            "tags": ["civic"],
            "category": "general",
            # FIX: renamed from `language` → `content_language`
            "content_language": random.choice(LANGUAGES),
        }
        notifications.append(notification)
    if notifications:
        await db.notifications.insert_many(notifications)
    log.info("  ✔ %d notifications inserted", len(notifications))

# ==========================
# CAMPAIGNS & DONATIONS
# ==========================

async def create_campaigns(db, corporator_id: ObjectId) -> List[Dict[str, Any]]:
    log.info("Creating %d campaigns …", CAMPAIGNS)
    campaigns = []
    for i in range(CAMPAIGNS):
        created_at = random_past_date(60)
        campaign = {
            "campaign_id": f"CAMP-2026-{i + 1:04d}",
            "title": CAMPAIGN_TITLES[i % len(CAMPAIGN_TITLES)],
            "description": "Ward development fundraising campaign.",
            "target_amount": float(random.choice([150000, 250000, 500000, 750000, 1000000])),
            "total_raised": 0.0,
            "upi_id": f"ward{i+1}.corp@upi",
            "upi_name": "Jan Sampark Development Fund",
            "created_by": str(corporator_id),
            "created_at": created_at,
            "is_active": True,
            "closed_at": None,
            "closed_by": None,
            "category": random.choice(["road_repair", "school_infrastructure", "drainage", "water_supply", "general"]),
            "ward": random.choice(WARDS),
            "area": random.choice(AREAS),
            "city": "Mumbai",
            "state": "Maharashtra",
            "donation_count": 0,
        }
        campaigns.append(campaign)
    if campaigns:
        await db.campaigns.insert_many(campaigns)
    log.info("  ✔ %d campaigns inserted", len(campaigns))
    return campaigns


async def create_donations(db, campaigns: List[Dict[str, Any]], voter_ids: List[ObjectId]) -> None:
    total_donations = random.randint(DONATIONS_MIN, DONATIONS_MAX)
    log.info("Creating ~%d donations …", total_donations)
    donations = []
    campaign_totals = {c["campaign_id"]: {"count": 0, "sum": 0.0} for c in campaigns}

    for i in range(total_donations):
        campaign = random.choice(campaigns)
        amount = random.choice([100, 250, 500, 750, 1000, 1500, 2000])
        created_at = random_past_date(30)

        donation = {
            "donation_id": f"DON-2026-{i + 1:05d}",
            "campaign_id": campaign["campaign_id"],
            "user_id": str(random.choice(voter_ids)),
            "amount": float(amount),
            "transaction_id": f"UPI-{uuid4().hex[:10].upper()}",
            "screenshot_url": "/static/donations/sample.jpg",
            "image_hash": uuid4().hex,
            "ocr_text": "Paid via UPI",
            "ocr_amount": float(amount),
            "ocr_txn_id": f"TXN{uuid4().hex[:8].upper()}",
            "is_duplicate_screenshot": False,
            "is_amount_mismatch": False,
            "is_txn_id_duplicate": False,
            "fraud_flags": [],
            "status": random.choice(["approved", "pending_review"]),
            "status_updated_at": created_at,
            "reviewed_by": None,
            "reviewed_at": None,
            "review_notes": "Auto-verified",
            "created_at": created_at,
            "receipt_id": f"RCPT-2026-{uuid4().hex[:6].upper()}",
            "receipt_url": "/static/receipts/sample.pdf",
            "contributor_name": "Voter",
            "contributor_role": UserRole.VOTER.value,
            "campaign_title": campaign["title"],
            "corporator_name": "Corporator",
            "receipt_generated_at": created_at,
            "counted_in_campaign": True,
        }
        donations.append(donation)
        cid = campaign["campaign_id"]
        campaign_totals[cid]["count"] += 1
        campaign_totals[cid]["sum"] += amount

    if donations:
        await db.donations.insert_many(donations)
    log.info("  ✔ %d donations inserted", len(donations))

    log.info("Updating campaign totals …")
    for cid, totals in campaign_totals.items():
        await db.campaigns.update_one(
            {"campaign_id": cid},
            {"$set": {"donation_count": totals["count"], "total_raised": totals["sum"]}},
        )
    log.info("  ✔ Campaign totals updated")

# ==========================
# HELP NUMBERS
# ==========================

async def create_help_numbers(db) -> None:
    log.info("Creating %d help numbers …", HELP_NUMBERS)
    docs = []
    for name, number, category in HELP_SERVICES[:HELP_NUMBERS]:
        docs.append({
            "service_name": name,
            "phone_number": number,
            "category": category,
            "created_by": "system",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "is_active": True,
            "is_system": True,
        })
    if docs:
        await db.help_numbers.insert_many(docs)
    log.info("  ✔ %d help numbers inserted", len(docs))

# ==========================
# CHATS & MESSAGES
# ==========================

async def create_chats(db, leader_ids: List[ObjectId], voter_ids: List[ObjectId]) -> List[ObjectId]:
    log.info("Creating %d chats …", CHATS)
    chats = []
    now = utc_now()
    for _ in range(CHATS):
        leader = str(random.choice(leader_ids))
        voter = str(random.choice(voter_ids))
        participants = sorted([leader, voter])
        chat = {
            "chat_type": "direct",
            "participants": participants,
            "created_by": leader,
            "broadcast_to": [],
            "last_message_text": None,
            "last_message_at": None,
            "last_message_sender": None,
            "unread_counts": {leader: 0, voter: 0},
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        chats.append(chat)
    if chats:
        result = await db.chats.insert_many(chats)
        log.info("  ✔ %d chats inserted", len(result.inserted_ids))
        return list(result.inserted_ids)
    return []


async def create_messages(db, chat_ids: List[ObjectId], leader_ids: List[ObjectId], voter_ids: List[ObjectId]) -> None:
    log.info("Creating messages for %d chats …", len(chat_ids))
    messages = []
    for chat_id in chat_ids:
        count = random.randint(4, 12)
        for _ in range(count):
            created_at = random_past_date(20)
            sender = str(random.choice(leader_ids + voter_ids))
            msg = {
                "chat_id": str(chat_id),
                "sender_id": sender,
                "content": "Hello, this is a demo message.",
                "template_flag": False,
                "is_broadcast": False,
                "broadcast_recipients": [],
                "status": "sent",
                "read_by": {sender: created_at.isoformat()},
                "is_deleted": False,
                "deleted_at": None,
                "is_deleted_globally": False,
                "deleted_for_users": [],
                "file_url": "https://example.com/file.jpg",
                "file_type": "image",
                "file_name": "file.jpg",
                "file_uploaded_at": created_at,
                "reactions": [{"user_id": sender, "reaction_type": "like", "emoji_value": None, "reacted_at": created_at}],
                "share_logs": [{"user_id": sender, "platform": "whatsapp", "shared_at": created_at}],
                "feedback": [{"user_id": sender, "text": "Good info", "rating": 4, "sentiment": "positive", "created_at": created_at, "updated_at": created_at}],
                "reaction_count": 1,
                "share_count": 1,
                "feedback_count": 1,
                "created_at": created_at,
                "updated_at": created_at,
            }
            messages.append(msg)
    if messages:
        await db.messages.insert_many(messages)
    log.info("  ✔ %d messages inserted", len(messages))

# ==========================
# VOTER LOOKUPS
# ==========================

async def create_voter_lookup_records(db, voter_ids: List[ObjectId]) -> None:
    sample_size = min(200, len(voter_ids))
    log.info("Creating %d voter lookup records …", sample_size)
    lookups = []
    for voter_id in random.sample(voter_ids, k=sample_size):
        lookups.append({
            "user_id": str(voter_id),
            "epic_number": "ITD" + "".join(random.choice(string.digits) for _ in range(7)),
            "full_name": random_name(),
            "gender": random.choice(["Male", "Female"]),
            "age": random.randint(18, 80),
            "relation_type": "Father",
            "relative_name": random_name(),
            "parliament": "Mumbai North",
            "district": "Mumbai Suburban",
            "constituency": "Andheri East",
            "state": "Maharashtra",
            "state_code": "S13",
            "polling_station": "Fatimadevi English High School",
            "polling_address": "Manchubhai Road, Malad East",
            "part_number": str(random.randint(1, 200)),
            "part_name": "Gr. Fl. Room No.4",
            "part_serial_no": random.randint(1, 500),
            "last_verified": random_past_date(30),
            "updated_at": random_past_date(10),
        })
    if lookups:
        await db.voter_lookups.insert_many(lookups)
    log.info("  ✔ %d voter lookup records inserted", len(lookups))

# ==========================
# ACTIVITY LOGS & AUDIT
# ==========================

async def create_activity_logs(db, leader_ids: List[ObjectId]) -> None:
    log.info("Creating activity logs …")
    logs = []
    for _ in range(200):
        logs.append({
            "leader_id": str(random.choice(leader_ids)),
            "activity_type": random.choice(["complaint_followup", "event", "message", "visit"]),
            "description": "Field activity logged",
            "timestamp": random_past_date(30),
            "metadata": {"ward": random.choice(WARDS)},
        })
    if logs:
        await db.activity_logs.insert_many(logs)
    log.info("  ✔ %d activity logs inserted", len(logs))


async def create_ground_verifications(db, leader_ids: List[ObjectId]) -> None:
    log.info("Creating ground verification records …")
    records = []
    for leader_id in random.sample(leader_ids, k=min(5, len(leader_ids))):
        records.append({
            "leader_id": str(leader_id),
            "location": random_location(),
            "completed_at": random_past_date(15),
            "photos": ["https://example.com/verification.jpg"],
            "notes": "Verification completed",
        })
    if records:
        await db.ground_verifications.insert_many(records)
    log.info("  ✔ %d ground verification records inserted", len(records))


async def create_audit_logs(db, ops_ids: List[ObjectId]) -> None:
    log.info("Creating audit logs …")
    logs = []
    for _ in range(50):
        logs.append({
            "ops_user_id": random.choice(ops_ids),
            "action": random.choice(["update", "delete", "approve"]),
            "resource_type": random.choice(["complaint", "campaign", "poll"]),
            "resource_id": ObjectId(),
            "changes": {"field": "status", "from": "pending", "to": "approved"},
            "timestamp": utc_now(),
        })
    if logs:
        await db.audit_logs.insert_many(logs)
    log.info("  ✔ %d audit logs inserted", len(logs))

# ==========================
# MAIN
# ==========================

async def seed() -> None:
    log.info("=" * 60)
    log.info("Starting seed script …")
    log.info("=" * 60)

    await connect_to_mongo()
    db = get_database()

    collections = [
        "users", "complaints", "events", "polls", "announcements",
        "appointments", "feedback", "notifications", "campaigns", "donations",
        "help_numbers", "chats", "messages", "voter_lookups",
        "activity_logs", "ground_verifications", "audit_logs",
    ]
    log.info("Clearing %d collections …", len(collections))
    for collection in collections:
        result = await db[collection].delete_many({})
        log.debug("  Cleared %-22s  (deleted %d docs)", collection, result.deleted_count)
    log.info("All collections cleared.")

    corporator_id = await create_corporator(db)
    ops_ids = await create_ops_users(db)
    leader_ids = await create_leaders(db, corporator_id)
    voter_ids = await create_voters(db, leader_ids)

    complaint_ids = await create_complaints(db, voter_ids, leader_ids, corporator_id)
    await create_events(db, corporator_id, leader_ids, voter_ids)
    poll_ids = await create_polls(db, corporator_id, voter_ids)
    await create_announcements(db, corporator_id)
    await create_appointments(db, voter_ids, leader_ids, corporator_id)
    await create_feedback(db, voter_ids, leader_ids, poll_ids, complaint_ids)
    await create_notifications(db, [corporator_id] + ops_ids + leader_ids + voter_ids)

    campaigns = await create_campaigns(db, corporator_id)
    await create_donations(db, campaigns, voter_ids)

    await create_help_numbers(db)
    chats = await create_chats(db, leader_ids, voter_ids)
    await create_messages(db, chats, leader_ids, voter_ids)

    await create_voter_lookup_records(db, voter_ids)
    await create_activity_logs(db, leader_ids)
    await create_ground_verifications(db, leader_ids)
    await create_audit_logs(db, ops_ids)

    await close_mongo_connection()

    log.info("=" * 60)
    log.info("Seed complete ✔")
    log.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed())
