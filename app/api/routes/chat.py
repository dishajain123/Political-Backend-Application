# backend/app/api/routes/chat.py
"""
Chat Routes
===========
REST API endpoints for the messaging system.
No WebSockets — polling-based design.

Permission summary:
  POST /chat/direct            → all authenticated (VOTER, LEADER, CORPORATOR)
  POST /chat/broadcast         → CORPORATOR, LEADER only
  GET  /chat/list              → all authenticated
  GET  /chat/{id}/messages     → participants + broadcast recipients + OPS
  POST /chat/{id}/messages     → direct chat participants only (multipart/form-data)
  DELETE /chat/messages/{id}   → sender only (legacy)
  POST /chat/{chat_id}/message/{message_id}/delete-for-me       → CORPORATOR only
  POST /chat/{chat_id}/message/{message_id}/delete-for-everyone → CORPORATOR only
  POST /chat/messages/{id}/react       → authenticated
  DELETE /chat/messages/{id}/react     → authenticated
  POST /chat/messages/{id}/share       → authenticated
  POST /chat/messages/{id}/feedback    → VOTER only
  GET  /chat/unread            → authenticated
  GET  /chat/search            → authenticated
  GET  /chat/analytics/me      → CORPORATOR only
  GET  /chat/analytics/ops     → OPS only
  GET  /chat/files/{filename}  → serve uploaded chat media (public)

Author: Political Communication Platform Team
"""

import json
import os

from fastapi import APIRouter, Depends, Query, HTTPException, status, Form, UploadFile, File
from fastapi.responses import FileResponse
from typing import Optional

from app.api.dependencies import (
    get_current_user,
    require_roles,
    require_permission,
    CurrentUser,
)
from app.core.roles import UserRole
from app.core.permissions import Permission
from app.services.chat_service import ChatService
from app.schemas.chat_schema import (
    CreateDirectChatRequest,
    SendMessageRequest,
    BroadcastMessageRequest,
    ForwardMessagesRequest,
    BroadcastGroupFilterRequest,
    BroadcastGroupFilterPreviewRequest,
    ReactToMessageRequest,
    ShareMessageRequest,
    MessageFeedbackRequest,
    SearchMessagesRequest,
)

router = APIRouter(prefix="/chat", tags=["Chat"])

_UPLOAD_DIR = "/uploads/chat"


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────

async def _get_viewer_name(user_id: str) -> str:
    try:
        from app.db.mongodb import get_database
        from bson import ObjectId
        db = get_database()
        user = await db.users.find_one({"_id": ObjectId(user_id)}, {"full_name": 1})
        return user.get("full_name", "") if user else ""
    except Exception:
        return ""


# ─────────────────────────────────────────────
# 0. SERVE UPLOADED FILES
# ─────────────────────────────────────────────

@router.get("/files/{filename}", summary="Serve an uploaded chat media file")
async def serve_chat_file(filename: str):
    """
    Public endpoint to retrieve uploaded chat attachments.
    Files are stored in /uploads/chat/ on the server.
    """
    # Sanitise: prevent directory traversal
    safe_name = os.path.basename(filename)
    file_path = os.path.join(_UPLOAD_DIR, safe_name)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)


# ─────────────────────────────────────────────
# 1. CREATE DIRECT CHAT
# ─────────────────────────────────────────────

@router.post("/direct", summary="Start or resume a direct chat")
async def create_direct_chat(
    body: CreateDirectChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    if current_user.role == UserRole.OPS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="OPS role cannot initiate chats")
    try:
        service = ChatService()
        chat = await service.get_or_create_direct_chat(
            sender_id=current_user.user_id,
            sender_role=current_user.role,
            receiver_id=body.receiver_id,
        )
        return {
            "chat_id":    str(chat["_id"]),
            "chat_type":  chat.get("chat_type"),
            "participants": chat.get("participants", []),
            "created_at": chat.get("created_at"),
        }
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─────────────────────────────────────────────
# 2. BROADCAST MESSAGE
# Accepts multipart/form-data.
# voter_ids must be a JSON-encoded string: '["id1","id2"]'
# ─────────────────────────────────────────────

@router.post("/broadcast", summary="Send a broadcast message to multiple voters")
async def send_broadcast(
    content:    str            = Form(""),
    voter_ids:  str            = Form(...),
    chat_title: Optional[str]  = Form(None),
    source_language: Optional[str] = Form(None),
    file:       Optional[UploadFile] = File(None),
    current_user: CurrentUser = Depends(
        require_roles(UserRole.CORPORATOR, UserRole.LEADER)
    ),
):
    # Parse voter_ids from JSON string
    try:
        voter_ids_list = json.loads(voter_ids)
        if not isinstance(voter_ids_list, list) or not voter_ids_list:
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="voter_ids must be a JSON-encoded list of strings",
        )

    # Read and validate file if provided
    file_bytes: Optional[bytes] = None
    file_name: Optional[str] = None
    if file and file.filename:
        file_bytes = await file.read()
        file_name = file.filename

    try:
        service = ChatService()
        result = await service.send_broadcast(
            sender_id=current_user.user_id,
            sender_role=current_user.role,
            content=content,
            voter_ids=voter_ids_list,
            chat_title=chat_title,
            source_language=source_language,
            file_bytes=file_bytes,
            file_name=file_name,
        )
        return result
    except (ValueError, PermissionError) as e:
        status_code = (
            status.HTTP_403_FORBIDDEN
            if isinstance(e, PermissionError)
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail=str(e))


# ─────────────────────────────────────────────
# 3. GET CHAT LIST
# ─────────────────────────────────────────────

@router.get("/list", summary="Get all chats for current user")
async def get_chat_list(
    current_user: CurrentUser = Depends(get_current_user),
):
    service = ChatService()
    viewer_name = await _get_viewer_name(current_user.user_id)
    chats = await service.get_chat_list(
        current_user.user_id,
        current_user.role,
        viewer_name=viewer_name,
    )
    return {"chats": chats, "total": len(chats)}


# ─────────────────────────────────────────────
# 4. SEND MESSAGE (DIRECT CHAT)
# Accepts multipart/form-data.
# content is optional when a file is attached.
# ─────────────────────────────────────────────

@router.post("/{chat_id}/messages", summary="Send a message in a direct chat")
async def send_message(
    chat_id:  str,
    content:  str                    = Form(""),
    source_language: Optional[str]   = Form(None),
    file:     Optional[UploadFile]   = File(None),
    current_user: CurrentUser = Depends(get_current_user),
):
    if current_user.role == UserRole.OPS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="OPS role cannot send messages")

    # Require at least content or file
    has_content = bool(content and content.strip())
    has_file = file is not None and bool(file.filename)
    if not has_content and not has_file:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message must contain text content or an attached file",
        )

    file_bytes: Optional[bytes] = None
    file_name: Optional[str] = None
    if has_file:
        file_bytes = await file.read()
        file_name = file.filename

    try:
        service = ChatService()
        msg = await service.send_message(
            chat_id=chat_id,
            sender_id=current_user.user_id,
            sender_role=current_user.role,
            content=content,
            source_language=source_language,
            file_bytes=file_bytes,
            file_name=file_name,
        )
        return msg
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─────────────────────────────────────────────
# 4. FORWARD MESSAGES
# ─────────────────────────────────────────────

@router.post("/forward", summary="Forward one or more messages to selected chats")
async def forward_messages(
    body: ForwardMessagesRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    service = ChatService()
    try:
        return await service.forward_messages(
            sender_id=current_user.user_id,
            sender_role=current_user.role,
            message_ids=body.message_ids,
            target_chat_ids=body.target_chat_ids,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─────────────────────────────────────────────
# 5. GET MESSAGES (PAGINATED)
# ─────────────────────────────────────────────

@router.get("/{chat_id}/messages", summary="Get paginated messages for a chat")
async def get_messages(
    chat_id: str,
    page:      int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    include_feedback = current_user.role in (UserRole.CORPORATOR, UserRole.OPS)
    viewer_name = await _get_viewer_name(current_user.user_id)

    try:
        service = ChatService()
        return await service.get_messages(
            chat_id=chat_id,
            viewer_id=current_user.user_id,
            viewer_role=current_user.role,
            viewer_name=viewer_name,
            page=page,
            page_size=page_size,
            include_feedback=include_feedback,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─────────────────────────────────────────────
# 6. SOFT DELETE MESSAGE (legacy — sender only)
# ─────────────────────────────────────────────

@router.delete("/messages/{message_id}", summary="Soft-delete a message (sender only)")
async def delete_message(
    message_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        service = ChatService()
        await service.delete_message(message_id, current_user.user_id)
        return {"message_id": message_id, "deleted": True}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─────────────────────────────────────────────
# 6a. DELETE FOR ME (Corporator only)
# ─────────────────────────────────────────────

@router.post(
    "/{chat_id}/message/{message_id}/delete-for-me",
    summary="Hide a message only for the requesting Corporator",
)
async def delete_message_for_me(
    chat_id: str,
    message_id: str,
    current_user: CurrentUser = Depends(require_roles(UserRole.CORPORATOR)),
):
    try:
        service = ChatService()
        await service.delete_for_me(
            message_id=message_id,
            corporator_id=current_user.user_id,
        )
        return {"message_id": message_id, "deleted_for_me": True}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─────────────────────────────────────────────
# 6b. DELETE FOR EVERYONE (Corporator only)
# ─────────────────────────────────────────────

@router.post(
    "/{chat_id}/message/{message_id}/delete-for-everyone",
    summary="Replace message content with deletion placeholder for all users",
)
async def delete_message_for_everyone(
    chat_id: str,
    message_id: str,
    current_user: CurrentUser = Depends(require_roles(UserRole.CORPORATOR)),
):
    try:
        service = ChatService()
        await service.delete_for_everyone(
            message_id=message_id,
            corporator_id=current_user.user_id,
        )
        return {"message_id": message_id, "deleted_for_everyone": True}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─────────────────────────────────────────────
# 7. REACT TO MESSAGE
# ─────────────────────────────────────────────

@router.post("/messages/{message_id}/react", summary="Add or update a reaction")
async def react_to_message(
    message_id: str,
    body: ReactToMessageRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        service = ChatService()
        return await service.react_to_message(
            message_id=message_id,
            user_id=current_user.user_id,
            reaction_type=body.reaction_type,
            emoji_value=body.emoji_value,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/messages/{message_id}/react", summary="Remove your reaction")
async def remove_reaction(
    message_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        service = ChatService()
        await service.remove_reaction(message_id, current_user.user_id)
        return {"message_id": message_id, "reaction_removed": True}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─────────────────────────────────────────────
# 8. SHARE TRACKING
# ─────────────────────────────────────────────

@router.post("/messages/{message_id}/share", summary="Log a message share event")
async def share_message(
    message_id: str,
    body: ShareMessageRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    try:
        service = ChatService()
        return await service.track_share(
            message_id=message_id,
            user_id=current_user.user_id,
            platform=body.platform,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─────────────────────────────────────────────
# 9. MESSAGE FEEDBACK (VOTER ONLY)
# ─────────────────────────────────────────────

@router.post("/messages/{message_id}/feedback",
             summary="Submit feedback on a message (Voter only)")
async def submit_feedback(
    message_id: str,
    body: MessageFeedbackRequest,
    current_user: CurrentUser = Depends(require_roles(UserRole.VOTER)),
):
    try:
        service = ChatService()
        return await service.submit_feedback(
            message_id=message_id,
            user_id=current_user.user_id,
            user_role=current_user.role,
            text=body.text,
            rating=body.rating,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─────────────────────────────────────────────
# 10. UNREAD COUNT
# ─────────────────────────────────────────────

@router.get("/unread", summary="Get unread message counts across all chats")
async def get_unread_counts(
    current_user: CurrentUser = Depends(get_current_user),
):
    service = ChatService()
    return await service.get_unread_counts(current_user.user_id, current_user.role)


# ─────────────────────────────────────────────
# 11. SEARCH MESSAGES
# ─────────────────────────────────────────────

@router.get("/search", summary="Full-text search across accessible messages")
async def search_messages(
    q:       str           = Query(..., min_length=1, description="Search query"),
    chat_id: Optional[str] = Query(None, description="Limit to specific chat"),
    limit:   int           = Query(20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
):
    service = ChatService()
    viewer_name = await _get_viewer_name(current_user.user_id)
    results = await service.search_messages(
        viewer_id=current_user.user_id,
        viewer_role=current_user.role,
        query=q,
        chat_id=chat_id,
        limit=limit,
        viewer_name=viewer_name,
    )
    return {"results": results, "count": len(results)}


# ─────────────────────────────────────────────
# 12. ANALYTICS — CORPORATOR
# ─────────────────────────────────────────────

@router.get("/analytics/me", summary="Messaging analytics for Corporator")
async def corporator_analytics(
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_ADVANCED_ANALYTICS)
    ),
):
    service = ChatService()
    return await service.corporator_analytics(current_user.user_id)


# ─────────────────────────────────────────────
# 13. ANALYTICS — OPS (GLOBAL)
# ─────────────────────────────────────────────

@router.get("/analytics/ops", summary="Global messaging analytics (OPS only)")
async def ops_analytics(
    current_user: CurrentUser = Depends(
        require_permission(Permission.VIEW_VOTER_INTELLIGENCE)
    ),
):
    service = ChatService()
    return await service.ops_analytics()

# backend/app/api/routes/chat.py
# ── ADD NEW ENDPOINT ──
# Add this endpoint to the router

@router.post("/broadcast-group", summary="Create broadcast group with dynamic filters")
async def create_broadcast_group(
    body: BroadcastGroupFilterRequest,
    current_user: CurrentUser = Depends(
        require_roles(UserRole.CORPORATOR, UserRole.LEADER)
    ),
):
    """
    Create a broadcast group by filtering users dynamically.
    
    Filters are optional. Any combination is supported:
    - language_preference: Language code
    - religion: Religion
    - age_group: Age bracket
    - state, city, ward, area: Geographic location
    - roles: User roles (voter, leader, etc.)
    - engagement_level: Engagement level
    
    Returns: Chat ID and group details
    
    Requires: CORPORATOR or LEADER role
    """
    service = ChatService()
    try:
        filters = {}
        if body.language_preference:
            filters["language_preference"] = body.language_preference
        if body.religion:
            filters["religion"] = body.religion
        if body.age_group:
            filters["age_group"] = body.age_group
        if body.state:
            filters["state"] = body.state
        if body.city:
            filters["city"] = body.city
        if body.ward:
            filters["ward"] = body.ward
        if body.area:
            filters["area"] = body.area
        if body.roles:
            filters["roles"] = body.roles
        if body.engagement_level:
            filters["engagement_level"] = body.engagement_level
        
        result = await service.create_broadcast_group_with_filters(
            group_name=body.group_name,
            sender_id=current_user.user_id,
            sender_role=current_user.role,
            filters=filters,
        )
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.post("/broadcast-group/preview", summary="Preview audience for broadcast group filters")
async def preview_broadcast_group(
    body: BroadcastGroupFilterPreviewRequest,
    current_user: CurrentUser = Depends(
        require_roles(UserRole.CORPORATOR, UserRole.LEADER)
    ),
):
    service = ChatService()
    try:
        filters = {}
        if body.language_preference:
            filters["language_preference"] = body.language_preference
        if body.religion:
            filters["religion"] = body.religion
        if body.age_group:
            filters["age_group"] = body.age_group
        if body.state:
            filters["state"] = body.state
        if body.city:
            filters["city"] = body.city
        if body.ward:
            filters["ward"] = body.ward
        if body.area:
            filters["area"] = body.area
        if body.roles:
            filters["roles"] = body.roles
        if body.engagement_level:
            filters["engagement_level"] = body.engagement_level

        return await service.preview_broadcast_group_filters(
            sender_id=current_user.user_id,
            sender_role=current_user.role,
            filters=filters,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )


@router.delete("/broadcast-group/{chat_id}", summary="Delete a broadcast group")
async def delete_broadcast_group(
    chat_id: str,
    current_user: CurrentUser = Depends(
        require_roles(UserRole.CORPORATOR, UserRole.LEADER)
    ),
):
    service = ChatService()
    try:
        return await service.delete_broadcast_group(
            chat_id=chat_id,
            requester_id=current_user.user_id,
            requester_role=current_user.role,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
