from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

BACKEND_DOCUMENT_PATHS = frozenset(
    {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}
)

###############################################################################
def normalize_api_base(value: str | None) -> str:
    candidate = (value or "").strip()
    if not candidate:
        return ""
    return "/" + candidate.strip("/")

###############################################################################
def create_client_app(client_root: Path) -> Starlette:
    root = client_root.resolve()
    index_file = root / "index.html"

    async def serve_client_path(request) -> FileResponse:
        requested = (root / request.path_params["full_path"]).resolve()
        if requested.is_relative_to(root) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(index_file)

    routes: list[Route | Mount] = []
    if (root / "assets").is_dir():
        routes.append(Mount("/assets", StaticFiles(directory=str(root / "assets"))))
    routes.append(Route("/{full_path:path}", serve_client_path))
    return Starlette(routes=routes)

###############################################################################
class ClientHostingMiddleware:
    """Serve the built SPA and the API from one origin.

    Requests under the API base path reach the backend with the prefix removed.
    Built files and browser navigations elsewhere receive the SPA so client routes survive a
    reload even when they share a name with an API route.
    """

    def __init__(self, app: ASGIApp, *, api_base: str, client_root: Path) -> None:
        self.app = app
        self.api_base = normalize_api_base(api_base)
        self.client_root = client_root.resolve()
        self.client_app = create_client_app(client_root)

    def _strip_api_base(self, path: str) -> str | None:
        if not self.api_base:
            return None
        if path == self.api_base:
            return "/"
        if path.startswith(self.api_base + "/"):
            return path[len(self.api_base) :]
        return None

    def _is_client_request(self, scope: Scope) -> bool:
        path = scope["path"]
        if scope["method"] not in ("GET", "HEAD") or path in BACKEND_DOCUMENT_PATHS:
            return False
        if path.startswith("/assets/"):
            return True
        relative = path.lstrip("/")
        if relative:
            candidate = (self.client_root / relative).resolve()
            if candidate.is_relative_to(self.client_root) and candidate.is_file():
                return True
        accept = dict(scope["headers"]).get(b"accept", b"")
        return b"text/html" in accept

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        stripped = self._strip_api_base(scope["path"])
        if stripped is not None:
            scope = dict(scope)
            scope["path"] = stripped
            if "raw_path" in scope:
                scope["raw_path"] = stripped.encode()
            await self.app(scope, receive, send)
            return

        if scope["type"] == "http" and self._is_client_request(scope):
            await self.client_app(scope, receive, send)
            return

        await self.app(scope, receive, send)
