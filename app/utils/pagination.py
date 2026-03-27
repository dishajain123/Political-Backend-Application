"""
Pagination Utilities Module
===========================
Provides utilities for paginated API responses.

Author: Political Communication Platform Team
"""

from typing import Generic, TypeVar, List, Optional, Tuple
from fastapi import Query
from pydantic import BaseModel, Field
from math import ceil
from app.core.config import settings


T = TypeVar('T')


class PaginationParams(BaseModel):
    """
    Common pagination parameters for API requests.
    """
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(
        default=settings.DEFAULT_PAGE_SIZE,
        ge=1,
        le=settings.MAX_PAGE_SIZE,
        description="Items per page"
    )
    
    def get_skip(self) -> int:
        """Calculate number of documents to skip for MongoDB query"""
        return (self.page - 1) * self.page_size
    
    def get_limit(self) -> int:
        """Get limit for MongoDB query"""
        return self.page_size


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Generic paginated response wrapper.
    
    Type Parameters:
        T: Type of items in the response
    """
    items: List[T] = Field(description="List of items for current page")
    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    total_pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")
    
    class Config:
        """Pydantic configuration"""
        json_schema_extra = {
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "page_size": 20,
                "total_pages": 5,
                "has_next": True,
                "has_prev": False
            }
        }


def create_paginated_response(
    items: List[T],
    total: int,
    page: int,
    page_size: int
) -> PaginatedResponse[T]:
    """
    Create a paginated response from query results.
    
    Args:
        items (List[T]): List of items for current page
        total (int): Total number of items across all pages
        page (int): Current page number (1-indexed)
        page_size (int): Number of items per page
        
    Returns:
        PaginatedResponse[T]: Formatted paginated response
        
    Example:
        >>> items = [{"id": 1}, {"id": 2}]
        >>> response = create_paginated_response(items, total=50, page=1, page_size=20)
        >>> response.total_pages
        3
    """
    total_pages = ceil(total / page_size) if page_size > 0 else 0
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1
    )


def get_paginated_params(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(
        settings.DEFAULT_PAGE_SIZE,
        ge=1,
        le=settings.MAX_PAGE_SIZE,
        description="Items per page"
    ),
) -> Tuple[int, int]:
    """
    Extract pagination parameters and convert to skip/limit.
    """
    skip = (page - 1) * page_size
    limit = page_size
    return (skip, limit)
