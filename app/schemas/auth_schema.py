"""
Authentication Schema Module
============================
Pydantic schemas for authentication endpoints.
Used for request/response validation.

Author: Political Communication Platform Team
"""

from pydantic import BaseModel, Field, EmailStr, model_validator
from typing import Optional, Dict, Any
from app.utils.geo import LocationHierarchy


class LoginRequest(BaseModel):
    email: Optional[EmailStr] = Field(default=None, description="Email address")
    mobile_number: Optional[str] = Field(default=None, description="Mobile number")
    password: str = Field(..., min_length=8, description="Plain text password")

    @model_validator(mode="before")
    def check_email_or_mobile(cls, values):
        if not values.get("email") and not values.get("mobile_number"):
            raise ValueError("Either email or mobile_number must be provided")
        return values


class VoterDemographicsRequired(BaseModel):
    education: str = Field(..., min_length=1)
    occupation: str = Field(..., min_length=1)
    profession: str = Field(..., min_length=1)
    annual_income_range: str = Field(..., min_length=1)
    age_group: str = Field(..., min_length=1)
    religion: str = Field(..., min_length=1)


class VoterRegistrationRequest(BaseModel):
    """
    Voter registration with full profile data collection.
    """
    email: EmailStr
    mobile_number: str = Field(..., description="10-digit mobile number")
    password: str = Field(..., min_length=8, description="Plain text password")
    full_name: str = Field(..., min_length=3, max_length=100)
    location: LocationHierarchy
    language_preference: str = Field(default="en", description="Language preference: en, hi, mr")
    
    # Demographics (required)
    family_adults: Optional[int] = Field(default=None, ge=0)
    family_kids: Optional[int] = Field(default=None, ge=0)

    # Additional demographics dict (required)
    demographics: VoterDemographicsRequired


class LeaderRegistrationRequest(BaseModel):
    """
    Leader registration with basic profile data.
    Territory will be assigned later by administrators.
    """
    email: EmailStr
    mobile_number: str = Field(..., description="10-digit mobile number")
    password: str = Field(..., min_length=8, description="Plain text password")
    full_name: str = Field(..., min_length=3, max_length=100)
    location: LocationHierarchy
    language_preference: str = Field(default="en")
    demographics: Optional[Dict[str, Any]] = Field(default=None, description="Optional demographics including gender")


class CorporatorRegistrationRequest(BaseModel):
    """
    Corporator registration with profile data.
    Corporators are municipal representatives with oversight authority.
    """
    email: EmailStr
    mobile_number: str = Field(..., description="10-digit mobile number")
    password: str = Field(..., min_length=8, description="Plain text password")
    full_name: str = Field(..., min_length=3, max_length=100)
    location: LocationHierarchy
    language_preference: str = Field(default="en")
    demographics: Optional[Dict[str, Any]] = Field(default=None, description="Optional demographics including gender")


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., min_length=8)

    @model_validator(mode="after")
    def passwords_match(cls, values):
        if values.new_password != values.confirm_password:
            raise ValueError("New password and confirm password must match")
        return values


class PasswordResetRequest(BaseModel):
    email: Optional[EmailStr] = None
    mobile_number: Optional[str] = None

    @model_validator(mode="before")
    def check_email_or_mobile(cls, values):
        if not values.get("email") and not values.get("mobile_number"):
            raise ValueError("Either email or mobile_number must be provided")
        return values


class PasswordResetConfirm(BaseModel):
    reset_token: str
    new_password: str
    confirm_password: str

    @model_validator(mode="after")
    def passwords_match(cls, values):
        if values.new_password != values.confirm_password:
            raise ValueError("New password and confirm password must match")
        return values


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
