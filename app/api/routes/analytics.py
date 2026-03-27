"""
Analytics Routes
================
API endpoints for analytics dashboards (OPS & Corporator only).
All data returned is AGGREGATED - never individual voter records.

Author: Political Communication Platform Team
"""

from fastapi import APIRouter, Depends, Query
from datetime import datetime
from typing import Optional
from app.services.analytics_service import AnalyticsService
from app.services.ops_analytics_service import OpsAnalyticsService
from app.api.dependencies import require_permission, require_ops
from app.schemas.ops_analytics_schema import (
    OpsOverviewResponse,
    OpsUsersResponse,
    OpsUsersAnalyticsResponse,
    OpsRoleResponse,
    OpsCampaignsResponse,
    OpsEventsResponse,
    OpsChatResponse,
    OpsComplaintsResponse,
    OpsComplaintsGeoResponse,
    OpsFeedbackResponse,
    OpsGeoResponse,
    OpsActivityResponse,
    OpsFiltersResponse,
    OpsAreaDetailResponse,
    OpsLeaderDetailResponse,
    OpsDemographicDetailResponse,
)
from app.core.permissions import Permission

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ==================================================
# BASIC ANALYTICS (Available to Corporator & OPS)
# ==================================================

@router.get("/complaints", summary="Complaint status summary (aggregated)")
async def complaint_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _=Depends(require_permission(Permission.VIEW_BASIC_ANALYTICS))
):
    """
    Get aggregated complaint counts by status.
    AGGREGATED ONLY - no individual records.
    Requires: VIEW_BASIC_ANALYTICS permission
    """
    service = AnalyticsService()
    return await service.complaint_summary(start_date=start_date, end_date=end_date)


@router.get("/sentiment", summary="Sentiment analysis summary (aggregated)")
async def sentiment_analytics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _=Depends(require_permission(Permission.VIEW_BASIC_ANALYTICS))
):
    """
    Get aggregated sentiment counts from feedback.
    AGGREGATED ONLY - counts by sentiment type.
    Requires: VIEW_BASIC_ANALYTICS permission
    """
    service = AnalyticsService()
    return await service.sentiment_summary(start_date=start_date, end_date=end_date)


@router.get("/issue-heatmap", summary="Geographic issue heatmap (aggregated)")
async def issue_heatmap(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _=Depends(require_permission(Permission.VIEW_ADVANCED_ANALYTICS))
):
    """
    Get complaint counts aggregated by geography.
    AGGREGATED ONLY - area-level counts, no voter identities.
    Requires: VIEW_ADVANCED_ANALYTICS permission
    """
    service = AnalyticsService()
    return await service.issue_heatmap(start_date=start_date, end_date=end_date)


@router.get("/voter-mood-trends", summary="Sentiment trends by day (aggregated)")
async def voter_mood_trends(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _=Depends(require_permission(Permission.VIEW_SENTIMENT_ANALYSIS))
):
    """
    Get sentiment aggregated by date.
    AGGREGATED ONLY - daily sentiment counts.
    Requires: VIEW_SENTIMENT_ANALYSIS permission
    """
    service = AnalyticsService()
    return await service.voter_mood_trends(start_date=start_date, end_date=end_date)


@router.get("/leader-performance", summary="Leader performance metrics (aggregated)")
async def leader_performance(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _=Depends(require_permission(Permission.VIEW_LEADER_PERFORMANCE))
):
    """
    Get aggregated leader performance metrics.
    AGGREGATED ONLY - performance metrics by leader, no voter data.
    Requires: VIEW_LEADER_PERFORMANCE permission
    """
    service = AnalyticsService()
    return await service.leader_performance()


@router.get("/communication-effectiveness", summary="Announcement engagement (aggregated)")
async def communication_effectiveness(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    _=Depends(require_permission(Permission.VIEW_ADVANCED_ANALYTICS))
):
    """
    Get aggregated announcement reach and engagement metrics.
    AGGREGATED ONLY - view counts, shares, reactions by announcement.
    Requires: VIEW_ADVANCED_ANALYTICS permission
    """
    service = AnalyticsService()
    return await service.communication_effectiveness(start_date=start_date, end_date=end_date)


# ==================================================
# OPS INTELLIGENCE (OPS & Corporator Only)
# ==================================================

@router.get("/ops/voter-intelligence", summary="Voter segmentation intelligence (OPS)")
async def ops_voter_intelligence(
    days_inactive: int = Query(30, description="Days to consider as inactive"),
    _=Depends(require_permission(Permission.VIEW_VOTER_INTELLIGENCE)),
):
    """
    Get aggregated voter intelligence and silent voter detection.
    CRITICAL: AGGREGATED ONLY - counts by segment, no voter names/IDs.
    
    Returns:
    - Segmentation: Engagement levels (count by level)
    - Geography: Voter distribution by area (no individual records)
    - Demographics: Age/gender distribution (aggregated only)
    - Engagement metrics: Averages across voter base
    - Silent voters COUNT: How many inactive voters (NO NAMES/IDS)
    
    Requires: VIEW_VOTER_INTELLIGENCE permission (OPS & Corporator only)
    """
    service = AnalyticsService()
    return await service.voter_intelligence(days_inactive=days_inactive)


@router.get("/ops/issue-intelligence", summary="Issue analysis and SLA metrics (OPS)")
async def ops_issue_intelligence(
    days_window: int = Query(90, description="Analysis window in days"),
    _=Depends(require_permission(Permission.VIEW_ADVANCED_ANALYTICS)),
):
    """
    Get aggregated issue intelligence including SLA metrics.
    CRITICAL: AGGREGATED ONLY - counts, averages, patterns.
    
    Returns:
    - Issue categories: Count by category
    - Area density: Complaint counts by geography
    - SLA metrics: Average time to acknowledge/resolve
    - Resolution quality: Satisfaction ratings (aggregated)
    - Leader responsibility: Count of complaints assigned (leader IDs only, no voters)
    
    Requires: VIEW_ADVANCED_ANALYTICS permission
    """
    service = AnalyticsService()
    return await service.issue_intelligence(days_window=days_window)


@router.get("/ops/sentiment-mood", summary="Sentiment trends and spikes (OPS)")
async def ops_sentiment_mood(
    days_window: int = Query(90, description="Analysis window in days"),
    spike_threshold: float = Query(0.35, description="Negativity spike threshold"),
    _=Depends(require_permission(Permission.VIEW_SENTIMENT_ANALYSIS)),
):
    """
    Get sentiment trends and anomaly detection.
    CRITICAL: AGGREGATED ONLY - trends by date/area, no voter identities.
    
    Returns:
    - Feedback trends: Sentiment counts by date
    - Complaint trends: Sentiment by date
    - Poll trends: Sentiment by date
    - Negative spikes: Dates with high negativity
    - Area negativity: Negativity rates by geography
    
    Requires: VIEW_SENTIMENT_ANALYSIS permission
    """
    service = AnalyticsService()
    return await service.sentiment_mood_analysis(
        days_window=days_window,
        spike_threshold=spike_threshold
    )


@router.get("/ops/sentiment-impact", summary="Sentiment before/after events (OPS)")
async def ops_sentiment_impact(
    entity_type: str = Query("announcements", description="announcements or events"),
    window_days: int = Query(7, description="Days before/after event"),
    limit: int = Query(20, description="Max results"),
    _=Depends(require_permission(Permission.VIEW_SENTIMENT_ANALYSIS)),
):
    """
    Get sentiment impact analysis around announcements/events.
    CRITICAL: AGGREGATED ONLY - sentiment counts, no voter identities.
    
    Returns aggregated sentiment counts before and after major communications.
    
    Requires: VIEW_SENTIMENT_ANALYSIS permission
    """
    service = AnalyticsService()
    return await service.sentiment_impact(
        entity_type=entity_type,
        window_days=window_days,
        limit=limit
    )


@router.get("/ops/leader-performance-dashboard", summary="Leader performance dashboard (OPS)")
async def ops_leader_performance(
    _=Depends(require_permission(Permission.VIEW_LEADER_PERFORMANCE)),
):
    """
    Get comprehensive leader performance dashboard.
    CRITICAL: AGGREGATED ONLY - performance metrics, no voter data.
    
    Returns:
    - Leader performance metrics aggregated from complaints/feedback
    - Engagement levels
    - Normalized performance scores
    - Area coverage counts
    
    Requires: VIEW_LEADER_PERFORMANCE permission
    """
    service = AnalyticsService()
    return await service.leader_performance_dashboard()


@router.get("/ops/communication-effectiveness", summary="Communication patterns (OPS)")
async def ops_communication_effectiveness(
    days_window: int = Query(90, description="Analysis window in days"),
    complaint_threshold: int = Query(5, description="Min complaints to flag pattern"),
    _=Depends(require_permission(Permission.VIEW_ADVANCED_ANALYTICS)),
):
    """
    Get communication effectiveness analysis including confusion signals.
    CRITICAL: AGGREGATED ONLY - patterns and anomalies, no voter data.
    
    Returns:
    - Message reach gaps: Announcements with no engagement
    - Poll participation: Aggregated participation rates
    - Confusion signals: Count of confused reactions (aggregated)
    - Repeated complaints: Issue patterns by category/area
    
    Requires: VIEW_ADVANCED_ANALYTICS permission
    """
    service = AnalyticsService()
    return await service.ops_communication_effectiveness(
        days_window=days_window,
        complaint_threshold=complaint_threshold
    )


@router.get("/ops/system-features", summary="System capability metrics (OPS)")
async def ops_system_features(
    _=Depends(require_permission(Permission.VIEW_ADVANCED_ANALYTICS)),
):
    """
    Get decision-grade system feature status and metrics.
    CRITICAL: AGGREGATED ONLY - feature availability and aggregate metrics.
    
    Returns system feature availability and high-level metrics for decision-making.
    
    Requires: VIEW_ADVANCED_ANALYTICS permission
    """
    service = AnalyticsService()
    return await service.ops_system_features()


# ==================================================
# CHAT & BROADCAST ANALYTICS (OPS Only)
# ==================================================

@router.get("/ops/chat-analytics", summary="Chat and messaging analytics (OPS)")
async def ops_chat_analytics(
    _=Depends(require_permission(Permission.VIEW_CHAT_ANALYTICS))
):
    """
    Get aggregated chat and messaging analytics.
    CRITICAL: AGGREGATED ONLY - message counts, reactions, shares.
    
    Returns:
    - Total messages
    - Messages by type
    - Reaction counts
    - Share counts
    - Top active users (by ID, no names)
    - Area-wise message distribution
    
    Requires: VIEW_CHAT_ANALYTICS permission (OPS & Corporator)
    """
    service = AnalyticsService()
    return await service.chat_analytics()


@router.get("/ops/broadcast-performance", summary="Broadcast performance analytics (OPS)")
async def ops_broadcast_performance(
    _=Depends(require_permission(Permission.VIEW_BROADCAST_PERFORMANCE))
):
    """
    Get broadcast (announcement) performance analytics.
    CRITICAL: AGGREGATED ONLY - engagement metrics, no recipient information.
    
    Returns:
    - Broadcast list with engagement metrics
    - Delivery rates
    - Engagement rates
    - Summary statistics
    
    Requires: VIEW_BROADCAST_PERFORMANCE permission (OPS & Corporator)
    """
    service = AnalyticsService()
    return await service.broadcast_performance()


# ==================================================
# OPS CONSOLE ANALYTICS (ADMIN DASHBOARD)
# ==================================================

@router.get("/ops/overview", response_model=OpsOverviewResponse, summary="OPS dashboard overview")
async def ops_overview(
    range: str = Query("last_30_days", description="today | last_7_days | last_30_days | last_90_days | this_month | last_month | this_year | custom"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD (for custom)"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD (for custom)"),
    ward: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.overview(range, start, end, ward=ward, role=role, category=category, status=status)


@router.get("/ops/users", response_model=OpsUsersResponse, summary="OPS users analytics")
async def ops_users(
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    ward: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.users(range, start, end, ward=ward, role=role)


@router.get("/ops/users-analytics", response_model=OpsUsersAnalyticsResponse, summary="OPS advanced users analytics")
async def ops_users_analytics(
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    ward: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    bucket_size: int = Query(5, ge=2, le=20),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.users_analytics(range, start, end, ward=ward, role=role, bucket_size=bucket_size)


@router.get("/ops/voters", response_model=OpsRoleResponse, summary="OPS voter analytics")
async def ops_voters(
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    ward: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.role_analytics("voter", range, start, end, ward=ward)


@router.get("/ops/leaders", response_model=OpsRoleResponse, summary="OPS leader analytics")
async def ops_leaders(
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    ward: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.role_analytics("leader", range, start, end, ward=ward)


@router.get("/ops/corporators", response_model=OpsRoleResponse, summary="OPS corporator analytics")
async def ops_corporators(
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    ward: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.role_analytics("corporator", range, start, end, ward=ward)


@router.get("/ops/campaigns", response_model=OpsCampaignsResponse, summary="OPS campaign analytics")
async def ops_campaigns(
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.campaigns(range, start, end)


@router.get("/ops/events", response_model=OpsEventsResponse, summary="OPS event analytics")
async def ops_events(
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.events(range, start, end)


@router.get("/ops/chat", response_model=OpsChatResponse, summary="OPS chat analytics")
async def ops_chat(
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.chat(range, start, end)


@router.get("/ops/complaints", response_model=OpsComplaintsResponse, summary="OPS complaint analytics")
async def ops_complaints(
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.complaints(range, start, end)


@router.get(
    "/ops/complaints-geo",
    response_model=OpsComplaintsGeoResponse,
    summary="OPS complaints geo drilldown",
)
async def ops_complaints_geo(
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    area: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.complaints_geo(range, start, end, area=area)


@router.get("/ops/feedback", response_model=OpsFeedbackResponse, summary="OPS feedback analytics")
async def ops_feedback(
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.feedback(range, start, end)


@router.get("/ops/geo", response_model=OpsGeoResponse, summary="OPS geographic analytics")
async def ops_geo(
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.geo(range, start, end)


@router.get("/ops/activity", response_model=OpsActivityResponse, summary="OPS recent activity feed")
async def ops_activity(
    limit: int = Query(20, ge=1, le=100),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    return await service.activity(limit=limit)


@router.get("/ops/filters", response_model=OpsFiltersResponse, summary="OPS filter options")
async def ops_filters(
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    return await service.filters()


@router.get("/ops/area/{ward}", response_model=OpsAreaDetailResponse, summary="OPS area detail")
async def ops_area_detail(
    ward: str,
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.area_detail(ward, range, start, end)


@router.get("/ops/leader/{leader_id}", response_model=OpsLeaderDetailResponse, summary="OPS leader detail")
async def ops_leader_detail(
    leader_id: str,
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    try:
        return await service.leader_detail(leader_id, range, start, end)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/ops/demographic/{segment_type}/{segment_value}",
    response_model=OpsDemographicDetailResponse,
    summary="OPS demographic segment detail",
)
async def ops_demographic_detail(
    segment_type: str,
    segment_value: str,
    range: str = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    _=Depends(require_ops()),
):
    service = OpsAnalyticsService()
    start = datetime.fromisoformat(start_date) if start_date else None
    end = datetime.fromisoformat(end_date) if end_date else None
    return await service.demographic_detail(segment_type, segment_value, range, start, end)
