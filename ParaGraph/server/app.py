from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse

from ParaGraph.server.common.constants import FASTAPI_DESCRIPTION, FASTAPI_TITLE, FASTAPI_VERSION
from ParaGraph.server.common.security import is_cloud_deployment
from ParaGraph.server.common.utils.variables import env_variables  # noqa: F401
from ParaGraph.server.api.configurations import router as configurations_router
from ParaGraph.server.api.executions import router as executions_router
from ParaGraph.server.api.nodes import router as nodes_router
from ParaGraph.server.api.providers import router as providers_router
from ParaGraph.server.api.workflows import router as workflows_router
from ParaGraph.server.api.ws import router as ws_router


cloud_mode = is_cloud_deployment()

app = FastAPI(
    title=FASTAPI_TITLE,
    version=FASTAPI_VERSION,
    description=FASTAPI_DESCRIPTION,
    docs_url=None if cloud_mode else "/docs",
    redoc_url=None if cloud_mode else "/redoc",
    openapi_url=None if cloud_mode else "/openapi.json",
)

app.include_router(workflows_router)
app.include_router(executions_router)
app.include_router(nodes_router)
app.include_router(providers_router)
app.include_router(configurations_router)
app.include_router(ws_router)


@app.get("/")
def redirect_to_docs():
    if cloud_mode:
        return JSONResponse({"status": "ok"})
    return RedirectResponse(url="/docs")
