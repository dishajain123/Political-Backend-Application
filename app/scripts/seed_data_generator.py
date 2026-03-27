"""
Comprehensive Dummy Data Seed Generator
=======================================
Generates realistic dummy data for the Political Communication Platform.
Creates users (Corporator, Leaders, Voters, OPS), complaints, announcements,
polls, events, feedback, appointments, and notifications.

This seed data is designed to:
- Match all model schemas exactly
- Provide realistic test scenarios
- Enable full feature testing
- Support analytics and reporting dashboards

Author: Political Communication Platform Team
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from bson import ObjectId
from faker import Faker
import string

# Configure Faker for India-centric data
faker = Faker(['en_IN', 'en_US'])

# ============================================================================
# CONSTANTS & CONFIGURATIONS
# ============================================================================

# Geographic data
STATES = ["Maharashtra", "Tamil Nadu", "Karnataka", "Delhi", "Gujarat"]
CITIES = {
    "Maharashtra": ["Mumbai", "Pune", "Nagpur"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai"],
    "Karnataka": ["Bangalore", "Mysore", "Kochi"],
    "Delhi": ["Delhi", "New Delhi"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara"]
}

WARDS = [f"Ward-{chr(65 + i)}" for i in range(10)]  # Ward-A to Ward-J
AREAS = [
    "Downtown", "Uptown", "Suburbs", "Industrial Zone", "Residential Complex",
    "Commercial Hub", "Tech Park", "Business District", "Garden City", "Waterfront"
]

# Complaint-related data
COMPLAINT_CATEGORIES = [
    "infrastructure", "water_supply", "electricity", "sanitation",
    "roads", "healthcare", "education", "safety", "corruption", "other"
]
COMPLAINT_PRIORITIES = ["low", "medium", "high", "urgent"]
COMPLAINT_STATUSES = ["pending", "acknowledged", "in_progress", "resolved", "closed", "rejected"]

# Event-related data
EVENT_TYPES = ["rally", "public_meeting", "town_hall", "campaign", "celebration", "awareness", "other"]
EVENT_STATUSES = ["scheduled", "ongoing", "completed", "cancelled", "postponed"]

# Poll-related data
POLL_STATUSES = ["draft", "active", "closed", "archived"]

# Announcement-related data
ANNOUNCEMENT_STATUSES = ["draft", "published", "archived"]
ANNOUNCEMENT_PRIORITIES = ["low", "normal", "high", "urgent"]
ANNOUNCEMENT_CATEGORIES = ["announcement", "policy", "scheme", "achievement", "party_message"]

# Feedback-related data
FEEDBACK_CATEGORIES = [
    "general", "service_quality", "leader_performance", "policy_feedback",
    "event_feedback", "app_feedback", "other"
]
SENTIMENT_TYPES = ["positive", "neutral", "negative", "mixed"]

# Appointment-related data
APPOINTMENT_STATUSES = ["requested", "approved", "rejected", "rescheduled", "completed", "cancelled"]
APPOINTMENT_REASONS = [
    "personal_issue", "community_issue", "feedback",
    "complaint_followup", "general_meeting", "other"
]

# Demographics
GENDERS = ["male", "female", "other", "prefer_not_to_say"]
AGE_GROUPS = ["below_18", "18_25", "26_35", "36_45", "46_60", "above_60"]
EDUCATION_LEVELS = [
    "no_formal", "primary", "secondary", "higher_secondary",
    "graduate", "post_graduate", "doctorate"
]
OCCUPATIONS = [
    "student", "employed_private", "employed_government", "self_employed",
    "business", "unemployed", "retired", "homemaker", "other"
]
ENGAGEMENT_LEVELS = ["active", "passive", "silent"]
INCOME_RANGES = ["lt_2l", "2_5l", "5_15l", "15_40l", "gt_40l"]

# Roles
ROLES = ["voter", "leader", "corporator", "ops"]

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_id() -> str:
    """Generate a unique tracking ID"""
    return f"{faker.bothify(text='????-####')}"

def generate_phone() -> str:
    """Generate an Indian phone number"""
    return f"+91{faker.numerify(text='##########')}"

def hash_password(password: str) -> str:
    """
    Simulate password hashing (in production, use bcrypt).
    For dummy data, we'll use a simple representation.
    """
    return f"$2b$12$hashed_{password}_dummy"

def get_random_location() -> Dict[str, str]:
    """Generate a random location from hierarchy"""
    state = random.choice(STATES)
    city = random.choice(CITIES[state])
    ward = random.choice(WARDS)
    area = random.choice(AREAS)
    
    return {
        "state": state,
        "city": city,
        "ward": ward,
        "area": area,
        "building": f"{random.choice(['Tower', 'Block', 'Building', 'Complex'])} {random.randint(1, 100)}",
        "booth_number": str(random.randint(100, 999))
    }

def get_random_date(start_days_ago: int = 90, end_days_ago: int = 0) -> datetime:
    """Generate a random date within a range"""
    start = datetime.utcnow() - timedelta(days=start_days_ago)
    end = datetime.utcnow() - timedelta(days=end_days_ago)
    return faker.date_time_between(start_date=start, end_date=end)

def generate_random_text(min_words: int = 5, max_words: int = 20) -> str:
    """Generate random text"""
    return faker.sentence(nb_words=random.randint(min_words, max_words))

# ============================================================================
# USER GENERATION
# ============================================================================

def generate_user_corporator() -> Dict[str, Any]:
    """Generate a Corporator user"""
    first_name = faker.first_name()
    last_name = faker.last_name()
    
    return {
        "_id": ObjectId(),
        "email": f"{first_name.lower()}.{last_name.lower()}@example.com",
        "mobile_number": generate_phone(),
        "password_hash": hash_password("CorpPassword123!"),
        "full_name": f"{first_name} {last_name}",
        "profile_photo_url": faker.image_url(),
        "role": "corporator",
        "location": get_random_location(),
        "is_active": True,
        "is_verified": True,
        "is_mobile_verified": True,
        "created_at": get_random_date(start_days_ago=180),
        "updated_at": datetime.utcnow(),
        "last_login": get_random_date(start_days_ago=7),
        "designation": random.choice(["MLA", "MP", "Party Head", "District Head"]),
        "constituency": f"{random.choice(CITIES[random.choice(STATES)])} Constituency",
        "language_preference": random.choice(["en", "hi", "mr"]),
        "notification_preferences": {
            "email": True,
            "sms": True,
            "push": True
        }
    }

def generate_user_leader() -> Dict[str, Any]:
    """Generate a Leader user"""
    first_name = faker.first_name()
    last_name = faker.last_name()
    
    return {
        "_id": ObjectId(),
        "email": f"{first_name.lower()}.{last_name.lower()}@example.com",
        "mobile_number": generate_phone(),
        "password_hash": hash_password("LeaderPassword123!"),
        "full_name": f"{first_name} {last_name}",
        "profile_photo_url": faker.image_url(),
        "role": "leader",
        "location": get_random_location(),
        "is_active": True,
        "is_verified": True,
        "is_mobile_verified": True,
        "created_at": get_random_date(start_days_ago=120),
        "updated_at": datetime.utcnow(),
        "last_login": get_random_date(start_days_ago=5),
        "territory": {
            "assigned_areas": random.sample(AREAS, k=random.randint(2, 4)),
            "assigned_wards": random.sample(WARDS, k=random.randint(2, 5)),
            "total_voters_assigned": random.randint(100, 500)
        },
        "performance": {
            "messages_shared": random.randint(10, 100),
            "complaints_followed_up": random.randint(5, 50),
            "complaints_handled": random.randint(5, 40),
            "complaints_resolved": random.randint(2, 30),
            "events_participated": random.randint(3, 20),
            "voter_interactions": random.randint(20, 150),
            "poll_responses": random.randint(50, 200),
            "poll_response_rate": round(random.uniform(0.3, 0.9), 2),
            "engagement_level": random.choice(["low", "medium", "high"]),
            "average_response_time_hours": round(random.uniform(1, 24), 1),
            "rating": round(random.uniform(3.0, 5.0), 1),
            "tasks_assigned": random.randint(10, 50),
            "tasks_completed": random.randint(5, 45),
            "ground_verifications_completed": random.randint(5, 30)
        },
        "language_preference": random.choice(["en", "hi", "mr"]),
        "notification_preferences": {
            "email": True,
            "sms": True,
            "push": True
        }
    }

def generate_user_voter() -> Dict[str, Any]:
    """Generate a Voter user"""
    first_name = faker.first_name()
    last_name = faker.last_name()
    
    return {
        "_id": ObjectId(),
        "email": f"{first_name.lower()}.{last_name.lower()}@example.com",
        "mobile_number": generate_phone(),
        "password_hash": hash_password("VoterPassword123!"),
        "full_name": f"{first_name} {last_name}",
        "profile_photo_url": faker.image_url(),
        "role": "voter",
        "location": get_random_location(),
        "is_active": True,
        "is_verified": random.choice([True, True, False]),  # 67% verified
        "is_mobile_verified": random.choice([True, True, False]),
        "created_at": get_random_date(start_days_ago=365),
        "updated_at": datetime.utcnow(),
        "last_login": get_random_date(start_days_ago=30),
        "demographics": {
            "voting_location": f"Booth {random.randint(100, 999)}",
            "age_group": random.choice(AGE_GROUPS),
            "gender": random.choice(GENDERS),
            "religion": random.choice(["Hindu", "Muslim", "Christian", "Sikh", "Buddhist", "Other"]),
            "occupation": random.choice(OCCUPATIONS),
            "profession": random.choice([
                "Software Engineer", "Teacher", "Farmer", "Business Owner",
                "Nurse", "Driver", "Shopkeeper", "Contractor", "Doctor", "Lawyer"
            ]),
            "education": random.choice(EDUCATION_LEVELS),
            "family_adults": random.randint(1, 4),
            "family_kids": random.randint(0, 3),
            "annual_income_range": random.choice(INCOME_RANGES)
        },
        "engagement": {
            "level": random.choice(ENGAGEMENT_LEVELS),
            "issues_of_interest": random.sample(COMPLAINT_CATEGORIES, k=random.randint(1, 4)),
            "last_active_date": get_random_date(start_days_ago=60),
            "total_complaints": random.randint(0, 10),
            "total_polls_participated": random.randint(0, 30),
            "total_feedback_given": random.randint(0, 15)
        },
        "language_preference": random.choice(["en", "hi", "mr"]),
        "notification_preferences": {
            "email": random.choice([True, False]),
            "sms": random.choice([True, False]),
            "push": random.choice([True, False])
        }
    }

def generate_user_ops() -> Dict[str, Any]:
    """Generate an OPS (Operations) user"""
    first_name = faker.first_name()
    last_name = faker.last_name()
    
    return {
        "_id": ObjectId(),
        "email": f"{first_name.lower()}.{last_name.lower()}@ops.example.com",
        "mobile_number": generate_phone(),
        "password_hash": hash_password("OpsPassword123!"),
        "full_name": f"{first_name} {last_name}",
        "profile_photo_url": faker.image_url(),
        "role": "ops",
        "location": get_random_location(),
        "is_active": True,
        "is_verified": True,
        "is_mobile_verified": True,
        "created_at": get_random_date(start_days_ago=200),
        "updated_at": datetime.utcnow(),
        "last_login": get_random_date(start_days_ago=1),
        "designation": random.choice(["Operations Manager", "Analyst", "Administrator", "Support Lead"]),
        "language_preference": "en",
        "notification_preferences": {
            "email": True,
            "sms": True,
            "push": True
        }
    }

# ============================================================================
# CONTENT GENERATION
# ============================================================================

def generate_complaint(creators: List[str], leaders: List[str]) -> Dict[str, Any]:
    """Generate a complaint"""
    creator_id = random.choice(creators)
    assigned_leader = random.choice(leaders) if leaders else None
    
    return {
        "_id": ObjectId(),
        "complaint_id": f"CMPL-{generate_id()}",
        "created_by": creator_id,
        "created_at": get_random_date(start_days_ago=90),
        "title": generate_random_text(min_words=5, max_words=10),
        "description": generate_random_text(min_words=20, max_words=50),
        "category": random.choice(COMPLAINT_CATEGORIES),
        "priority": random.choice(COMPLAINT_PRIORITIES),
        "status": random.choice(COMPLAINT_STATUSES),
        "location": get_random_location(),
        "assigned_to": assigned_leader,
        "assigned_at": get_random_date(start_days_ago=60) if assigned_leader else None,
        "attachment_urls": [faker.image_url() for _ in range(random.randint(0, 3))],
        "notes": [
            {
                "added_by": assigned_leader or "ops_user",
                "content": generate_random_text(min_words=10, max_words=25),
                "added_at": get_random_date(start_days_ago=30),
                "is_internal": True
            }
            for _ in range(random.randint(0, 3))
        ],
        "resolved_at": get_random_date(start_days_ago=10) if random.choice([True, False]) else None,
        "resolved_by": assigned_leader if random.choice([True, False]) else None,
        "sla_breached": random.choice([True, False, False, False])  # 25% breach rate
    }

def generate_announcement(creators: List[str]) -> Dict[str, Any]:
    """Generate an announcement"""
    created_by = random.choice(creators)
    
    return {
        "_id": ObjectId(),
        "announcement_id": f"ANN-{generate_id()}",
        "title": generate_random_text(min_words=5, max_words=12),
        "content": generate_random_text(min_words=30, max_words=100),
        "summary": generate_random_text(min_words=10, max_words=20),
        "category": random.choice(ANNOUNCEMENT_CATEGORIES),
        "priority": random.choice(ANNOUNCEMENT_PRIORITIES),
        "status": random.choice(ANNOUNCEMENT_STATUSES),
        "created_by": created_by,
        "created_at": get_random_date(start_days_ago=60),
        "published_at": get_random_date(start_days_ago=50) if random.choice([True, False]) else None,
        "is_public": random.choice([True, True, False]),
        "target": {
            "roles": random.sample(["voter", "leader"], k=random.randint(1, 2)),
            "geography": get_random_location() if random.choice([True, False]) else None,
            "issue_categories": random.sample(COMPLAINT_CATEGORIES, k=random.randint(0, 3)),
        },
        "media_urls": [faker.image_url() for _ in range(random.randint(0, 2))],
        "metrics": {
            "view_count": random.randint(0, 500),
            "unique_viewers": [str(ObjectId()) for _ in range(random.randint(0, 100))],
            "share_count": random.randint(0, 50),
            "reaction_count": random.randint(0, 100),
            "acknowledgment_count": random.randint(0, 200)
        }
    }

def generate_poll(creators: List[str]) -> Dict[str, Any]:
    """Generate a poll"""
    poll_options = [
        {"option_id": f"opt_{i}", "text": generate_random_text(3, 8), "votes": random.randint(0, 500)}
        for i in range(random.randint(2, 5))
    ]
    
    total_votes = sum(opt["votes"] for opt in poll_options)
    for opt in poll_options:
        opt["percentage"] = (opt["votes"] / total_votes * 100) if total_votes > 0 else 0
    
    return {
        "_id": ObjectId(),
        "poll_id": f"POLL-{generate_id()}",
        "title": generate_random_text(5, 12),
        "description": generate_random_text(10, 30),
        "options": poll_options,
        "status": random.choice(POLL_STATUSES),
        "created_by": random.choice(creators),
        "created_at": get_random_date(start_days_ago=60),
        "published_at": get_random_date(start_days_ago=50) if random.choice([True, False]) else None,
        "closed_at": get_random_date(start_days_ago=10) if random.choice([True, False]) else None,
        "total_responses": total_votes,
        "target": {
            "roles": random.sample(["voter", "leader"], k=random.randint(1, 2)),
        }
    }

def generate_event(creators: List[str], leaders: List[str]) -> Dict[str, Any]:
    """Generate an event"""
    event_date = datetime.utcnow() + timedelta(days=random.randint(-30, 60))
    
    return {
        "_id": ObjectId(),
        "event_id": f"EVT-{generate_id()}",
        "title": generate_random_text(5, 12),
        "description": generate_random_text(30, 80),
        "event_type": random.choice(EVENT_TYPES),
        "created_by": random.choice(creators),
        "created_at": get_random_date(start_days_ago=60),
        "event_date": event_date,
        "end_date": event_date + timedelta(hours=random.randint(1, 6)),
        "location": get_random_location(),
        "venue_name": random.choice([
            "Town Hall", "Community Center", "Public Park", "Assembly Hall",
            "School Ground", "Community Garden", "Market Square", "Stadium"
        ]),
        "status": random.choice(EVENT_STATUSES),
        "estimated_attendees": random.randint(50, 500),
        "actual_attendees": random.randint(0, 500),
        "assigned_leaders": random.sample(leaders, k=min(random.randint(1, 3), len(leaders))),
        "agenda": [generate_random_text(5, 12) for _ in range(random.randint(2, 5))],
        "media_urls": [faker.image_url() for _ in range(random.randint(0, 3))]
    }

def generate_feedback(creators: List[str], related_to: Optional[str] = None) -> Dict[str, Any]:
    """Generate feedback"""
    return {
        "_id": ObjectId(),
        "feedback_id": f"FB-{generate_id()}",
        "created_by": random.choice(creators),
        "created_at": get_random_date(start_days_ago=90),
        "category": random.choice(FEEDBACK_CATEGORIES),
        "title": generate_random_text(5, 12),
        "content": generate_random_text(20, 60),
        "rating": random.choice([1, 2, 3, 4, 5, None]),
        "related_to": related_to,
        "sentiment": random.choice(SENTIMENT_TYPES),
        "sentiment_score": round(random.uniform(-1, 1), 2),
        "keywords": [faker.word() for _ in range(random.randint(2, 5))],
        "attachment_urls": [faker.image_url() for _ in range(random.randint(0, 2))],
        "is_reviewed": random.choice([True, False, False]),
    }

def generate_appointment(voters: List[str], leaders: List[str]) -> Dict[str, Any]:
    """Generate an appointment"""
    appointment_date = datetime.utcnow() + timedelta(days=random.randint(-30, 30))
    
    return {
        "_id": ObjectId(),
        "appointment_id": f"APT-{generate_id()}",
        "requested_by": random.choice(voters),
        "requested_with": random.choice(leaders),
        "reason": random.choice(APPOINTMENT_REASONS),
        "description": generate_random_text(10, 30),
        "created_at": appointment_date - timedelta(days=random.randint(1, 5)),
        "appointment_date": appointment_date,
        "duration_minutes": random.choice([15, 30, 45, 60]),
        "location": random.choice(["Office", "Community Center", "Online", "Residence"]),
        "status": random.choice(APPOINTMENT_STATUSES),
        "notes": generate_random_text(5, 20) if random.choice([True, False]) else None,
        "feedback": {
            "rating": random.choice([1, 2, 3, 4, 5]),
            "comments": generate_random_text(10, 25),
            "given_by": random.choice(voters),
            "given_at": datetime.utcnow()
        } if random.choice([True, False]) else None
    }

def generate_notification(users: List[str]) -> Dict[str, Any]:
    """Generate a notification"""
    notification_type = random.choice([
        "announcement", "poll", "event", "complaint_update",
        "appointment_update", "system", "general"
    ])
    
    return {
        "_id": ObjectId(),
        "notification_id": f"NOT-{generate_id()}",
        "user_id": random.choice(users),
        "notification_type": notification_type,
        "title": f"{notification_type.replace('_', ' ').title()} Notification",
        "message": generate_random_text(10, 30),
        "body": generate_random_text(20, 60),
        "icon_url": faker.image_url(),
        "action_url": f"/api/v1/{notification_type}/123",
        "created_at": get_random_date(start_days_ago=30),
        "is_read": random.choice([True, False, False, False]),
        "read_at": get_random_date(start_days_ago=20) if random.choice([True, False]) else None
    }

# ============================================================================
# MAIN SEED DATA GENERATOR
# ============================================================================

async def generate_seed_data(
    num_corporators: int = 3,
    num_leaders: int = 15,
    num_voters: int = 100,
    num_ops: int = 2,
    num_complaints: int = 50,
    num_announcements: int = 20,
    num_polls: int = 15,
    num_events: int = 10,
    num_feedback: int = 30,
    num_appointments: int = 25,
    num_notifications: int = 100,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Generate complete dummy dataset for the platform.
    
    Args:
        num_corporators: Number of Corporator users
        num_leaders: Number of Leader users
        num_voters: Number of Voter users
        num_ops: Number of OPS users
        num_complaints: Number of complaints
        num_announcements: Number of announcements
        num_polls: Number of polls
        num_events: Number of events
        num_feedback: Number of feedback items
        num_appointments: Number of appointments
        num_notifications: Number of notifications
    
    Returns:
        Dictionary containing all generated data
    """
    
    print("Generating dummy data...")
    print(f"  Corporators: {num_corporators}")
    print(f"  Leaders: {num_leaders}")
    print(f"  Voters: {num_voters}")
    print(f"  OPS Users: {num_ops}")
    print(f"  Complaints: {num_complaints}")
    print(f"  Announcements: {num_announcements}")
    print(f"  Polls: {num_polls}")
    print(f"  Events: {num_events}")
    print(f"  Feedback: {num_feedback}")
    print(f"  Appointments: {num_appointments}")
    print(f"  Notifications: {num_notifications}")
    print()
    
    seed_data = {
        "users": {
            "corporators": [],
            "leaders": [],
            "voters": [],
            "ops": []
        },
        "content": {
            "complaints": [],
            "announcements": [],
            "polls": [],
            "events": [],
            "feedback": [],
            "appointments": [],
            "notifications": []
        }
    }
    
    # Generate users
    print("Generating users...")
    seed_data["users"]["corporators"] = [generate_user_corporator() for _ in range(num_corporators)]
    print(f"  Created {num_corporators} corporators")
    
    seed_data["users"]["leaders"] = [generate_user_leader() for _ in range(num_leaders)]
    print(f"  Created {num_leaders} leaders")
    
    seed_data["users"]["voters"] = [generate_user_voter() for _ in range(num_voters)]
    print(f"  Created {num_voters} voters")
    
    seed_data["users"]["ops"] = [generate_user_ops() for _ in range(num_ops)]
    print(f"  Created {num_ops} OPS users")
    print()
    
    # Extract user IDs for content generation
    corporator_ids = [u["_id"] for u in seed_data["users"]["corporators"]]
    leader_ids = [u["_id"] for u in seed_data["users"]["leaders"]]
    voter_ids = [u["_id"] for u in seed_data["users"]["voters"]]
    ops_ids = [u["_id"] for u in seed_data["users"]["ops"]]
    all_user_ids = corporator_ids + leader_ids + voter_ids + ops_ids
    
    # Generate content
    print("Generating content...")
    
    # Complaints
    seed_data["content"]["complaints"] = [
        generate_complaint(voter_ids, leader_ids)
        for _ in range(num_complaints)
    ]
    print(f"  Created {num_complaints} complaints")
    
    # Announcements
    seed_data["content"]["announcements"] = [
        generate_announcement(corporator_ids + leader_ids)
        for _ in range(num_announcements)
    ]
    print(f"  Created {num_announcements} announcements")
    
    # Polls
    seed_data["content"]["polls"] = [
        generate_poll(corporator_ids + leader_ids)
        for _ in range(num_polls)
    ]
    print(f"  Created {num_polls} polls")
    
    # Events
    seed_data["content"]["events"] = [
        generate_event(corporator_ids + leader_ids, leader_ids)
        for _ in range(num_events)
    ]
    print(f"  Created {num_events} events")
    
    # Feedback
    seed_data["content"]["feedback"] = [
        generate_feedback(voter_ids + leader_ids, related_to=random.choice(leader_ids) if random.choice([True, False]) else None)
        for _ in range(num_feedback)
    ]
    print(f"  Created {num_feedback} feedback items")
    
    # Appointments
    seed_data["content"]["appointments"] = [
        generate_appointment(voter_ids, leader_ids)
        for _ in range(num_appointments)
    ]
    print(f"  Created {num_appointments} appointments")
    
    # Notifications
    seed_data["content"]["notifications"] = [
        generate_notification(all_user_ids)
        for _ in range(num_notifications)
    ]
    print(f"  Created {num_notifications} notifications")
    print()
    
    return seed_data

# ============================================================================
# DATABASE INSERTION (ASYNC)
# ============================================================================

async def insert_seed_data_to_db(seed_data: Dict[str, Any], db=None):
    """
    Insert generated seed data into MongoDB database.
    
    Args:
        seed_data: Dictionary containing all generated data
        db: MongoDB database connection
    """
    if not db:
        print("ERROR: Database connection not provided")
        return False
    
    try:
        print("Inserting data into database...")
        
        # Insert users
        print("  Inserting corporators...")
        await db.users.insert_many(seed_data["users"]["corporators"])
        
        print("  Inserting leaders...")
        await db.users.insert_many(seed_data["users"]["leaders"])
        
        print("  Inserting voters...")
        await db.users.insert_many(seed_data["users"]["voters"])
        
        print("  Inserting OPS users...")
        await db.users.insert_many(seed_data["users"]["ops"])
        
        # Insert content
        print("  Inserting complaints...")
        if seed_data["content"]["complaints"]:
            await db.complaints.insert_many(seed_data["content"]["complaints"])
        
        print("  Inserting announcements...")
        if seed_data["content"]["announcements"]:
            await db.announcements.insert_many(seed_data["content"]["announcements"])
        
        print("  Inserting polls...")
        if seed_data["content"]["polls"]:
            await db.polls.insert_many(seed_data["content"]["polls"])
        
        print("  Inserting events...")
        if seed_data["content"]["events"]:
            await db.events.insert_many(seed_data["content"]["events"])
        
        print("  Inserting feedback...")
        if seed_data["content"]["feedback"]:
            await db.feedback.insert_many(seed_data["content"]["feedback"])
        
        print("  Inserting appointments...")
        if seed_data["content"]["appointments"]:
            await db.appointments.insert_many(seed_data["content"]["appointments"])
        
        print("  Inserting notifications...")
        if seed_data["content"]["notifications"]:
            await db.notifications.insert_many(seed_data["content"]["notifications"])
        
        print()
        print("Seed data successfully inserted into database!")
        return True
        
    except Exception as e:
        print(f"ERROR inserting seed data: {str(e)}")
        return False

# ============================================================================
# EXPORT SEED DATA TO JSON
# ============================================================================

import json

def export_seed_data_to_json(seed_data: Dict[str, Any], filename: str = "seed_data.json"):
    """
    Export seed data to JSON file for manual review or import.
    
    Args:
        seed_data: Dictionary containing all generated data
        filename: Output filename
    """
    # Convert ObjectId to string for JSON serialization
    def convert_objectid(obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, dict):
            return {k: convert_objectid(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_objectid(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return obj
    
    converted_data = convert_objectid(seed_data)
    
    try:
        with open(filename, 'w') as f:
            json.dump(converted_data, f, indent=2, default=str)
        print(f"Seed data exported to {filename}")
        return True
    except Exception as e:
        print(f"ERROR exporting seed data: {str(e)}")
        return False

# ============================================================================
# STANDALONE EXECUTION
# ============================================================================

if __name__ == "__main__":
    """
    Standalone execution for generating and exporting seed data.
    
    To use:
    1. Run: python seed_data_generator.py
    2. Check output files and logs
    
    To integrate with your FastAPI app:
    1. Import this module in your startup script
    2. Call generate_seed_data() to create dummy data
    3. Call insert_seed_data_to_db() to insert into MongoDB
    """
    
    async def main():
        # Generate seed data
        seed_data = await generate_seed_data(
            num_corporators=3,
            num_leaders=15,
            num_voters=100,
            num_ops=2,
            num_complaints=50,
            num_announcements=20,
            num_polls=15,
            num_events=10,
            num_feedback=30,
            num_appointments=25,
            num_notifications=100,
        )
        
        # Export to JSON
        export_seed_data_to_json(seed_data, "dummy_seed_data.json")
        
        # Print summary statistics
        print("=" * 60)
        print("SEED DATA GENERATION SUMMARY")
        print("=" * 60)
        print(f"Total Users: {sum(len(v) for v in seed_data['users'].values())}")
        print(f"  - Corporators: {len(seed_data['users']['corporators'])}")
        print(f"  - Leaders: {len(seed_data['users']['leaders'])}")
        print(f"  - Voters: {len(seed_data['users']['voters'])}")
        print(f"  - OPS: {len(seed_data['users']['ops'])}")
        print()
        print(f"Total Content Items: {sum(len(v) for v in seed_data['content'].values())}")
        print(f"  - Complaints: {len(seed_data['content']['complaints'])}")
        print(f"  - Announcements: {len(seed_data['content']['announcements'])}")
        print(f"  - Polls: {len(seed_data['content']['polls'])}")
        print(f"  - Events: {len(seed_data['content']['events'])}")
        print(f"  - Feedback: {len(seed_data['content']['feedback'])}")
        print(f"  - Appointments: {len(seed_data['content']['appointments'])}")
        print(f"  - Notifications: {len(seed_data['content']['notifications'])}")
        print("=" * 60)
    
    # Run async main
    asyncio.run(main())
