from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ParaGraph.server.services.runtime.events import execution_event_service


router = APIRouter(tags=["execution-ws"])
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@router.websocket("/executions/ws/runs/{run_id}")
async def execution_run_events(websocket: WebSocket, run_id: str, replay: bool = True) -> None:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        await websocket.close(code=1008, reason="Invalid run identifier")
        return
    await websocket.accept()
    queue = execution_event_service.subscribe(run_id)

    try:
        if replay:
            history = execution_event_service.get_history(run_id)
            for event in history.events:
                await websocket.send_json(event.model_dump(mode="json"))

        while True:
            event = await asyncio.to_thread(queue.get)
            await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        return
    finally:
        execution_event_service.unsubscribe(run_id, queue)
