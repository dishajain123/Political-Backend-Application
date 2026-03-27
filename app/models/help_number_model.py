from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class HelpNumberModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    service_name: str = Field(..., min_length=2, max_length=200)
    phone_number: str = Field(..., min_length=1, max_length=100)
    category: str = Field(default="Emergency")
    created_by: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    is_system: bool = Field(default=False)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        json_schema_extra = {
            "example": {
                "service_name": "Police",
                "phone_number": "100",
                "category": "Emergency",
                "is_active": True,
            }
        }
