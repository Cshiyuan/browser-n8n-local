"""FastAPI dependencies"""

from typing import Optional
from fastapi import Header

from task.storage.base import DEFAULT_USER_ID


async def get_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    """Extract user ID from header or use default"""
    return x_user_id or DEFAULT_USER_ID
