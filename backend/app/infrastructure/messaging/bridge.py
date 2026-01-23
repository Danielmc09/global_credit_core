from ...core.logging import get_logger
from .pubsub import subscribe_to_updates
from .websocket import websocket_manager

logger = get_logger(__name__)


async def handle_redis_message(message: dict):
    """Handle message received from Redis and forward to WebSocket clients.
    
    This is the bridge function that connects Redis Pub/Sub to WebSocket.
    When a worker publishes to Redis, this function receives it and
    forwards to the appropriate WebSocket clients.
    
    Args:
        message: Message from Redis Pub/Sub containing application update
    """
    try:
        if message.get('broadcast'):
            # Broadcast to all connected WebSocket clients
            await websocket_manager.broadcast_to_all(message)
            logger.debug(
                "Broadcasted Redis message to all WebSocket clients",
                extra={
                    'application_id': message.get('data', {}).get('id'),
                    'client_count': len(websocket_manager.active_connections)
                } 
            )
        else:
            # Broadcast to specific application subscribers only
            application_id = message.get('data', {}).get('id')
            if application_id:
                await websocket_manager.broadcast_to_application(application_id, message)
                logger.debug(
                    "Broadcasted Redis message to application subscribers",
                    extra={'application_id': application_id}
                )
    except Exception as e:
        logger.error(
            "Error handling Redis message for WebSocket broadcast",
            extra={'error': str(e), 'message': message},
            exc_info=True
        )


async def start_notification_bridge():
    """Start the bridge between Redis Pub/Sub and WebSocket connections.
    
    This function should be run as a background task during API startup.
    It continuously listens for Redis Pub/Sub messages and forwards them
    to connected WebSocket clients.
    
    Flow:
    1. Worker publishes to Redis (pubsub_service.publish_application_update)
    2. This function receives via Redis Pub/Sub (pubsub_service.subscribe_to_updates)
    3. Forwards to WebSocket clients (websocket_manager.broadcast_*)
    """
    logger.info("Starting notification bridge (Redis Pub/Sub → WebSocket)")
    await subscribe_to_updates(handle_redis_message)
