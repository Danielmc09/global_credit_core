"""Messaging infrastructure.

Handles inter-process communication and real-time updates:
- pubsub.py: Redis Pub/Sub
- websocket.py: WebSocket connections
- bridge.py: Bridge between Pub/Sub and WebSocket
"""

from .bridge import handle_redis_message, start_notification_bridge
from .pubsub import get_redis_client, publish_application_update, subscribe_to_updates
from .websocket import websocket_manager

__all__ = [
    # WebSocket
    "websocket_manager",
    # Pub/Sub
    "get_redis_client",
    "publish_application_update",
    "subscribe_to_updates",
    # Bridge
    "start_notification_bridge",
    "handle_redis_message",
]
