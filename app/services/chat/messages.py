"""
Chat Service Messages Module
============================
Message operations, reactions, shares, feedback, and analytics.

Author: Political Communication Platform Team
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from bson import ObjectId
from pymongo import ReturnDocument

from app.core.config import settings
from app.core.roles import UserRole
from app.models.chat_model import (
    ChatType,
    MessageStatus,
    ReactionType,
    SharePlatform,
    MessageSentiment,
)
from app.services.chat.helpers import (
    _oid,
    _normalize_id_set,
    _str_id,
    _render_template,
    _extract_first_url,
    _fetch_link_metadata,
    _save_file,
    _serialize_message,
    _classify_sentiment,
    _DELETED_GLOBALLY_PLACEHOLDER,
    BROADCAST_ROLES,
)

logger = logging.getLogger("app.services.chat_service")


class ChatMessagesMixin:
    @staticmethod
    def _normalize_language(lang: Optional[str]) -> str:
        if not lang:
            return "en"
        return str(lang).strip().lower()

    @staticmethod
    def _build_preview_text(text: str, file_name: Optional[str]) -> str:
        preview_source = text.strip() if text and text.strip() else (file_name or "Media")
        return preview_source[:80] + ("..." if len(preview_source) > 80 else "")

    def _build_last_message_snapshot(
        self,
        msg_doc: dict,
        source_language: str,
        message_type: str,
        sender_id: str,
        timestamp: datetime,
    ) -> dict:
        original_text = msg_doc.get("original_text")
        if original_text is None:
            original_text = msg_doc.get("content", "")
        return {
            "message_id":    str(msg_doc.get("_id", "")),
            "text_original": original_text,
            "text_translated": None,
            "display_language": source_language,
            "translations":  {},
            "source_language": source_language,
            "message_type":  message_type,
            "file_name":     msg_doc.get("file_name"),
            "sender_id":     sender_id,
            "timestamp":     timestamp,
        }

    async def _sync_last_message_translation(
        self,
        doc: dict,
        target_language: str,
        translated_text: str,
    ) -> None:
        chat_id = doc.get("chat_id")
        if not chat_id:
            return
        try:
            await self.db.chats.update_one(
                {"_id": _oid(chat_id), "last_message.message_id": str(doc.get("_id"))},
                {"$set": {
                    f"last_message.translations.{target_language}": translated_text,
                    "updated_at": datetime.utcnow(),
                }},
            )
        except Exception:
            logger.warning(
                "Failed to sync last_message translation for chat %s", chat_id
            )

    async def _get_user_language(self, user_id: str) -> Optional[str]:
        """
        Fetch user language preference.
        Returns None if user not found or preference missing.
        """
        try:
            if not ObjectId.is_valid(user_id):
                return None
            user = await self.db.users.find_one(
                {"_id": _oid(user_id)},
                {"language_preference": 1},
            )
            if not user:
                return None
            lang = user.get("language_preference")
            if not lang:
                return None
            return self._normalize_language(lang)
        except Exception:
            return None

    async def _resolve_source_language(
        self,
        provided_language: Optional[str],
        sender_id: str,
        text: str,
    ) -> str:
        if provided_language:
            return self._normalize_language(provided_language)

        sender_lang = await self._get_user_language(sender_id)
        if sender_lang:
            return sender_lang

        if text and text.strip():
            detected = await self.translation_service.detect_language(text)
            if detected:
                return self._normalize_language(detected)

        return "en"

    async def _get_or_create_translation(
        self,
        doc: dict,
        source_language: str,
        target_language: str,
        original_text: str,
    ) -> Optional[str]:
        translations = doc.get("translations") or {}
        existing = translations.get(target_language)
        if isinstance(existing, dict) and existing.get("text"):
            logger.info(
                "Translation cache hit: message_id=%s target=%s source=%s",
                str(doc.get("_id")),
                target_language,
                source_language,
            )
            return existing.get("text")

        # Try to claim translation slot to reduce duplicate generation
        now = datetime.utcnow()
        claimed = await self.db.messages.find_one_and_update(
            {"_id": doc["_id"], f"translations.{target_language}": {"$exists": False}},
            {"$set": {
                f"translations.{target_language}": {
                    "status": "pending",
                    "created_at": now,
                    "updated_at": now,
                }
            }},
            return_document=ReturnDocument.AFTER,
        )
        if claimed is None:
            latest = await self.db.messages.find_one(
                {"_id": doc["_id"]},
                {f"translations.{target_language}": 1},
            )
            if latest:
                entry = (latest.get("translations") or {}).get(target_language)
                if isinstance(entry, dict) and entry.get("text"):
                    return entry.get("text")
            return None

        translated = await self.translation_service.translate_text(
            original_text, source_language, target_language
        )
        if translated:
            logger.info(
                "Translation generated: message_id=%s target=%s source=%s",
                str(doc.get("_id")),
                target_language,
                source_language,
            )
            await self.db.messages.update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    f"translations.{target_language}": {
                        "text": translated,
                        "model": settings.gpt_model,
                        "source_language": source_language,
                        "created_at": now,
                        "updated_at": now,
                    }
                }},
            )
            await self._sync_last_message_translation(doc, target_language, translated)
            return translated

        # Translation failed â€” remove pending marker to allow retries
        await self.db.messages.update_one(
            {"_id": doc["_id"]},
            {"$unset": {f"translations.{target_language}": ""}},
        )
        logger.warning(
            "Translation failed: message_id=%s target=%s source=%s",
            str(doc.get("_id")),
            target_language,
            source_language,
        )
        return None

    async def _build_message_response(
        self,
        doc: dict,
        viewer_id: str,
        viewer_name: str,
        viewer_language: str,
        include_feedback: bool = False,
    ) -> dict:
        original_text = doc.get("original_text")
        if original_text is None:
            original_text = doc.get("content", "")

        source_language = doc.get("source_language")
        if not source_language:
            source_language = await self._resolve_source_language(
                None,
                doc.get("sender_id", ""),
                original_text,
            )
            await self.db.messages.update_one(
                {"_id": doc["_id"]},
                {"$set": {"source_language": source_language, "updated_at": datetime.utcnow()}},
            )

        if doc.get("original_text") is None:
            await self.db.messages.update_one(
                {"_id": doc["_id"]},
                {"$set": {"original_text": original_text, "updated_at": datetime.utcnow()}},
            )

        source_language = self._normalize_language(source_language)
        target_language = self._normalize_language(viewer_language)

        is_deleted_globally = doc.get("is_deleted_globally", False)
        if is_deleted_globally:
            return _serialize_message(
                doc,
                viewer_id,
                viewer_name,
                include_feedback=include_feedback,
                display_text=_DELETED_GLOBALLY_PLACEHOLDER,
                original_text=original_text,
                source_language=source_language,
                display_language=target_language,
                is_translated=False,
            )

        display_text = original_text
        display_language = source_language
        is_translated = False

        if original_text and source_language != target_language:
            logger.info(
                "Translation needed: message_id=%s viewer=%s source=%s target=%s",
                str(doc.get("_id")),
                viewer_id,
                source_language,
                target_language,
            )
            translated = await self._get_or_create_translation(
                doc, source_language, target_language, original_text
            )
            if translated:
                display_text = translated
                display_language = target_language
                is_translated = True
                logger.info(
                    "Translation applied: message_id=%s viewer=%s target=%s",
                    str(doc.get("_id")),
                    viewer_id,
                    target_language,
                )
            else:
                logger.info(
                    "Translation fallback to original: message_id=%s viewer=%s",
                    str(doc.get("_id")),
                    viewer_id,
                )

        if doc.get("template_flag"):
            display_text = _render_template(display_text, viewer_name)

        return _serialize_message(
            doc,
            viewer_id,
            viewer_name,
            include_feedback=include_feedback,
            display_text=display_text,
            original_text=original_text,
            source_language=source_language,
            display_language=display_language,
            is_translated=is_translated,
        )

    async def _pretranslate_for_languages(
        self,
        doc: dict,
        source_language: str,
        target_languages: List[str],
    ) -> None:
        """
        Fire-and-forget pretranslation for a set of target languages.
        """
        original_text = doc.get("original_text") or doc.get("content", "")
        if not original_text:
            return
        tasks = []
        for lang in target_languages:
            lang = self._normalize_language(lang)
            if not lang or lang == source_language:
                continue
            tasks.append(
                self._get_or_create_translation(
                    doc, source_language, lang, original_text
                )
            )
        if not tasks:
            return
        try:
            await asyncio.gather(*tasks)
        except Exception as exc:
            logger.warning(f"Pretranslation failed: {exc}")

    async def _queue_pretranslation_for_chat(
        self,
        chat: dict,
        doc: dict,
        source_language: str,
    ) -> None:
        """
        Starts pretranslation for all unique recipient languages in the chat.
        """
        recipient_ids: List[str] = []
        if chat.get("chat_type") == ChatType.DIRECT:
            recipient_ids = [str(v) for v in chat.get("participants", [])]
        else:
            recipient_ids = [str(v) for v in chat.get("broadcast_to", [])]

        if not recipient_ids:
            return

        cursor = self.db.users.find(
            {"_id": {"$in": [ObjectId(r) for r in recipient_ids if ObjectId.is_valid(r)]}},
            {"language_preference": 1},
        )
        langs: set[str] = set()
        async for user in cursor:
            lang = user.get("language_preference")
            if lang:
                langs.add(self._normalize_language(lang))
        if not langs:
            return

        # Run in background so send is not blocked
        async def _run():
            await self._pretranslate_for_languages(doc, source_language, list(langs))

        try:
            asyncio.create_task(_run())
        except Exception as exc:
            logger.warning(f"Failed to start pretranslation task: {exc}")

    # ──────────────────────────────────────────
    # 1. CREATE / GET CHAT
    # ──────────────────────────────────────────

    async def send_message(
        self,
        chat_id: str,
        sender_id: str,
        sender_role: UserRole,
        content: str,
        source_language: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        file_name: Optional[str] = None,
    ) -> dict:
        """
        Send a message in a direct chat.
        Supports optional file attachment (image, video, or document).
        """
        chat = await self._get_chat_or_raise(chat_id)
        self._assert_participant(chat, sender_id, sender_role)

        # Validate and save file if provided
        saved_file_url: Optional[str] = None
        saved_file_type: Optional[str] = None
        saved_file_name: Optional[str] = None
        saved_file_size: Optional[int] = None
        saved_preview_url: Optional[str] = None
        file_uploaded_at: Optional[datetime] = None
        link_url: Optional[str] = None
        link_title: Optional[str] = None
        link_description: Optional[str] = None
        link_image: Optional[str] = None

        if file_bytes and file_name:
            (
                saved_file_url,
                saved_file_type,
                saved_file_name,
                saved_file_size,
                saved_preview_url,
            ) = _save_file(file_bytes, file_name)
            file_uploaded_at = datetime.utcnow()

        # Best-effort link preview (first URL only)
        link_url = _extract_first_url(content)
        if link_url:
            meta = await _fetch_link_metadata(link_url)
            link_title = meta.get("title")
            link_description = meta.get("description")
            link_image = meta.get("image")

        now = datetime.utcnow()
        has_template = "{{" in content and "}}" in content
        resolved_source_language = await self._resolve_source_language(
            source_language, sender_id, content
        )
        message_type = "media" if saved_file_url else "text"

        msg_doc = {
            "chat_id":               chat_id,
            "sender_id":             sender_id,
            "content":               content,
            "original_text":         content,
            "source_language":       resolved_source_language,
            "translations":          {},
            "message_type":          message_type,
            "template_flag":         has_template,
            "is_broadcast":          False,
            "broadcast_recipients":  [],
            "status":                MessageStatus.SENT,
            "read_by":               {sender_id: now.isoformat()},
            "is_deleted":            False,
            "deleted_at":            None,
            "is_deleted_globally":   False,
            "deleted_for_users":     [],
            # ── Media fields ──
            "file_url":              saved_file_url,
            "file_type":             saved_file_type,
            "file_name":             saved_file_name,
            "file_uploaded_at":      file_uploaded_at,
            "file_size":             saved_file_size,
            "preview_url":           saved_preview_url,
            "link_url":              link_url,
            "link_title":            link_title,
            "link_description":      link_description,
            "link_image":            link_image,
            # ──────────────────
            "reactions":             [],
            "share_logs":            [],
            "feedback":              [],
            "reaction_count":        0,
            "share_count":           0,
            "feedback_count":        0,
            "created_at":            now,
            "updated_at":            now,
        }
        result = await self.db.messages.insert_one(msg_doc)
        msg_doc["_id"] = result.inserted_id
        await self._queue_pretranslation_for_chat(
            chat, msg_doc, resolved_source_language
        )

        participants = chat.get("participants", [])
        unread_inc = {
            f"unread_counts.{p}": 1
            for p in participants if p != sender_id
        }
        # Preview text: show file name if content is empty
        preview = self._build_preview_text(content, saved_file_name)
        last_snapshot = self._build_last_message_snapshot(
            msg_doc,
            resolved_source_language,
            message_type,
            sender_id,
            now,
        )
        await self.db.chats.update_one(
            {"_id": _oid(chat_id)},
            {"$set": {
                "last_message_text":   preview,
                "last_message_at":     now,
                "last_message_sender": sender_id,
                "last_message_id":     str(msg_doc["_id"]),
                "last_message":        last_snapshot,
                "updated_at":          now,
            }, "$inc": unread_inc}
        )

        logger.info(f"Message sent in chat {chat_id} by {sender_id}")
        viewer_language = await self._get_user_language(sender_id)
        if not viewer_language:
            viewer_language = resolved_source_language
        viewer_language = self._normalize_language(viewer_language)
        return await self._build_message_response(
            msg_doc,
            sender_id,
            "",
            viewer_language,
            include_feedback=False,
        )

    async def forward_messages(
        self,
        sender_id: str,
        sender_role: UserRole,
        message_ids: List[str],
        target_chat_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Forward existing messages to one or more chats.
        Copies content and attachment metadata without re-uploading files.
        """
        forwarded = 0
        now = datetime.utcnow()

        for chat_id in target_chat_ids:
            chat = await self._get_chat_or_raise(chat_id)
            if chat.get("chat_type") == ChatType.DIRECT:
                self._assert_participant(chat, sender_id, sender_role)
            else:
                if str(chat.get("created_by")) != str(sender_id):
                    raise PermissionError("You cannot forward to this chat")

            for mid in message_ids:
                src = await self.db.messages.find_one({"_id": _oid(mid)})
                if not src:
                    continue
                source_chat = await self._get_chat_or_raise(src.get("chat_id"))
                self._assert_access(source_chat, sender_id, sender_role)

                content = src.get("content", "")
                has_template = "{{" in content and "}}" in content
                src_source_language = src.get("source_language")
                if not src_source_language:
                    src_source_language = await self._resolve_source_language(
                        None,
                        src.get("sender_id", ""),
                        content,
                    )
                message_type = src.get("message_type") or ("media" if src.get("file_url") else "text")
                new_doc = {
                    "chat_id":              chat_id,
                    "sender_id":            sender_id,
                    "content":              content,
                    "original_text":        src.get("original_text") or content,
                    "source_language":      src_source_language,
                    "translations":         {},
                    "message_type":         message_type,
                    "template_flag":        has_template,
                    "is_broadcast":         False,
                    "broadcast_recipients": [],
                    "status":               MessageStatus.SENT,
                    "read_by":              {sender_id: now.isoformat()},
                    "is_deleted":           False,
                    "deleted_at":           None,
                    "is_deleted_globally":  False,
                    "deleted_for_users":    [],
                    "file_url":             src.get("file_url"),
                    "file_type":            src.get("file_type"),
                    "file_name":            src.get("file_name"),
                    "file_uploaded_at":     src.get("file_uploaded_at"),
                    "file_size":            src.get("file_size"),
                    "preview_url":          src.get("preview_url"),
                    "link_url":             src.get("link_url"),
                    "link_title":           src.get("link_title"),
                    "link_description":     src.get("link_description"),
                    "link_image":           src.get("link_image"),
                    "reactions":            [],
                    "share_logs":           [],
                    "feedback":             [],
                    "reaction_count":       0,
                    "share_count":          0,
                    "feedback_count":       0,
                    "created_at":           now,
                    "updated_at":           now,
                }
                result = await self.db.messages.insert_one(new_doc)
                new_doc["_id"] = result.inserted_id

                preview = self._build_preview_text(content, new_doc.get("file_name"))
                last_snapshot = self._build_last_message_snapshot(
                    new_doc,
                    src_source_language,
                    message_type,
                    sender_id,
                    now,
                )
                unread_inc = {}
                if chat.get("chat_type") == ChatType.DIRECT:
                    participants = chat.get("participants", [])
                    unread_inc = {
                        f"unread_counts.{p}": 1
                        for p in participants if p != sender_id
                    }
                else:
                    broadcast_to = chat.get("broadcast_to", [])
                    unread_inc = {
                        f"unread_counts.{v}": 1
                        for v in broadcast_to if v != sender_id
                    }
                await self.db.chats.update_one(
                    {"_id": _oid(chat_id)},
                    {"$set": {
                        "last_message_text":   preview,
                        "last_message_at":     now,
                        "last_message_sender": sender_id,
                        "last_message_id":     str(new_doc["_id"]),
                        "last_message":        last_snapshot,
                        "updated_at":          now,
                    }, "$inc": unread_inc},
                )
                forwarded += 1

        return {"forwarded": forwarded}

    # ──────────────────────────────────────────
    # 3. BROADCAST MESSAGE
    # ──────────────────────────────────────────

    async def send_broadcast(
        self,
        sender_id: str,
        sender_role: UserRole,
        content: str,
        voter_ids: List[str],
        chat_title: Optional[str] = None,
        source_language: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        file_name: Optional[str] = None,
    ) -> dict:
        """
        Send a broadcast message to multiple voters.
        Only Corporator and Leader roles can broadcast.
        Supports optional file attachment.
        """
        if sender_role not in BROADCAST_ROLES:
            raise PermissionError("Only Corporator and Leader can broadcast messages")

        # Validate and save file if provided
        saved_file_url: Optional[str] = None
        saved_file_type: Optional[str] = None
        saved_file_name: Optional[str] = None
        saved_file_size: Optional[int] = None
        saved_preview_url: Optional[str] = None
        file_uploaded_at: Optional[datetime] = None

        if file_bytes and file_name:
            (
                saved_file_url,
                saved_file_type,
                saved_file_name,
                saved_file_size,
                saved_preview_url,
            ) = _save_file(file_bytes, file_name)
            file_uploaded_at = datetime.utcnow()

        # Best-effort link preview (first URL only)
        link_url = _extract_first_url(content)
        if link_url:
            meta = await _fetch_link_metadata(link_url)
            link_title = meta.get("title")
            link_description = meta.get("description")
            link_image = meta.get("image")

        now = datetime.utcnow()
        has_template = "{{" in content and "}}" in content
        resolved_source_language = await self._resolve_source_language(
            source_language, sender_id, content
        )
        message_type = "media" if saved_file_url else "text"

        chat_doc = {
            "chat_type":           ChatType.BROADCAST,
            "participants":        [sender_id],
            "created_by":          sender_id,
            "broadcast_to":        voter_ids,
            "last_message_text":   None,
            "last_message_at":     None,
            "last_message_sender": None,
            "last_message_id":     None,
            "last_message":        None,
            "unread_counts":       {vid: 0 for vid in voter_ids},
            "is_active":           True,
            "created_at":          now,
            "updated_at":          now,
        }
        if chat_title:
            chat_doc["title"] = chat_title

        chat_result = await self.db.chats.insert_one(chat_doc)
        chat_id = str(chat_result.inserted_id)

        msg_doc = {
            "chat_id":               chat_id,
            "sender_id":             sender_id,
            "content":               content,
            "original_text":         content,
            "source_language":       resolved_source_language,
            "translations":          {},
            "message_type":          message_type,
            "template_flag":         has_template,
            "is_broadcast":          True,
            "broadcast_recipients":  voter_ids,
            "status":                MessageStatus.SENT,
            "read_by":               {sender_id: now.isoformat()},
            "is_deleted":            False,
            "deleted_at":            None,
            "is_deleted_globally":   False,
            "deleted_for_users":     [],
            # ── Media fields ──
            "file_url":              saved_file_url,
            "file_type":             saved_file_type,
            "file_name":             saved_file_name,
            "file_uploaded_at":      file_uploaded_at,
            "file_size":             saved_file_size,
            "preview_url":           saved_preview_url,
            "link_url":              link_url,
            "link_title":            link_title,
            "link_description":      link_description,
            "link_image":            link_image,
            # ──────────────────
            "reactions":             [],
            "share_logs":            [],
            "feedback":              [],
            "reaction_count":        0,
            "share_count":           0,
            "feedback_count":        0,
            "created_at":            now,
            "updated_at":            now,
        }
        msg_result = await self.db.messages.insert_one(msg_doc)
        msg_doc["_id"] = msg_result.inserted_id
        await self._queue_pretranslation_for_chat(
            chat_doc, msg_doc, resolved_source_language
        )

        unread_inc = {f"unread_counts.{vid}": 1 for vid in voter_ids}
        preview = self._build_preview_text(content, saved_file_name)
        last_snapshot = self._build_last_message_snapshot(
            msg_doc,
            resolved_source_language,
            message_type,
            sender_id,
            now,
        )
        await self.db.chats.update_one(
            {"_id": chat_result.inserted_id},
            {"$set": {
                "last_message_text":   preview,
                "last_message_at":     now,
                "last_message_sender": sender_id,
                "last_message_id":     str(msg_doc["_id"]),
                "last_message":        last_snapshot,
                "updated_at":          now,
            }, "$inc": unread_inc}
        )

        logger.info(
            f"Broadcast sent by {sender_id} to {len(voter_ids)} voters. "
            f"chat_id={chat_id}, msg_id={msg_result.inserted_id}, "
            f"has_file={saved_file_url is not None}"
        )
        return {
            "chat_id":    chat_id,
            "message_id": str(msg_result.inserted_id),
            "recipients": len(voter_ids),
            "template_flag": has_template,
        }

    async def get_messages(
        self,
        chat_id: str,
        viewer_id: str,
        viewer_role: UserRole,
        viewer_name: str,
        page: int = 1,
        page_size: int = 20,
        include_feedback: bool = False,
    ) -> dict:
        """
        Fetch paginated messages for a chat.

        Filtering applied per viewer:
          - Messages with is_deleted=True are always excluded (legacy delete).
          - Messages where viewer_id is in deleted_for_users are excluded
            (Corporator "Delete for Me" — hides only for that corporator).
          - Messages with is_deleted_globally=True are included but content
            is replaced with the deletion placeholder.

        Pagination counts respect the deleted_for_users filter so page math stays correct.
        Automatically marks messages as read for the viewer.
        """
        chat = await self._get_chat_or_raise(chat_id)
        self._assert_access(chat, viewer_id, viewer_role)

        skip = (page - 1) * page_size

        # Base query: exclude legacy-deleted AND messages hidden for this viewer
        base_query = {
            "chat_id":            chat_id,
            "is_deleted":         False,
            "deleted_for_users":  {"$nin": [viewer_id]},
        }

        total = await self.db.messages.count_documents(base_query)
        cursor = (
            self.db.messages
            .find(base_query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(page_size)
        )
        raw_messages = await cursor.to_list(length=page_size)

        now = datetime.utcnow()
        message_ids = [m["_id"] for m in raw_messages]
        if message_ids:
            await self.db.messages.update_many(
                {"_id": {"$in": message_ids}, f"read_by.{viewer_id}": {"$exists": False}},
                {"$set": {
                    f"read_by.{viewer_id}": now.isoformat(),
                    "status": MessageStatus.SEEN,
                    "updated_at": now,
                }}
            )
            await self.db.chats.update_one(
                {"_id": _oid(chat_id)},
                {"$set": {f"unread_counts.{viewer_id}": 0, "updated_at": now}}
            )

        viewer_language = await self._get_user_language(viewer_id)
        viewer_language = self._normalize_language(viewer_language)

        serialized: List[dict] = []
        for m in raw_messages:
            serialized.append(
                await self._build_message_response(
                    m,
                    viewer_id,
                    viewer_name,
                    viewer_language,
                    include_feedback=include_feedback,
                )
            )

        return {
            "chat_id":   chat_id,
            "messages":  serialized,
            "total":     total,
            "page":      page,
            "page_size": page_size,
            "has_more":  (skip + page_size) < total,
        }

    # ──────────────────────────────────────────
    # 5. UNREAD COUNT
    # ──────────────────────────────────────────

    async def get_unread_counts(self, user_id: str, user_role: UserRole) -> dict:
        """
        Get unread message counts for all chats accessible to the user.
        """
        if user_role in (UserRole.CORPORATOR, UserRole.LEADER, UserRole.OPS):
            query = {
                "is_active": True,
                "$or": [{"participants": user_id}, {"created_by": user_id}]
            }
        else:
            query = {
                "is_active": True,
                "$or": [{"participants": user_id}, {"broadcast_to": user_id}]
            }

        cursor = self.db.chats.find(query, {f"unread_counts.{user_id}": 1})
        per_chat = {}
        total = 0
        async for chat in cursor:
            count = chat.get("unread_counts", {}).get(user_id, 0)
            per_chat[str(chat["_id"])] = count
            total += count

        return {"total_unread": total, "per_chat": per_chat}

    # ──────────────────────────────────────────
    # 6. SOFT DELETE MESSAGE (legacy — sender only)
    # ──────────────────────────────────────────

    async def delete_message(self, message_id: str, requestor_id: str) -> bool:
        """
        Soft-delete a message (legacy method).
        Only the sender can delete their own message.
        """
        msg = await self.db.messages.find_one({"_id": _oid(message_id)})
        if not msg:
            raise ValueError("Message not found")
        if msg.get("sender_id") != requestor_id:
            raise PermissionError("Only the sender can delete this message")

        now = datetime.utcnow()
        await self.db.messages.update_one(
            {"_id": _oid(message_id)},
            {"$set": {"is_deleted": True, "deleted_at": now, "updated_at": now}}
        )
        logger.info(f"Message {message_id} soft-deleted by {requestor_id}")
        return True

    # ──────────────────────────────────────────
    # 6a. DELETE FOR ME (Corporator only)
    # ──────────────────────────────────────────

    async def delete_for_me(self, message_id: str, corporator_id: str) -> bool:
        """
        Hide this message only for the requesting corporator.
        Message remains visible and unchanged for all other users.
        Does NOT affect analytics, reactions, feedback, or broadcast logic.
        """
        msg = await self.db.messages.find_one({"_id": _oid(message_id)})
        if not msg:
            raise ValueError("Message not found")

        # Idempotent: skip if already hidden for this user
        if corporator_id in msg.get("deleted_for_users", []):
            return True

        now = datetime.utcnow()
        await self.db.messages.update_one(
            {"_id": _oid(message_id)},
            {
                "$addToSet": {"deleted_for_users": corporator_id},
                "$set":      {"updated_at": now},
            }
        )
        logger.info(f"Message {message_id} hidden for user {corporator_id} (delete-for-me)")
        return True

    # ──────────────────────────────────────────
    # 6b. DELETE FOR EVERYONE (Corporator only)
    # ──────────────────────────────────────────

    async def delete_for_everyone(self, message_id: str, corporator_id: str) -> bool:
        """
        Mark the message as globally deleted for all users.
        Content is replaced with placeholder at serialization time.
        Metadata (reactions, feedback, analytics references) is preserved intact.
        Does NOT hard-delete. Does NOT set is_deleted=True (preserves analytics).
        """
        msg = await self.db.messages.find_one({"_id": _oid(message_id)})
        if not msg:
            raise ValueError("Message not found")

        # Idempotent
        if msg.get("is_deleted_globally"):
            return True

        now = datetime.utcnow()
        await self.db.messages.update_one(
            {"_id": _oid(message_id)},
            {"$set": {"is_deleted_globally": True, "updated_at": now}}
        )
        logger.info(f"Message {message_id} deleted for everyone by corporator {corporator_id}")
        return True

    # ──────────────────────────────────────────
    # 7. REACTIONS
    # ──────────────────────────────────────────

    async def react_to_message(
        self,
        message_id: str,
        user_id: str,
        reaction_type: ReactionType,
        emoji_value: Optional[str] = None,
    ) -> dict:
        """
        Add or update a reaction to a message.
        Reactions are tracked per user (one reaction per user per message).
        """
        msg = await self.db.messages.find_one(
            {"_id": _oid(message_id), "is_deleted": False}
        )
        if not msg:
            raise ValueError("Message not found")

        if msg.get("sender_id") == user_id:
            raise PermissionError("You cannot react to your own message")

        now = datetime.utcnow()
        existing_reactions: List[dict] = msg.get("reactions", [])
        user_had_reaction = any(r.get("user_id") == user_id for r in existing_reactions)

        reaction_obj = {
            "user_id":       user_id,
            "reaction_type": reaction_type,
            "emoji_value":   emoji_value,
            "reacted_at":    now,
        }

        if user_had_reaction:
            await self.db.messages.update_one(
                {"_id": _oid(message_id), "reactions.user_id": user_id},
                {"$set": {
                    "reactions.$": reaction_obj,
                    "updated_at": now,
                }}
            )
        else:
            await self.db.messages.update_one(
                {"_id": _oid(message_id)},
                {
                    "$push": {"reactions": reaction_obj},
                    "$inc":  {"reaction_count": 1},
                    "$set":  {"updated_at": now},
                }
            )

        logger.info(f"Reaction '{reaction_type}' (emoji={emoji_value}) by {user_id} on message {message_id}")
        return {"message_id": message_id, "reaction_type": reaction_type, "emoji_value": emoji_value}

    async def remove_reaction(self, message_id: str, user_id: str) -> bool:
        """
        Remove a user's reaction from a message.
        """
        msg = await self.db.messages.find_one(
            {"_id": _oid(message_id), "reactions.user_id": user_id}
        )
        if not msg:
            raise ValueError("Reaction not found")

        now = datetime.utcnow()
        await self.db.messages.update_one(
            {"_id": _oid(message_id)},
            {
                "$pull": {"reactions": {"user_id": user_id}},
                "$inc":  {"reaction_count": -1},
                "$set":  {"updated_at": now},
            }
        )
        logger.info(f"Reaction removed by {user_id} from message {message_id}")
        return True

    # ──────────────────────────────────────────
    # 8. SHARE TRACKING
    # ──────────────────────────────────────────

    async def track_share(
        self,
        message_id: str,
        user_id: str,
        platform: SharePlatform,
    ) -> dict:
        """
        Log a message share event to a specific platform.
        """
        msg = await self.db.messages.find_one(
            {"_id": _oid(message_id), "is_deleted": False}
        )
        if not msg:
            raise ValueError("Message not found")

        now = datetime.utcnow()
        share_log = {
            "user_id":   user_id,
            "platform":  platform,
            "shared_at": now,
        }
        await self.db.messages.update_one(
            {"_id": _oid(message_id)},
            {
                "$push": {"share_logs": share_log},
                "$inc":  {"share_count": 1},
                "$set":  {"updated_at": now},
            }
        )
        logger.info(f"Share logged: message {message_id}, user {user_id}, platform {platform}")
        return {"message_id": message_id, "platform": platform, "shared_at": now}

    # ──────────────────────────────────────────
    # 9. MESSAGE FEEDBACK
    # ──────────────────────────────────────────

    async def submit_feedback(
        self,
        message_id: str,
        user_id: str,
        user_role: UserRole,
        text: Optional[str] = None,
        rating: Optional[int] = None,
    ) -> dict:
        """
        Submit feedback on a message (Voter only).
        Supports optional text feedback and/or star rating (1-5).
        """
        if user_role != UserRole.VOTER:
            raise PermissionError("Only voters can submit message feedback")

        msg = await self.db.messages.find_one(
            {"_id": _oid(message_id), "is_deleted": False}
        )
        if not msg:
            raise ValueError("Message not found")

        now = datetime.utcnow()
        clean_text = text.strip() if text and text.strip() else None
        sentiment = _classify_sentiment(clean_text) if clean_text else None

        existing_feedback: List[dict] = msg.get("feedback", [])
        user_has_feedback = any(f.get("user_id") == user_id for f in existing_feedback)

        feedback_obj: Dict[str, Any] = {
            "user_id":    user_id,
            "updated_at": now,
        }
        if clean_text is not None:
            feedback_obj["text"] = clean_text
            feedback_obj["sentiment"] = sentiment
        if rating is not None:
            feedback_obj["rating"] = rating

        if user_has_feedback:
            set_fields: Dict[str, Any] = {"updated_at": now}
            if clean_text is not None:
                set_fields["feedback.$.text"]      = clean_text
                set_fields["feedback.$.sentiment"] = sentiment
            if rating is not None:
                set_fields["feedback.$.rating"]    = rating
            await self.db.messages.update_one(
                {"_id": _oid(message_id), "feedback.user_id": user_id},
                {"$set": set_fields}
            )
        else:
            feedback_obj["created_at"] = now
            await self.db.messages.update_one(
                {"_id": _oid(message_id)},
                {
                    "$push": {"feedback": feedback_obj},
                    "$inc":  {"feedback_count": 1},
                    "$set":  {"updated_at": now},
                }
            )

        logger.info(
            f"Feedback from voter {user_id} on message {message_id}: "
            f"sentiment={sentiment}, rating={rating}"
        )
        return {
            "message_id": message_id,
            "sentiment":  sentiment,
            "text":       clean_text,
            "rating":     rating,
        }

    # ──────────────────────────────────────────
    # 10. SEARCH MESSAGES
    # ──────────────────────────────────────────

    async def search_messages(
        self,
        viewer_id: str,
        viewer_role: UserRole,
        query: str,
        chat_id: Optional[str] = None,
        limit: int = 20,
        viewer_name: str = "",
    ) -> List[dict]:
        """
        Full-text search across messages accessible to the viewer.
        Respects the same access controls and deletion filters as get_messages.
        """
        if viewer_role in (UserRole.CORPORATOR, UserRole.LEADER, UserRole.OPS):
            chat_query = {
                "is_active": True,
                "$or": [{"participants": viewer_id}, {"created_by": viewer_id}]
            }
        else:
            chat_query = {
                "is_active": True,
                "$or": [{"participants": viewer_id}, {"broadcast_to": viewer_id}]
            }

        accessible_chats = await self.db.chats.find(chat_query, {"_id": 1}).to_list(200)
        accessible_chat_ids = [str(c["_id"]) for c in accessible_chats]

        msg_filter: dict = {
            "$text":             {"$search": query},
            "is_deleted":        False,
            "deleted_for_users": {"$nin": [viewer_id]},
            "chat_id":           {"$in": accessible_chat_ids},
        }
        if chat_id:
            msg_filter["chat_id"] = chat_id

        cursor = (
            self.db.messages
            .find(msg_filter, {"score": {"$meta": "textScore"}})
            .sort([("score", {"$meta": "textScore"})])
            .limit(limit)
        )
        results = await cursor.to_list(length=limit)
        viewer_language = await self._get_user_language(viewer_id)
        viewer_language = self._normalize_language(viewer_language)

        serialized: List[dict] = []
        for m in results:
            serialized.append(
                await self._build_message_response(
                    m,
                    viewer_id,
                    viewer_name,
                    viewer_language,
                    include_feedback=False,
                )
            )
        return serialized

    # ──────────────────────────────────────────
    # 11. ANALYTICS — CORPORATOR
    # ──────────────────────────────────────────

    async def corporator_analytics(self, corporator_id: str) -> dict:
        """
        Get personalized messaging analytics for a Corporator.
        Includes message counts, engagement rates, voter engagement, sentiment distribution, and ratings.
        """
        totals_pipeline = [
            {"$match": {"sender_id": corporator_id, "is_deleted": False}},
            {"$group": {
                "_id": None,
                "total_messages":  {"$sum": 1},
                "total_broadcasts": {"$sum": {"$cond": ["$is_broadcast", 1, 0]}},
                "total_reactions":  {"$sum": "$reaction_count"},
                "total_shares":     {"$sum": "$share_count"},
            }}
        ]
        totals_result = await self.db.messages.aggregate(totals_pipeline).to_list(1)
        totals = totals_result[0] if totals_result else {
            "total_messages": 0, "total_broadcasts": 0,
            "total_reactions": 0, "total_shares": 0,
        }

        total_messages = totals.get("total_messages", 0)
        total_reactions = totals.get("total_reactions", 0)
        total_shares    = totals.get("total_shares", 0)
        engagement_rate = round(
            (total_reactions + total_shares) / total_messages, 4
        ) if total_messages else 0.0

        engagement_pipeline = [
            {"$match": {"sender_id": corporator_id, "is_deleted": False}},
            {"$facet": {
                "by_reaction": [
                    {"$unwind": "$reactions"},
                    {"$group": {"_id": "$reactions.user_id", "reaction_count": {"$sum": 1}}},
                ],
                "by_share": [
                    {"$unwind": "$share_logs"},
                    {"$group": {"_id": "$share_logs.user_id", "share_count": {"$sum": 1}}},
                ],
            }}
        ]
        engagement_raw = await self.db.messages.aggregate(engagement_pipeline).to_list(1)
        top_voters = self._merge_voter_engagement(engagement_raw)

        sentiment_pipeline = [
            {"$match": {"sender_id": corporator_id, "is_deleted": False}},
            {"$unwind": {"path": "$feedback", "preserveNullAndEmptyArrays": False}},
            {"$match": {"feedback.sentiment": {"$ne": None}}},
            {"$group": {"_id": "$feedback.sentiment", "count": {"$sum": 1}}},
        ]
        sentiments_raw = await self.db.messages.aggregate(sentiment_pipeline).to_list(None)
        sentiment_dist = {r["_id"] or "unknown": r["count"] for r in sentiments_raw}

        rating_pipeline = [
            {"$match": {"sender_id": corporator_id, "is_deleted": False}},
            {"$unwind": {"path": "$feedback", "preserveNullAndEmptyArrays": False}},
            {"$match": {"feedback.rating": {"$ne": None}}},
            {"$group": {
                "_id": None,
                "total_ratings": {"$sum": 1},
                "rating_sum":    {"$sum": "$feedback.rating"},
            }}
        ]
        rating_result = await self.db.messages.aggregate(rating_pipeline).to_list(1)
        if rating_result:
            total_ratings = rating_result[0].get("total_ratings", 0)
            rating_sum    = rating_result[0].get("rating_sum", 0)
            average_star_rating = round(rating_sum / total_ratings, 2) if total_ratings else None
        else:
            average_star_rating = None

        rating_dist_pipeline = [
            {"$match": {"sender_id": corporator_id, "is_deleted": False}},
            {"$unwind": {"path": "$feedback", "preserveNullAndEmptyArrays": False}},
            {"$match": {"feedback.rating": {"$ne": None}}},
            {"$group": {"_id": "$feedback.rating", "count": {"$sum": 1}}},
        ]
        rating_dist_raw = await self.db.messages.aggregate(rating_dist_pipeline).to_list(None)
        rating_distribution = {str(star): 0 for star in range(1, 6)}
        for r in rating_dist_raw:
            if r["_id"]:
                rating_distribution[str(r["_id"])] = r["count"]

        return {
            "total_messages_sent":    total_messages,
            "total_broadcasts":       totals.get("total_broadcasts", 0),
            "total_reactions":        total_reactions,
            "total_shares":           total_shares,
            "engagement_rate":        engagement_rate,
            "most_engaged_voters":    top_voters[:10],
            "sentiment_distribution": sentiment_dist,
            "average_star_rating":    average_star_rating,
            "rating_distribution":    rating_distribution,
        }

    # ──────────────────────────────────────────
    # 12. ANALYTICS — OPS (GLOBAL)
    # ──────────────────────────────────────────

    async def ops_analytics(self) -> dict:
        """
        Get global messaging analytics (OPS role only).
        Includes global stats, most active leaders, most shared messages, sentiment, and platform breakdown.
        """
        global_pipeline = [
            {"$match": {"is_deleted": False}},
            {"$group": {
                "_id": None,
                "total_messages":   {"$sum": 1},
                "total_broadcasts": {"$sum": {"$cond": ["$is_broadcast", 1, 0]}},
                "total_reactions":  {"$sum": "$reaction_count"},
                "total_shares":     {"$sum": "$share_count"},
                "total_feedback":   {"$sum": "$feedback_count"},
            }}
        ]
        global_raw = await self.db.messages.aggregate(global_pipeline).to_list(1)
        global_stats = global_raw[0] if global_raw else {}
        global_stats.pop("_id", None)

        leader_pipeline = [
            {
                "$lookup": {
                    "from": "users",
                    "let":  {"sid": "$sender_id"},
                    "pipeline": [
                        {"$match": {"$expr": {
                            "$eq": ["$_id", {"$convert": {"input": "$$sid", "to": "objectId",
                                                           "onError": None, "onNull": None}}]
                        }}},
                        {"$match": {"role": "leader"}},
                        {"$project": {"_id": 1, "role": 1}},
                    ],
                    "as": "leader_doc",
                }
            },
            {"$match": {"leader_doc": {"$ne": []}, "is_deleted": False}},
            {"$group": {"_id": "$sender_id", "message_count": {"$sum": 1}}},
            {"$sort": {"message_count": -1}},
            {"$limit": 10},
        ]
        most_active_leaders = await self.db.messages.aggregate(leader_pipeline).to_list(10)
        for r in most_active_leaders:
            r["leader_id"] = r.pop("_id")

        shared_pipeline = [
            {"$match": {"is_deleted": False, "share_count": {"$gt": 0}}},
            {"$sort": {"share_count": -1}},
            {"$limit": 10},
            {"$project": {
                "message_id":      {"$toString": "$_id"},
                "content_preview": {"$substrCP": ["$content", 0, 100]},
                "share_count":     1,
                "sender_id":       1,
                "is_broadcast":    1,
                "_id":             0,
            }},
        ]
        most_shared = await self.db.messages.aggregate(shared_pipeline).to_list(10)

        sentiment_pipeline = [
            {"$match": {"is_deleted": False}},
            {"$unwind": {"path": "$feedback", "preserveNullAndEmptyArrays": False}},
            {"$match": {"feedback.sentiment": {"$ne": None}}},
            {"$group": {"_id": "$feedback.sentiment", "count": {"$sum": 1}}},
        ]
        sentiments_raw = await self.db.messages.aggregate(sentiment_pipeline).to_list(None)
        sentiment_dist = {r["_id"] or "unknown": r["count"] for r in sentiments_raw}

        platform_pipeline = [
            {"$match": {"is_deleted": False}},
            {"$unwind": {"path": "$share_logs", "preserveNullAndEmptyArrays": False}},
            {"$group": {"_id": "$share_logs.platform", "count": {"$sum": 1}}},
        ]
        platform_raw = await self.db.messages.aggregate(platform_pipeline).to_list(None)
        platform_dist = {r["_id"] or "unknown": r["count"] for r in platform_raw}

        global_rating_pipeline = [
            {"$match": {"is_deleted": False}},
            {"$unwind": {"path": "$feedback", "preserveNullAndEmptyArrays": False}},
            {"$match": {"feedback.rating": {"$ne": None}}},
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "sum":   {"$sum": "$feedback.rating"},
            }}
        ]
        global_rating_raw = await self.db.messages.aggregate(global_rating_pipeline).to_list(1)
        if global_rating_raw:
            total_r = global_rating_raw[0].get("total", 0)
            sum_r   = global_rating_raw[0].get("sum", 0)
            average_star_rating = round(sum_r / total_r, 2) if total_r else None
        else:
            average_star_rating = None

        return {
            "global_stats":             global_stats,
            "most_active_leaders":      most_active_leaders,
            "most_shared_messages":     most_shared,
            "sentiment_distribution":   sentiment_dist,
            "platform_share_breakdown": platform_dist,
            "average_star_rating":      average_star_rating,
        }

    # ──────────────────────────────────────────
    # PRIVATE HELPERS
    # ──────────────────────────────────────────

    @staticmethod
    def _merge_voter_engagement(facet_raw: List[dict]) -> List[dict]:
        """
        Merge reaction and share engagement data for voters.
        Returns sorted list by total engagement score.
        """
        if not facet_raw:
            return []
        data = facet_raw[0]
        reaction_map: dict = {r["_id"]: r.get("reaction_count", 0)
                               for r in data.get("by_reaction", [])}
        share_map: dict    = {r["_id"]: r.get("share_count", 0)
                               for r in data.get("by_share", [])}
        all_voters = set(reaction_map.keys()) | set(share_map.keys())
        merged = [
            {
                "voter_id":       vid,
                "reaction_count": reaction_map.get(vid, 0),
                "share_count":    share_map.get(vid, 0),
                "total_score":    reaction_map.get(vid, 0) + share_map.get(vid, 0),
            }
            for vid in all_voters
        ]
        return sorted(merged, key=lambda x: x["total_score"], reverse=True)
