from __future__ import annotations

import asyncio
import queue
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from ParaGraph.server.services.runtime.events import execution_event_service


router = APIRouter(tags=["execution-ws"])
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@router.websocket("/executions/ws/runs/{run_id}")
async def execution_run_events(
    websocket: WebSocket, run_id: str, replay: bool = True
) -> None:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        await websocket.close(code=1008, reason="Invalid run identifier")
        return
    await websocket.accept()
    subscription_queue = execution_event_service.subscribe(run_id)

    try:
        if replay:
            history = execution_event_service.get_history(run_id)
            for event in history.events:
                await websocket.send_json(event.model_dump(mode="json"))

        while True:
            if (
                websocket.client_state == WebSocketState.DISCONNECTED
                or websocket.application_state == WebSocketState.DISCONNECTED
            ):
                break
            try:
                event = await asyncio.to_thread(subscription_queue.get, True, 0.25)
            except queue.Empty:
                continue
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        return
    finally:
        execution_event_service.unsubscribe(run_id, subscription_queue)
