"""
Chat Service Rooms Module
=========================
Chat room and broadcast group operations.

Author: Political Communication Platform Team
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pymongo import ReturnDocument
from bson import ObjectId

from app.core.roles import UserRole
from app.models.chat_model import ChatType
from app.services.chat.helpers import (
    _oid,
    _normalize_id_set,
    _candidate_user_ids,
    ALLOWED_DIRECT_COMMS,
    BROADCAST_ROLES,
)

logger = logging.getLogger("app.services.chat_service")


class ChatRoomsMixin:
    async def get_or_create_direct_chat(
        self,
        sender_id: str,
        sender_role: UserRole,
        receiver_id: str,
    ) -> dict:
        """
        Get existing direct chat or create a new one between two users.
        Validates that communication is allowed based on roles.
        """
        receiver_doc = await self.db.users.find_one({"_id": _oid(receiver_id)})
        if not receiver_doc:
            raise ValueError("Receiver user not found")

        receiver_role = UserRole(receiver_doc.get("role"))
        allowed = ALLOWED_DIRECT_COMMS.get(sender_role, set())
        if receiver_role not in allowed:
            raise PermissionError(
                f"{sender_role.value} cannot message {receiver_role.value} directly"
            )

        participants_sorted = sorted([sender_id, receiver_id])
        existing = await self.db.chats.find_one({
            "chat_type":    ChatType.DIRECT,
            "participants": {"$all": participants_sorted},
            "is_active":    True,
        })
        if existing:
            return existing

        now = datetime.utcnow()
        chat_doc = {
            "chat_type":           ChatType.DIRECT,
            "participants":        participants_sorted,
            "created_by":          sender_id,
            "broadcast_to":        [],
            "last_message_text":   None,
            "last_message_at":     None,
            "last_message_sender": None,
            "last_message_id":     None,
            "last_message":        None,
            "unread_counts":       {sender_id: 0, receiver_id: 0},
            "is_active":           True,
            "created_at":          now,
            "updated_at":          now,
        }
        result = await self.db.chats.insert_one(chat_doc)
        chat_doc["_id"] = result.inserted_id
        logger.info(f"Created direct chat {result.inserted_id} between {sender_id} and {receiver_id}")
        return chat_doc

    async def get_chat_list(
        self,
        user_id: str,
        user_role: UserRole,
        viewer_name: str = "",
    ) -> List[dict]:
        """
        Get all chats accessible to the user, ordered by most recent message.
        """
        candidate_ids = _candidate_user_ids(user_id)
        if user_role in (UserRole.CORPORATOR, UserRole.LEADER, UserRole.OPS):
            query = {
                "is_active": True,
                "$or": [
                    {"participants": {"$in": candidate_ids}},
                    {"created_by": {"$in": candidate_ids}},
                ]
            }
        else:
            query = {
                "is_active": True,
                "$or": [
                    {"participants": {"$in": candidate_ids}},
                    {"broadcast_to": {"$in": candidate_ids}},
                ]
            }

        cursor = self.db.chats.find(query).sort("last_message_at", -1)
        chats = await cursor.to_list(length=100)

        viewer_language = await self._get_user_language(user_id)
        viewer_language = self._normalize_language(viewer_language)

        last_message_ids = []
        for c in chats:
            lm_id = c.get("last_message_id")
            if not lm_id:
                lm = c.get("last_message") or {}
                lm_id = lm.get("message_id")
            if lm_id and ObjectId.is_valid(str(lm_id)):
                last_message_ids.append(_oid(str(lm_id)))

        msg_map = {}
        if last_message_ids:
            msg_cursor = self.db.messages.find({"_id": {"$in": last_message_ids}})
            msg_docs = await msg_cursor.to_list(length=len(last_message_ids))
            msg_map = {str(m["_id"]): m for m in msg_docs}

        result = []
        for c in chats:
            unread = c.get("unread_counts", {}).get(user_id, 0)
            broadcast_to = c.get("broadcast_to", [])
            title = c.get("title") or c.get("group_name")
            participants = _normalize_id_set(c.get("participants", []))
            created_by = c.get("created_by")
            created_by = str(created_by) if created_by is not None else None
            last_message_at = c.get("last_message_at")
            created_at = c.get("created_at")
            last_message_text = c.get("last_message_text")
            last_message = c.get("last_message")
            lm_id = c.get("last_message_id")
            if not lm_id and isinstance(last_message, dict):
                lm_id = last_message.get("message_id")
            msg_doc = msg_map.get(lm_id) if lm_id else None
            if msg_doc:
                msg_resp = await self._build_message_response(
                    msg_doc,
                    user_id,
                    viewer_name,
                    viewer_language,
                    include_feedback=False,
                )
                display_text = (msg_resp.get("display_text") or "").strip()
                if not display_text:
                    display_text = msg_resp.get("file_name") or "Media"
                last_message_text = self._build_preview_text(display_text, None)
                last_message = {
                    "message_id":      msg_resp.get("message_id"),
                    "text_original":   msg_resp.get("original_text"),
                    "text_translated": msg_resp.get("display_text")
                    if msg_resp.get("is_translated") else None,
                    "display_text":    msg_resp.get("display_text"),
                    "source_language": msg_resp.get("source_language"),
                    "display_language": msg_resp.get("display_language"),
                    "is_translated":   msg_resp.get("is_translated"),
                    "sender_id":       msg_resp.get("sender_id"),
                    "timestamp":       msg_resp.get("created_at"),
                    "message_type":    msg_doc.get("message_type"),
                    "file_name":       msg_doc.get("file_name"),
                }
            result.append({
                "chat_id":             str(c["_id"]),
                "chat_type":           c.get("chat_type"),
                "participants":        sorted(participants),
                "last_message_text":   last_message_text,
                "last_message_at":     last_message_at.isoformat() if hasattr(last_message_at, "isoformat") else last_message_at,
                "last_message_sender": c.get("last_message_sender"),
                "last_message":        last_message,
                "unread_count":        unread,
                "is_active":           c.get("is_active", True),
                "created_at":          created_at.isoformat() if hasattr(created_at, "isoformat") else created_at,
                "created_by":          created_by,
                "title":               title,
                "broadcast_count":     len(broadcast_to),
            })
        return result

    # ──────────────────────────────────────────
    # 2. SEND MESSAGE (DIRECT CHAT)
    # ──────────────────────────────────────────

    def _build_broadcast_group_query(
        self,
        sender_id: str,
        filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {"is_active": True}
        # Broadcast groups must include only voters and leaders (never OPS)
        allowed_roles = {UserRole.VOTER.value, UserRole.LEADER.value}
        try:
            query["_id"] = {"$ne": _oid(sender_id)}
        except Exception:
            pass

        def _apply_in(field: str, value: Any):
            if value is None:
                return
            if isinstance(value, list):
                vals = [v for v in value if v is not None and str(v).strip() != ""]
                if not vals:
                    return
                query[field] = {"$in": vals} if len(vals) > 1 else vals[0]
            else:
                query[field] = value

        _apply_in("language_preference", filters.get("language_preference"))
        _apply_in("demographics.religion", filters.get("religion"))
        _apply_in("demographics.age_group", filters.get("age_group"))
        _apply_in("location.state", filters.get("state"))
        _apply_in("location.city", filters.get("city"))
        _apply_in("location.ward", filters.get("ward"))
        _apply_in("location.area", filters.get("area"))
        if filters.get("roles"):
            filtered = [r for r in filters["roles"] if r in allowed_roles]
            query["role"] = {"$in": filtered} if filtered else {"$in": []}
        else:
            query["role"] = {"$in": list(allowed_roles)}
        if filters.get("engagement_level"):
            _apply_in("engagement.level", filters.get("engagement_level"))

        return query

    # ─────────────────────────────────────────────
    # 3.5 CREATE BROADCAST GROUP (FILTER-BASED)
    # ─────────────────────────────────────────────

    async def create_broadcast_group_with_filters(
        self,
        group_name: str,
        sender_id: str,
        sender_role: UserRole,
        filters: Dict[str, Any],
    ) -> dict:
        """
        Create a broadcast group by filtering users dynamically.
        Returns chat metadata (no message sent).
        """
        if sender_role not in BROADCAST_ROLES:
            raise PermissionError("Only Corporator and Leader can create broadcast groups")

        if not group_name or not group_name.strip():
            raise ValueError("group_name is required")

        query = self._build_broadcast_group_query(sender_id, filters)

        # Find matching users
        cursor = self.db.users.find(query, {"_id": 1})
        matched = await cursor.to_list(length=10000)
        voter_ids = [str(u["_id"]) for u in matched]

        if not voter_ids:
            # We return a specific error message that the frontend can show
            return {
                "error": "No users match the selected filters",
                "chat_id": None,
                "member_count": 0
            }

        now = datetime.utcnow()
        chat_doc = {
            "chat_type":           ChatType.BROADCAST,
            "participants":        [sender_id],
            "created_by":          sender_id,
            "broadcast_to":        voter_ids,
            "group_name":          group_name.strip(),
            "last_message_text":   None,
            "last_message_at":     now,
            "last_message_sender": None,
            "last_message_id":     None,
            "last_message":        None,
            "unread_counts":       {vid: 0 for vid in voter_ids},
            "is_active":           True,
            "created_at":          now,
            "updated_at":          now,
            "title":               group_name.strip(),
        }

        chat_result = await self.db.chats.insert_one(chat_doc)

        return {
            "chat_id":       str(chat_result.inserted_id),
            "group_name":    group_name.strip(),
            "member_count":  len(voter_ids),
            "filters_applied": filters,
            "created_at":    now,
        }

    async def preview_broadcast_group_filters(
        self,
        sender_id: str,
        sender_role: UserRole,
        filters: Dict[str, Any],
    ) -> dict:
        """
        Preview audience for broadcast group filters.
        Returns total count, per-role counts, and user list.
        """
        if sender_role not in BROADCAST_ROLES:
            raise PermissionError("Only Corporator and Leader can preview broadcast groups")

        query = self._build_broadcast_group_query(sender_id, filters)
        cursor = self.db.users.find(
            query,
            {"_id": 1, "full_name": 1, "role": 1, "location": 1, "language_preference": 1},
        )
        users = await cursor.to_list(length=5000)

        by_role: Dict[str, int] = {}
        items: List[Dict[str, Any]] = []
        for u in users:
            role = u.get("role")
            by_role[role] = by_role.get(role, 0) + 1
            loc = u.get("location") or {}
            items.append({
                "user_id": str(u.get("_id")),
                "full_name": u.get("full_name") or "",
                "role": role,
                "language_preference": u.get("language_preference"),
                "location": {
                    "state": loc.get("state"),
                    "city": loc.get("city"),
                    "ward": loc.get("ward"),
                    "area": loc.get("area"),
                },
            })

        return {
            "total": len(items),
            "by_role": by_role,
            "users": items,
        }

    async def delete_broadcast_group(
        self,
        chat_id: str,
        requester_id: str,
        requester_role: UserRole,
    ) -> dict:
        """
        Soft-delete a broadcast group created by the requester.
        """
        if requester_role not in BROADCAST_ROLES:
            raise PermissionError("Only Corporator and Leader can delete broadcast groups")

        chat = await self.db.chats.find_one({"_id": _oid(chat_id), "is_active": True})
        if not chat:
            raise ValueError("Broadcast group not found")
        if chat.get("chat_type") != ChatType.BROADCAST:
            raise ValueError("Chat is not a broadcast group")
        if chat.get("created_by") != requester_id:
            raise PermissionError("You can only delete broadcast groups you created")

        now = datetime.utcnow()
        await self.db.chats.update_one(
            {"_id": _oid(chat_id)},
            {"$set": {"is_active": False, "updated_at": now, "deleted_at": now}},
        )

        # Hide all messages in this broadcast group for everyone
        await self.db.messages.update_many(
            {"chat_id": chat_id},
            {"$set": {
                "is_deleted": True,
                "is_deleted_globally": True,
                "updated_at": now,
            }},
        )

        return {"chat_id": chat_id, "deleted": True, "deleted_at": now}

    # ──────────────────────────────────────────
    # 4. GET MESSAGES (PAGINATED + MARK READ)
    # ──────────────────────────────────────────

    async def _get_chat_or_raise(self, chat_id: str) -> dict:
        """Get a chat by ID or raise ValueError if not found."""
        chat = await self.db.chats.find_one({"_id": _oid(chat_id), "is_active": True})
        if not chat:
            raise ValueError("Chat not found")
        return chat

    def _assert_participant(self, chat: dict, user_id: str, role: UserRole) -> None:
        """Verify user is a participant in the chat."""
        participants = _normalize_id_set(chat.get("participants", []))
        creator = chat.get("created_by")
        creator = str(creator) if creator is not None else None
        if user_id not in participants and user_id != creator:
            raise PermissionError("You are not a participant in this chat")

    def _assert_access(self, chat: dict, user_id: str, role: UserRole) -> None:
        """
        Verify user has access to view chat messages.
        OPS role has access to all chats.
        """
        if role == UserRole.OPS:
            return
        participants = _normalize_id_set(chat.get("participants", []))
        creator = chat.get("created_by")
        creator = str(creator) if creator is not None else None
        broadcast_to = _normalize_id_set(chat.get("broadcast_to", []))
        has_access = (
            user_id in participants
            or user_id == creator
            or user_id in broadcast_to
        )
        if not has_access:
            raise PermissionError("You do not have access to this chat")
