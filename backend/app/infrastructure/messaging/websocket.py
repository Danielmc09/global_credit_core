from fastapi import WebSocket

from ...core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections with clients."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.subscriptions: dict[str, set[str]] = {}


    async def connect(self, websocket: WebSocket, connection_id: str):
        """Accept and register a new WebSocket connection.

        Args:
            websocket: WebSocket connection
            connection_id: Unique connection identifier
        """
        await websocket.accept()
        self.active_connections[connection_id] = websocket

        logger.debug(
            "WebSocket connected",
            extra={
                'connection_id': connection_id,
                'total_connections': len(self.active_connections)
            }
        )


    def disconnect(self, connection_id: str):
        """Remove a WebSocket connection.

        Args:
            connection_id: Connection identifier
        """
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

            # Clean up subscriptions
            for app_id in list(self.subscriptions.keys()):
                if connection_id in self.subscriptions[app_id]:
                    self.subscriptions[app_id].remove(connection_id)
                    if not self.subscriptions[app_id]:
                        del self.subscriptions[app_id]

            logger.debug(
                "WebSocket disconnected",
                extra={
                    'connection_id': connection_id,
                    'total_connections': len(self.active_connections)
                }
            )


    def subscribe(self, connection_id: str, application_id: str):
        """Subscribe a connection to updates for a specific application.

        Args:
            connection_id: Connection identifier
            application_id: Application UUID
        """
        if application_id not in self.subscriptions:
            self.subscriptions[application_id] = set()

        self.subscriptions[application_id].add(connection_id)

        logger.debug(
            "Subscribed to application",
            extra={
                'connection_id': connection_id,
                'application_id': application_id
            }
        )


    async def send_to_connection(self, message: dict, connection_id: str):
        """Send message to a specific connection.

        Args:
            message: Message to send
            connection_id: Connection identifier
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            await websocket.send_json(message)


    async def broadcast_to_all(self, message: dict):
        """Broadcast message to all active connections.

        Args:
            message: Message to broadcast
        """
        for connection_id in list(self.active_connections.keys()):
            try:
                await self.send_to_connection(message, connection_id)
            except Exception as e:
                logger.error(
                    "Error broadcasting to connection",
                    extra={
                        'connection_id': connection_id,
                        'error': str(e)
                    }
                )
                self.disconnect(connection_id)


    async def broadcast_to_application(self, application_id: str, message: dict):
        """Broadcast message to all connections subscribed to an application.

        Args:
            application_id: Application UUID
            message: Message to broadcast
        """
        if application_id in self.subscriptions:
            subscribers = list(self.subscriptions[application_id])

            logger.debug(
                "Broadcasting to application subscribers",
                extra={
                    'application_id': application_id,
                    'subscriber_count': len(subscribers)
                }
            )

            for connection_id in subscribers:
                try:
                    await self.send_to_connection(message, connection_id)
                except Exception as e:
                    logger.error(
                        "Error sending to subscriber",
                        extra={
                            'connection_id': connection_id,
                            'error': str(e)
                        }
                    )
                    self.disconnect(connection_id)


websocket_manager = ConnectionManager()
