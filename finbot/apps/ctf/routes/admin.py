"""Admin API Routes
TODO:
- Protect these routes
- Take care of CSRF protection (Super Admin portal should take care of this)
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["admin"])
