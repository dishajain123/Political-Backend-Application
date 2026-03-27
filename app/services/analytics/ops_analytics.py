"""
OPS Analytics Service
=====================
Aggregated analytics for OPS console.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, List
from bson import ObjectId
from app.db.mongodb import get_database
from app.utils.enums import ComplaintStatus


class OpsAnalyticsService:
    def __init__(self):
        self.db = get_database()

    def _parse_range(
        self,
        range_key: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        now = datetime.utcnow()
        if range_key == "today":
            start = datetime(now.year, now.month, now.day)
            return start, now
        if range_key == "last_7_days":
            return now - timedelta(days=7), now
        if range_key == "last_30_days":
            return now - timedelta(days=30), now
        if range_key == "last_90_days":
            return now - timedelta(days=90), now
        if range_key == "this_month":
            start = datetime(now.year, now.month, 1)
            return start, now
        if range_key == "last_month":
            first_this = datetime(now.year, now.month, 1)
            last_month_end = first_this - timedelta(seconds=1)
            start = datetime(last_month_end.year, last_month_end.month, 1)
            return start, last_month_end
        if range_key == "this_year":
            start = datetime(now.year, 1, 1)
            return start, now
        if range_key == "custom":
            if start_date and end_date and start_date > end_date:
                raise ValueError("start_date must be before end_date")
            return start_date, end_date
        return start_date, end_date

    def _date_match(self, field: str, start: Optional[datetime], end: Optional[datetime]) -> List[Dict[str, Any]]:
        if not start and not end:
            return []
        match: Dict[str, Any] = {}
        if start:
            match["$gte"] = start
        if end:
            match["$lte"] = end
        return [{"$match": {field: match}}]

    @staticmethod
    def _safe_label(value: Any, fallback: str = "Unknown") -> str:
        if value is None:
            return fallback
        label = str(value).strip()
        return label if label else fallback

    @staticmethod
    def _normalize_user_id(value: Any) -> Optional[str]:
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, str) and ObjectId.is_valid(value):
            return str(ObjectId(value))
        return None

    @staticmethod
    def _user_display_name(user: Optional[Dict[str, Any]]) -> str:
        if not user:
            return "Unknown"
        return (
            user.get("full_name")
            or user.get("name")
            or user.get("username")
            or user.get("email")
            or "Unknown"
        )

    async def _count_by_field(self, collection: str, field: str, start: Optional[datetime], end: Optional[datetime]) -> Dict[str, int]:
        pipeline = [
            *self._date_match("created_at", start, end),
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
        ]
        rows = await self.db[collection].aggregate(pipeline).to_list(None)
        return {str(r["_id"] or "unknown"): r["count"] for r in rows}

    async def _trend_by_day(self, collection: str, date_field: str, start: Optional[datetime], end: Optional[datetime]) -> List[Dict[str, Any]]:
        pipeline = [
            *self._date_match(date_field, start, end),
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": f"${date_field}"}}
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.date": 1}},
        ]
        rows = await self.db[collection].aggregate(pipeline).to_list(None)
        return [{"date": r["_id"]["date"], "value": r["count"]} for r in rows]

    async def overview(
        self,
        range_key: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        ward: Optional[str] = None,
        role: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)

        user_filter: Dict[str, Any] = {}
        if ward and ward != "All":
            user_filter["location.ward"] = ward
        if role and role != "all":
            user_filter["role"] = role

        total_users = await self.db.users.count_documents(user_filter)
        total_voters = await self.db.users.count_documents({**user_filter, "role": "voter"})
        total_leaders = await self.db.users.count_documents({**user_filter, "role": "leader"})
        total_corporators = await self.db.users.count_documents({**user_filter, "role": "corporator"})

        campaign_filter: Dict[str, Any] = {}
        if ward and ward != "All":
            campaign_filter["ward"] = ward
        if category and category != "all":
            campaign_filter["category"] = category

        event_filter: Dict[str, Any] = {}
        if ward and ward != "All":
            event_filter["location.ward"] = ward
        if status and status != "all":
            event_filter["status"] = status

        complaint_filter: Dict[str, Any] = {}
        if ward and ward != "All":
            complaint_filter["location.ward"] = ward
        if category and category != "all":
            complaint_filter["category"] = category
        if status and status != "all":
            complaint_filter["status"] = status

        total_campaigns = await self.db.campaigns.count_documents(campaign_filter)
        total_events = await self.db.events.count_documents(event_filter)
        total_complaints = await self.db.complaints.count_documents(complaint_filter)
        total_appointments = await self.db.appointments.count_documents({})
        total_messages = await self.db.messages.count_documents({})
        total_chats = await self.db.chats.count_documents({})
        total_feedback = await self.db.feedback.count_documents({})
        total_notifications = await self.db.notifications.count_documents({})

        new_users = await self.db.users.count_documents({
            **user_filter,
            **({"created_at": {"$gte": start}} if start else {}),
            **({"created_at": {"$lte": end}} if end else {}),
        })

        # Active users by last_login in range if available
        active_query: Dict[str, Any] = {"last_login": {"$exists": True}, **user_filter}
        if start:
            active_query["last_login"]["$gte"] = start
        if end:
            active_query["last_login"]["$lte"] = end
        active_users = await self.db.users.count_documents(active_query)

        # Growth vs previous period
        growth_pct = 0.0
        if start and end:
            delta = end - start
            prev_start = start - delta
            prev_end = start
            prev_new = await self.db.users.count_documents({
                "created_at": {"$gte": prev_start, "$lte": prev_end}
            })
            if prev_new > 0:
                growth_pct = ((new_users - prev_new) / prev_new) * 100.0

        role_distribution = await self._count_by_field("users", "role", None, None)
        complaint_status = await self._count_by_field("complaints", "status", start, end)
        event_status = await self._count_by_field("events", "status", start, end)
        campaign_status = await self._count_by_field("campaigns", "is_active", start, end)

        user_growth = await self._trend_by_day("users", "created_at", start, end)
        message_trend = await self._trend_by_day("messages", "created_at", start, end)

        recent_activity = await self._recent_activity(limit=15)

        # Add demographics (gender, age, occupation)
        demographics = {}
        
        # Gender distribution (normalized to Male, Female, Other)
        gender_pipeline = [
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {"_id": {"$ifNull": ["$demographics.gender", "$gender"]}, "count": {"$sum": 1}}},
        ]
        genders = await self.db.users.aggregate(gender_pipeline).to_list(None)
        demographics["gender_distribution"] = self._aggregate_gender_distribution(genders)
        
        # Age groups
        age_pipeline = [
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {"_id": {"$ifNull": ["$demographics.age_group", "$age_group"]}, "count": {"$sum": 1}}},
        ]
        ages = await self.db.users.aggregate(age_pipeline).to_list(None)
        demographics["age_groups"] = [
            {"label": r["_id"] or "Unknown", "value": r["count"]} for r in ages
        ]
        
        # Occupation categories
        occ_pipeline = [
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {"_id": {"$ifNull": ["$demographics.occupation", "$occupation"]}, "count": {"$sum": 1}}},
        ]
        occs = await self.db.users.aggregate(occ_pipeline).to_list(None)
        demographics["occupation_distribution"] = [
            {"label": r["_id"] or "Unknown", "value": r["count"]} for r in occs
        ]

        return {
            "total_users": total_users,
            "total_voters": total_voters,
            "total_leaders": total_leaders,
            "total_corporators": total_corporators,
            "total_campaigns": total_campaigns,
            "total_events": total_events,
            "total_complaints": total_complaints,
            "total_appointments": total_appointments,
            "total_messages": total_messages,
            "total_chats": total_chats,
            "total_feedback": total_feedback,
            "total_notifications": total_notifications,
            "active_users": active_users,
            "new_users": new_users,
            "growth_pct": round(growth_pct, 2),
            "role_distribution": [
                {"label": k, "value": v} for k, v in role_distribution.items()
            ],
            "complaint_status": [
                {"label": k, "value": v} for k, v in complaint_status.items()
            ],
            "event_status": [
                {"label": k, "value": v} for k, v in event_status.items()
            ],
            "campaign_status": [
                {"label": "active" if k == "True" else "closed", "value": v}
                for k, v in campaign_status.items()
            ],
            "user_growth": user_growth,
            "message_trend": message_trend,
            "recent_activity": recent_activity,
            "demographics": demographics,
        }

    async def users(self, range_key: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime], ward: Optional[str] = None, role: Optional[str] = None) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)

        user_filter: Dict[str, Any] = {}
        if ward and ward != "All":
            user_filter["location.ward"] = ward
        if role and role != "all":
            user_filter["role"] = role

        total_users = await self.db.users.count_documents(user_filter)
        verified_users = await self.db.users.count_documents({**user_filter, "is_verified": True})
        new_users = await self.db.users.count_documents({
            **user_filter,
            **({"created_at": {"$gte": start}} if start else {}),
            **({"created_at": {"$lte": end}} if end else {}),
        })
        active_query: Dict[str, Any] = {"last_login": {"$exists": True}, **user_filter}
        if start:
            active_query["last_login"]["$gte"] = start
        if end:
            active_query["last_login"]["$lte"] = end
        active_users = await self.db.users.count_documents(active_query)

        role_distribution = await self._count_by_field("users", "role", None, None)
        signup_trend = await self._trend_by_day("users", "created_at", start, end)

        language_pipeline = [
            *self._date_match("created_at", start, end),
            {"$group": {"_id": "$language_preference", "count": {"$sum": 1}}},
        ]
        languages = await self.db.users.aggregate(language_pipeline).to_list(None)
        language_distribution = [
            {"label": (r["_id"] or "unknown"), "value": r["count"]} for r in languages
        ]

        region_pipeline = [
            *self._date_match("created_at", start, end),
            {"$group": {"_id": "$location.ward", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
        regions = await self.db.users.aggregate(region_pipeline).to_list(None)
        region_distribution = [
            {"label": (r["_id"] or "unknown"), "value": r["count"]} for r in regions
        ]

        return {
            "total_users": total_users,
            "active_users": active_users,
            "verified_users": verified_users,
            "new_users": new_users,
            "role_distribution": [{"label": k, "value": v} for k, v in role_distribution.items()],
            "signup_trend": signup_trend,
            "language_distribution": language_distribution,
            "region_distribution": region_distribution,
        }

    async def users_analytics(
        self,
        range_key: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        ward: Optional[str] = None,
        role: Optional[str] = None,
        bucket_size: int = 5,
    ) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)
        now = end or datetime.utcnow()

        user_filter: Dict[str, Any] = {}
        if ward and ward != "All":
            user_filter["location.ward"] = ward
        if role and role != "all":
            user_filter["role"] = role

        total_users = await self.db.users.count_documents(user_filter)
        verified_users = await self.db.users.count_documents({**user_filter, "is_verified": True})

        active_filter: Dict[str, Any] = {"last_login": {"$exists": True}, **user_filter}
        if start:
            active_filter["last_login"]["$gte"] = start
        if end:
            active_filter["last_login"]["$lte"] = end
        active_users = await self.db.users.count_documents(active_filter)

        new_users_daily = await self.db.users.count_documents({
            **user_filter,
            "created_at": {"$gte": now - timedelta(days=1), "$lte": now},
        })
        new_users_weekly = await self.db.users.count_documents({
            **user_filter,
            "created_at": {"$gte": now - timedelta(days=7), "$lte": now},
        })
        new_users_monthly = await self.db.users.count_documents({
            **user_filter,
            "created_at": {"$gte": now - timedelta(days=30), "$lte": now},
        })

        growth_rate_pct = 0.0
        if start and end:
            delta = end - start
            prev_start = start - delta
            prev_end = start
            prev_new = await self.db.users.count_documents({
                **user_filter,
                "created_at": {"$gte": prev_start, "$lte": prev_end},
            })
            curr_new = await self.db.users.count_documents({
                **user_filter,
                "created_at": {"$gte": start, "$lte": end},
            })
            if prev_new > 0:
                growth_rate_pct = ((curr_new - prev_new) / prev_new) * 100.0

        # Demographics
        gender_pipeline = [
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {"_id": {"$ifNull": ["$demographics.gender", "$gender"]}, "count": {"$sum": 1}}},
        ]
        genders = await self.db.users.aggregate(gender_pipeline).to_list(None)
        gender_distribution = self._aggregate_gender_distribution(genders)

        safe_bucket = min(max(bucket_size, 2), 20)
        age_pipeline = [
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$project": {
                "age": {"$ifNull": ["$demographics.age", "$age"]},
                "age_group": {"$ifNull": ["$demographics.age_group", "$age_group"]},
            }},
            {"$addFields": {
                "bucket": {
                    "$cond": [
                        {"$and": [{"$ne": ["$age", None]}, {"$isNumber": "$age"}]},
                        {
                            "$concat": [
                                {"$toString": {"$subtract": ["$age", {"$mod": ["$age", safe_bucket]}]}},
                                "-",
                                {"$toString": {"$add": [{"$subtract": ["$age", {"$mod": ["$age", safe_bucket]}]}, safe_bucket - 1]}},
                            ]
                        },
                        {"$ifNull": ["$age_group", "Unknown"]},
                    ]
                }
            }},
            {"$group": {"_id": "$bucket", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        ages = await self.db.users.aggregate(age_pipeline).to_list(None)
        age_buckets = [{"label": r["_id"] or "Unknown", "value": r["count"]} for r in ages]

        occ_pipeline = [
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {"_id": {"$ifNull": ["$demographics.occupation", "$occupation"]}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        occs = await self.db.users.aggregate(occ_pipeline).to_list(None)
        occupation_distribution = [{"label": r["_id"] or "Unknown", "value": r["count"]} for r in occs]

        location_pipeline = [
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {
                "_id": {
                    "state": "$location.state",
                    "city": "$location.city",
                    "ward": "$location.ward",
                    "area": "$location.area",
                },
                "count": {"$sum": 1},
            }},
            {"$sort": {"count": -1}},
            {"$limit": 50},
        ]
        location_rows = await self.db.users.aggregate(location_pipeline).to_list(None)
        location_hierarchy = [
            {
                "region": " / ".join([s for s in [r["_id"].get("state"), r["_id"].get("city")] if s]),
                "ward": r["_id"].get("ward") or "",
                "area": r["_id"].get("area") or "",
                "value": r["count"],
            }
            for r in location_rows
        ]

        # Role analytics
        role_distribution_rows = await self.db.users.aggregate([
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {"_id": "$role", "count": {"$sum": 1}}},
        ]).to_list(None)
        role_distribution = [{"label": r["_id"] or "unknown", "value": r["count"]} for r in role_distribution_rows]

        role_growth_rows = await self.db.users.aggregate([
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {
                "_id": {
                    "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "role": "$role",
                },
                "count": {"$sum": 1},
            }},
            {"$sort": {"_id.date": 1}},
        ]).to_list(None)
        role_growth_trend = [
            {"date": r["_id"]["date"], "role": r["_id"]["role"] or "unknown", "value": r["count"]}
            for r in role_growth_rows
        ]

        active_users_per_role_rows = await self.db.users.aggregate([
            {"$match": active_filter},
            {"$group": {"_id": "$role", "count": {"$sum": 1}}},
        ]).to_list(None)
        active_users_per_role = [
            {"label": r["_id"] or "unknown", "value": r["count"]} for r in active_users_per_role_rows
        ]

        # Time-based analytics
        signup_trend = await self._trend_by_day("users", "created_at", start, end)

        base_activity_pipeline = [
            {"$project": {"created_at": "$created_at"}},
            *self._date_match("created_at", start, end),
        ]
        activity_pipeline = [
            *base_activity_pipeline,
            {"$unionWith": {"coll": "complaints", "pipeline": base_activity_pipeline}},
            {"$unionWith": {"coll": "feedback", "pipeline": base_activity_pipeline}},
            {"$unionWith": {"coll": "polls", "pipeline": [
                {"$unwind": {"path": "$responses", "preserveNullAndEmptyArrays": False}},
                {"$project": {"created_at": "$responses.responded_at"}},
                *self._date_match("created_at", start, end),
            ]}},
            {
                "$group": {
                    "_id": {"date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.date": 1}},
        ]
        activity_rows = await self.db.messages.aggregate(activity_pipeline).to_list(None)
        activity_trend = [{"date": r["_id"]["date"], "value": r["count"]} for r in activity_rows]

        retention_rows = await self.db.users.aggregate([
            {"$match": user_filter},
            {"$project": {
                "cohort": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
                "created_at": "$created_at",
                "last_login": "$last_login",
            }},
            {"$project": {
                "cohort": 1,
                "w1": {
                    "$cond": [
                        {"$and": [
                            {"$ne": ["$last_login", None]},
                            {"$gte": ["$last_login", "$created_at"]},
                            {"$lt": ["$last_login", {"$add": ["$created_at", 7 * 86400000]}]},
                        ]},
                        1,
                        0,
                    ]
                },
                "w4": {
                    "$cond": [
                        {"$and": [
                            {"$ne": ["$last_login", None]},
                            {"$gte": ["$last_login", "$created_at"]},
                            {"$lt": ["$last_login", {"$add": ["$created_at", 28 * 86400000]}]},
                        ]},
                        1,
                        0,
                    ]
                },
                "w12": {
                    "$cond": [
                        {"$and": [
                            {"$ne": ["$last_login", None]},
                            {"$gte": ["$last_login", "$created_at"]},
                            {"$lt": ["$last_login", {"$add": ["$created_at", 84 * 86400000]}]},
                        ]},
                        1,
                        0,
                    ]
                },
            }},
            {"$group": {
                "_id": "$cohort",
                "size": {"$sum": 1},
                "w1": {"$sum": "$w1"},
                "w4": {"$sum": "$w4"},
                "w12": {"$sum": "$w12"},
            }},
            {"$sort": {"_id": 1}},
        ]).to_list(None)
        retention = []
        for r in retention_rows:
            size = r.get("size", 0) or 0
            retention.append({
                "cohort": r["_id"],
                "week_1": round((r.get("w1", 0) / size) * 100, 2) if size else 0.0,
                "week_4": round((r.get("w4", 0) / size) * 100, 2) if size else 0.0,
                "week_12": round((r.get("w12", 0) / size) * 100, 2) if size else 0.0,
            })

        cohort_rows = await self.db.users.aggregate([
            {"$match": user_filter},
            {"$project": {
                "cohort": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
                "last_login": "$last_login",
            }},
            {"$project": {
                "cohort": 1,
                "active_in_period": {
                    "$cond": [
                        {"$and": [
                            {"$ne": ["$last_login", None]},
                            *([{"$gte": ["$last_login", start]}] if start else []),
                            *([{"$lte": ["$last_login", end]}] if end else []),
                        ]},
                        1,
                        0,
                    ]
                },
            }},
            {"$group": {
                "_id": "$cohort",
                "size": {"$sum": 1},
                "active_in_period": {"$sum": "$active_in_period"},
            }},
            {"$sort": {"_id": 1}},
        ]).to_list(None)
        cohorts = [
            {"cohort": r["_id"], "size": r.get("size", 0), "active_in_period": r.get("active_in_period", 0)}
            for r in cohort_rows
        ]

        # Engagement analytics
        engagement_pipeline = [
            *self._date_match("created_at", start, end),
            {"$project": {"user_id": {"$toString": "$sender_id"}, "weight": {"$literal": 1}}},
            {"$unionWith": {"coll": "complaints", "pipeline": [
                *self._date_match("created_at", start, end),
                {"$project": {"user_id": {"$toString": "$created_by"}, "weight": {"$literal": 2}}},
            ]}},
            {"$unionWith": {"coll": "feedback", "pipeline": [
                *self._date_match("created_at", start, end),
                {"$project": {"user_id": {"$toString": "$created_by"}, "weight": {"$literal": 1}}},
            ]}},
            {"$unionWith": {"coll": "polls", "pipeline": [
                {"$unwind": {"path": "$responses", "preserveNullAndEmptyArrays": False}},
                {"$project": {
                    "created_at": "$responses.responded_at",
                    "user_id": {"$toString": "$responses.user_id"},
                    "weight": {"$literal": 2},
                }},
                *self._date_match("created_at", start, end),
            ]}},
            {"$group": {"_id": "$user_id", "score": {"$sum": "$weight"}, "actions": {"$sum": 1}}},
        ]
        engagement_rows = await self.db.messages.aggregate(engagement_pipeline).to_list(None)
        engagement_rows = [r for r in engagement_rows if r.get("_id")]
        total_score = sum(r.get("score", 0) for r in engagement_rows)
        engagement_score_avg = round(total_score / len(engagement_rows), 2) if engagement_rows else 0.0

        engagement_rows_sorted = sorted(engagement_rows, key=lambda x: x.get("score", 0), reverse=True)
        top_engagement = engagement_rows_sorted[:10]

        top_ids = [r["_id"] for r in top_engagement]
        obj_ids = [ObjectId(x) for x in top_ids if ObjectId.is_valid(x)]
        user_docs = await self.db.users.find({"_id": {"$in": obj_ids}}).to_list(None) if obj_ids else []
        user_map = {str(u["_id"]): u for u in user_docs}

        most_active_users = [
            {
                "id": r["_id"],
                "label": user_map.get(r["_id"], {}).get("full_name", "Unknown"),
                "value": int(r.get("score", 0)),
                "secondary": user_map.get(r["_id"], {}).get("role", ""),
            }
            for r in top_engagement
        ]

        total_messages = await self.db.messages.count_documents({
            **({"created_at": {"$gte": start}} if start else {}),
            **({"created_at": {"$lte": end}} if end else {}),
        })
        total_complaints = await self.db.complaints.count_documents({
            **({"created_at": {"$gte": start}} if start else {}),
            **({"created_at": {"$lte": end}} if end else {}),
        })
        total_feedback = await self.db.feedback.count_documents({
            **({"created_at": {"$gte": start}} if start else {}),
            **({"created_at": {"$lte": end}} if end else {}),
        })
        poll_responses_rows = await self.db.polls.aggregate([
            {"$unwind": {"path": "$responses", "preserveNullAndEmptyArrays": False}},
            {"$project": {"created_at": "$responses.responded_at"}},
            *self._date_match("created_at", start, end),
            {"$count": "count"},
        ]).to_list(None)
        total_poll_responses = int(poll_responses_rows[0]["count"]) if poll_responses_rows else 0
        total_actions = total_messages + total_complaints + total_feedback + total_poll_responses
        avg_actions_per_user = round((total_actions / active_users), 2) if active_users else 0.0

        feature_usage_frequency = [
            {"label": "messages", "value": total_messages},
            {"label": "complaints", "value": total_complaints},
            {"label": "feedback", "value": total_feedback},
            {"label": "poll_responses", "value": total_poll_responses},
        ]

        # Complaint-based analytics
        complaints_per_user_rows = await self.db.complaints.aggregate([
            *self._date_match("created_at", start, end),
            {"$group": {"_id": "$created_by", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]).to_list(None)
        complaint_ids = [r["_id"] for r in complaints_per_user_rows if r.get("_id")]
        complaint_obj_ids = [ObjectId(x) for x in complaint_ids if ObjectId.is_valid(x)]
        complaint_users = await self.db.users.find({"_id": {"$in": complaint_obj_ids}}).to_list(None) if complaint_obj_ids else []
        complaint_user_map = {str(u["_id"]): u for u in complaint_users}
        complaints_per_user = [
            {
                "id": str(r["_id"]),
                "label": complaint_user_map.get(str(r["_id"]), {}).get("full_name", "Unknown"),
                "value": int(r.get("count", 0)),
            }
            for r in complaints_per_user_rows
        ]

        resolution_rate_rows = await self.db.complaints.aggregate([
            *self._date_match("created_at", start, end),
            {"$lookup": {
                "from": "users",
                "let": {"uid": "$created_by"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": [{"$toString": "$_id"}, {"$toString": "$$uid"}]}}},
                    {"$project": {"location": 1}},
                ],
                "as": "user",
            }},
            {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
            {"$group": {
                "_id": "$user.location.ward",
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
        ]).to_list(None)
        resolution_rate_by_group = [
            {"label": r["_id"] or "unknown", "value": int(round(r.get("rate", 0)))}
            for r in resolution_rate_rows
        ]

        active_complainants = len(await self.db.complaints.distinct(
            "created_by",
            {**({"created_at": {"$gte": start}} if start else {}), **({"created_at": {"$lte": end}} if end else {})},
        ))

        # Segmentation
        segment_counts = {"high": 0, "medium": 0, "low": 0}
        scores = sorted([int(r.get("score", 0)) for r in engagement_rows], reverse=True)
        if scores:
            high_idx = max(int(len(scores) * 0.2) - 1, 0)
            med_idx = max(int(len(scores) * 0.5) - 1, 0)
            high_threshold = scores[high_idx]
            med_threshold = scores[med_idx]
            for score in scores:
                if score >= high_threshold:
                    segment_counts["high"] += 1
                elif score >= med_threshold:
                    segment_counts["medium"] += 1
                else:
                    segment_counts["low"] += 1
        activity_segments = [
            {"label": "high", "value": segment_counts["high"]},
            {"label": "medium", "value": segment_counts["medium"]},
            {"label": "low", "value": segment_counts["low"]},
        ]

        new_users_range = await self.db.users.count_documents({
            **user_filter,
            **({"created_at": {"$gte": start}} if start else {}),
            **({"created_at": {"$lte": end}} if end else {}),
        })
        returning_users = 0
        if start and end:
            returning_users = await self.db.users.count_documents({
                **user_filter,
                "created_at": {"$lt": start},
                "last_login": {"$exists": True, "$gte": start, "$lte": end},
            })
        new_vs_returning = [
            {"label": "new", "value": new_users_range},
            {"label": "returning", "value": returning_users},
        ]

        # Geo analytics
        region_rows = await self.db.users.aggregate([
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {
                "_id": {"$concat": [{"$ifNull": ["$location.state", ""]}, " / ", {"$ifNull": ["$location.city", ""]}]},
                "count": {"$sum": 1},
            }},
            {"$sort": {"count": -1}},
        ]).to_list(None)
        region_distribution = [{"label": r["_id"] or "unknown", "value": r["count"]} for r in region_rows]

        ward_rows = await self.db.users.aggregate([
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {"_id": "$location.ward", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]).to_list(None)
        ward_distribution = [{"label": r["_id"] or "unknown", "value": r["count"]} for r in ward_rows]

        area_rows = await self.db.users.aggregate([
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {"_id": "$location.area", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]).to_list(None)
        area_distribution = [{"label": r["_id"] or "unknown", "value": r["count"]} for r in area_rows]

        density_rows = await self.db.users.aggregate([
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {"_id": {"ward": "$location.ward", "area": "$location.area"}, "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]).to_list(None)
        high_density_zones = [
            {
                "label": " / ".join([v for v in [r["_id"].get("ward"), r["_id"].get("area")] if v]),
                "value": r["count"],
            }
            for r in density_rows
        ]

        return {
            "summary": {
                "total_users": total_users,
                "active_users": active_users,
                "verified_users": verified_users,
                "growth_rate_pct": round(growth_rate_pct, 2),
                "new_users_daily": new_users_daily,
                "new_users_weekly": new_users_weekly,
                "new_users_monthly": new_users_monthly,
            },
            "demographics": {
                "gender_distribution": gender_distribution,
                "age_buckets": age_buckets,
                "occupation_distribution": occupation_distribution,
                "location_hierarchy": location_hierarchy,
            },
            "role_analytics": {
                "role_distribution": role_distribution,
                "role_growth_trend": role_growth_trend,
                "active_users_per_role": active_users_per_role,
            },
            "time_based": {
                "signup_trend": signup_trend,
                "activity_trend": activity_trend,
                "retention": retention,
                "cohorts": cohorts,
            },
            "engagement": {
                "engagement_score_avg": engagement_score_avg,
                "most_active_users": most_active_users,
                "feature_usage_frequency": feature_usage_frequency,
                "avg_actions_per_user": avg_actions_per_user,
            },
            "complaints": {
                "complaints_per_user": complaints_per_user,
                "resolution_rate_by_group": resolution_rate_by_group,
                "active_complainants": active_complainants,
            },
            "segmentation": {
                "activity_segments": activity_segments,
                "new_vs_returning": new_vs_returning,
            },
            "geo": {
                "region_distribution": region_distribution,
                "ward_distribution": ward_distribution,
                "area_distribution": area_distribution,
                "high_density_zones": high_density_zones,
            },
        }

    async def role_analytics(
        self,
        role: str,
        range_key: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        ward: Optional[str] = None,
    ) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)

        base_filter: Dict[str, Any] = {"role": role}
        if ward and ward != "All":
            base_filter["location.ward"] = ward

        total = await self.db.users.count_documents(base_filter)
        verified = await self.db.users.count_documents({**base_filter, "is_verified": True})
        new_in_period = await self.db.users.count_documents({
            **base_filter,
            **({"created_at": {"$gte": start}} if start else {}),
            **({"created_at": {"$lte": end}} if end else {}),
        })
        active_query: Dict[str, Any] = {**base_filter, "last_login": {"$exists": True}}
        if start:
            active_query["last_login"]["$gte"] = start
        if end:
            active_query["last_login"]["$lte"] = end
        active = await self.db.users.count_documents(active_query)

        trend = await self._trend_by_day("users", "created_at", start, end)
        region_pipeline = [
            *self._date_match("created_at", start, end),
            {"$match": base_filter},
            {"$group": {"_id": "$location.ward", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
        regions = await self.db.users.aggregate(region_pipeline).to_list(None)
        region_distribution = [
            {"label": (r["_id"] or "unknown"), "value": r["count"]} for r in regions
        ]

        # Top/low by performance score if present
        perf_pipeline = [
            {"$match": base_filter},
            {"$project": {"full_name": 1, "score": "$performance.rating"}},
            {"$sort": {"score": -1}},
            {"$limit": 5},
        ]
        top = await self.db.users.aggregate(perf_pipeline).to_list(None)
        low_pipeline = [
            {"$match": {"role": role}},
            {"$project": {"full_name": 1, "score": "$performance.rating"}},
            {"$sort": {"score": 1}},
            {"$limit": 5},
        ]
        low = await self.db.users.aggregate(low_pipeline).to_list(None)

        return {
            "total": total,
            "active": active,
            "verified": verified,
            "new_in_period": new_in_period,
            "trend": trend,
            "region_distribution": region_distribution,
            "top_entities": [
                {"id": str(r.get("_id", "")), "label": r.get("full_name", "Unknown"), "value": int(r.get("score") or 0)}
                for r in top
            ],
            "low_entities": [
                {"id": str(r.get("_id", "")), "label": r.get("full_name", "Unknown"), "value": int(r.get("score") or 0)}
                for r in low
            ],
        }

    async def campaigns(self, range_key: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)

        total_campaigns = await self.db.campaigns.count_documents({})
        active_campaigns = await self.db.campaigns.count_documents({"is_active": True})
        closed_campaigns = await self.db.campaigns.count_documents({"is_active": False})

        total_raised_doc = await self.db.campaigns.aggregate([
            {"$group": {"_id": None, "sum": {"$sum": "$total_raised"}}}
        ]).to_list(None)
        total_raised = float(total_raised_doc[0]["sum"]) if total_raised_doc else 0.0

        category_distribution = await self._count_by_field("campaigns", "category", start, end)
        status_distribution = {
            "active": active_campaigns,
            "closed": closed_campaigns,
        }
        trend = await self._trend_by_day("campaigns", "created_at", start, end)

        top_campaigns = await self.db.campaigns.find().sort("total_raised", -1).limit(5).to_list(None)
        low_campaigns = await self.db.campaigns.find().sort("total_raised", 1).limit(5).to_list(None)

        return {
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "closed_campaigns": closed_campaigns,
            "total_raised": total_raised,
            "category_distribution": [{"label": k, "value": v} for k, v in category_distribution.items()],
            "status_distribution": [{"label": k, "value": v} for k, v in status_distribution.items()],
            "trend": trend,
            "top_campaigns": [
                {"id": str(c.get("_id", "")), "label": c.get("title", "Unknown"), "value": int(c.get("total_raised") or 0)}
                for c in top_campaigns
            ],
            "low_campaigns": [
                {"id": str(c.get("_id", "")), "label": c.get("title", "Unknown"), "value": int(c.get("total_raised") or 0)}
                for c in low_campaigns
            ],
        }

    async def events(self, range_key: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)
        now = datetime.utcnow()

        date_filter: Dict[str, Any] = {}
        if start:
            date_filter["$gte"] = start
        if end:
            date_filter["$lte"] = end
        range_filter = {"event_date": date_filter} if date_filter else {}

        total_events = await self.db.events.count_documents(range_filter)

        status_rows = await self.db.events.aggregate([
            *self._date_match("event_date", start, end),
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]).to_list(None)
        status_distribution = [
            {"label": r.get("_id") or "unknown", "value": r.get("count", 0)}
            for r in status_rows
        ]

        type_rows = await self.db.events.aggregate([
            *self._date_match("event_date", start, end),
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
        ]).to_list(None)
        type_distribution = [
            {"label": r.get("_id") or "unknown", "value": r.get("count", 0)}
            for r in type_rows
        ]
        upcoming_rows = await self.db.events.aggregate([
            *self._date_match("event_date", start, end),
            {"$match": {"status": "scheduled", "event_date": {"$gte": now}}},
            {"$count": "count"},
        ]).to_list(None)
        upcoming_events = int(upcoming_rows[0]["count"]) if upcoming_rows else 0

        ongoing_events = await self.db.events.count_documents({**range_filter, "status": "ongoing"})
        completed_events = await self.db.events.count_documents({**range_filter, "status": "completed"})
        cancelled_events = await self.db.events.count_documents({**range_filter, "status": "cancelled"})
        postponed_events = await self.db.events.count_documents({**range_filter, "status": "postponed"})
        registration_open_events = await self.db.events.count_documents({**range_filter, "registration_open": True})

        total_reg_rows = await self.db.events.aggregate([
            *self._date_match("event_date", start, end),
            {"$project": {"reg_count": {"$size": {"$ifNull": ["$registrations", []]}}}},
            {"$group": {"_id": None, "total": {"$sum": "$reg_count"}}},
        ]).to_list(None)
        total_registrations = int(total_reg_rows[0]["total"]) if total_reg_rows else 0

        total_att_rows = await self.db.events.aggregate([
            *self._date_match("event_date", start, end),
            {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$actual_attendees", 0]}}}},
        ]).to_list(None)
        total_attendees = int(total_att_rows[0]["total"]) if total_att_rows else 0

        avg_attendance = (total_attendees / total_events) if total_events > 0 else 0.0

        avg_part_rows = await self.db.events.aggregate([
            *self._date_match("event_date", start, end),
            {"$group": {"_id": None, "avg": {"$avg": {"$ifNull": ["$participation_rate", 0]}}}},
        ]).to_list(None)
        avg_participation_rate = float(avg_part_rows[0]["avg"]) if avg_part_rows else 0.0

        avg_cap_rows = await self.db.events.aggregate([
            *self._date_match("event_date", start, end),
            {
                "$project": {
                    "utilization": {
                        "$cond": [
                            {"$and": [
                                {"$ifNull": ["$max_capacity", False]},
                                {"$gt": ["$max_capacity", 0]},
                            ]},
                            {"$divide": ["$actual_attendees", "$max_capacity"]},
                            None,
                        ]
                    }
                }
            },
            {"$match": {"utilization": {"$ne": None}}},
            {"$group": {"_id": None, "avg": {"$avg": "$utilization"}}},
        ]).to_list(None)
        avg_capacity_utilization = float(avg_cap_rows[0]["avg"]) if avg_cap_rows else 0.0

        ward_rows = await self.db.events.aggregate([
            *self._date_match("event_date", start, end),
            {"$group": {"_id": "$location.ward", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]).to_list(None)
        ward_distribution = [
            {"label": r.get("_id") or "unknown", "value": r.get("count", 0)}
            for r in ward_rows
        ]

        city_rows = await self.db.events.aggregate([
            *self._date_match("event_date", start, end),
            {"$group": {"_id": "$location.city", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]).to_list(None)
        city_distribution = [
            {"label": r.get("_id") or "unknown", "value": r.get("count", 0)}
            for r in city_rows
        ]

        organizer_rows = await self.db.events.aggregate([
            *self._date_match("event_date", start, end),
            {"$group": {"_id": "$created_by", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "user",
                }
            },
            {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
        ]).to_list(None)
        top_organizers = [
            {
                "id": str(r.get("_id") or ""),
                "label": r.get("user", {}).get("full_name", "Unknown"),
                "value": int(r.get("count", 0)),
                "secondary": r.get("user", {}).get("role"),
            }
            for r in organizer_rows
        ]

        recent_rows = await self.db.events.find(range_filter).sort("event_date", -1).limit(6).to_list(None)
        recent_events = []
        for e in recent_rows:
            location = e.get("location") or {}
            recent_events.append({
                "id": str(e.get("_id") or e.get("event_id") or ""),
                "title": e.get("title", "Untitled"),
                "date": (e.get("event_date") or e.get("created_at") or "").isoformat()
                if hasattr((e.get("event_date") or e.get("created_at")), "isoformat")
                else str(e.get("event_date") or e.get("created_at") or ""),
                "status": e.get("status", "unknown"),
                "event_type": e.get("event_type"),
                "city": location.get("city"),
                "ward": location.get("ward"),
                "attendees": int(e.get("actual_attendees") or 0),
                "registrations": len(e.get("registrations") or []),
            })

        trend = await self._trend_by_day("events", "event_date", start, end)

        return {
            "total_events": total_events,
            "upcoming_events": upcoming_events,
            "ongoing_events": ongoing_events,
            "completed_events": completed_events,
            "cancelled_events": cancelled_events,
            "postponed_events": postponed_events,
            "registration_open_events": registration_open_events,
            "total_registrations": total_registrations,
            "total_attendees": total_attendees,
            "avg_attendance": round(avg_attendance, 2),
            "avg_participation_rate": round(avg_participation_rate, 2),
            "avg_capacity_utilization": round(avg_capacity_utilization * 100, 2),
            "status_distribution": status_distribution,
            "type_distribution": type_distribution,
            "ward_distribution": ward_distribution,
            "city_distribution": city_distribution,
            "top_organizers": top_organizers,
            "recent_events": recent_events,
            "trend": trend,
        }

    async def chat(self, range_key: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)
        date_match = self._date_match("created_at", start, end)
        message_match = {"$match": {"is_deleted": False}}

        chat_date_filter: Dict[str, Any] = {}
        if start or end:
            chat_date_filter["created_at"] = {}
            if start:
                chat_date_filter["created_at"]["$gte"] = start
            if end:
                chat_date_filter["created_at"]["$lte"] = end

        total_chats = await self.db.chats.count_documents(chat_date_filter)
        active_chats = await self.db.chats.count_documents({**chat_date_filter, "is_active": True})

        message_date_filter: Dict[str, Any] = {"is_deleted": False}
        if start or end:
            message_date_filter["created_at"] = {}
            if start:
                message_date_filter["created_at"]["$gte"] = start
            if end:
                message_date_filter["created_at"]["$lte"] = end
        total_messages = await self.db.messages.count_documents(message_date_filter)

        messages_by_type_pipeline = [
            message_match,
            *date_match,
            {"$group": {"_id": {"$ifNull": ["$message_type", "unknown"]}, "count": {"$sum": 1}}},
        ]
        messages_by_type_rows = await self.db.messages.aggregate(messages_by_type_pipeline).to_list(None)
        messages_by_type = [{"label": r["_id"] or "unknown", "value": r["count"]} for r in messages_by_type_rows]

        trend_pipeline = [
            message_match,
            *date_match,
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"_id.date": 1}},
        ]
        trend_rows = await self.db.messages.aggregate(trend_pipeline).to_list(None)
        message_trend = [{"date": r["_id"]["date"], "value": r["count"]} for r in trend_rows]

        def _user_lookup(alias: str) -> Dict[str, Any]:
            return {
                "$lookup": {
                    "from": "users",
                    "let": {"sid": "$sender_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$eq": [
                                        "$_id",
                                        {
                                            "$convert": {
                                                "input": "$$sid",
                                                "to": "objectId",
                                                "onError": None,
                                                "onNull": None,
                                            }
                                        },
                                    ]
                                }
                            }
                        },
                        {"$project": {"_id": 1, "full_name": 1, "role": 1, "location": 1}},
                    ],
                    "as": alias,
                }
            }

        # Sender role distribution
        role_pipeline = [
            message_match,
            *date_match,
            _user_lookup("sender"),
            {"$unwind": {"path": "$sender", "preserveNullAndEmptyArrays": True}},
            {"$group": {"_id": {"$ifNull": ["$sender.role", "unknown"]}, "count": {"$sum": 1}}},
        ]
        roles = await self.db.messages.aggregate(role_pipeline).to_list(None)
        messages_by_role = [{"label": r["_id"] or "unknown", "value": r["count"]} for r in roles]

        # Top senders
        sender_pipeline = [
            message_match,
            *date_match,
            {"$group": {"_id": "$sender_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5},
            {
                "$lookup": {
                    "from": "users",
                    "let": {"sid": "$_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$eq": [
                                        "$_id",
                                        {
                                            "$convert": {
                                                "input": "$$sid",
                                                "to": "objectId",
                                                "onError": None,
                                                "onNull": None,
                                            }
                                        },
                                    ]
                                }
                            }
                        },
                        {"$project": {"_id": 1, "full_name": 1, "role": 1}},
                    ],
                    "as": "user",
                }
            },
            {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": True}},
        ]
        top = await self.db.messages.aggregate(sender_pipeline).to_list(None)
        top_senders = [
            {
                "id": str(r["_id"]),
                "label": r.get("user", {}).get("full_name", "Unknown"),
                "value": r.get("count", 0),
                "secondary": r.get("user", {}).get("role"),
            }
            for r in top
        ]

        reaction_pipeline = [
            message_match,
            *date_match,
            {"$unwind": {"path": "$reactions", "preserveNullAndEmptyArrays": False}},
            {"$group": {"_id": "$reactions.reaction_type", "count": {"$sum": 1}}},
        ]
        reaction_counts = await self.db.messages.aggregate(reaction_pipeline).to_list(None)
        reaction_counts = [
            {"label": r["_id"] or "unknown", "value": r["count"]} for r in reaction_counts
        ]

        total_shares_doc = await self.db.messages.aggregate([
            message_match,
            *date_match,
            {"$project": {"share_count": {"$size": {"$ifNull": ["$share_logs", []]}}}},
            {"$group": {"_id": None, "total": {"$sum": "$share_count"}}},
        ]).to_list(None)
        total_shares = int(total_shares_doc[0]["total"]) if total_shares_doc else 0

        area_pipeline = [
            message_match,
            *date_match,
            _user_lookup("sender"),
            {"$unwind": {"path": "$sender", "preserveNullAndEmptyArrays": True}},
            {
                "$group": {
                    "_id": {
                        "$ifNull": [
                            "$sender.location.area",
                            {"$ifNull": ["$sender.location.ward", "unknown"]},
                        ]
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]
        area_distribution = await self.db.messages.aggregate(area_pipeline).to_list(None)
        area_distribution = [
            {"label": r["_id"] or "unknown", "value": r["count"]} for r in area_distribution
        ]

        return {
            "total_chats": total_chats,
            "active_chats": active_chats,
            "total_messages": total_messages,
            "messages_by_type": messages_by_type,
            "messages_by_role": messages_by_role,
            "message_trend": message_trend,
            "top_senders": top_senders,
            "reaction_counts": reaction_counts,
            "total_shares": total_shares,
            "area_distribution": area_distribution,
        }

    async def complaints(self, range_key: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)
        total = await self.db.complaints.count_documents({})
        status_distribution = await self._count_by_field("complaints", "status", start, end)
        category_distribution = await self._count_by_field("complaints", "category", start, end)
        priority_distribution = await self._count_by_field("complaints", "priority", start, end)
        trend = await self._trend_by_day("complaints", "created_at", start, end)

        top_areas = await self.db.complaints.aggregate([
            *self._date_match("created_at", start, end),
            {"$group": {"_id": "$location.ward", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5},
        ]).to_list(None)
        top_areas = [
            {"id": str(i["_id"] or "unknown"), "label": str(i["_id"] or "unknown"), "value": i["count"]}
            for i in top_areas
        ]

        return {
            "total_complaints": total,
            "status_distribution": [{"label": k, "value": v} for k, v in status_distribution.items()],
            "category_distribution": [{"label": k, "value": v} for k, v in category_distribution.items()],
            "priority_distribution": [{"label": k, "value": v} for k, v in priority_distribution.items()],
            "trend": trend,
            "top_areas": top_areas,
        }

    async def complaints_geo(
        self,
        range_key: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        area: Optional[str] = None,
    ) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)

        match: Dict[str, Any] = {}
        if start or end:
            date_filter: Dict[str, Any] = {}
            if start:
                date_filter["$gte"] = start
            if end:
                date_filter["$lte"] = end
            match["created_at"] = date_filter
        if area and area != "All":
            match["location.area"] = area

        pipeline = [
            {"$match": match} if match else {"$match": {}},
            {
                "$group": {
                    "_id": {
                        "area": "$location.area",
                        "ward": "$location.ward",
                        "assigned_to": "$assigned_to",
                        "assigned_by": "$assigned_by",
                    },
                    "count": {"$sum": 1},
                }
            },
        ]
        rows = await self.db.complaints.aggregate(pipeline).to_list(None)

        # Resolve user names for leader/corporator ids
        user_ids: List[ObjectId] = []
        for row in rows:
            group = row.get("_id", {})
            for key in ("assigned_to", "assigned_by"):
                raw_id = group.get(key)
                if isinstance(raw_id, ObjectId):
                    user_ids.append(raw_id)
                elif isinstance(raw_id, str) and ObjectId.is_valid(raw_id):
                    user_ids.append(ObjectId(raw_id))
        user_ids = list({uid for uid in user_ids})
        users = await self.db.users.find({"_id": {"$in": user_ids}}).to_list(None) if user_ids else []
        user_map = {str(u["_id"]): u for u in users}

        areas_map: Dict[str, Any] = {}
        for row in rows:
            group = row.get("_id", {})
            count = int(row.get("count", 0) or 0)

            area_label = self._safe_label(group.get("area"))
            ward_label = self._safe_label(group.get("ward"))

            area_entry = areas_map.setdefault(
                area_label,
                {"area": area_label, "total": 0, "wards": {}},
            )
            area_entry["total"] += count

            ward_entry = area_entry["wards"].setdefault(
                ward_label,
                {"ward": ward_label, "total": 0, "leaders": {}, "corporators": {}},
            )
            ward_entry["total"] += count

            # Leader assignment (assigned_to)
            leader_id = self._normalize_user_id(group.get("assigned_to"))
            leader_key = leader_id or "unassigned"
            leader_name = (
                self._user_display_name(user_map.get(leader_id)) if leader_id else "Unassigned"
            )
            leader_bucket = ward_entry["leaders"].setdefault(
                leader_key, {"id": leader_key, "name": leader_name, "count": 0}
            )
            leader_bucket["count"] += count

            # Corporator / OPS assignment (assigned_by)
            assigned_by_raw = group.get("assigned_by")
            corporator_id = self._normalize_user_id(assigned_by_raw)
            if corporator_id:
                corporator_key = corporator_id
                corporator_name = self._user_display_name(user_map.get(corporator_id))
            elif isinstance(assigned_by_raw, str) and assigned_by_raw.strip():
                corporator_key = assigned_by_raw.strip()
                corporator_name = "System" if assigned_by_raw.strip().lower() == "system" else assigned_by_raw.strip()
            else:
                corporator_key = "unassigned"
                corporator_name = "Unassigned"

            corporator_bucket = ward_entry["corporators"].setdefault(
                corporator_key,
                {"id": corporator_key, "name": corporator_name, "count": 0},
            )
            corporator_bucket["count"] += count

        areas = []
        for area_entry in sorted(areas_map.values(), key=lambda a: a["total"], reverse=True):
            wards = []
            for ward_entry in sorted(area_entry["wards"].values(), key=lambda w: w["total"], reverse=True):
                leaders = sorted(
                    ward_entry["leaders"].values(), key=lambda l: l["count"], reverse=True
                )
                corporators = sorted(
                    ward_entry["corporators"].values(), key=lambda c: c["count"], reverse=True
                )
                wards.append({
                    "ward": ward_entry["ward"],
                    "total_complaints": ward_entry["total"],
                    "leaders": leaders,
                    "corporators": corporators,
                })

            areas.append({
                "area": area_entry["area"],
                "total_complaints": area_entry["total"],
                "wards": wards,
            })

        return {"areas": areas}

    async def feedback(self, range_key: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)
        total = await self.db.feedback.count_documents({})
        sentiment_distribution = await self._count_by_field("feedback", "sentiment", start, end)
        trend = await self._trend_by_day("feedback", "created_at", start, end)
        return {
            "total_feedback": total,
            "sentiment_distribution": [{"label": k, "value": v} for k, v in sentiment_distribution.items()],
            "trend": trend,
        }

    async def geo(self, range_key: Optional[str], start_date: Optional[datetime], end_date: Optional[datetime]) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)

        users_by_ward = await self.db.users.aggregate([
            *self._date_match("created_at", start, end),
            {"$group": {"_id": "$location.ward", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]).to_list(None)
        complaints_by_ward = await self.db.complaints.aggregate([
            *self._date_match("created_at", start, end),
            {"$group": {"_id": "$location.ward", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]).to_list(None)
        events_by_city = await self.db.events.aggregate([
            *self._date_match("event_date", start, end),
            {"$group": {"_id": "$location.city", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10},
        ]).to_list(None)

        return {
            "users_by_ward": [{"label": r["_id"] or "unknown", "value": r["count"]} for r in users_by_ward],
            "complaints_by_ward": [{"label": r["_id"] or "unknown", "value": r["count"]} for r in complaints_by_ward],
            "events_by_city": [{"label": r["_id"] or "unknown", "value": r["count"]} for r in events_by_city],
        }

    async def activity(self, limit: int = 20) -> Dict[str, Any]:
        return {"items": await self._recent_activity(limit=limit)}

    async def filters(self) -> Dict[str, Any]:
        wards_users = await self.db.users.distinct("location.ward")
        wards_complaints = await self.db.complaints.distinct("location.ward")
        wards_events = await self.db.events.distinct("location.ward")
        wards = sorted({w for w in (wards_users + wards_complaints + wards_events) if w})

        roles = sorted({r for r in await self.db.users.distinct("role") if r})

        complaint_categories = sorted({c for c in await self.db.complaints.distinct("category") if c})
        complaint_statuses = sorted({s for s in await self.db.complaints.distinct("status") if s})
        campaign_categories = sorted({c for c in await self.db.campaigns.distinct("category") if c})
        event_statuses = sorted({s for s in await self.db.events.distinct("status") if s})

        # Combined lists for generic filters
        categories = sorted({*complaint_categories, *campaign_categories})
        statuses = sorted({*complaint_statuses, *event_statuses})

        return {
            "wards": wards,
            "roles": roles,
            "categories": categories,
            "statuses": statuses,
            "complaint_categories": complaint_categories,
            "complaint_statuses": complaint_statuses,
            "campaign_categories": campaign_categories,
            "event_statuses": event_statuses,
        }

    async def area_detail(
        self,
        ward: str,
        range_key: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)

        user_filter: Dict[str, Any] = {"location.ward": ward}
        complaint_filter: Dict[str, Any] = {"location.ward": ward}
        event_filter: Dict[str, Any] = {"location.ward": ward}

        total_users = await self.db.users.count_documents(user_filter)
        total_voters = await self.db.users.count_documents({**user_filter, "role": "voter"})
        total_leaders = await self.db.users.count_documents({**user_filter, "role": "leader"})
        total_corporators = await self.db.users.count_documents({**user_filter, "role": "corporator"})

        active_query: Dict[str, Any] = {**user_filter, "last_login": {"$exists": True}}
        if start:
            active_query["last_login"]["$gte"] = start
        if end:
            active_query["last_login"]["$lte"] = end
        active_users = await self.db.users.count_documents(active_query)
        engagement_rate = (active_users / total_users) * 100.0 if total_users else 0.0

        complaint_status_rows = await self.db.complaints.aggregate([
            *self._date_match("created_at", start, end),
            {"$match": complaint_filter},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]).to_list(None)
        complaint_status = {str(r["_id"] or "unknown"): r["count"] for r in complaint_status_rows}

        complaint_category_rows = await self.db.complaints.aggregate([
            *self._date_match("created_at", start, end),
            {"$match": complaint_filter},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        ]).to_list(None)
        complaint_categories = {str(r["_id"] or "unknown"): r["count"] for r in complaint_category_rows}

        event_status_rows = await self.db.events.aggregate([
            *self._date_match("event_date", start, end),
            {"$match": event_filter},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]).to_list(None)
        event_status = {str(r["_id"] or "unknown"): r["count"] for r in event_status_rows}

        demographics = {}
        # Age groups
        age_pipeline = [
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {"_id": {"$ifNull": ["$demographics.age_group", "$age_group"]}, "count": {"$sum": 1}}},
        ]
        ages = await self.db.users.aggregate(age_pipeline).to_list(None)
        demographics["age_groups"] = [
            {"label": r["_id"] or "unknown", "value": r["count"]} for r in ages
        ]
        # Gender (normalized to Male, Female, Other)
        gender_pipeline = [
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {"_id": {"$ifNull": ["$demographics.gender", "$gender"]}, "count": {"$sum": 1}}},
        ]
        genders = await self.db.users.aggregate(gender_pipeline).to_list(None)
        demographics["gender_distribution"] = self._aggregate_gender_distribution(genders)
        # Occupation
        occ_pipeline = [
            *self._date_match("created_at", start, end),
            {"$match": user_filter},
            {"$group": {"_id": {"$ifNull": ["$demographics.occupation_category", "$occupation_category"]}, "count": {"$sum": 1}}},
        ]
        occs = await self.db.users.aggregate(occ_pipeline).to_list(None)
        demographics["occupation_distribution"] = [
            {"label": r["_id"] or "unknown", "value": r["count"]} for r in occs
        ]

        recent_activity = await self._recent_activity(limit=12, ward=ward)

        return {
            "ward": ward,
            "totals": {
                "total_users": total_users,
                "total_voters": total_voters,
                "total_leaders": total_leaders,
                "total_corporators": total_corporators,
                "total_complaints": await self.db.complaints.count_documents(complaint_filter),
                "total_events": await self.db.events.count_documents(event_filter),
            },
            "active_users": active_users,
            "engagement_rate": round(engagement_rate, 2),
            "complaint_status": [{"label": k, "value": v} for k, v in complaint_status.items()],
            "complaint_categories": [{"label": k, "value": v} for k, v in complaint_categories.items()],
            "event_status": [{"label": k, "value": v} for k, v in event_status.items()],
            "demographics": demographics,
            "recent_activity": recent_activity,
        }

    async def leader_detail(
        self,
        leader_id: str,
        range_key: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)

        try:
            leader_obj = ObjectId(leader_id)
        except Exception:
            leader_obj = None

        leader = await self.db.users.find_one({
            "_id": leader_obj if leader_obj else leader_id,
            "role": "leader",
        })
        if not leader:
            raise ValueError("Leader not found")

        leader_ids = [leader_id]
        if leader_obj:
            leader_ids.append(leader_obj)
        assigned_filter = {"assigned_to": {"$in": leader_ids}}
        complaints_assigned = await self.db.complaints.count_documents(assigned_filter)
        complaints_resolved = await self.db.complaints.count_documents({
            **assigned_filter,
            "status": ComplaintStatus.RESOLVED.value if hasattr(ComplaintStatus, "RESOLVED") else "resolved",
        })

        message_filter: Dict[str, Any] = {"sender_id": {"$in": leader_ids}}
        if start or end:
            date_match = {}
            if start:
                date_match["$gte"] = start
            if end:
                date_match["$lte"] = end
            message_filter["created_at"] = date_match
        messages_sent = await self.db.messages.count_documents(message_filter)

        recent_activity = await self._recent_activity(limit=12, leader_id=leader_id)

        return {
            "leader_id": leader_id,
            "full_name": leader.get("full_name", "Unknown"),
            "location": leader.get("location", {}) or {},
            "performance": leader.get("performance", {}) or {},
            "complaints_assigned": complaints_assigned,
            "complaints_resolved": complaints_resolved,
            "messages_sent": messages_sent,
            "recent_activity": recent_activity,
        }

    async def demographic_detail(
        self,
        segment_type: str,
        segment_value: str,
        range_key: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> Dict[str, Any]:
        start, end = self._parse_range(range_key, start_date, end_date)

        # Map segment_type to user fields
        field_map = {
            "age_group": "$demographics.age_group",
            "gender": "$demographics.gender",
            "occupation": "$demographics.occupation_category",
            "language": "$language_preference",
            "ward": "$location.ward",
        }
        field = field_map.get(segment_type, "$demographics.age_group")

        user_match = {"$expr": {"$eq": [field, segment_value]}}
        users_pipeline = [
            *self._date_match("created_at", start, end),
            {"$match": user_match},
        ]
        users = await self.db.users.aggregate(users_pipeline).to_list(None)
        total_users = len(users)

        active_users = 0
        if total_users:
            active_filter = {**user_match, "last_login": {"$exists": True}}
            if start:
                active_filter["last_login"]["$gte"] = start
            if end:
                active_filter["last_login"]["$lte"] = end
            active_users = await self.db.users.count_documents(active_filter)

        engagement_rate = (active_users / total_users) * 100.0 if total_users else 0.0

        complaint_status = await self._count_by_field("complaints", "status", start, end)
        sentiment_distribution = await self._count_by_field("feedback", "sentiment", start, end)

        return {
            "segment_type": segment_type,
            "segment_value": segment_value,
            "totals": {"total_users": total_users},
            "active_users": active_users,
            "engagement_rate": round(engagement_rate, 2),
            "complaint_status": [{"label": k, "value": v} for k, v in complaint_status.items()],
            "sentiment_distribution": [{"label": k, "value": v} for k, v in sentiment_distribution.items()],
        }

    async def _recent_activity(self, limit: int = 20, ward: Optional[str] = None, leader_id: Optional[str] = None) -> List[Dict[str, Any]]:
        # Fetch recent items from key collections
        complaint_filter: Dict[str, Any] = {}
        event_filter: Dict[str, Any] = {}
        campaign_filter: Dict[str, Any] = {}
        if ward:
            complaint_filter["location.ward"] = ward
            event_filter["location.ward"] = ward
            campaign_filter["ward"] = ward

        complaints = await self.db.complaints.find(complaint_filter).sort("created_at", -1).limit(5).to_list(None)
        events = await self.db.events.find(event_filter).sort("created_at", -1).limit(5).to_list(None)
        campaigns = await self.db.campaigns.find(campaign_filter).sort("created_at", -1).limit(5).to_list(None)
        appointments = await self.db.appointments.find().sort("created_at", -1).limit(5).to_list(None)

        message_filter: Dict[str, Any] = {}
        if leader_id:
            try:
                leader_obj = ObjectId(leader_id)
            except Exception:
                leader_obj = None
            sender_ids = [leader_id]
            if leader_obj:
                sender_ids.append(leader_obj)
            message_filter["sender_id"] = {"$in": sender_ids}
        messages = await self.db.messages.find(message_filter).sort("created_at", -1).limit(5).to_list(None)

        items: List[Dict[str, Any]] = []

        def _to_iso(value: Any) -> str:
            if not value:
                return ""
            if hasattr(value, "isoformat"):
                try:
                    return value.isoformat()
                except Exception:
                    pass
            if isinstance(value, str):
                return value
            if isinstance(value, (int, float)):
                try:
                    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
                except Exception:
                    return ""
            return str(value)

        for c in complaints:
            items.append({
                "type": "complaint",
                "title": c.get("title", "Complaint"),
                "timestamp": _to_iso(c.get("created_at")),
                "meta": {"status": c.get("status", "")},
            })
        for e in events:
            items.append({
                "type": "event",
                "title": e.get("title", "Event"),
                "timestamp": _to_iso(e.get("created_at")),
                "meta": {"status": e.get("status", "")},
            })
        for c in campaigns:
            items.append({
                "type": "campaign",
                "title": c.get("title", "Campaign"),
                "timestamp": _to_iso(c.get("created_at")),
                "meta": {"status": "active" if c.get("is_active") else "closed"},
            })
        for a in appointments:
            items.append({
                "type": "appointment",
                "title": f"Appointment {a.get('appointment_id', '')}",
                "timestamp": _to_iso(a.get("created_at")),
                "meta": {"status": a.get("status", "")},
            })
        for m in messages:
            items.append({
                "type": "message",
                "title": "New message",
                "timestamp": _to_iso(m.get("created_at")),
                "meta": {"type": m.get("message_type", "")},
            })

        items = sorted(items, key=lambda x: x.get("timestamp", ""), reverse=True)
        return items[:limit]

    def _normalize_gender(self, gender_value: str) -> str:
        """Normalize gender values to standard options: Male, Female, Other"""
        if not gender_value:
            return "Other"
        
        gender_lower = str(gender_value).lower().strip()
        
        # Map all variations to standard values
        if "male" in gender_lower and "female" not in gender_lower:
            return "Male"
        elif "female" in gender_lower:
            return "Female"
        else:
            # Everything else (other, prefer_not_to_say, unknown, etc.) -> Other
            return "Other"

    def _aggregate_gender_distribution(self, gender_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aggregate and normalize gender distribution data"""
        gender_counts: Dict[str, int] = {"Male": 0, "Female": 0, "Other": 0}
        
        for item in gender_list:
            raw_gender = item.get("_id") or "Unknown"
            normalized = self._normalize_gender(raw_gender)
            gender_counts[normalized] += item.get("count", 0)
        
        # Return only non-zero categories
        return [
            {"label": gender, "value": count}
            for gender, count in gender_counts.items()
            if count > 0
        ]
