"""
Ops Analytics Schema
====================
Pydantic schemas for OPS analytics responses.
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class TimeSeriesPoint(BaseModel):
    date: str
    value: int


class DistributionItem(BaseModel):
    label: str
    value: int


class RankedItem(BaseModel):
    id: str
    label: str
    value: int
    secondary: Optional[str] = None


class EventSummaryItem(BaseModel):
    id: str
    title: str
    date: str
    status: str
    event_type: Optional[str] = None
    city: Optional[str] = None
    ward: Optional[str] = None
    attendees: int = 0
    registrations: int = 0


class ActivityItem(BaseModel):
    type: str
    title: str
    timestamp: str
    meta: Optional[Dict[str, str]] = None


class OpsOverviewResponse(BaseModel):
    total_users: int = 0
    total_voters: int = 0
    total_leaders: int = 0
    total_corporators: int = 0
    total_campaigns: int = 0
    total_events: int = 0
    total_complaints: int = 0
    total_appointments: int = 0
    total_messages: int = 0
    total_chats: int = 0
    total_feedback: int = 0
    total_notifications: int = 0

    active_users: int = 0
    new_users: int = 0
    growth_pct: float = 0.0

    role_distribution: List[DistributionItem] = Field(default_factory=list)
    complaint_status: List[DistributionItem] = Field(default_factory=list)
    event_status: List[DistributionItem] = Field(default_factory=list)
    campaign_status: List[DistributionItem] = Field(default_factory=list)

    user_growth: List[TimeSeriesPoint] = Field(default_factory=list)
    message_trend: List[TimeSeriesPoint] = Field(default_factory=list)

    recent_activity: List[ActivityItem] = Field(default_factory=list)
    
    # Demographics data
    demographics: Dict[str, List[DistributionItem]] = Field(default_factory=dict)


class OpsUsersResponse(BaseModel):
    total_users: int = 0
    active_users: int = 0
    verified_users: int = 0
    new_users: int = 0
    role_distribution: List[DistributionItem] = Field(default_factory=list)
    signup_trend: List[TimeSeriesPoint] = Field(default_factory=list)
    language_distribution: List[DistributionItem] = Field(default_factory=list)
    region_distribution: List[DistributionItem] = Field(default_factory=list)


class OpsRoleTrendPoint(BaseModel):
    date: str
    role: str
    value: int


class OpsLocationHierarchyItem(BaseModel):
    region: str = ""
    ward: str = ""
    area: str = ""
    value: int = 0


class OpsUserSummary(BaseModel):
    total_users: int = 0
    active_users: int = 0
    verified_users: int = 0
    growth_rate_pct: float = 0.0
    new_users_daily: int = 0
    new_users_weekly: int = 0
    new_users_monthly: int = 0


class OpsUserDemographics(BaseModel):
    gender_distribution: List[DistributionItem] = Field(default_factory=list)
    age_buckets: List[DistributionItem] = Field(default_factory=list)
    occupation_distribution: List[DistributionItem] = Field(default_factory=list)
    location_hierarchy: List[OpsLocationHierarchyItem] = Field(default_factory=list)


class OpsUserRoleAnalytics(BaseModel):
    role_distribution: List[DistributionItem] = Field(default_factory=list)
    role_growth_trend: List[OpsRoleTrendPoint] = Field(default_factory=list)
    active_users_per_role: List[DistributionItem] = Field(default_factory=list)


class OpsCohortRetention(BaseModel):
    cohort: str
    week_1: float = 0.0
    week_4: float = 0.0
    week_12: float = 0.0


class OpsCohortSize(BaseModel):
    cohort: str
    size: int = 0
    active_in_period: int = 0


class OpsUserTimeBased(BaseModel):
    signup_trend: List[TimeSeriesPoint] = Field(default_factory=list)
    activity_trend: List[TimeSeriesPoint] = Field(default_factory=list)
    retention: List[OpsCohortRetention] = Field(default_factory=list)
    cohorts: List[OpsCohortSize] = Field(default_factory=list)


class OpsUserEngagement(BaseModel):
    engagement_score_avg: float = 0.0
    most_active_users: List[RankedItem] = Field(default_factory=list)
    feature_usage_frequency: List[DistributionItem] = Field(default_factory=list)
    avg_actions_per_user: float = 0.0


class OpsUserComplaintAnalytics(BaseModel):
    complaints_per_user: List[RankedItem] = Field(default_factory=list)
    resolution_rate_by_group: List[DistributionItem] = Field(default_factory=list)
    active_complainants: int = 0


class OpsUserSegmentation(BaseModel):
    activity_segments: List[DistributionItem] = Field(default_factory=list)
    new_vs_returning: List[DistributionItem] = Field(default_factory=list)


class OpsUserGeoAnalytics(BaseModel):
    region_distribution: List[DistributionItem] = Field(default_factory=list)
    ward_distribution: List[DistributionItem] = Field(default_factory=list)
    area_distribution: List[DistributionItem] = Field(default_factory=list)
    high_density_zones: List[DistributionItem] = Field(default_factory=list)


class OpsUsersAnalyticsResponse(BaseModel):
    summary: OpsUserSummary = Field(default_factory=OpsUserSummary)
    demographics: OpsUserDemographics = Field(default_factory=OpsUserDemographics)
    role_analytics: OpsUserRoleAnalytics = Field(default_factory=OpsUserRoleAnalytics)
    time_based: OpsUserTimeBased = Field(default_factory=OpsUserTimeBased)
    engagement: OpsUserEngagement = Field(default_factory=OpsUserEngagement)
    complaints: OpsUserComplaintAnalytics = Field(default_factory=OpsUserComplaintAnalytics)
    segmentation: OpsUserSegmentation = Field(default_factory=OpsUserSegmentation)
    geo: OpsUserGeoAnalytics = Field(default_factory=OpsUserGeoAnalytics)


class OpsRoleResponse(BaseModel):
    total: int = 0
    active: int = 0
    verified: int = 0
    new_in_period: int = 0
    trend: List[TimeSeriesPoint] = Field(default_factory=list)
    region_distribution: List[DistributionItem] = Field(default_factory=list)
    top_entities: List[RankedItem] = Field(default_factory=list)
    low_entities: List[RankedItem] = Field(default_factory=list)


class OpsCampaignsResponse(BaseModel):
    total_campaigns: int = 0
    active_campaigns: int = 0
    closed_campaigns: int = 0
    total_raised: float = 0.0
    category_distribution: List[DistributionItem] = Field(default_factory=list)
    status_distribution: List[DistributionItem] = Field(default_factory=list)
    trend: List[TimeSeriesPoint] = Field(default_factory=list)
    top_campaigns: List[RankedItem] = Field(default_factory=list)
    low_campaigns: List[RankedItem] = Field(default_factory=list)


class OpsEventsResponse(BaseModel):
    total_events: int = 0
    upcoming_events: int = 0
    ongoing_events: int = 0
    completed_events: int = 0
    cancelled_events: int = 0
    postponed_events: int = 0
    registration_open_events: int = 0
    total_registrations: int = 0
    total_attendees: int = 0
    avg_attendance: float = 0.0
    avg_participation_rate: float = 0.0
    avg_capacity_utilization: float = 0.0

    status_distribution: List[DistributionItem] = Field(default_factory=list)
    type_distribution: List[DistributionItem] = Field(default_factory=list)
    ward_distribution: List[DistributionItem] = Field(default_factory=list)
    city_distribution: List[DistributionItem] = Field(default_factory=list)
    top_organizers: List[RankedItem] = Field(default_factory=list)
    recent_events: List[EventSummaryItem] = Field(default_factory=list)
    trend: List[TimeSeriesPoint] = Field(default_factory=list)


class OpsChatResponse(BaseModel):
    total_chats: int = 0
    active_chats: int = 0
    total_messages: int = 0
    messages_by_type: List[DistributionItem] = Field(default_factory=list)
    messages_by_role: List[DistributionItem] = Field(default_factory=list)
    message_trend: List[TimeSeriesPoint] = Field(default_factory=list)
    top_senders: List[RankedItem] = Field(default_factory=list)
    reaction_counts: List[DistributionItem] = Field(default_factory=list)
    total_shares: int = 0
    area_distribution: List[DistributionItem] = Field(default_factory=list)


class OpsComplaintsResponse(BaseModel):
    total_complaints: int = 0
    status_distribution: List[DistributionItem] = Field(default_factory=list)
    category_distribution: List[DistributionItem] = Field(default_factory=list)
    priority_distribution: List[DistributionItem] = Field(default_factory=list)
    trend: List[TimeSeriesPoint] = Field(default_factory=list)
    top_areas: List[RankedItem] = Field(default_factory=list)


class OpsAssigneeCount(BaseModel):
    id: str
    name: str
    count: int = 0


class OpsWardComplaintsInsight(BaseModel):
    ward: str
    total_complaints: int = 0
    leaders: List[OpsAssigneeCount] = Field(default_factory=list)
    corporators: List[OpsAssigneeCount] = Field(default_factory=list)


class OpsAreaComplaintsInsight(BaseModel):
    area: str
    total_complaints: int = 0
    wards: List[OpsWardComplaintsInsight] = Field(default_factory=list)


class OpsComplaintsGeoResponse(BaseModel):
    areas: List[OpsAreaComplaintsInsight] = Field(default_factory=list)


class OpsFeedbackResponse(BaseModel):
    total_feedback: int = 0
    sentiment_distribution: List[DistributionItem] = Field(default_factory=list)
    trend: List[TimeSeriesPoint] = Field(default_factory=list)


class OpsGeoResponse(BaseModel):
    users_by_ward: List[DistributionItem] = Field(default_factory=list)
    complaints_by_ward: List[DistributionItem] = Field(default_factory=list)
    events_by_city: List[DistributionItem] = Field(default_factory=list)


class OpsActivityResponse(BaseModel):
    items: List[ActivityItem] = Field(default_factory=list)


class OpsFiltersResponse(BaseModel):
    wards: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    statuses: List[str] = Field(default_factory=list)
    complaint_categories: List[str] = Field(default_factory=list)
    complaint_statuses: List[str] = Field(default_factory=list)
    campaign_categories: List[str] = Field(default_factory=list)
    event_statuses: List[str] = Field(default_factory=list)


class OpsAreaDetailResponse(BaseModel):
    ward: str
    totals: Dict[str, int] = Field(default_factory=dict)
    active_users: int = 0
    engagement_rate: float = 0.0
    complaint_status: List[DistributionItem] = Field(default_factory=list)
    complaint_categories: List[DistributionItem] = Field(default_factory=list)
    event_status: List[DistributionItem] = Field(default_factory=list)
    demographics: Dict[str, List[DistributionItem]] = Field(default_factory=dict)
    recent_activity: List[ActivityItem] = Field(default_factory=list)


class OpsLeaderDetailResponse(BaseModel):
    leader_id: str
    full_name: str = ""
    location: Dict[str, str] = Field(default_factory=dict)
    performance: Dict[str, int] = Field(default_factory=dict)
    complaints_assigned: int = 0
    complaints_resolved: int = 0
    messages_sent: int = 0
    recent_activity: List[ActivityItem] = Field(default_factory=list)


class OpsDemographicDetailResponse(BaseModel):
    segment_type: str
    segment_value: str
    totals: Dict[str, int] = Field(default_factory=dict)
    active_users: int = 0
    engagement_rate: float = 0.0
    complaint_status: List[DistributionItem] = Field(default_factory=list)
    sentiment_distribution: List[DistributionItem] = Field(default_factory=list)
