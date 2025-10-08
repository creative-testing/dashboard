"""
JWT utilities for API authentication
Minimal implementation for tenant-isolated API access
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from jose import jwt, JWTError
from ..config import settings

# JWT Configuration
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
AUDIENCE = "api"


def create_access_token(
    user_id: UUID,
    tenant_id: UUID,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token for API authentication

    Args:
        user_id: User UUID
        tenant_id: Tenant UUID (critical for multi-tenant isolation)
        expires_delta: Optional custom expiration

    Returns:
        Encoded JWT string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": str(user_id),      # Subject: user ID
        "tid": str(tenant_id),     # Tenant ID (custom claim)
        "aud": AUDIENCE,           # Audience: api
        "iss": settings.JWT_ISSUER,  # Issuer
        "iat": datetime.now(timezone.utc),  # Issued at
        "exp": expire,             # Expiration
    }

    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    Verify and decode a JWT token

    Args:
        token: JWT string

    Returns:
        Decoded payload dict with 'sub' (user_id) and 'tid' (tenant_id)

    Raises:
        JWTError: If token is invalid, expired, or has wrong audience/issuer
    """
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[ALGORITHM],
        audience=AUDIENCE,
        issuer=settings.JWT_ISSUER
    )

    # Validate required claims
    if "sub" not in payload or "tid" not in payload:
        raise JWTError("Missing required claims (sub or tid)")

    return payload
