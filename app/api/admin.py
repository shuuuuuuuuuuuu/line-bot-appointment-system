"""Routes for the management application.

Add authenticated management endpoints to this router. Keeping the prefix here
prevents admin routes from being mixed with the public booking API.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/admin", tags=["admin"])
