"""
FastAPI dependencies for authentication, authorization, and shared logic
"""
from .auth import get_current_tenant_id, get_current_user_id

__all__ = ["get_current_tenant_id", "get_current_user_id"]
