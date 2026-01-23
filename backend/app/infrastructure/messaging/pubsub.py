import asyncio
import json

import redis.asyncio as aioredis

from ...core.config import settings
from ...core.constants import WebSocket as WSConstants, WebSocketMessageTypes
from ...core.logging import get_logger
from ...utils import format_datetime

logger = get_logger(__name__)

# Global Redis client for pub/sub
_redis_client = None


async def get_redis_client():
    """Get or create Redis client for pub/sub.
    
    Returns:
        Redis client configured for pub/sub operations
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        logger.debug("Redis Pub/Sub client initialized")
    return _redis_client


async def publish_application_update(
    application_id: str,
    status: str,
    risk_score: float | None = None,
    updated_at: str | None = None
):
    """Publish application update to Redis channel.
    
    This function is called from:
    - Workers: After processing application (tasks.py)
    - API: After manual status updates (endpoints)
    
    The message is published to Redis Pub/Sub and will be received by
    all API instances subscribed to the channel, which then broadcast
    to their connected WebSocket clients.
    
    Args:
        application_id: Application UUID as string
        status: Application status (enum value or string)
        risk_score: Optional risk score
        updated_at: Optional ISO formatted datetime string
    """
    risk_score_value = str(risk_score) if risk_score is not None else None
    
    logger.debug(
        "Preparing application update for Redis",
        extra={
            'application_id': application_id,
            'status': status,
            'risk_score': risk_score_value
        }
    )
    
    message = {
        "type": WebSocketMessageTypes.APPLICATION_UPDATE,
        "data": {
            "id": application_id,
            "status": status,
            "risk_score": risk_score_value,
            "updated_at": updated_at
        },
        "broadcast": True
    }
    
    try:
        redis = await get_redis_client()
        await redis.publish('websocket:broadcast', json.dumps(message))
        logger.info(
            "Application update published to Redis",
            extra={
                'application_id': application_id,
                'status': status,
                'channel': 'websocket:broadcast',
                'message_type': message['type']
            }
        )
    except Exception as e:
        logger.error(
            "Failed to publish to Redis",
            extra={
                'application_id': application_id,
                'status': status,
                'error': str(e)
            },
            exc_info=True
        )


async def subscribe_to_updates(message_handler):
    """Subscribe to Redis channel and process messages.
    
    This should run as a background task in the API process.
    It listens for messages published by workers and other API instances,
    then calls the provided handler to process them (typically forwarding to WebSocket).
    
    Uses exponential backoff with retry limits to handle connection failures.
    
    Args:
        message_handler: Async function to handle received messages.
                        Signature: async def handler(message: dict) -> None
    """
    retry_count = 0
    backoff_seconds = WSConstants.INITIAL_BACKOFF_SECONDS
    pubsub = None
    
    while retry_count < WSConstants.MAX_RETRIES:
        try:
            logger.debug(
                "Starting Redis subscriber for pub/sub messages",
                extra={'retry_count': retry_count}
            )
            
            redis = await get_redis_client()
            pubsub = redis.pubsub()
            await pubsub.subscribe('websocket:broadcast')
            
            logger.debug("Successfully subscribed to Redis channel: websocket:broadcast")
            
            # Reset retry counter on successful connection
            retry_count = 0
            backoff_seconds = WSConstants.INITIAL_BACKOFF_SECONDS
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        
                        logger.debug(
                            "Received message from Redis Pub/Sub",
                            extra={
                                'message_type': data.get('type'),
                                'application_id': data.get('data', {}).get('id'),
                                'status': data.get('data', {}).get('status')
                            }
                        )
                        
                        # Delegate to handler (typically forwards to WebSocket)
                        await message_handler(data)
                        
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
        
        except asyncio.CancelledError:
            # Task was cancelled (normal shutdown) - exit gracefully
            logger.info("Redis subscriber task cancelled (shutdown initiated)")
            if pubsub:
                try:
                    await pubsub.unsubscribe('websocket:broadcast')
                    await pubsub.close()
                    logger.debug("Redis pubsub connection closed gracefully")
                except Exception as e:
                    logger.debug(f"Error closing pubsub during shutdown: {e}")
            raise  # Re-raise to allow proper task cancellation
        
        except aioredis.ConnectionError as e:
            # Connection error - could be shutdown or network issue
            error_msg = str(e)
            if "Connection closed by server" in error_msg or "Server closed" in error_msg:
                logger.info(
                    "Redis connection closed by server (likely shutdown)",
                    extra={'error': error_msg}
                )
                # Clean up pubsub if it exists
                if pubsub:
                    try:
                        await pubsub.close()
                    except Exception:
                        pass
                break 
            else:
                # Unexpected connection error - retry with backoff
                retry_count += 1
                logger.warning(
                    "Redis connection error, will retry",
                    extra={
                        'error': error_msg,
                        'retry_count': retry_count,
                        'max_retries': WSConstants.MAX_RETRIES,
                        'backoff_seconds': backoff_seconds
                    }
                )
        
        except Exception as e:
            retry_count += 1
            logger.error(
                "Redis subscriber error",
                extra={
                    'error': str(e),
                    'retry_count': retry_count,
                    'max_retries': WSConstants.MAX_RETRIES,
                    'backoff_seconds': backoff_seconds
                },
                exc_info=True
            )
            
            if retry_count >= WSConstants.MAX_RETRIES:
                logger.critical(
                    "Redis subscriber failed after maximum retries. Stopping subscriber.",
                    extra={
                        'max_retries': WSConstants.MAX_RETRIES,
                        'final_error': str(e)
                    }
                )
                break
            
            await asyncio.sleep(backoff_seconds)
            logger.debug(
                "Attempting to restart Redis subscriber",
                extra={
                    'retry_count': retry_count,
                    'next_backoff': min(backoff_seconds * 2, WSConstants.MAX_BACKOFF_SECONDS)
                }
            )
            # si la primera vez que se intenta conectar falla, se espera 5 segundos y se vuelve a intentar
            backoff_seconds = min(backoff_seconds * 2, WSConstants.MAX_BACKOFF_SECONDS)
    
    logger.info("Redis subscriber task exiting")

