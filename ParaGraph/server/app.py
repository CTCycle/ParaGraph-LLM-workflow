from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from ParaGraph.server.common.constants import FASTAPI_DESCRIPTION, FASTAPI_TITLE, FASTAPI_VERSION
from ParaGraph.server.common.utils.variables import env_variables  # noqa: F401
from ParaGraph.server.routes.workflow import router as workflow_router


###############################################################################
app = FastAPI(
    title=FASTAPI_TITLE,
    version=FASTAPI_VERSION,
    description=FASTAPI_DESCRIPTION,
)

app.include_router(workflow_router)


@app.get("/")
def redirect_to_docs() -> RedirectResponse:
    return RedirectResponse(url="/docs")
