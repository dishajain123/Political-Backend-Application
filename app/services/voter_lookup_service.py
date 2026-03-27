"""
Voter Lookup Service Module
============================
Response parsing confirmed from live ECI API capture — March 2026.

Response is a JSON array. Each element has:
  { index, id, score, content: { epicNumber, applicantFirstName, ... } }

Author: Political Communication Platform Team
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.db.mongodb import get_database
from app.utils.eci_session_manager import (
    create_eci_session,
    search_by_epic,
    search_by_details,
)
from app.schemas.voter_lookup_schema import (
    VoterSearchByEpicRequest,
    VoterSearchByDetailsRequest,
    VoterSearchResult,
    VoterSaveRequest,
    VoterSaveResponse,
)

logger = logging.getLogger(__name__)


def _encrypt_epic(epic: str) -> str:
    import base64
    return base64.b64encode(epic.upper().encode()).decode()


def _parse_voter_result(raw: Any) -> Optional[VoterSearchResult]:
    """
    Parse confirmed ECI response format:
      Array of hit objects → [0].content → voter fields

    Confirmed content fields from live capture:
      epicNumber, applicantFirstName, applicantLastName, fullName,
      age, gender, asmblyName, acNumber, prlmntName,
      districtValue, stateName, stateCd,
      partNumber, partName, partSerialNumber,
      psbuildingName, buildingAddress,
      relativeFullName, relationType
    """
    if not raw:
        return None

    # ECI returns a list of hit objects
    if isinstance(raw, list):
        if not raw:
            return None
        hit = raw[0]
    elif isinstance(raw, dict):
        hit = raw
    else:
        return None

    # The actual voter data is nested under "content"
    content = hit.get("content")
    if not content:
        logger.warning(f"ECI hit has no 'content' key. Keys: {list(hit.keys())}")
        return None

    # Map gender code to readable
    gender_map = {"M": "Male", "F": "Female", "T": "Third Gender"}
    gender_raw = content.get("gender", "")
    gender = gender_map.get(gender_raw, gender_raw)

    # Map relation type to readable
    relation_map = {
        "FTHR": "Father",
        "MTHR": "Mother",
        "HUSB": "Husband",
        "WIFE": "Wife",
        "SON":  "Son",
        "DAUG": "Daughter",
    }
    relation_raw = content.get("relationType", "")
    relation = relation_map.get(relation_raw, relation_raw)

    return VoterSearchResult(
        epic_number     = content.get("epicNumber"),
        first_name      = content.get("applicantFirstName"),
        last_name       = content.get("applicantLastName"),
        full_name       = content.get("fullName", "").title() or None,
        age             = content.get("age"),
        gender          = gender,
        relative_name   = content.get("relativeFullName", "").title() or None,
        relation_type   = relation,
        state           = content.get("stateName"),
        state_code      = content.get("stateCd"),
        district        = content.get("districtValue"),
        parliament      = content.get("prlmntName"),
        constituency    = content.get("asmblyName"),
        ac_number       = content.get("acNumber"),
        part_number     = str(content.get("partNumber") or ""),
        part_name       = content.get("partName"),
        part_serial_no  = content.get("partSerialNumber"),
        polling_station = content.get("psbuildingName"),
        polling_address = content.get("buildingAddress"),
    )


class VoterLookupService:

    @staticmethod
    async def get_captcha() -> Dict[str, str]:
        return await create_eci_session()

    @staticmethod
    async def search_epic(
        request: VoterSearchByEpicRequest,
    ) -> Optional[VoterSearchResult]:
        raw = await search_by_epic(
            session_id = request.session_id,
            epic       = request.epic,
            state      = request.state,
            captcha    = request.captcha,
        )
        result = _parse_voter_result(raw)
        if result is None:
            logger.info(f"No voter found | epic={request.epic} state={request.state}")
        return result

    @staticmethod
    async def search_details(
        request: VoterSearchByDetailsRequest,
    ) -> Optional[VoterSearchResult]:
        payload: Dict[str, Any] = {
            "name":        request.name.strip(),
            "stateCd":     request.state.upper().strip(),
            "districtCd":  request.district.strip(),
            "captchaData": request.captcha.strip(),
        }
        if request.father_name:
            payload["relativeName"] = request.father_name.strip()
        if request.age is not None:
            payload["age"] = request.age
        if request.gender:
            payload["gender"] = request.gender.strip()

        raw = await search_by_details(
            session_id = request.session_id,
            payload    = payload,
        )
        result = _parse_voter_result(raw)
        if result is None:
            logger.info(f"No voter found | name={request.name} state={request.state}")
        return result

    @staticmethod
    async def save_voter_profile(request: VoterSaveRequest) -> VoterSaveResponse:
        db = get_database()

        try:
            user = await db.users.find_one({"_id": ObjectId(request.user_id)})
        except Exception:
            raise ValueError("Invalid user_id format")

        if not user:
            raise ValueError("User not found")

        doc = {
            "user_id":         request.user_id,
            "epic_encrypted":  _encrypt_epic(request.epic_encrypted),
            "epic_number":     request.epic_number,
            "full_name":       request.full_name,
            "gender":          request.gender,
            "age":             request.age,
            "relation_type":   request.relation_type,
            "relative_name":   request.relative_name,
            "parliament":      request.parliament,
            "district":        request.district,
            "constituency":    request.constituency,
            "state_code":      request.state_code,
            "polling_station": request.polling_station,
            "polling_address": request.polling_address,
            "part_number":     request.part_number,
            "part_name":       request.part_name,
            "part_serial_no":  request.part_serial_no,
            "state":           request.state,
            "last_verified":   datetime.now(timezone.utc),
            "updated_at":      datetime.now(timezone.utc),
        }

        await db.voter_lookups.update_one(
            {"user_id": request.user_id},
            {"$set": doc},
            upsert=True,
        )

        logger.info(f"Voter profile saved | user={request.user_id}")

        return VoterSaveResponse(
            success  = True,
            user_id  = request.user_id,
            message  = "Voter profile saved successfully",
        )
