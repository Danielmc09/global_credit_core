import logging

from arq import run_worker
from arq.connections import RedisSettings
from arq.worker import func
from prometheus_client import start_http_server

CRON_AVAILABLE = False
cron = None

try:
    from arq.worker import cron
    CRON_AVAILABLE = True
except ImportError:
    try:
        from arq import cron
        CRON_AVAILABLE = True
    except ImportError:
        CRON_AVAILABLE = False
        cron = None

from ..core.config import settings
from ..core.constants import Timeout
from ..core.logging import setup_logging
from .dlq_handler import handle_failed_job
from .success_handler import handle_job_success
from .cleanup import (
    cleanup_old_applications,
    cleanup_old_webhook_events,
)
from .consumer import consume_pending_jobs_from_db
from .notifications import send_webhook_notification
from .retry_jobs import retry_failed_jobs
from .tasks import process_credit_application

setup_logging()


class WorkerSettings:
    """ARQ Worker settings.

    This configuration allows:
    - Multiple concurrent workers (horizontal scaling)
    - Task retries on failure
    - Job timeouts
    - Periodic tasks (cron-like)
    """

    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)

    max_jobs = 10
    job_timeout = Timeout.JOB_TIMEOUT
    max_tries = 3

    functions = [
        func(process_credit_application, name='process_credit_application'),
        func(send_webhook_notification, name='send_webhook_notification'),
        func(cleanup_old_applications, name='cleanup_old_applications'),
        func(cleanup_old_webhook_events, name='cleanup_old_webhook_events'),
        func(consume_pending_jobs_from_db, name='consume_pending_jobs_from_db'),
        func(retry_failed_jobs, name='retry_failed_jobs'),
    ]

    cron_jobs = []

    log_results = True

    worker_name = "credit-worker"

    on_job_success = handle_job_success
    on_job_failure = handle_failed_job


if CRON_AVAILABLE and cron is not None:
    consume_jobs_crons = [
        cron(consume_pending_jobs_from_db, minute=m)
        for m in range(60)
    ]

    WorkerSettings.cron_jobs = consume_jobs_crons + [
        cron(cleanup_old_webhook_events, hour=3, minute=0),
        cron(retry_failed_jobs, minute={5, 20, 35, 50}),  # Every 15 minutes, offset by 5
    ]


if __name__ == "__main__":
    port = 8001
    start_http_server(port)
    logging.getLogger("prometheus_client").setLevel(logging.WARNING)
    print(f"Started Prometheus metrics server on port {port}")

    run_worker(WorkerSettings)
