"""
CSRF Protection Middleware for Cookie-Based Authentication

Protects against CSRF attacks when authentication uses HttpOnly cookies.
Does NOT affect Bearer token authentication (which is inherently CSRF-safe).

Strategy:
- Allow GET/HEAD/OPTIONS (safe methods)
- For POST/PUT/DELETE/PATCH:
  - If Authorization: Bearer header present → ALLOW (CSRF-safe)
  - If only cookie auth → Check Origin/Referer matches DASHBOARD_URL → ALLOW
  - Otherwise → BLOCK (403 CSRF protection)

This is a minimal, non-over-engineered approach that:
1. Doesn't break API clients using Bearer tokens
2. Protects browser-based dashboard from CSRF
3. Requires no changes to frontend (Origin header is automatic)
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from urllib.parse import urlparse
from ..config import settings


class CSRFFromCookieGuard(BaseHTTPMiddleware):
    """
    Minimal CSRF protection for cookie-based authentication

    Only blocks cross-origin requests that:
    1. Use state-changing methods (POST/PUT/DELETE/PATCH)
    2. Are authenticated via cookie (not Bearer token)
    3. Come from an Origin different from DASHBOARD_URL
    """

    # Safe methods that don't need CSRF protection
    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

    # Paths excluded from CSRF check (DEBUG endpoints, webhooks)
    CSRF_EXEMPT_PATHS = (
        "/auth/facebook/dev-login",
        "/billing/webhook",  # Stripe webhooks (verified via signature)
        "/facebook/data-deletion",  # Meta data deletion callback
    )

    async def dispatch(self, request, call_next):
        # Skip CSRF check for exempt paths (DEBUG endpoints)
        if request.url.path in self.CSRF_EXEMPT_PATHS:
            return await call_next(request)

        # Skip CSRF check for safe methods
        if request.method in self.SAFE_METHODS:
            return await call_next(request)

        # Check if request uses Bearer token (CSRF-safe by design)
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            # Bearer token auth → CSRF-safe, allow
            return await call_next(request)

        # Cookie-based auth → check Origin
        origin = request.headers.get("origin") or request.headers.get("referer", "")

        # Parse netloc (domain:port) from Origin and DASHBOARD_URL
        origin_netloc = urlparse(origin).netloc if origin else ""
        expected_netloc = urlparse(settings.DASHBOARD_URL).netloc

        if origin_netloc != expected_netloc:
            # Cross-origin cookie-based request → BLOCK
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "CSRF protection: cross-origin requests must use Bearer token authentication"
                }
            )

        # Same-origin cookie-based request → ALLOW
        return await call_next(request)
