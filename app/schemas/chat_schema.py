# backend/app/schemas/chat_schema.py
"""
Chat Schema Module
==================
Pydantic request/response schemas for the chat and messaging system.
Separates API contract from MongoDB document structure.

Author: Political Communication Platform Team
"""

from datetime import datetime
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, Field, validator
from app.models.chat_model import (
    ChatType, MessageStatus, ReactionType, SharePlatform, MessageSentiment
)


# ─────────────────────────────────────────────
# REQUEST SCHEMAS
# ─────────────────────────────────────────────

class CreateDirectChatRequest(BaseModel):
    receiver_id: str = Field(..., description="The other participant's user ID")


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    source_language: Optional[str] = Field(
        None, description="ISO 639-1 code of the message source language"
    )


class BroadcastMessageRequest(BaseModel):
    content:      str        = Field(..., min_length=1, max_length=4000)
    voter_ids:    List[str]  = Field(..., min_items=1)
    chat_title:   Optional[str] = Field(None)
    source_language: Optional[str] = Field(
        None, description="ISO 639-1 code of the message source language"
    )


class ForwardMessagesRequest(BaseModel):
    message_ids:     List[str] = Field(..., min_items=1)
    target_chat_ids: List[str] = Field(..., min_items=1)


class BroadcastGroupFilterRequest(BaseModel):
    """
    Create a broadcast group using dynamic user filters.
    Filters are OPTIONAL — any combination is supported.
    """
    group_name: str = Field(..., min_length=1, max_length=100)

    # Demographic filters (optional)
    language_preference: Optional[List[str]] = Field(None, description="e.g., ['en', 'hi', 'mr']")
    religion: Optional[List[str]] = Field(None)
    age_group: Optional[List[str]] = Field(None, description="e.g., ['18-25', '26-35']")

    # Geographic filters (optional)
    state: Optional[List[str]] = Field(None)
    city: Optional[List[str]] = Field(None)
    ward: Optional[List[str]] = Field(None)
    area: Optional[List[str]] = Field(None)

    # Role filters (optional)
    roles: Optional[List[str]] = Field(
        default=None,
        description="Role IDs to include: 'voter', 'leader', 'corporator', 'ops'"
    )

    # Engagement filter (optional)
    engagement_level: Optional[List[str]] = Field(
        None,
        description="e.g., ['active', 'passive']"
    )

    @validator(
        "language_preference",
        "religion",
        "age_group",
        "state",
        "city",
        "ward",
        "area",
        "engagement_level",
        pre=True,
    )
    def normalize_list(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = [v]
        else:
            v = list(v)
        
        age_map = {"18-25": "18_25", "26-35": "26_35", "36-45": "36_45", "46-60": "46_60", "60+": "above_60"}
        return [age_map.get(str(i).strip(), str(i).strip()) for i in v if i]

    @validator("roles", pre=True, each_item=True)
    def normalize_roles(cls, v):
        # Accept both display values (e.g. 'Leader') and enum values ('leader')
        if v is None:
            return v
        return str(v).strip().lower()

    @validator("engagement_level", pre=True, each_item=True)
    def normalize_engagement_level(cls, v):
        if v is None:
            return v
        s = str(v).strip().lower()
        if s == "inactive":
            return "silent"
        return s

    @validator("roles", pre=True)
    def normalize_roles_list(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = [v]
        else:
            v = list(v)
        
        age_map = {"18-25": "18_25", "26-35": "26_35", "36-45": "36_45", "46-60": "46_60", "60+": "above_60"}
        return [age_map.get(str(i).strip(), str(i).strip()) for i in v if i]

    class Config:
        json_schema_extra = {
            "example": {
                "group_name": "Hindi Speaking Ward Leaders",
                "language_preference": "hi",
                "roles": ["leader"],
                "area": "Ward-12"
            }
        }


class BroadcastGroupFilterPreviewRequest(BaseModel):
    """
    Preview a broadcast group using dynamic user filters.
    Filters are OPTIONAL — any combination is supported.
    """
    # Demographic filters (optional)
    language_preference: Optional[List[str]] = Field(None, description="e.g., ['en', 'hi', 'mr']")
    religion: Optional[List[str]] = Field(None)
    age_group: Optional[List[str]] = Field(None, description="e.g., ['18-25', '26-35']")

    # Geographic filters (optional)
    state: Optional[List[str]] = Field(None)
    city: Optional[List[str]] = Field(None)
    ward: Optional[List[str]] = Field(None)
    area: Optional[List[str]] = Field(None)

    # Role filters (optional)
    roles: Optional[List[str]] = Field(
        default=None,
        description="Role IDs to include: 'voter', 'leader', 'corporator', 'ops'"
    )

    # Engagement filter (optional)
    engagement_level: Optional[List[str]] = Field(
        None,
        description="e.g., ['active', 'passive']"
    )

    @validator(
        "language_preference",
        "religion",
        "age_group",
        "state",
        "city",
        "ward",
        "area",
        "engagement_level",
        pre=True,
    )
    def normalize_list(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = [v]
        else:
            v = list(v)
        
        age_map = {"18-25": "18_25", "26-35": "26_35", "36-45": "36_45", "46-60": "46_60", "60+": "above_60"}
        return [age_map.get(str(i).strip(), str(i).strip()) for i in v if i]

    @validator("roles", pre=True, each_item=True)
    def normalize_roles(cls, v):
        if v is None:
            return v
        return str(v).strip().lower()

    @validator("engagement_level", pre=True, each_item=True)
    def normalize_engagement_level(cls, v):
        if v is None:
            return v
        s = str(v).strip().lower()
        if s == "inactive":
            return "silent"
        return s


class ReactToMessageRequest(BaseModel):
    reaction_type: ReactionType
    emoji_value:   Optional[str] = Field(None)

    @validator("emoji_value", always=True)
    def emoji_required_for_emoji_type(cls, v, values):
        if values.get("reaction_type") == ReactionType.EMOJI and not v:
            raise ValueError("emoji_value is required when reaction_type is 'emoji'")
        return v


class ShareMessageRequest(BaseModel):
    platform: SharePlatform


class MessageFeedbackRequest(BaseModel):
    text:   Optional[str] = Field(None, max_length=2000)
    rating: Optional[int] = Field(None, ge=1, le=5)

    @validator("rating", always=True)
    def at_least_one_required(cls, v, values):
        text_provided = bool(values.get("text") and values["text"].strip())
        if not text_provided and v is None:
            raise ValueError("At least one of 'text' or 'rating' must be provided")
        return v


class SearchMessagesRequest(BaseModel):
    query:   str = Field(..., min_length=1, max_length=200)
    chat_id: Optional[str] = Field(None)


# ─────────────────────────────────────────────
# RESPONSE SCHEMAS
# ─────────────────────────────────────────────

class ReactionResponse(BaseModel):
    user_id:       str
    reaction_type: ReactionType
    emoji_value:   Optional[str]
    reacted_at:    datetime


class ShareLogResponse(BaseModel):
    user_id:   str
    platform:  SharePlatform
    shared_at: datetime


class FeedbackResponse(BaseModel):
    user_id:    str
    text:       Optional[str]
    rating:     Optional[int]
    sentiment:  Optional[MessageSentiment]
    created_at: datetime
    updated_at: datetime


class MessageResponse(BaseModel):
    """
    Full message response.
    is_deleted_globally=True means content is replaced with the deletion placeholder.
    file_url / file_type / file_name / file_uploaded_at are populated when a
    media attachment was uploaded with the message.
    """
    message_id:    str
    chat_id:       str
    sender_id:     str
    content:       str
    original_text: str
    display_text:  str
    source_language: Optional[str] = None
    display_language: Optional[str] = None
    is_translated: bool = False
    template_flag: bool
    is_broadcast:  bool
    status:        MessageStatus
    is_deleted:    bool
    is_deleted_globally: bool = False

    # ── Media attachment fields (NEW) ──
    file_url:         Optional[str] = None
    file_type:        Optional[str] = None   # 'image' | 'video' | 'document'
    file_name:        Optional[str] = None
    file_uploaded_at: Optional[datetime] = None
    file_size:        Optional[int] = None
    preview_url:      Optional[str] = None
    link_url:         Optional[str] = None
    link_title:       Optional[str] = None
    link_description: Optional[str] = None
    link_image:       Optional[str] = None
    # ────────────────────────────────────

    reaction_count: int
    share_count:    int
    feedback_count: int
    reactions:     List[ReactionResponse] = []
    feedback:      Optional[List[FeedbackResponse]] = None
    created_at:    datetime
    updated_at:    datetime


class LastMessagePreview(BaseModel):
    message_id:       Optional[str] = None
    text_original:    Optional[str] = None
    text_translated:  Optional[str] = None
    display_text:     Optional[str] = None
    source_language:  Optional[str] = None
    display_language: Optional[str] = None
    is_translated:    Optional[bool] = None
    sender_id:        Optional[str] = None
    timestamp:        Optional[datetime] = None
    message_type:     Optional[str] = None
    file_name:        Optional[str] = None


class ChatSummaryResponse(BaseModel):
    chat_id:             str
    chat_type:           ChatType
    participants:        List[str]
    last_message_text:   Optional[str]
    last_message_at:     Optional[datetime]
    last_message_sender: Optional[str]
    last_message:        Optional[LastMessagePreview] = None
    unread_count:        int
    is_active:           bool
    created_at:          datetime
    created_by:          Optional[str] = None
    title:               Optional[str] = None
    broadcast_count:     Optional[int] = None


class PaginatedMessagesResponse(BaseModel):
    chat_id:      str
    messages:     List[MessageResponse]
    total:        int
    page:         int
    page_size:    int
    has_more:     bool


class UnreadCountResponse(BaseModel):
    total_unread: int
    per_chat:     Dict[str, int]


# ─────────────────────────────────────────────
# ANALYTICS RESPONSE SCHEMAS
# ─────────────────────────────────────────────

class CorporatorMessagingAnalytics(BaseModel):
    total_messages_sent:    int
    total_broadcasts:       int
    total_reactions:        int
    total_shares:           int
    engagement_rate:        float
    most_engaged_voters:    List[Dict[str, Any]]
    sentiment_distribution: Dict[str, int]
    average_star_rating:    Optional[float]
    rating_distribution:    Dict[str, int]


class OpsMessagingAnalytics(BaseModel):
    global_stats:             Dict[str, int]
    most_active_leaders:      List[Dict[str, Any]]
    most_shared_messages:     List[Dict[str, Any]]
    sentiment_distribution:   Dict[str, int]
    platform_share_breakdown: Dict[str, int]
    average_star_rating:      Optional[float]
