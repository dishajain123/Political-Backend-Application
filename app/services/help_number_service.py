from datetime import datetime
from typing import List, Optional
from bson import ObjectId
from app.db.mongodb import get_database
from app.schemas.help_number_schema import HelpNumberCreate, HelpNumberUpdate, HelpNumberResponse
from app.core.roles import UserRole
import logging

logger = logging.getLogger(__name__)

INITIAL_HELP_NUMBERS = [
    {"service_name": "Police", "phone_number": "100", "category": "Emergency"},
    {"service_name": "Fire Brigade", "phone_number": "101", "category": "Emergency"},
    {"service_name": "Ambulance", "phone_number": "102", "category": "Emergency"},
    {"service_name": "Electricity Helpline", "phone_number": "1912", "category": "Utilities"},
    {"service_name": "Water Supply Helpline", "phone_number": "1910", "category": "Utilities"},
    {"service_name": "Municipal Corporation", "phone_number": "1916", "category": "Government"},
    {"service_name": "Women Helpline", "phone_number": "1091", "category": "Support"},
    {"service_name": "Child Helpline", "phone_number": "1098", "category": "Support"},
]

ALLOWED_CATEGORIES = {
    "Emergency",
    "Government",
    "Safety",
    "Utilities",
    "Support",
    "Operations",
}


class HelpNumberService:

    def __init__(self):
        self.db = get_database()
        self.collection = self.db.help_numbers

    async def seed_initial_data(self):
        count = await self.collection.count_documents({})
        if count == 0:
            now = datetime.utcnow()
            docs = [
                {
                    **entry,
                    "created_by": "system",
                    "created_at": now,
                    "updated_at": now,
                    "is_active": True,
                    "is_system": True,
                }
                for entry in INITIAL_HELP_NUMBERS
            ]
            await self.collection.insert_many(docs)
            logger.info("Help numbers seeded successfully.")

    async def get_all_help_numbers(self, include_inactive: bool = False) -> List[HelpNumberResponse]:
        query = {} if include_inactive else {"is_active": True}
        cursor = self.collection.find(query).sort("category", 1)
        items = []
        async for doc in cursor:
            items.append(HelpNumberResponse(**self._normalize(doc)))
        return items

    async def create_help_number(self, payload: HelpNumberCreate, current_user) -> HelpNumberResponse:
        if current_user.role != UserRole.CORPORATOR:
            raise PermissionError("Only Corporator can create help numbers")
        now = datetime.utcnow()
        category = self._normalize_category(payload.category)
        doc = {
            "service_name": payload.service_name,
            "phone_number": self._clean_phone(payload.phone_number),
            "category": category,
            "created_by": current_user.user_id,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
            "is_system": False,
        }
        result = await self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        return HelpNumberResponse(**self._normalize(doc))

    async def update_help_number(self, help_number_id: str, payload: HelpNumberUpdate, current_user) -> HelpNumberResponse:
        if current_user.role != UserRole.CORPORATOR:
            raise PermissionError("Only Corporator can update help numbers")
        doc = await self._get_by_id(help_number_id)
        if doc.get("is_system") or doc.get("created_by") == "system" or doc.get("service_name") in {e["service_name"] for e in INITIAL_HELP_NUMBERS}:
            raise PermissionError("System help numbers cannot be edited")
        updates = {k: v for k, v in payload.dict().items() if v is not None}
        if "phone_number" in updates:
            updates["phone_number"] = self._clean_phone(updates["phone_number"])
        if "category" in updates:
            updates["category"] = self._normalize_category(updates["category"])
        updates["updated_at"] = datetime.utcnow()
        await self.collection.update_one({"_id": doc["_id"]}, {"$set": updates})
        updated = await self._get_by_id(help_number_id)
        return HelpNumberResponse(**self._normalize(updated))

    async def delete_help_number(self, help_number_id: str, current_user) -> bool:
        if current_user.role != UserRole.CORPORATOR:
            raise PermissionError("Only Corporator can delete help numbers")
        doc = await self._get_by_id(help_number_id)
        if doc.get("is_system") or doc.get("created_by") == "system" or doc.get("service_name") in {e["service_name"] for e in INITIAL_HELP_NUMBERS}:
            raise PermissionError("System help numbers cannot be deleted")
        result = await self.collection.update_one(
            {"_id": doc["_id"]},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
        )
        return result.modified_count > 0

    async def _get_by_id(self, help_number_id: str) -> dict:
        if not ObjectId.is_valid(help_number_id):
            raise ValueError("Invalid ID")
        doc = await self.collection.find_one({"_id": ObjectId(help_number_id)})
        if not doc:
            raise ValueError("Help number not found")
        return doc

    @staticmethod
    def _normalize(doc: dict) -> dict:
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        for field in ("created_at", "updated_at"):
            val = doc.get(field)
            if isinstance(val, datetime):
                doc[field] = val.isoformat()
        if "is_system" not in doc:
            doc["is_system"] = (
                doc.get("created_by") == "system"
                or doc.get("service_name") in {e["service_name"] for e in INITIAL_HELP_NUMBERS}
            )
        return doc

    @staticmethod
    def _normalize_category(value: Optional[str]) -> str:
        if not value:
            return "Emergency"
        normalized = value.strip().lower()
        mapping = {
            "emergency": "Emergency",
            "government": "Government",
            "safety": "Safety",
            "utilities": "Utilities",
            "support": "Support",
            "operations": "Operations",
        }
        if normalized in mapping:
            return mapping[normalized]
        # Allow custom categories by returning a title-cased label.
        return " ".join(
            part[:1].upper() + part[1:].lower()
            for part in value.strip().split()
            if part
        )

    @staticmethod
    def _clean_phone(value: str) -> str:
        if not value:
            return value
        cleaned = []
        for ch in value.strip():
            if ch == "+" and not cleaned:
                cleaned.append(ch)
            elif ch.isdigit():
                cleaned.append(ch)
        return "".join(cleaned)
