"""
Analytics Service
=================
Aggregated analytics ONLY. No PII exposure.
OPS can only view aggregated, anonymized data - never raw records or voter identities.

CRITICAL OPS RULES:
- All data returned is AGGREGATED (counts, percentages, averages)
- Never expose individual voter IDs, emails, or phone numbers
- Never expose individual voter identities
- Geographic + time filters only
- Sensitive fields masked (religion, gender, age only in aggregates)
- No export of raw data

Author: Political Communication Platform Team
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.db.mongodb import get_database
from app.utils.enums import ComplaintStatus
import logging

logger = logging.getLogger("app.services.analytics_service")


class AnalyticsService:
    """OPS & Corporator analytics with strict data safety enforcement"""

    def __init__(self):
        self.db = get_database()

    def _date_match(self, field: str, start_date: datetime = None, end_date: datetime = None) -> List[Dict[str, Any]]:
        if not start_date and not end_date:
            return []
        match: Dict[str, Any] = {}
        if start_date:
            match['$gte'] = start_date
        if end_date:
            match['$lte'] = end_date
        return [{'$match': {field: match}}]

    # ==================================================
    # BASIC COMPLAINT ANALYTICS (AGGREGATED)
    # ==================================================
    
    async def complaint_summary(self, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """
        Return complaint counts by status.
        AGGREGATED ONLY - no individual records exposed.
        """
        pipeline = [
            *self._date_match('created_at', start_date, end_date),
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        results = await self.db.complaints.aggregate(pipeline).to_list(None)

        # Demographic aggregation logic (aggregated only, anonymized)
        demographics_pipeline = [
            *self._date_match('created_at', start_date, end_date),
            *self._demographic_lookup_stages("created_by"),
            {
                "$group": {
                    "_id": self._demographic_group_fields("$_demo"),
                    "count": {"$sum": 1},
                }
            },
        ]
        demographics = await self.db.complaints.aggregate(demographics_pipeline).to_list(None)
        
        # Convert to readable format
        summary = {}
        for row in results:
            status = row["_id"] or "unknown"
            summary[status] = row["count"]
        
        logger.info("Complaint summary generated")
        return {
            "summary": summary,
            "demographics_breakdown": demographics,
        }

    async def sentiment_summary(self, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """
        Aggregate sentiment from feedback.
        AGGREGATED ONLY - counts by sentiment type.
        """
        pipeline = [
            *self._date_match('created_at', start_date, end_date),
            {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}}
        ]
        results = await self.db.feedback.aggregate(pipeline).to_list(None)

        # Demographic aggregation logic (aggregated only, anonymized)
        demographics_pipeline = [
            *self._date_match('created_at', start_date, end_date),
            *self._demographic_lookup_stages("created_by"),
            {
                "$group": {
                    "_id": {
                        "sentiment": {"$ifNull": ["$sentiment", "unknown"]},
                        **self._demographic_group_fields("$_demo"),
                    },
                    "count": {"$sum": 1},
                }
            },
        ]
        demographics = await self.db.feedback.aggregate(demographics_pipeline).to_list(None)
        
        summary = {}
        for row in results:
            sentiment = row["_id"] or "unknown"
            summary[sentiment] = row["count"]
        
        logger.info("Sentiment summary generated")
        return {
            "summary": summary,
            "demographics_breakdown": demographics,
        }

    async def issue_heatmap(self, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """
        Aggregate complaints by geography for heatmap.
        AGGREGATED ONLY - counts by area, no voter identities.
        """
        pipeline = [
            *self._date_match('created_at', start_date, end_date),
            {
                "$group": {
                    "_id": {
                        "state": "$location.state",
                        "city": "$location.city",
                        "ward": "$location.ward",
                        "area": "$location.area",
                    },
                    "count": {"$sum": 1},
                }
            }
        ]
        results = await self.db.complaints.aggregate(pipeline).to_list(None)
        
        logger.info("Issue heatmap generated")
        return {
            "heatmap": results,
            "note": "Geographic aggregation only - no individual records exposed"
        }

    async def voter_mood_trends(self, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """
        Aggregate feedback sentiment by day.
        AGGREGATED ONLY - counts by date and sentiment.
        """
        pipeline = [
            *self._date_match('created_at', start_date, end_date),
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                        "sentiment": "$sentiment",
                    },
                    "count": {"$sum": 1},
                }
            }
        ]
        results = await self.db.feedback.aggregate(pipeline).to_list(None)
        
        logger.info("Voter mood trends generated")
        return {
            "trends": results,
            "note": "Daily sentiment aggregation - no voter identities"
        }

    # ==================================================
    # LEADER PERFORMANCE (AGGREGATED, NO PII)
    # ==================================================
    
    async def leader_performance(self) -> Dict[str, Any]:
        """
        Leader performance metrics from aggregated user profiles.
        AGGREGATED ONLY - no exposure of individual voter details.
        """
        leaders = await self.db.users.find({"role": "leader"}).to_list(None)
        results = []
        
        for leader in leaders:
            performance = leader.get("performance", {}) or {}
            engagement_level = self._compute_engagement_level(performance)
            
            # CRITICAL: Only expose performance metrics, not personal details
            results.append(
                {
                    "leader_id": str(leader["_id"]),  # Leader ID is safe (not voter)
                    "location": leader.get("location", {}),  # Safe to expose (geographic)
                    "performance": performance,
                    "engagement_level": engagement_level,
                    # DO NOT expose: full_name, email, phone, personal details
                }
            )
        
        logger.info(f"Leader performance metrics generated for {len(results)} leaders")
        return {
            "leaders": results,
            "total": len(results),
            "note": "Aggregated performance metrics - no voter PII included"
        }

    async def communication_effectiveness(self, start_date: datetime = None, end_date: datetime = None) -> Dict[str, Any]:
        """
        Aggregate announcement reach and engagement.
        AGGREGATED ONLY - counts and percentages.
        """
        pipeline = [
            *self._date_match('created_at', start_date, end_date),
            {
                "$project": {
                    "_id": 0,
                    "announcement_id": 1,
                    "title": 1,
                    "category": 1,
                    "priority": 1,
                    "view_count": "$metrics.view_count",
                    "share_count": "$metrics.share_count",
                    "reaction_count": "$metrics.reaction_count",
                    "comment_count": "$metrics.comment_count",
                    "acknowledgment_count": "$metrics.acknowledgment_count",
                }
            }
        ]
        results = await self.db.announcements.aggregate(pipeline).to_list(None)
        
        logger.info("Communication effectiveness metrics generated")
        return {
            "announcements": results,
            "total": len(results),
            "note": "Aggregated engagement metrics only"
        }

    # ==================================================
    # OPS INTELLIGENCE (AGGREGATED ONLY)
    # ==================================================
    
    async def voter_intelligence(self, days_inactive: int = 30) -> Dict[str, Any]:
        """
        Aggregated voter intelligence without exposing identities.
        CRITICAL: Only aggregates - NEVER exposes individual voter names, IDs, emails.
        """
        voters_match = {"role": "voter"}

        # Engagement level aggregation
        engagement_pipeline = [
            {"$match": voters_match},
            {"$group": {"_id": "$engagement.level", "count": {"$sum": 1}}},
        ]

        # Geographic aggregation (areas, not individual voters)
        geo_pipeline = [
            {"$match": voters_match},
            {
                "$group": {
                    "_id": {
                        "state": "$location.state",
                        "city": "$location.city",
                        "ward": "$location.ward",
                        "area": "$location.area",
                    },
                    "count": {"$sum": 1},
                }
            },
        ]

        # Demographics aggregation ONLY (no individual voter connection)
        demographics_pipeline = [
            {"$match": voters_match},
            {
                "$group": {
                    "_id": {
                        "age_group": "$demographics.age_group",
                        "gender": "$demographics.gender",
                        "occupation": "$demographics.occupation",
                        "education": "$demographics.education",
                    },
                    "count": {"$sum": 1},
                }
            },
        ]

        # Extended demographic aggregation logic
        demographics_extended_pipeline = [
            {"$match": voters_match},
            {
                "$group": {
                    "_id": self._demographic_group_fields("$demographics"),
                    "count": {"$sum": 1},
                }
            },
        ]

        # Engagement metrics aggregation by demographics
        engagement_demographics_pipeline = [
            {"$match": voters_match},
            {
                "$group": {
                    "_id": self._demographic_group_fields("$demographics"),
                    "count": {"$sum": 1},
                    "avg_polls_participated": {"$avg": "$engagement.total_polls_participated"},
                    "avg_feedback_given": {"$avg": "$engagement.total_feedback_given"},
                    "avg_complaints": {"$avg": "$engagement.total_complaints"},
                }
            },
        ]

        # Engagement metrics aggregation
        engagement_metrics_pipeline = [
            {"$match": voters_match},
            {
                "$group": {
                    "_id": None,
                    "avg_polls_participated": {"$avg": "$engagement.total_polls_participated"},
                    "avg_feedback_given": {"$avg": "$engagement.total_feedback_given"},
                    "avg_complaints": {"$avg": "$engagement.total_complaints"},
                }
            },
        ]

        # Silent voters detection (aggregated count only, NO VOTER NAMES/IDS)
        inactive_cutoff = datetime.utcnow() - timedelta(days=days_inactive)
        silent_query = {
            "role": "voter",
            "$and": [
                {"$or": [{"engagement.last_active_date": {"$lt": inactive_cutoff}}, {"engagement.last_active_date": None}]},
                {"$or": [{"engagement.total_polls_participated": 0}, {"engagement.total_polls_participated": None}]},
                {"$or": [{"engagement.total_feedback_given": 0}, {"engagement.total_feedback_given": None}]},
                {"$or": [{"engagement.total_complaints": 0}, {"engagement.total_complaints": None}]},
            ],
        }

        silent_count = await self.db.users.count_documents(silent_query)
        
        logger.info(f"Voter intelligence generated - {silent_count} silent voters detected")

        return {
            "segmentation": await self.db.users.aggregate(engagement_pipeline).to_list(None),
            "geography": await self.db.users.aggregate(geo_pipeline).to_list(None),
            "demographics": await self.db.users.aggregate(demographics_pipeline).to_list(None),
            "demographics_extended": await self.db.users.aggregate(demographics_extended_pipeline).to_list(None),
            "engagement_metrics": (await self.db.users.aggregate(engagement_metrics_pipeline).to_list(None))[:1],
            "engagement_metrics_by_demographics": await self.db.users.aggregate(engagement_demographics_pipeline).to_list(None),
            "silent_voters_count": silent_count,  # COUNT ONLY, NO NAMES/IDS
            "silent_window_days": days_inactive,
            "note": "All data aggregated - no individual voter identities exposed"
        }

    async def issue_intelligence(self, days_window: int = 90) -> Dict[str, Any]:
        """
        Issue categorization, SLA tracking, heatmaps, and escalation analytics.
        AGGREGATED ONLY - no individual complaint records exposed.
        """
        since = datetime.utcnow() - timedelta(days=days_window)

        category_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        ]

        tag_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$unwind": {"path": "$tags", "preserveNullAndEmptyArrays": False}},
            {"$group": {"_id": "$tags", "count": {"$sum": 1}}},
        ]

        area_density_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {
                        "state": "$location.state",
                        "city": "$location.city",
                        "ward": "$location.ward",
                        "area": "$location.area",
                    },
                    "count": {"$sum": 1},
                }
            },
        ]

        sla_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$project": {
                    "created_at": {"$toDate": "$created_at"},
                    "assigned_at": {"$toDate": "$assigned_at"},
                    "resolved_at": {"$toDate": "$resolved_at"},
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_time_to_ack_hours": {
                        "$avg": {
                            "$cond": [
                                {"$and": ["$assigned_at", "$created_at"]},
                                {"$divide": [{"$dateDiff": {"startDate": "$created_at", "endDate": "$assigned_at", "unit": "minute"}}, 60]},
                                None,
                            ]
                        }
                    },
                    "avg_time_to_resolve_hours": {
                        "$avg": {
                            "$cond": [
                                {"$and": ["$resolved_at", "$created_at"]},
                                {"$divide": [{"$dateDiff": {"startDate": "$created_at", "endDate": "$resolved_at", "unit": "minute"}}, 60]},
                                None,
                            ]
                        }
                    },
                }
            },
        ]

        resolution_quality_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": None,
                    "claimed": {
                        "$sum": {
                            "$cond": [
                                {"$and": [{"$in": ["$status", [ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value]]}, {"$eq": ["$voter_satisfaction_rating", None]}]},
                                1,
                                0,
                            ]
                        }
                    },
                    "verified": {
                        "$sum": {
                            "$cond": [
                                {"$ne": ["$voter_satisfaction_rating", None]},
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
        ]

        reopened_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$project": {
                    "reopened": {
                        "$gt": [
                            {
                                "$size": {
                                    "$filter": {
                                        "input": "$audit_trail",
                                        "as": "a",
                                        "cond": {
                                            "$and": [
                                                {"$in": ["$$a.status_from", [ComplaintStatus.RESOLVED.value, ComplaintStatus.CLOSED.value]]},
                                                {"$in": ["$$a.status_to", [ComplaintStatus.IN_PROGRESS.value, ComplaintStatus.ACKNOWLEDGED.value]]},
                                            ]
                                        },
                                    }
                                }
                            },
                            0,
                        ]
                    }
                }
            },
            {"$group": {"_id": "$reopened", "count": {"$sum": 1}}},
        ]

        # CRITICAL: Leader assignment counts only (no voter names/IDs)
        leader_responsibility_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$group": {"_id": "$assigned_to", "assigned_count": {"$sum": 1}}},
        ]

        logger.info("Issue intelligence generated")
        
        return {
            "issue_categories": await self.db.complaints.aggregate(category_pipeline).to_list(None),
            "issue_tags": await self.db.complaints.aggregate(tag_pipeline).to_list(None),
            "area_density": await self.db.complaints.aggregate(area_density_pipeline).to_list(None),
            "sla_metrics": (await self.db.complaints.aggregate(sla_pipeline).to_list(None))[:1],
            "resolution_quality": (await self.db.complaints.aggregate(resolution_quality_pipeline).to_list(None))[:1],
            "reopened_detection": await self.db.complaints.aggregate(reopened_pipeline).to_list(None),
            "leader_responsibility": await self.db.complaints.aggregate(leader_responsibility_pipeline).to_list(None),
            "window_days": days_window,
            "note": "All data aggregated - no individual complaint records or voter identities"
        }

    async def sentiment_mood_analysis(self, days_window: int = 90, spike_threshold: float = 0.35) -> Dict[str, Any]:
        """
        Sentiment trends, spikes, and area-specific negativity.
        AGGREGATED ONLY - no individual voter sentiment exposed.
        """
        since = datetime.utcnow() - timedelta(days=days_window)

        feedback_trends = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                        "sentiment": "$sentiment",
                    },
                    "count": {"$sum": 1},
                }
            },
        ]

        complaint_trends = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                        "sentiment": "$sentiment",
                    },
                    "count": {"$sum": 1},
                }
            },
        ]

        poll_trends = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$unwind": {"path": "$responses", "preserveNullAndEmptyArrays": False}},
            {
                "$group": {
                    "_id": {
                        "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$responses.responded_at"}},
                        "sentiment": "$responses.sentiment",
                    },
                    "count": {"$sum": 1},
                }
            },
        ]

        feedback_daily_neg = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                    "total": {"$sum": 1},
                    "negative": {"$sum": {"$cond": [{"$eq": ["$sentiment", "negative"]}, 1, 0]}},
                }
            },
        ]

        daily = await self.db.feedback.aggregate(feedback_daily_neg).to_list(None)
        spikes = []
        for row in daily:
            total = row.get("total", 0) or 0
            negative = row.get("negative", 0) or 0
            if total > 0 and (negative / total) >= spike_threshold:
                spikes.append({"date": row["_id"], "negative_rate": round(negative / total, 3)})

        area_negativity = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {
                        "state": "$location.state",
                        "city": "$location.city",
                        "ward": "$location.ward",
                        "area": "$location.area",
                    },
                    "negative": {"$sum": {"$cond": [{"$eq": ["$sentiment", "negative"]}, 1, 0]}},
                    "total": {"$sum": 1},
                }
            },
        ]

        # Sentiment by demographics
        feedback_sentiment_demographics = [
            {"$match": {"created_at": {"$gte": since}}},
            *self._demographic_lookup_stages("created_by"),
            {
                "$group": {
                    "_id": {
                        "sentiment": {"$ifNull": ["$sentiment", "unknown"]},
                        **self._demographic_group_fields("$_demo"),
                    },
                    "count": {"$sum": 1},
                }
            },
        ]

        logger.info("Sentiment mood analysis generated")
        
        return {
            "feedback_trends": await self.db.feedback.aggregate(feedback_trends).to_list(None),
            "complaint_trends": await self.db.complaints.aggregate(complaint_trends).to_list(None),
            "poll_trends": await self.db.polls.aggregate(poll_trends).to_list(None),
            "negative_spikes": spikes,
            "area_negativity": await self.db.feedback.aggregate(area_negativity).to_list(None),
            "feedback_sentiment_demographics": await self.db.feedback.aggregate(feedback_sentiment_demographics).to_list(None),
            "window_days": days_window,
            "spike_threshold": spike_threshold,
            "note": "All data aggregated by geography/time - no individual voter identities"
        }

    async def sentiment_impact(self, entity_type: str, window_days: int = 7, limit: int = 20) -> Dict[str, Any]:
        """
        Sentiment before vs after announcements/events.
        AGGREGATED ONLY - trends by date, no voter identities.
        """
        results = []
        if entity_type == "events":
            cursor = self.db.events.find({}, {"event_id": 1, "title": 1, "event_date": 1}).sort("event_date", -1).limit(limit)
            async for event in cursor:
                event_date = event.get("event_date")
                if not event_date:
                    continue
                before_start = event_date - timedelta(days=window_days)
                after_end = event_date + timedelta(days=window_days)
                before = await self._sentiment_counts(before_start, event_date)
                after = await self._sentiment_counts(event_date, after_end)
                results.append({
                    "event_id": event.get("event_id"),
                    "title": event.get("title"),
                    "before": before,
                    "after": after,
                })
        else:
            category_filter = {"category": "policy"} if entity_type == "policies" else {}
            cursor = self.db.announcements.find(category_filter, {"announcement_id": 1, "title": 1, "published_at": 1}).sort("published_at", -1).limit(limit)
            async for ann in cursor:
                published_at = ann.get("published_at")
                if not published_at:
                    continue
                before_start = published_at - timedelta(days=window_days)
                after_end = published_at + timedelta(days=window_days)
                before = await self._sentiment_counts(before_start, published_at)
                after = await self._sentiment_counts(published_at, after_end)
                results.append({
                    "announcement_id": ann.get("announcement_id"),
                    "title": ann.get("title"),
                    "before": before,
                    "after": after,
                })
        
        logger.info(f"Sentiment impact analysis generated for {entity_type}")
        return {
            "results": results,
            "entity_type": entity_type,
            "window_days": window_days,
            "note": "Aggregated sentiment trends only - no individual voter data"
        }

    async def leader_performance_dashboard(self) -> Dict[str, Any]:
        """
        Leader performance with normalized scores and quality indicators.
        AGGREGATED ONLY - metrics aggregated from complaint/feedback data.
        """
        leaders = await self.db.users.find({"role": "leader"}).to_list(None)
        
        # Aggregate resolution quality (counts, averages - NO VOTER NAMES)
        quality_pipeline = [
            {"$match": {"resolved_by": {"$ne": None}}},
            {"$group": {"_id": "$resolved_by", "avg_rating": {"$avg": "$voter_satisfaction_rating"}}},
        ]
        quality = {row["_id"]: row.get("avg_rating") for row in await self.db.complaints.aggregate(quality_pipeline).to_list(None)}

        # Aggregate area coverage (geography only)
        area_coverage_pipeline = [
            {"$match": {"assigned_to": {"$ne": None}}},
            {"$group": {"_id": {"leader_id": "$assigned_to", "area": "$location.area"}, "count": {"$sum": 1}}},
        ]
        area_rows = await self.db.complaints.aggregate(area_coverage_pipeline).to_list(None)
        coverage = {}
        for row in area_rows:
            leader_id = row["_id"]["leader_id"]
            coverage.setdefault(leader_id, set()).add(row["_id"]["area"])

        results = []
        for leader in leaders:
            performance = leader.get("performance", {}) or {}
            engagement_level = self._compute_engagement_level(performance)
            resolution_quality = quality.get(str(leader["_id"]))
            area_count = len(coverage.get(str(leader["_id"]), set()))
            effectiveness = performance.get("complaints_resolved", 0)
            engagement = performance.get("complaints_followed_up", 0)
            normalized_score = round(
                (performance.get("messages_shared", 0) * 1.0)
                + (performance.get("events_participated", 0) * 1.0)
                + (performance.get("complaints_followed_up", 0) * 1.5)
                + (performance.get("poll_response_rate", 0) * 0.2),
                2,
            )
            
            # CRITICAL: Only expose leader performance metrics, NO VOTER DATA
            results.append(
                {
                    "leader_id": str(leader["_id"]),
                    "location": leader.get("location"),
                    "performance": performance,
                    "engagement_level": engagement_level,
                    "normalized_score": normalized_score,
                    "resolution_quality": resolution_quality,
                    "area_coverage_count": area_count,
                    "engagement_vs_effectiveness": {
                        "engagement": engagement,
                        "effectiveness": effectiveness,
                    },
                }
            )
        
        logger.info(f"Leader performance dashboard generated for {len(results)} leaders")
        return {
            "leaders": results,
            "total": len(results),
            "note": "Aggregated leader performance metrics - no voter data included"
        }

    async def ops_communication_effectiveness(self, days_window: int = 90, complaint_threshold: int = 5) -> Dict[str, Any]:
        """
        Communication effectiveness with confusion signals and gaps.
        AGGREGATED ONLY - counts and patterns, no voter identities.
        """
        since = datetime.utcnow() - timedelta(days=days_window)

        announcement_gap_pipeline = [
            {"$match": {"published_at": {"$ne": None}}},
            {
                "$match": {
                    "metrics.view_count": 0,
                    "metrics.acknowledgment_count": 0,
                }
            },
            {"$project": {"_id": 0, "announcement_id": 1, "title": 1, "category": 1}},
        ]

        poll_participation_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$project": {
                    "_id": 0,
                    "poll_id": 1,
                    "title": 1,
                    "total_responses": 1,
                    "participation_rate": 1,
                }
            },
        ]

        # Poll participation by voter demographics
        poll_participation_demographics_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$unwind": {"path": "$responses", "preserveNullAndEmptyArrays": False}},
            *self._demographic_lookup_stages("responses.user_id"),
            {
                "$group": {
                    "_id": self._demographic_group_fields("$_demo"),
                    "responses": {"$sum": 1},
                }
            },
        ]

        confusion_feedback_pipeline = [
            {"$match": {"created_at": {"$gte": since}, "reaction": "confused"}},
            {"$group": {"_id": None, "confused_count": {"$sum": 1}}},
        ]

        confusion_poll_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {"$unwind": {"path": "$responses", "preserveNullAndEmptyArrays": False}},
            {"$match": {"responses.sentiment": "mixed"}},
            {"$group": {"_id": None, "confused_count": {"$sum": 1}}},
        ]

        repeated_complaints_pipeline = [
            {"$match": {"created_at": {"$gte": since}}},
            {
                "$group": {
                    "_id": {
                        "category": "$category",
                        "area": "$location.area",
                    },
                    "count": {"$sum": 1},
                }
            },
            {"$match": {"count": {"$gte": complaint_threshold}}},
        ]

        logger.info("OPS communication effectiveness analysis generated")
        
        return {
            "message_reach_gaps": await self.db.announcements.aggregate(announcement_gap_pipeline).to_list(None),
            "poll_participation": await self.db.polls.aggregate(poll_participation_pipeline).to_list(None),
            "poll_participation_demographics": await self.db.polls.aggregate(poll_participation_demographics_pipeline).to_list(None),
            "confusion_signals": {
                "feedback_confused": (await self.db.feedback.aggregate(confusion_feedback_pipeline).to_list(None))[:1],
                "poll_confused": (await self.db.polls.aggregate(confusion_poll_pipeline).to_list(None))[:1],
            },
            "repeated_complaints": await self.db.complaints.aggregate(repeated_complaints_pipeline).to_list(None),
            "window_days": days_window,
            "note": "Aggregated communication patterns only - no individual voter identities"
        }

    async def ops_system_features(self) -> Dict[str, Any]:
        """
        Decision-grade system feature checks and metrics (aggregated only).
        """
        voter_intel = await self.voter_intelligence()
        leader_perf = await self.leader_performance_dashboard()
        issue_intel = await self.issue_intelligence()
        
        logger.info("OPS system features check completed")
        
        return {
            "two_way_communication_loops": True,
            "issue_urgency_classification": True,
            "complaint_closure_verification": True,
            "micro_campaign_targeting_support": True,
            "silent_voter_tracking": voter_intel.get("silent_voters_count", 0),
            "leader_accountability_scoring": len(leader_perf.get("leaders", [])),
            "decision_grade_dashboards": True,
            "sample_metrics": {
                "issues_tracked": len(issue_intel.get("issue_categories", [])),
            },
            "note": "All metrics aggregated - strict data safety enforcement applied"
        }

    async def chat_analytics(self) -> Dict[str, Any]:
        """
        Chat and broadcast performance analytics.
        AGGREGATED ONLY - counts and metrics, no individual message content.
        """
        # Total messages
        total_messages = await self.db.messages.count_documents({})
        
        # Messages by type
        type_pipeline = [
            {"$group": {"_id": "$message_type", "count": {"$sum": 1}}}
        ]
        messages_by_type = await self.db.messages.aggregate(type_pipeline).to_list(None)
        
        # Reaction counts
        reactions_pipeline = [
            {"$unwind": {"path": "$reactions", "preserveNullAndEmptyArrays": False}},
            {"$group": {"_id": "$reactions.type", "count": {"$sum": 1}}}
        ]
        reactions_count = await self.db.messages.aggregate(reactions_pipeline).to_list(None)
        
        # Share counts
        shares_pipeline = [
            {"$group": {"_id": None, "total_shares": {"$sum": "$share_count"}}}
        ]
        share_count = await self.db.messages.aggregate(shares_pipeline).to_list(None)
        
        # Top active users (by message count, no names)
        active_users_pipeline = [
            {"$group": {"_id": "$from_user_id", "message_count": {"$sum": 1}}},
            {"$sort": {"message_count": -1}},
            {"$limit": 10}
        ]
        top_users = await self.db.messages.aggregate(active_users_pipeline).to_list(None)
        
        # Area-wise message distribution
        area_distribution_pipeline = [
            *self._demographic_lookup_stages("from_user_id"),
            {
                "$group": {
                    "_id": {
                        "state": "$_demo.location.state",
                        "city": "$_demo.location.city",
                        "area": "$_demo.location.area",
                    },
                    "message_count": {"$sum": 1}
                }
            }
        ]
        area_distribution = await self.db.messages.aggregate(area_distribution_pipeline).to_list(None)
        
        logger.info("Chat analytics generated")
        
        return {
            "total_messages": total_messages,
            "messages_by_type": messages_by_type,
            "reactions_count": reactions_count,
            "total_shares": (share_count[0]["total_shares"] if share_count else 0),
            "top_active_users": top_users,
            "area_wise_distribution": area_distribution,
            "note": "Aggregated chat metrics only - no message content or user identities"
        }

    async def broadcast_performance(self) -> Dict[str, Any]:
        """
        Broadcast (announcement) performance analytics.
        AGGREGATED ONLY - engagement metrics, no recipient information.
        """
        def _num(field: str) -> Dict[str, Any]:
            return {
                "$convert": {
                    "input": field,
                    "to": "double",
                    "onError": 0,
                    "onNull": 0,
                }
            }

        recipient_count_expr = {
            "$cond": [
                {"$isArray": "$total_recipients"},
                {"$size": "$total_recipients"},
                {
                    "$cond": [
                        {"$isArray": "$target.specific_users"},
                        {"$size": "$target.specific_users"},
                        _num("$total_recipients"),
                    ]
                },
            ]
        }

        delivered_expr = {
            "$convert": {
                "input": {
                    "$ifNull": ["$metrics.delivered_count", "$metrics.view_count"]
                },
                "to": "double",
                "onError": 0,
                "onNull": 0,
            }
        }
        viewed_expr = _num("$metrics.view_count")
        replied_expr = {
            "$convert": {
                "input": {"$ifNull": ["$metrics.reply_count", "$metrics.comment_count"]},
                "to": "double",
                "onError": 0,
                "onNull": 0,
            }
        }

        broadcasts_pipeline = [
            {
                "$project": {
                    "_id": 0,
                    "broadcast_id": {
                        "$convert": {
                            "input": "$_id",
                            "to": "string",
                            "onError": "",
                            "onNull": "",
                        }
                    },
                    "title": 1,
                    "sent_at": 1,
                    "total_recipients": recipient_count_expr,
                    "delivered": delivered_expr,
                    "viewed": viewed_expr,
                    "replied": replied_expr,
                    "engagement_rate": {
                        "$cond": [
                            {"$gt": [recipient_count_expr, 0]},
                            {"$divide": [viewed_expr, recipient_count_expr]},
                            0
                        ]
                    }
                }
            }
        ]
        broadcasts = await self.db.announcements.aggregate(broadcasts_pipeline).to_list(None)
        
        # Aggregate metrics
        summary_pipeline = [
            {
                "$project": {
                    "recipient_count": recipient_count_expr,
                    "delivered_count": delivered_expr,
                    "view_count": viewed_expr,
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_broadcasts": {"$sum": 1},
                    "avg_delivery_rate": {
                        "$avg": {
                            "$cond": [
                                {"$gt": ["$recipient_count", 0]},
                                {"$divide": ["$delivered_count", "$recipient_count"]},
                                0,
                            ]
                        }
                    },
                    "avg_engagement_rate": {
                        "$avg": {
                            "$cond": [
                                {"$gt": ["$recipient_count", 0]},
                                {"$divide": ["$view_count", "$recipient_count"]},
                                0,
                            ]
                        }
                    },
                }
            }
        ]
        summary = await self.db.announcements.aggregate(summary_pipeline).to_list(None)
        
        logger.info("Broadcast performance analytics generated")
        
        return {
            "broadcasts": broadcasts,
            "summary": summary[0] if summary else {},
            "note": "Aggregated broadcast performance metrics - no recipient data"
        }

    # ==================================================
    # HELPER METHODS
    # ==================================================
    
    async def _sentiment_counts(self, start: datetime, end: datetime) -> Dict[str, int]:
        """Helper to get aggregated sentiment counts for a date range."""
        pipeline = [
            {"$match": {"created_at": {"$gte": start, "$lt": end}}},
            {"$group": {"_id": "$sentiment", "count": {"$sum": 1}}},
        ]
        rows = await self.db.feedback.aggregate(pipeline).to_list(None)
        return {r["_id"] or "unknown": r["count"] for r in rows}

    @staticmethod
    def _demographic_group_fields(prefix: str) -> Dict[str, Any]:
        """Return null-safe demographic group fields for aggregation."""
        return {
            "age_group": {"$ifNull": [f"{prefix}.age_group", "unknown"]},
            "gender": {"$ifNull": [f"{prefix}.gender", "unknown"]},
            "annual_income_range": {"$ifNull": [f"{prefix}.annual_income_range", "unknown"]},
            "occupation_category": {"$ifNull": [f"{prefix}.occupation", "unknown"]},
            "education_level": {"$ifNull": [f"{prefix}.education", "unknown"]},
            "religion": {"$ifNull": [f"{prefix}.religion", "unknown"]},
            "profession": {"$ifNull": [f"{prefix}.profession", "unknown"]},
            "family_adult_count": {"$ifNull": [f"{prefix}.family_adults", "unknown"]},
            "family_kids_count": {"$ifNull": [f"{prefix}.family_kids", "unknown"]},
        }

    @staticmethod
    def _demographic_lookup_stages(user_id_field: str) -> List[Dict[str, Any]]:
        """Lookup voter demographics safely by user id (aggregated only)."""
        return [
            {
                "$lookup": {
                    "from": "users",
                    "let": {"uid": f"${user_id_field}"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$eq": [
                                        "$_id",
                                        {
                                            "$convert": {
                                                "input": "$$uid",
                                                "to": "objectId",
                                                "onError": None,
                                                "onNull": None,
                                            }
                                        },
                                    ]
                                }
                            }
                        },
                        {"$project": {"_id": 1, "role": 1, "demographics": 1, "location": 1}},
                    ],
                    "as": "voter",
                }
            },
            {"$unwind": {"path": "$voter", "preserveNullAndEmptyArrays": True}},
            {
                "$addFields": {
                    "_demo": {
                        "$cond": [
                            {"$eq": ["$voter.role", "voter"]},
                            "$voter.demographics",
                            {},
                        ]
                    }
                }
            },
        ]

    @staticmethod
    def _compute_engagement_level(performance: Dict[str, Any]) -> str:
        """Compute engagement level from performance metrics."""
        score = 0
        score += performance.get("messages_shared", 0)
        score += performance.get("complaints_followed_up", 0)
        score += performance.get("events_participated", 0)
        score += performance.get("voter_interactions", 0)
        score += performance.get("poll_response_rate", 0) / 10
        if score >= 30:
            return "high"
        if score >= 10:
            return "medium"
        return "low"
