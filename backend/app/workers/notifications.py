import asyncio

from ..core.constants import Security, Timeout
from ..core.logging import get_logger, set_request_id

logger = get_logger(__name__)


async def send_webhook_notification(ctx, application_id: str, webhook_url: str):
    """Task: Send webhook notification to external system.

    Args:
        ctx: ARQ context
        application_id: Application UUID
        webhook_url: URL to send notification to
    """
    set_request_id(
        f"{Security.REQUEST_ID_PREFIX_WEBHOOK}{application_id[:Security.REQUEST_ID_UUID_LENGTH]}"
    )

    logger.info(
        "Sending webhook notification",
        extra={
            'application_id': application_id,
            'webhook_url': webhook_url
        }
    )

    await asyncio.sleep(Timeout.WEBHOOK_SIMULATION)

    logger.info(
        "Webhook sent successfully",
        extra={'application_id': application_id}
    )

    return f"Webhook sent for {application_id}"
