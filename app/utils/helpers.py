"""
Helper Utilities Module
=======================
Miscellaneous helper functions used across the application.

Author: Political Communication Platform Team
"""

from datetime import datetime, timezone
from typing import Optional, Any, Dict
from bson import ObjectId
import re


def utc_now() -> datetime:
    """
    Get current UTC datetime.
    
    Returns:
        datetime: Current UTC time
    """
    return datetime.now(timezone.utc)


def convert_objectid_to_str(obj: Any) -> Any:
    """
    Recursively convert ObjectId instances to strings in dictionaries.
    Useful for JSON serialization.
    
    Args:
        obj (Any): Object to process (dict, list, or any value)
        
    Returns:
        Any: Processed object with ObjectIds converted to strings
        
    Example:
        >>> data = {"_id": ObjectId("507f1f77bcf86cd799439011"), "name": "Test"}
        >>> convert_objectid_to_str(data)
        {'_id': '507f1f77bcf86cd799439011', 'name': 'Test'}
    """
    if isinstance(obj, dict):
        return {key: convert_objectid_to_str(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid_to_str(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    else:
        return obj


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email (str): Email address to validate
        
    Returns:
        bool: True if valid email format
        
    Example:
        >>> validate_email("user@example.com")
        True
        >>> validate_email("invalid.email")
        False
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_mobile_number(mobile: str) -> bool:
    """
    Validate Indian mobile number format.
    
    Args:
        mobile (str): Mobile number to validate
        
    Returns:
        bool: True if valid mobile format
        
    Example:
        >>> validate_mobile_number("+919876543210")
        True
        >>> validate_mobile_number("9876543210")
        True
    """
    # Remove spaces and dashes
    mobile_clean = re.sub(r'[\s-]', '', mobile)
    
    # Check Indian mobile patterns
    # With country code: +919876543210 or 919876543210
    # Without country code: 9876543210
    pattern = r'^(\+91|91)?[6-9]\d{9}$'
    
    return re.match(pattern, mobile_clean) is not None


def sanitize_string(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize string input by removing extra whitespace and optionally truncating.
    
    Args:
        text (str): Text to sanitize
        max_length (Optional[int]): Maximum length to truncate to
        
    Returns:
        str: Sanitized text
    """
    if not text:
        return ""
    
    # Remove leading/trailing whitespace and collapse multiple spaces
    sanitized = re.sub(r'\s+', ' ', text.strip())
    
    # Truncate if needed
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length].strip()
    
    return sanitized


def generate_unique_code(prefix: str = "", length: int = 8) -> str:
    """
    Generate a unique code for tracking purposes.
    
    Args:
        prefix (str): Optional prefix for the code
        length (int): Length of random part
        
    Returns:
        str: Generated unique code
        
    Example:
        >>> code = generate_unique_code("COMP", 6)
        >>> code.startswith("COMP")
        True
    """
    import random
    import string
    
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    
    if prefix:
        return f"{prefix}-{random_part}"
    return random_part


def calculate_percentage(part: float, total: float) -> float:
    """
    Calculate percentage with safe division.
    
    Args:
        part (float): Part value
        total (float): Total value
        
    Returns:
        float: Percentage (0-100)
    """
    if total == 0:
        return 0.0
    return round((part / total) * 100, 2)


def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Mask sensitive data like phone numbers, emails.
    
    Args:
        data (str): Data to mask
        visible_chars (int): Number of characters to leave visible
        
    Returns:
        str: Masked data
        
    Example:
        >>> mask_sensitive_data("9876543210", 2)
        '98******10'
    """
    if len(data) <= visible_chars * 2:
        return "*" * len(data)
    
    visible_start = visible_chars
    visible_end = visible_chars
    masked_length = len(data) - (visible_start + visible_end)
    
    return f"{data[:visible_start]}{'*' * masked_length}{data[-visible_end:]}"


def get_age_from_birthdate(birthdate: datetime) -> int:
    """
    Calculate age from birthdate.
    
    Args:
        birthdate (datetime): Date of birth
        
    Returns:
        int: Age in years
    """
    today = datetime.now()
    age = today.year - birthdate.year
    
    # Adjust if birthday hasn't occurred this year
    if (today.month, today.day) < (birthdate.month, birthdate.day):
        age -= 1
    
    return age


def dict_to_dot_notation(data: Dict, parent_key: str = '') -> Dict:
    """
    Convert nested dictionary to dot notation for MongoDB updates.
    
    Args:
        data (Dict): Nested dictionary
        parent_key (str): Parent key prefix
        
    Returns:
        Dict: Flattened dictionary with dot notation
        
    Example:
        >>> dict_to_dot_notation({"user": {"name": "John", "age": 30}})
        {'user.name': 'John', 'user.age': 30}
    """
    items = []
    for key, value in data.items():
        new_key = f"{parent_key}.{key}" if parent_key else key
        if isinstance(value, dict):
            items.extend(dict_to_dot_notation(value, new_key).items())
        else:
            items.append((new_key, value))
    return dict(items)