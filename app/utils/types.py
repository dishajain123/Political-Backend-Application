"""
Custom Types Module
===================
Defines reusable Pydantic types for the application.
"""

from typing import Any, Annotated, Union
from bson import ObjectId
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class _ObjectIdPydanticAnnotation:
    """
    Pydantic V2 annotation for MongoDB ObjectId.
    Handles validation from string/bytes and serialization to string.
    """
    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        _source_type: Any,
        _handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        def validate(value: Union[str, bytes, ObjectId]) -> ObjectId:
            if isinstance(value, ObjectId):
                return value
            if isinstance(value, (str, bytes)) and ObjectId.is_valid(value):
                return ObjectId(value)
            raise ValueError("Invalid ObjectId")

        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.no_info_plain_validator_function(validate),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda instance: str(instance),
                when_used='always'
            ),
        )


# Reusable ObjectId type for Pydantic V2
PyObjectId = Annotated[ObjectId, _ObjectIdPydanticAnnotation]
