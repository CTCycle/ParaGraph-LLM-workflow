from __future__ import annotations

import asyncio
import queue
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from server.contracts.execution import RUN_ID_PATTERN
from server.services.runtime.events import execution_event_service
from server.services.workflow import execution_service


router = APIRouter(tags=["execution-ws"])
RUN_ID_PATTERN_RE = re.compile(RUN_ID_PATTERN)

###############################################################################
@router.websocket("/executions/ws/runs/{run_id}")
async def execution_run_events(
    websocket: WebSocket, run_id: str, replay: bool = True
) -> None:
    if not RUN_ID_PATTERN_RE.fullmatch(run_id):
        await websocket.close(code=1008, reason="Invalid run identifier")
        return
    if execution_service.get_run(run_id) is None:
        await websocket.close(code=1008, reason="Run not found")
        return
    await websocket.accept()
    subscription_queue = execution_event_service.subscribe(run_id)

    try:
        replay_high_water_mark = 0
        if replay:
            history = execution_event_service.get_history(run_id)
            replay_high_water_mark = (
                history.events[-1].sequence if history.events else 0
            )
            for event in history.events:
                if subscription_queue.overflowed:
                    await websocket.close(
                        code=1013,
                        reason="Event buffer overflowed; reconnect to replay",
                    )
                    return
                await websocket.send_json(event.model_dump(mode="json"))

            # Events published after the history snapshot are already durable
            # and may also be waiting in the live queue. Drop only events that
            # were part of the replay snapshot, preserving the live handoff.
            while True:
                if subscription_queue.overflowed:
                    await websocket.close(
                        code=1013,
                        reason="Event buffer overflowed; reconnect to replay",
                    )
                    return
                try:
                    event = subscription_queue.get_nowait()
                except queue.Empty:
                    break
                if event.sequence <= replay_high_water_mark:
                    continue
                await websocket.send_json(event.model_dump(mode="json"))

        while True:
            if (
                websocket.client_state == WebSocketState.DISCONNECTED
                or websocket.application_state == WebSocketState.DISCONNECTED
            ):
                break
            if subscription_queue.overflowed:
                await websocket.close(
                    code=1013,
                    reason="Event buffer overflowed; reconnect to replay",
                )
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
