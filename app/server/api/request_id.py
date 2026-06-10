from __future__ import annotations

from uuid import uuid4

from fastapi import Request, Response


REQUEST_ID_HEADER = "X-Request-ID"


###############################################################################
def resolve_request_id(request: Request) -> str:
    raw_value = request.headers.get(REQUEST_ID_HEADER, "")
    normalized = raw_value.strip()
    return normalized if normalized else uuid4().hex


###############################################################################
async def request_id_middleware(request: Request, call_next) -> Response:
    request_id = resolve_request_id(request)
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
