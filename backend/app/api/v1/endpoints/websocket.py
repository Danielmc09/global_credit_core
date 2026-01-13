"""WebSocket Endpoints.

Real-time communication for application updates (Requirement 3.10).
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ....core.constants import (
    WebSocketActions,
    WebSocketMessageTypes,
)
from ....core.logging import get_logger
from ....services.websocket_service import manager
from ....utils import generate_request_id

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates.

    Clients can connect to receive real-time notifications about:
    - Application status changes
    - Processing results
    - System events

    **Protocol:**
    - Client connects
    - Client can send: {"action": "subscribe", "application_id": "..."}
    - Server sends updates as JSON messages
    """
    connection_id = generate_request_id("WS")

    await manager.connect(websocket, connection_id)

    try:
        # Send welcome message
        await manager.send_personal_message(
            {
                "type": WebSocketMessageTypes.CONNECTION,
                "status": "connected",
                "message": "Connected to Global Credit Core",
                "connection_id": connection_id
            },
            connection_id
        )

        # Listen for messages
        while True:
            data = await websocket.receive_json()

            # Handle subscription requests
            if data.get("action") == WebSocketActions.SUBSCRIBE and data.get("application_id"):
                application_id = data["application_id"]
                manager.subscribe(connection_id, application_id)

                await manager.send_personal_message(
                    {
                        "type": WebSocketMessageTypes.SUBSCRIBED,
                        "application_id": application_id,
                        "message": f"Subscribed to updates for application {application_id}"
                    },
                    connection_id
                )

            # Handle ping/pong for keepalive
            elif data.get("action") == WebSocketActions.PING:
                await manager.send_personal_message(
                    {"type": WebSocketMessageTypes.PONG},
                    connection_id
                )

    except WebSocketDisconnect:
        manager.disconnect(connection_id)
        logger.info(
            "Client disconnected",
            extra={'connection_id': connection_id}
        )

    except Exception as e:
        logger.error(
            "WebSocket error",
            extra={
                'connection_id': connection_id,
                'error': str(e)
            },
            exc_info=True
        )
        manager.disconnect(connection_id)
