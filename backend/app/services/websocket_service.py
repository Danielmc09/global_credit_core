"""WebSocket Service.

Manages WebSocket connections for real-time updates (Requirement 3.10).
Uses Redis Pub/Sub for cross-process communication (worker → API).
"""

import asyncio
import json

import redis.asyncio as aioredis
from fastapi import WebSocket

from ..core.config import settings
from ..core.constants import WebSocket, WebSocketMessageTypes
from ..core.logging import get_logger
from ..models.application import Application
from ..utils import format_datetime

logger = get_logger(__name__)

# Redis client for pub/sub (global instance)
_redis_client = None

async def get_redis():
    """Get or create Redis client for pub/sub."""
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        logger.debug("Redis client initialized for pub/sub")
    return _redis_client


class ConnectionManager:
    """Manages WebSocket connections.

    Supports:
    - Multiple concurrent connections
    - Broadcasting to all clients
    - Broadcasting to specific clients/applications
    """

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

    async def send_personal_message(self, message: dict, connection_id: str):
        """Send message to a specific connection.

        Args:
            message: Message to send
            connection_id: Connection identifier
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        """Broadcast message to all active connections.

        Args:
            message: Message to broadcast
        """
        for connection_id in list(self.active_connections.keys()):
            try:
                await self.send_personal_message(message, connection_id)
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
                    await self.send_personal_message(message, connection_id)
                except Exception as e:
                    logger.error(
                        "Error sending to subscriber",
                        extra={
                            'connection_id': connection_id,
                            'error': str(e)
                        }
                    )
                    self.disconnect(connection_id)


manager = ConnectionManager()


async def broadcast_application_update(application: Application):
    """Broadcast an application update to all subscribers.

    This is called from:
    - Workers after processing (publishes to Redis)
    - API endpoints after status updates (publishes to Redis)

    Uses Redis Pub/Sub to communicate across processes (workers → API).

    Args:
        application: Updated application
    """
    application_id = str(application.id)
    status_value = application.status.value if hasattr(application.status, 'value') else str(application.status)
    risk_score_value = str(application.risk_score) if application.risk_score is not None else None
    updated_at_value = application.updated_at
    if updated_at_value:
        updated_at_str = format_datetime(updated_at_value, "%Y-%m-%dT%H:%M:%S")
    else:
        updated_at_str = None
    
    raw_status = application.status
    logger.debug(
        "Preparing broadcast message",
        extra={
            'application_id': application_id,
            'raw_status': str(raw_status),
            'raw_status_type': type(raw_status).__name__,
            'status_value': status_value,
            'status_value_type': type(status_value).__name__
        }
    )
    
    message = {
        "type": WebSocketMessageTypes.APPLICATION_UPDATE,
        "data": {
            "id": application_id,
            "status": status_value,
            "risk_score": risk_score_value,
            "updated_at": updated_at_str
        },
        "broadcast": True
    }
    
    logger.debug(
        "Broadcast message prepared",
        extra={
            'application_id': application_id,
            'message': message,
            'message_data_status': message['data']['status']
        }
    )

    try:
        redis = await get_redis()
        await redis.publish('websocket:broadcast', json.dumps(message))
        logger.info(
            "Application update published to Redis",
            extra={
                'application_id': application_id,
                'status': status_value,
                'risk_score': risk_score_value,
                'updated_at': updated_at_str,
                'message_type': message['type']
            }
        )
    except Exception as e:
        logger.error(
            "Failed to publish to Redis",
            extra={
                'application_id': application_id,
                'status': status_value,
                'error': str(e)
            },
            exc_info=True
        )


async def redis_subscriber():
    """Subscribe to Redis channel and forward messages to WebSocket clients.

    This runs as a background task in the API process.
    It listens for messages published by workers and broadcasts them to connected WebSocket clients.
    
    Uses exponential backoff with retry limits to prevent infinite recursion.
    """
    retry_count = 0
    backoff_seconds = WebSocket.INITIAL_BACKOFF_SECONDS
    
    while retry_count < WebSocket.MAX_RETRIES:
        try:
            logger.debug(
                "Starting Redis subscriber for WebSocket broadcasts",
                extra={'retry_count': retry_count}
            )
            
            redis = await get_redis()
            pubsub = redis.pubsub()
            await pubsub.subscribe('websocket:broadcast')

            logger.debug("Successfully subscribed to Redis channel: websocket:broadcast")
            
            retry_count = 0
            backoff_seconds = WebSocket.INITIAL_BACKOFF_SECONDS

            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])

                        logger.debug(
                            "Received message from Redis",
                            extra={
                                'message_type': data.get('type'),
                                'application_id': data.get('data', {}).get('id'),
                                'status': data.get('data', {}).get('status')
                            }
                        )

                        if data.get('broadcast'):
                            await manager.broadcast(data)
                            logger.debug(
                                "Broadcasted to WebSocket clients",
                                extra={
                                    'application_id': data.get('data', {}).get('id'),
                                    'subscriber_count': len(manager.active_connections)
                                }
                            )
                        else:
                            application_id = data.get('data', {}).get('id')
                            if application_id:
                                await manager.broadcast_to_application(application_id, data)

                    except json.JSONDecodeError as e:
                        logger.error(
                            "Failed to decode Redis message",
                            extra={'error': str(e), 'message': message.get('data')},
                            exc_info=True
                        )
                    except Exception as e:
                        logger.error(
                            "Error processing Redis message",
                            extra={'error': str(e)},
                            exc_info=True
                        )

        except Exception as e:
            retry_count += 1
            logger.error(
                "Redis subscriber error",
                extra={
                    'error': str(e),
                    'retry_count': retry_count,
                    'max_retries': WebSocket.MAX_RETRIES,
                    'backoff_seconds': backoff_seconds
                },
                exc_info=True
            )
            
            if retry_count >= WebSocket.MAX_RETRIES:
                logger.critical(
                    "Redis subscriber failed after maximum retries. Stopping subscriber.",
                    extra={
                        'max_retries': WebSocket.MAX_RETRIES,
                        'final_error': str(e)
                    }
                )
                break
            
            await asyncio.sleep(backoff_seconds)
            logger.debug(
                "Attempting to restart Redis subscriber",
                extra={
                    'retry_count': retry_count,
                    'next_backoff': min(backoff_seconds * 2, WebSocket.MAX_BACKOFF_SECONDS)
                }
            )
            
            backoff_seconds = min(backoff_seconds * 2, WebSocket.MAX_BACKOFF_SECONDS)
