#!/usr/bin/env python3
"""Generate JWT token for testing"""
import sys
from datetime import datetime, timedelta, timezone
try:
    import jwt as pyjwt
except ImportError:
    print("ERROR: PyJWT not installed. Run: pip install PyJWT", file=sys.stderr)
    sys.exit(1)

# From api/.env (dev key - will test if Render uses same key)
SECRET_KEY = "dev-secret-key-change-in-production-min-32-chars-long"
ALGORITHM = "HS256"

# Tenant ID PRODUCTION
tenant_id = "c0c595ab-3903-4256-b8d7-cb9709ac9206"
user_email = "production@adsalchemy.com"

# Create JWT token (expires in 7 days)
expires_at = datetime.now(timezone.utc) + timedelta(days=7)
payload = {
    "sub": tenant_id,
    "email": user_email,
    "tenant_id": tenant_id,
    "exp": int(expires_at.timestamp())
}

token = pyjwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
print(token)
