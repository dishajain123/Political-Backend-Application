from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class HelpNumberCreate(BaseModel):
    service_name: str = Field(..., min_length=2, max_length=200)
    phone_number: str = Field(..., min_length=1, max_length=100)
    category: str = Field(default="Emergency")

    class Config:
        json_schema_extra = {
            "example": {
                "service_name": "Police",
                "phone_number": "100",
                "category": "Emergency",
            }
        }


class HelpNumberUpdate(BaseModel):
    service_name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    phone_number: Optional[str] = Field(default=None, min_length=1, max_length=100)
    category: Optional[str] = None
    is_active: Optional[bool] = None

    class Config:
        json_schema_extra = {
            "example": {
                "phone_number": "100",
                "is_active": True,
            }
        }


class HelpNumberResponse(BaseModel):
    id: str = Field(..., alias="_id")
    service_name: str
    phone_number: str
    category: str
    created_by: Optional[str] = None
    created_at: str
    updated_at: str
    is_active: bool
    is_system: bool = False

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "service_name": "Police",
                "phone_number": "100",
                "category": "Emergency",
                "is_active": True,
                "is_system": True,
            }
        }


class HelpNumberListResponse(BaseModel):
    total: int
    items: List[HelpNumberResponse]
