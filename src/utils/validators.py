"""Shared validation helpers."""
import re
from fastapi import HTTPException

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def validate_uuid(value: str, field_name: str = "id") -> str:
    """Validate that a string is a valid UUID v4 format."""
    if not UUID_PATTERN.match(value):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name} format")
    return value


def get_pagination_params(
    page: int = 1,
    limit: int = 20,
    max_limit: int = 100,
) -> tuple[int, int]:
    """Validate and return (offset, limit) for pagination."""
    if page < 1:
        page = 1
    if limit < 1:
        limit = 1
    if limit > max_limit:
        limit = max_limit
    offset = (page - 1) * limit
    return offset, limit
