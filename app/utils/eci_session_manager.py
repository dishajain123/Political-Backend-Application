"""
ECI Session Manager
===================
100% confirmed from live DevTools capture — March 2026.

Confirmed payload for searchByEpic:
  { isPortal, epicNumber, stateCd, captchaData, captchaId, securityKey }

Confirmed generateCaptcha response fields:
  { status, statusCode, message, captcha (base64 image), captchaId }

Author: Political Communication Platform Team
"""

import uuid
import time
import logging
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)

CAPTCHA_EXPIRY_SECONDS = 120
MAX_SEARCHES_PER_MINUTE = 3

ECI_GATEWAY_BASE = "https://gateway-voters.eci.gov.in/api/v1"
ECI_CAPTCHA_URL  = f"{ECI_GATEWAY_BASE}/captcha-service/generateCaptcha"
ECI_EPIC_URL     = f"{ECI_GATEWAY_BASE}/elastic/search-by-epic-from-national-display"
ECI_DETAILS_URL  = f"{ECI_GATEWAY_BASE}/elastic/search-by-details-from-national-display"

COMMON_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,en-IN;q=0.8",
    "Origin":          "https://electoralsearch.eci.gov.in",
    "Referer":         "https://electoralsearch.eci.gov.in/",
    "applicationname": "ELECTORAL-SEARCH",
    "appname":         "ELECTORAL-SEARCH",
    "channelidobo":    "ELECTORAL-SEARCH",
    "sec-fetch-dest":  "empty",
    "sec-fetch-mode":  "cors",
    "sec-fetch-site":  "same-site",
}

# session_id -> { captcha_id, jsessionid, created_at, search_count, last_minute_start }
_sessions: Dict[str, Dict[str, Any]] = {}


def _purge_expired_sessions() -> None:
    now = time.time()
    expired = [
        sid for sid, data in _sessions.items()
        if now - data["created_at"] > CAPTCHA_EXPIRY_SECONDS
    ]
    for sid in expired:
        _sessions.pop(sid, None)


def _get_session(session_id: str) -> Optional[Dict[str, Any]]:
    _purge_expired_sessions()
    session = _sessions.get(session_id)
    if not session:
        return None
    if time.time() - session["created_at"] > CAPTCHA_EXPIRY_SECONDS:
        _sessions.pop(session_id, None)
        return None
    return session


def _check_rate_limit(session: Dict[str, Any]) -> bool:
    now = time.time()
    if now - session.get("last_minute_start", now) > 60:
        session["search_count"] = 0
        session["last_minute_start"] = now
    if session.get("search_count", 0) >= MAX_SEARCHES_PER_MINUTE:
        return False
    session["search_count"] = session.get("search_count", 0) + 1
    return True


async def create_eci_session() -> Dict[str, str]:
    """
    Fetch captcha from ECI.
    Confirmed response fields: 'captcha' = base64 image, 'captchaId' = UUID string.
    Both are required — captchaId must be sent back with search requests.
    """
    _purge_expired_sessions()
    session_id = str(uuid.uuid4())

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            response = await client.get(ECI_CAPTCHA_URL, headers=COMMON_HEADERS)
            response.raise_for_status()
            data = response.json()

            # Confirmed field name: "captcha" (base64 image string)
            captcha_image = data.get("captcha", "")

            # Confirmed field name: "captchaId" OR "id" (UUID used in search payload)
            captcha_id = data.get("captchaId") or data.get("id") or ""

            if not captcha_image:
                logger.error(f"ECI captcha response keys: {list(data.keys())}")
                raise RuntimeError(
                    f"'captcha' field missing. Got keys: {list(data.keys())}"
                )
            if not captcha_id:
                logger.error(f"ECI captcha response keys: {list(data.keys())}")
                raise RuntimeError(
                    f"'captchaId'/'id' field missing. Got keys: {list(data.keys())}"
                )

            # Extract JSESSIONID for session continuity
            jsessionid = ""
            set_cookie = response.headers.get("set-cookie", "")
            if "JSESSIONID=" in set_cookie:
                jsessionid = set_cookie.split("JSESSIONID=")[1].split(";")[0]

            logger.info(
                f"ECI captcha OK | session={session_id} | "
                f"captchaId={captcha_id[:12]}... | "
                f"jsessionid={'set' if jsessionid else 'missing'}"
            )

    except httpx.HTTPStatusError as exc:
        logger.error(f"ECI captcha HTTP {exc.response.status_code}: {exc.response.text[:200]}")
        raise RuntimeError(f"ECI portal returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        logger.error(f"ECI captcha network error: {exc}")
        raise RuntimeError("Failed to reach ECI portal") from exc

    _sessions[session_id] = {
        "captcha_id":        captcha_id,
        "jsessionid":        jsessionid,
        "created_at":        time.time(),
        "search_count":      0,
        "last_minute_start": time.time(),
    }

    return {
        "session_id":    session_id,
        "captcha_image": captcha_image,
    }


async def search_by_epic(
    session_id: str,
    epic: str,
    state: str,
    captcha: str,
) -> Dict[str, Any]:
    """
    POST voter search by EPIC.
    Confirmed payload from DevTools:
      { isPortal: true, epicNumber, stateCd, captchaData, captchaId, securityKey: "na" }
    """
    session = _get_session(session_id)
    if not session:
        raise ValueError("Session expired. Please refresh the captcha.")
    if not _check_rate_limit(session):
        raise ValueError("Rate limit reached (max 3/min). Please wait a moment.")

    headers = {**COMMON_HEADERS, "Content-Type": "application/json"}
    if session["jsessionid"]:
        headers["Cookie"] = f"JSESSIONID={session['jsessionid']}"

    # Confirmed payload field names from DevTools capture
    payload = {
        "isPortal":    True,
        "epicNumber":  epic.upper().strip(),
        "stateCd":     state.upper().strip(),
        "captchaData": captcha.strip(),
        "captchaId":   session["captcha_id"],
        "securityKey": "na",
    }

    logger.info(f"ECI EPIC search | epic={epic} | state={state} | captchaId={session['captcha_id'][:12]}...")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.post(ECI_EPIC_URL, json=payload, headers=headers)
            logger.info(f"ECI EPIC response status: {response.status_code}")
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as exc:
        logger.error(f"ECI EPIC HTTP {exc.response.status_code}: {exc.response.text[:300]}")
        raise RuntimeError(f"ECI portal returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        logger.error(f"ECI EPIC network error: {exc}")
        raise RuntimeError("ECI portal request failed") from exc


async def search_by_details(
    session_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    POST voter search by personal details.
    Injects confirmed fields: isPortal, captchaId, securityKey.
    """
    session = _get_session(session_id)
    if not session:
        raise ValueError("Session expired. Please refresh the captcha.")
    if not _check_rate_limit(session):
        raise ValueError("Rate limit reached (max 3/min). Please wait a moment.")

    headers = {**COMMON_HEADERS, "Content-Type": "application/json"}
    if session["jsessionid"]:
        headers["Cookie"] = f"JSESSIONID={session['jsessionid']}"

    payload["isPortal"]    = True
    payload["captchaId"]   = session["captcha_id"]
    payload["securityKey"] = "na"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
            response = await client.post(ECI_DETAILS_URL, json=payload, headers=headers)
            logger.info(f"ECI details response status: {response.status_code}")
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as exc:
        logger.error(f"ECI details HTTP {exc.response.status_code}: {exc.response.text[:300]}")
        raise RuntimeError(f"ECI portal returned HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        logger.error(f"ECI details network error: {exc}")
        raise RuntimeError("ECI portal request failed") from exc
