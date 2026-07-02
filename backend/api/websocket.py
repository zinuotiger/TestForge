"""WebSocket 实时推送 API"""

import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.core.pipeline import pipeline_engine

router = APIRouter()


@router.websocket("/events")
async def websocket_events(ws: WebSocket):
    """Pipeline 事件实时推送"""
    await ws.accept()

    async def callback(event: dict):
        await ws.send_json(event)

    sid = pipeline_engine.subscribe(callback)

    async def heartbeat():
        """每 15 秒发送 ping，检测连接是否存活"""
        try:
            while True:
                await asyncio.sleep(15)
                await ws.send_json({"type": "ping"})
        except Exception:
            pass

    heartbeat_task = asyncio.ensure_future(heartbeat())

    try:
        while True:
            # 保持连接，接收客户端命令
            data = await ws.receive_json()
            action = data.get("action")
            if action == "pause":
                pipeline_engine.pause()
            elif action == "resume":
                pipeline_engine.resume()
            elif action == "cancel":
                pipeline_engine.cancel()
            elif action == "skip_stage":
                pipeline_engine.skip_stage(data.get("stage_id"))
            elif action == "pong":
                pass  # 心跳响应
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        pipeline_engine.unsubscribe(sid)
