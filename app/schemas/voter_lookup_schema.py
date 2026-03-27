"""
Voter Lookup Schema Module
==========================
Field names confirmed from live DevTools capture — March 2026.
Response is an array of hit objects, each with a 'content' nested object.

Author: Political Communication Platform Team
"""

from typing import Optional
from pydantic import BaseModel, Field


class BaseSchema(BaseModel):
    class Config:
        populate_by_name = True
        from_attributes = True
        extra = "forbid"


class CaptchaResponse(BaseSchema):
    session_id: str
    captcha_image: str  # base64, field confirmed as "captcha" in ECI response


class VoterSearchByEpicRequest(BaseSchema):
    session_id: str  = Field(..., description="Session ID from /voter/captcha")
    epic: str        = Field(..., description="EPIC number e.g. ITD7697345")
    state: str       = Field(..., description="State code e.g. S13")
    captcha: str     = Field(..., description="Text the user typed from captcha image")


class VoterSearchByDetailsRequest(BaseSchema):
    session_id:  str           = Field(..., description="Session ID from /voter/captcha")
    name:        str           = Field(..., min_length=2)
    state:       str           = Field(..., description="State code e.g. S13")
    district:    str
    captcha:     str
    father_name: Optional[str] = None
    age:         Optional[int] = Field(default=None, ge=18, le=120)
    gender:      Optional[str] = None


class VoterSearchResult(BaseSchema):
    """
    Parsed from ECI response array → [0].content
    All field names confirmed from live response.
    """
    class Config:
        populate_by_name = True
        from_attributes  = True
        extra            = "allow"

    # Identity
    epic_number:    Optional[str] = None   # epicNumber
    first_name:     Optional[str] = None   # applicantFirstName
    last_name:      Optional[str] = None   # applicantLastName
    full_name:      Optional[str] = None   # fullName
    age:            Optional[int] = None   # age
    gender:         Optional[str] = None   # gender  "M" / "F"

    # Relative
    relative_name:  Optional[str] = None   # relativeFullName
    relation_type:  Optional[str] = None   # relationType e.g. "FTHR"

    # Location
    state:          Optional[str] = None   # stateName
    state_code:     Optional[str] = None   # stateCd
    district:       Optional[str] = None   # districtValue
    parliament:     Optional[str] = None   # prlmntName
    constituency:   Optional[str] = None   # asmblyName
    ac_number:      Optional[int] = None   # acNumber

    # Polling station
    part_number:    Optional[str] = None   # partNumber
    part_name:      Optional[str] = None   # partName  (building + room)
    part_serial_no: Optional[int] = None   # partSerialNumber
    polling_station:Optional[str] = None   # psbuildingName
    polling_address:Optional[str] = None   # buildingAddress


class VoterSaveRequest(BaseSchema):
    user_id:         str            = Field(..., description="App user ID")
    epic_encrypted:  str            = Field(..., description="EPIC number to encrypt")
    epic_number:     Optional[str]  = None
    full_name:       Optional[str]  = None
    gender:          Optional[str]  = None
    age:             Optional[int]  = None
    relation_type:   Optional[str]  = None
    relative_name:   Optional[str]  = None
    parliament:      Optional[str]  = None
    district:        Optional[str]  = None
    constituency:    Optional[str]  = None
    state_code:      Optional[str]  = None
    polling_station: Optional[str]  = None
    polling_address: Optional[str]  = None
    part_number:     Optional[str]  = None
    part_name:       Optional[str]  = None
    part_serial_no:  Optional[int]  = None
    state:           Optional[str]  = None


class VoterSaveResponse(BaseSchema):
    success: bool
    user_id: str
    message: str
