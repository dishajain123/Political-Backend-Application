"""
Geographic/Location Utilities Module
====================================
Handles location hierarchy and geographic data structures.

Author: Political Communication Platform Team
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class LocationHierarchy(BaseModel):
    """
    Represents geographic hierarchy for users and data.
    Used for targeted communication and analytics.
    """
    state: Optional[str] = None
    city: Optional[str] = None
    ward: Optional[str] = None
    area: Optional[str] = None
    building: Optional[str] = None
    booth_number: Optional[str] = None
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "state": "Maharashtra",
                "city": "Mumbai",
                "ward": "Ward-A",
                "area": "Andheri East",
                "building": "Sapphire Heights",
                "booth_number": "123"
            }
        }
    )


def build_location_filter(location: LocationHierarchy) -> Dict:
    """
    Build MongoDB query filter from location hierarchy.
    Only includes non-null location fields.
    
    Args:
        location (LocationHierarchy): Location object
        
    Returns:
        Dict: MongoDB filter dictionary
        
    Example:
        >>> loc = LocationHierarchy(state="Maharashtra", city="Mumbai")
        >>> build_location_filter(loc)
        {'location.state': 'Maharashtra', 'location.city': 'Mumbai'}
    """
    filter_dict = {}
    
    if location.state:
        filter_dict["location.state"] = location.state
    if location.city:
        filter_dict["location.city"] = location.city
    if location.ward:
        filter_dict["location.ward"] = location.ward
    if location.area:
        filter_dict["location.area"] = location.area
    if location.building:
        filter_dict["location.building"] = location.building
    if location.booth_number:
        filter_dict["location.booth_number"] = location.booth_number
    
    return filter_dict


def get_location_hierarchy_levels() -> List[str]:
    """
    Get ordered list of location hierarchy levels.
    
    Returns:
        List[str]: Ordered location levels from broad to specific
    """
    return ["state", "city", "ward", "area", "building", "booth_number"]


def validate_location_hierarchy(location: LocationHierarchy) -> bool:
    """
    Validate that location hierarchy is logical.
    Cannot have specific location without broader location.
    
    Args:
        location (LocationHierarchy): Location to validate
        
    Returns:
        bool: True if hierarchy is valid
        
    Example:
        >>> loc = LocationHierarchy(area="Andheri") # Invalid: area without city
        >>> validate_location_hierarchy(loc)
        False
    """
    # State is the broadest level, always valid if present
    if location.state is None:
        return True
    
    # If city is set, state must be set
    if location.city and not location.state:
        return False
    
    # If ward is set, city must be set
    if location.ward and not location.city:
        return False
    
    # If area is set, ward must be set
    if location.area and not location.ward:
        return False
    
    # If building is set, area must be set
    if location.building and not location.area:
        return False
    
    # If booth is set, area must be set
    if location.booth_number and not location.area:
        return False
    
    return True


def get_location_display_name(location: LocationHierarchy) -> str:
    """
    Generate human-readable location string.
    
    Args:
        location (LocationHierarchy): Location object
        
    Returns:
        str: Formatted location string
        
    Example:
        >>> loc = LocationHierarchy(state="Maharashtra", city="Mumbai", area="Andheri")
        >>> get_location_display_name(loc)
        'Andheri, Mumbai, Maharashtra'
    """
    parts = []
    
    if location.building:
        parts.append(location.building)
    if location.area:
        parts.append(location.area)
    if location.ward:
        parts.append(location.ward)
    if location.city:
        parts.append(location.city)
    if location.state:
        parts.append(location.state)
    
    return ", ".join(parts) if parts else "Location not specified"