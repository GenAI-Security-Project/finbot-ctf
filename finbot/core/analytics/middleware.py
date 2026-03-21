"""Analytics middleware — records page views for server-side analytics"""

import logging
import time
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from finbot.core.data.database import SessionLocal

from .models import PageView
from .ua_parser import parse_user_agent

logger = logging.getLogger(__name__)

SKIP_PREFIXES = (
    "/static",
    "/ws",
    "/api/session",
    "/favicon.ico",
    "/cc",
)

SKIP_EXTENSIONS = (".js", ".css", ".png", ".jpg", ".ico", ".svg", ".woff", ".woff2")


class AnalyticsMiddleware(BaseHTTPMiddleware):
    """Records non-static HTTP requests into the page_views table"""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if self._should_skip(path):
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        try:
            self._record(request, response, elapsed_ms)
        except Exception:  # pylint: disable=broad-exception-caught
            logger.debug("Analytics recording failed for %s", path, exc_info=True)

        return response

    def _should_skip(self, path: str) -> bool:
        if any(path.startswith(p) for p in SKIP_PREFIXES):
            return True
        if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
            return True
        return False

    def _record(self, request: Request, response: Response, elapsed_ms: int) -> None:
        session_ctx = getattr(request.state, "session_context", None)
        session_id = session_ctx.session_id if session_ctx else None
        session_type = None
        if session_ctx:
            session_type = "temp" if session_ctx.is_temporary else "perm"

        ua_string = request.headers.get("user-agent", "")
        ua = parse_user_agent(ua_string)

        referer = request.headers.get("referer")
        referer_domain = None
        if referer:
            try:
                referer_domain = urlparse(referer).netloc
            except Exception:  # pylint: disable=broad-exception-caught
                pass

        db = SessionLocal()
        try:
            pv = PageView(
                path=request.url.path[:500],
                method=request.method,
                status_code=response.status_code,
                response_time_ms=elapsed_ms,
                session_id=session_id[:64] if session_id else None,
                session_type=session_type,
                user_agent=ua_string[:500] if ua_string else None,
                browser=ua["browser"],
                os=ua["os"],
                device_type=ua["device_type"],
                referer=referer[:500] if referer else None,
                referer_domain=referer_domain[:255] if referer_domain else None,
            )
            db.add(pv)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
