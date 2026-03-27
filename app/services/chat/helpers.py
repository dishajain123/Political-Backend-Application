"""
Chat Service Helpers
====================
Shared constants and helper utilities for chat services.

Author: Political Communication Platform Team
"""

import logging
import os
import re
import uuid
import shutil
import subprocess
import tempfile
from typing import Optional, List, Dict, Any, Tuple
from bson import ObjectId
from html.parser import HTMLParser
import httpx

from app.core.roles import UserRole
from app.models.chat_model import MessageStatus, MessageSentiment

logger = logging.getLogger("app.services.chat_service")

_UPLOAD_DIR = "/uploads/chat"
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

_ALLOWED_EXTENSIONS: Dict[str, str] = {
    "jpg":  "image",
    "jpeg": "image",
    "png":  "image",
    "mp4":  "video",
    "mov":  "video",
    "pdf":  "document",
    "doc":  "document",
    "docx": "document",
}

_PREVIEW_PREFIX = "preview_"

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

_DELETED_GLOBALLY_PLACEHOLDER = "This message was deleted"
_URL_REGEX = re.compile(r"(https?://[^\s]+)", re.IGNORECASE)


def _oid(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise ValueError(f"Invalid ObjectId: {value}")
    return ObjectId(value)


def _normalize_id_set(values: list) -> set[str]:
    return {str(v) for v in values if v is not None}


def _candidate_user_ids(user_id: str) -> list:
    candidates: list = [user_id]
    if ObjectId.is_valid(user_id):
        candidates.append(ObjectId(user_id))
    return candidates


def _str_id(doc: dict) -> str:
    return str(doc["_id"])


def _render_template(content: str, full_name: str) -> str:
    first_name = (full_name or "").split()[0] if full_name else "there"
    return re.sub(r"\{\{\s*name\s*\}\}", first_name, content)


def _classify_sentiment(text: str) -> MessageSentiment:
    text_lower = text.lower()
    positive_words = {"great", "good", "excellent", "helpful", "thanks", "love", "amazing", "happy"}
    negative_words = {"bad", "terrible", "poor", "useless", "hate", "awful", "disappointed", "worst"}
    pos = sum(1 for w in positive_words if w in text_lower)
    neg = sum(1 for w in negative_words if w in text_lower)
    if pos > 0 and neg > 0:
        return MessageSentiment.MIXED
    if pos > neg:
        return MessageSentiment.POSITIVE
    if neg > pos:
        return MessageSentiment.NEGATIVE
    return MessageSentiment.NEUTRAL


class _LinkMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.title: Optional[str] = None
        self.description: Optional[str] = None
        self.image: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs or [])
        if tag == "title":
            self.in_title = True
            return
        if tag == "meta":
            name = (attrs_dict.get("name") or "").lower()
            prop = (attrs_dict.get("property") or "").lower()
            content = attrs_dict.get("content")
            if not content:
                return
            if prop == "og:title" and not self.title:
                self.title = content.strip()
            elif prop == "og:description" and not self.description:
                self.description = content.strip()
            elif prop == "og:image" and not self.image:
                self.image = content.strip()
            elif name == "description" and not self.description:
                self.description = content.strip()

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title and not self.title:
            text = (data or "").strip()
            if text:
                self.title = text


def _extract_first_url(text: str) -> Optional[str]:
    if not text:
        return None
    match = _URL_REGEX.search(text)
    if not match:
        return None
    return match.group(1).rstrip(").,]")


async def _fetch_link_metadata(url: str) -> Dict[str, Optional[str]]:
    """
    Best-effort link preview metadata.
    Returns title/description/image when available; always returns url.
    """
    meta = {"url": url, "title": None, "description": None, "image": None}
    try:
        async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code >= 400:
                return meta
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type:
                return meta
            parser = _LinkMetaParser()
            parser.feed(resp.text)
            meta["title"] = parser.title
            meta["description"] = parser.description
            meta["image"] = parser.image
            return meta
    except Exception as exc:
        logger.info(f"Link preview fetch failed: {exc}")
        return meta


def _generate_pdf_preview(pdf_path: str) -> Optional[str]:
    """
    Best-effort first-page preview for PDF files.
    Returns a public URL to the preview image or None if unavailable.
    """
    try:
        import fitz  # PyMuPDF
    except Exception as exc:
        logger.info(f"PDF preview generation skipped (PyMuPDF not available): {exc}")
        return None

    doc = None
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count < 1:
            return None
        page = doc.load_page(0)
        # Render at higher resolution for clarity
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        preview_name = f"{_PREVIEW_PREFIX}{uuid.uuid4().hex}.png"
        preview_path = os.path.join(_UPLOAD_DIR, preview_name)
        pix.save(preview_path)
        return f"/api/v1/chat/files/{preview_name}"
    except Exception as exc:
        logger.warning(f"PDF preview generation failed: {exc}")
        return None
    finally:
        try:
            if doc is not None:
                doc.close()
        except Exception:
            pass


def _find_soffice_executable() -> Optional[str]:
    env_path = os.environ.get("LIBREOFFICE_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    for cmd in ("soffice", "libreoffice"):
        path = shutil.which(cmd)
        if path:
            return path
    # Common Windows paths
    win_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for path in win_paths:
        if os.path.isfile(path):
            return path
    return None


def _generate_office_preview(doc_path: str) -> Optional[str]:
    """
    Convert DOC/DOCX to PDF using LibreOffice and generate a first-page preview.
    Returns preview URL or None.
    """
    soffice = _find_soffice_executable()
    if not soffice:
        logger.info("LibreOffice not found; DOC/DOCX preview skipped")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            cmd = [
                soffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                tmpdir,
                doc_path,
            ]
            subprocess.run(cmd, check=True, timeout=30)
            base = os.path.splitext(os.path.basename(doc_path))[0]
            pdf_path = os.path.join(tmpdir, f"{base}.pdf")
            if not os.path.isfile(pdf_path):
                # LibreOffice sometimes changes casing; fallback to any pdf in tmpdir
                for name in os.listdir(tmpdir):
                    if name.lower().endswith(".pdf"):
                        pdf_path = os.path.join(tmpdir, name)
                        break
            if os.path.isfile(pdf_path):
                return _generate_pdf_preview(pdf_path)
            return None
        except Exception as exc:
            logger.warning(f"DOC/DOCX preview generation failed: {exc}")
            return None


def _save_file(file_bytes: bytes, original_filename: str) -> Tuple[str, str, str, int, Optional[str]]:
    """
    Validate and persist an uploaded file.

    Returns:
        (file_url, file_type, file_name, file_size, preview_url)

    Raises:
        ValueError: on invalid extension or size limit exceeded.
    """
    if not original_filename or "." not in original_filename:
        raise ValueError("Invalid filename: no extension found")

    ext = original_filename.rsplit(".", 1)[-1].lower()
    if ext not in _ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(_ALLOWED_EXTENSIONS.keys()))
        raise ValueError(
            f"File type '.{ext}' is not allowed. "
            f"Allowed types: {allowed}"
        )

    if len(file_bytes) > _MAX_FILE_SIZE:
        raise ValueError(
            f"File size {len(file_bytes) // (1024 * 1024):.1f} MB "
            f"exceeds the 10 MB limit"
        )

    os.makedirs(_UPLOAD_DIR, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(_UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as fh:
        fh.write(file_bytes)

    file_type = _ALLOWED_EXTENSIONS[ext]
    file_size = len(file_bytes)
    # URL served by GET /api/v1/chat/files/{filename}
    file_url = f"/api/v1/chat/files/{unique_name}"

    preview_url: Optional[str] = None
    if file_type == "document":
        if ext == "pdf":
            preview_url = _generate_pdf_preview(file_path)
        elif ext in ("doc", "docx"):
            preview_url = _generate_office_preview(file_path)

    logger.info(
        f"File saved: {unique_name} ({file_type}, "
        f"{file_size // 1024} KB)"
    )
    return file_url, file_type, original_filename, file_size, preview_url


def _serialize_message(
    doc: dict,
    viewer_id: str,
    viewer_name: str,
    include_feedback: bool = False,
    display_text: Optional[str] = None,
    original_text: Optional[str] = None,
    source_language: Optional[str] = None,
    display_language: Optional[str] = None,
    is_translated: Optional[bool] = None,
) -> dict:
    """
    Convert raw MongoDB message document to API response dict.

    Deletion priority:
      1. is_deleted_globally → replace content with placeholder, set flag
      2. template_flag       → render {{name}} normally

    Media fields (file_url, file_type, file_name, file_uploaded_at) are
    included when present on the document.
    """
    is_deleted_globally = doc.get("is_deleted_globally", False)

    if display_text is not None:
        content = display_text
    else:
        if is_deleted_globally:
            content = _DELETED_GLOBALLY_PLACEHOLDER
        else:
            content = doc.get("content", "")
            if doc.get("template_flag"):
                content = _render_template(content, viewer_name)

    resolved_original = original_text
    if resolved_original is None:
        resolved_original = doc.get("original_text")
    if resolved_original is None:
        resolved_original = doc.get("content", "")

    resolved_source = source_language or doc.get("source_language")
    resolved_display_lang = display_language or resolved_source
    resolved_display_text = display_text if display_text is not None else content
    resolved_is_translated = is_translated if is_translated is not None else False

    result = {
        "message_id":          str(doc["_id"]),
        "chat_id":             doc.get("chat_id", ""),
        "sender_id":           doc.get("sender_id", ""),
        "content":             content,
        "original_text":       resolved_original,
        "display_text":        resolved_display_text,
        "source_language":     resolved_source,
        "display_language":    resolved_display_lang,
        "is_translated":       resolved_is_translated,
        "template_flag":       doc.get("template_flag", False),
        "is_broadcast":        doc.get("is_broadcast", False),
        "status":              doc.get("status", MessageStatus.SENT),
        "is_deleted":          doc.get("is_deleted", False),
        "is_deleted_globally": is_deleted_globally,
        # ── Media fields ──────────────────────────
        "file_url":            doc.get("file_url"),
        "file_type":           doc.get("file_type"),
        "file_name":           doc.get("file_name"),
        "file_uploaded_at":    doc.get("file_uploaded_at"),
        "file_size":           doc.get("file_size"),
        "preview_url":         doc.get("preview_url"),
        "link_url":            doc.get("link_url"),
        "link_title":          doc.get("link_title"),
        "link_description":    doc.get("link_description"),
        "link_image":          doc.get("link_image"),
        # ─────────────────────────────────────────
        "reaction_count":      doc.get("reaction_count", 0),
        "share_count":         doc.get("share_count", 0),
        "feedback_count":      doc.get("feedback_count", 0),
        "reactions":           doc.get("reactions", []),
        "created_at":          doc.get("created_at"),
        "updated_at":          doc.get("updated_at"),
    }
    if include_feedback:
        result["feedback"] = doc.get("feedback", [])
    return result


# ─────────────────────────────────────────────
# ALLOWED COMMUNICATION MATRIX
# ─────────────────────────────────────────────

ALLOWED_DIRECT_COMMS: Dict[UserRole, set] = {
    UserRole.CORPORATOR: {UserRole.LEADER},
    UserRole.LEADER:     {UserRole.VOTER, UserRole.CORPORATOR},
    UserRole.VOTER:      {UserRole.LEADER, UserRole.CORPORATOR},
    UserRole.OPS:        set(),
}

BROADCAST_ROLES = {UserRole.CORPORATOR, UserRole.LEADER}


# ─────────────────────────────────────────────
# CHAT SERVICE
# ─────────────────────────────────────────────
