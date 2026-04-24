from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse


router = APIRouter(tags=["root"])


@router.get("/", include_in_schema=False, response_model=None)
def root(request: Request) -> Response:
    if bool(getattr(request.app.state, "cloud_mode", False)):
        return JSONResponse({"status": "ok"})
    return RedirectResponse(url="/docs")
