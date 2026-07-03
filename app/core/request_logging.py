import json
import time
from typing import Any, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from core.logging import get_logger

logger = get_logger("access")

SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}
SKIP_METHODS = {"OPTIONS"}
SENSITIVE_KEYS = {"token", "password", "channel_secret", "access_token", "channel_access_token"}

LOG_BODY_PATHS = {
    "/appointments/",
    "/api/slot/lock",
    "/api/slot/action",
}

CONTEXT_KEYS = (
    "line_user_id",
    "userId",
    "date",
    "time",
    "action",
    "first_name",
    "last_name",
    "category_id",
)


def _sanitize(data: Any) -> Any:
    if isinstance(data, dict):
        return {
            key: ("***" if key.lower() in SENSITIVE_KEYS else _sanitize(value))
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [_sanitize(item) for item in data]
    return data


def _build_context(path: str, query: dict, body: Optional[dict]) -> str:
    parts = []

    for key in CONTEXT_KEYS:
        if key in query:
            parts.append(f"{key}={query[key]}")

    if body and path in LOG_BODY_PATHS:
        sanitized = _sanitize(body)
        for key in CONTEXT_KEYS:
            if key in sanitized:
                parts.append(f"{key}={sanitized[key]}")

    if path == "/approve" and "action" in query:
        parts.append("token=***")

    return " ".join(parts)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in SKIP_METHODS or request.url.path in SKIP_PATHS:
            return await call_next(request)

        start = time.perf_counter()
        body_dict = None

        if request.method in {"POST", "PUT", "PATCH"}:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                raw_body = await request.body()

                if raw_body:
                    try:
                        body_dict = json.loads(raw_body)
                    except json.JSONDecodeError:
                        body_dict = None

                async def receive():
                    return {"type": "http.request", "body": raw_body, "more_body": False}

                request = Request(request.scope, receive)

        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        client = request.client.host if request.client else "-"
        context = _build_context(
            request.url.path,
            dict(request.query_params),
            body_dict,
        )

        message = (
            f"{request.method} {request.url.path} "
            f"{response.status_code} {duration_ms:.0f}ms client={client}"
        )
        if context:
            message = f"{message} | {context}"

        if response.status_code >= 500:
            logger.error(message)
        elif response.status_code >= 400:
            logger.warning(message)
        else:
            logger.info(message)

        return response
