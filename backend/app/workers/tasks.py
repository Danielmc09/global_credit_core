import asyncio
import time

from redis.asyncio.lock import Lock

from sqlalchemy.exc import DatabaseError, OperationalError, TimeoutError as SQLTimeoutError

try:
    from opentelemetry import context as otel_context
except ImportError:
    otel_context = None

from ..core.config import settings
from ..core.constants import (
    Security,
)
from ..core.exceptions import (
    ApplicationNotFoundError,
    DatabaseConnectionError,
    ExternalServiceError,
    InvalidApplicationIdError,
    NetworkTimeoutError,
    PermanentError,
    RecoverableError,
    StateTransitionError,
    ValidationError,
)
from ..core.logging import get_logger, set_request_id
from ..infrastructure.monitoring import (
    worker_task_duration_seconds,
    worker_tasks_in_progress,
    worker_tasks_total,
)

try:
    from ..infrastructure.monitoring import (
        extract_trace_context,
        get_tracer,
        inject_trace_context,
    )
except ImportError:

    def get_tracer(name: str):
        """No-op tracer when tracing is not available."""
        class NoOpTracer:
            def start_as_current_span(self, *args, **kwargs):
                from contextlib import nullcontext
                return nullcontext()
        return NoOpTracer()

    def extract_trace_context(carrier: dict):
        """No-op trace context extraction."""
        return None

    def inject_trace_context(carrier: dict):
        """No-op trace context injection."""
        pass

    if otel_context is None:
        class NullContext:
            def attach(self, context):
                from contextlib import nullcontext
                return nullcontext()
        otel_context = NullContext()

from ..db.database import AsyncSessionLocal
from ..utils import generate_request_id

from ..services.application_processing_service import ApplicationProcessingService

logger = get_logger(__name__)

# + 1 en servicio de metricas Prometheus
@worker_tasks_in_progress.track_inprogress()
async def process_credit_application(ctx, application_id: str, trace_context: dict | None = None):
    """Main task: Process a credit application.

    This task:
    1. Fetches banking data from provider (mock)
    2. Applies country-specific business rules
    3. Updates application status and risk score
    4. Sends WebSocket notification (for real-time updates)

    Args:
        ctx: ARQ context
        application_id: UUID of the application to process
        trace_context: Optional trace context dictionary for distributed tracing

    Raises:
        PermanentError: For errors that won't resolve on retry (invalid data, not found, etc.)
        RecoverableError: For transient errors that may resolve on retry (network, DB connection)
        Exception: Any other unexpected error (will be retried by ARQ)
    """
    start_time = time.time()

    # Crea un span para el proceso de la aplicacion 
    tracer = get_tracer(__name__)
    if trace_context:
        # Extrae el contexto de la traza
        otel_context_obj = extract_trace_context(trace_context)
        if otel_context_obj:
            # Asocia el contexto de la traza con el span
            with otel_context.attach(otel_context_obj):
                # Inicia el span
                with tracer.start_as_current_span("process_credit_application") as span:
                    span.set_attribute("application.id", application_id)
                    return await _process_credit_application_impl(
                        ctx, application_id, start_time, tracer, span
                    )
    
    with tracer.start_as_current_span("process_credit_application") as span:
        span.set_attribute("application.id", application_id)
        return await _process_credit_application_impl(
            ctx, application_id, start_time, tracer, span
        )


async def _process_credit_application_impl(
    ctx, application_id: str, start_time: float, tracer, span
):
    """Internal implementation of credit application processing."""
    # Genera un ID de solicitud para el worker
    set_request_id(
        generate_request_id(Security.REQUEST_ID_PREFIX_WORKER)
    )

    logger.info(
        "Processing credit application",
        extra={'application_id': application_id}
    )

    redis_client = ctx['redis']

    lock_key = f"process:{application_id}"
    lock_timeout = 300

    try:
        # Genera un cerrojo distribuido para evitar procesos paralelos
        lock = Lock(redis_client, lock_key, timeout=lock_timeout, sleep=0.1)
        async with lock:
            logger.debug(
                "Acquired distributed lock for application processing",
                extra={'application_id': application_id, 'lock_key': lock_key}
            )

            async with AsyncSessionLocal() as db:
                service = ApplicationProcessingService(db)
                
                try:
                    result = await service.process_application(application_id)
                    
                    # Incrementa el contador de tareas en las graficas de prometheus
                    worker_tasks_total.labels(
                        task_name='process_credit_application',
                        status='success'
                    ).inc()
                    
                    # Obtiene el tiempo de ejecucion
                    duration = time.time() - start_time
                    worker_task_duration_seconds.labels(
                        task_name='process_credit_application'
                    ).observe(duration)
                    
                    return result

                except (PermanentError, InvalidApplicationIdError, ApplicationNotFoundError,
                        ValidationError, StateTransitionError) as e:
                    error_type = type(e).__name__
                    error_message = str(e)

                    logger.error(
                        "Permanent error processing application (will not retry)",
                        extra={
                            'application_id': application_id,
                            'error': error_message,
                            'error_type': error_type,
                            'stage': 'processing',
                            'retryable': False
                        },
                        exc_info=True
                    )

                    worker_tasks_total.labels(
                        task_name='process_credit_application',
                        status='failure'
                    ).inc()
                    duration = time.time() - start_time
                    worker_task_duration_seconds.labels(
                        task_name='process_credit_application'
                    ).observe(duration)

                    raise

                except (RecoverableError, DatabaseConnectionError, ExternalServiceError,
                        NetworkTimeoutError) as e:
                    error_type = type(e).__name__
                    error_message = str(e)

                    logger.warning(
                        "Recoverable error processing application (will retry)",
                        extra={
                            'application_id': application_id,
                            'error': error_message,
                            'error_type': error_type,
                            'stage': 'processing',
                            'retryable': True
                        },
                        exc_info=True
                    )

                    worker_tasks_total.labels(
                        task_name='process_credit_application',
                        status='failure'
                    ).inc()
                    duration = time.time() - start_time
                    worker_task_duration_seconds.labels(
                        task_name='process_credit_application'
                    ).observe(duration)

                    raise

                except (OperationalError, DatabaseError, SQLTimeoutError) as e:
                    error_type = type(e).__name__
                    error_message = str(e)

                    logger.warning(
                        "Database error processing application (will retry)",
                        extra={
                            'application_id': application_id,
                            'error': error_message,
                            'error_type': error_type,
                            'stage': 'processing',
                            'retryable': True
                        },
                        exc_info=True
                    )

                    worker_tasks_total.labels(
                        task_name='process_credit_application',
                        status='failure'
                    ).inc()
                    duration = time.time() - start_time
                    worker_task_duration_seconds.labels(
                        task_name='process_credit_application'
                    ).observe(duration)

                    raise DatabaseConnectionError(
                        f"Database error: {error_message}"
                    ) from e

                except (TimeoutError, asyncio.TimeoutError) as e:
                    error_type = type(e).__name__
                    error_message = str(e)

                    logger.warning(
                        "Timeout error processing application (will retry)",
                        extra={
                            'application_id': application_id,
                            'error': error_message,
                            'error_type': error_type,
                            'stage': 'processing',
                            'retryable': True
                        },
                        exc_info=True
                    )

                    worker_tasks_total.labels(
                        task_name='process_credit_application',
                        status='failure'
                    ).inc()
                    duration = time.time() - start_time
                    worker_task_duration_seconds.labels(
                        task_name='process_credit_application'
                    ).observe(duration)

                    raise NetworkTimeoutError(
                        f"Timeout error: {error_message}"
                    ) from e

                except Exception as e:
                    error_type = type(e).__name__
                    error_message = str(e)

                    logger.error(
                        "Unexpected error processing application",
                        extra={
                            'application_id': application_id,
                            'error': error_message,
                            'error_type': error_type,
                            'stage': 'processing',
                            'retryable': 'unknown'
                        },
                        exc_info=True
                    )

                    worker_tasks_total.labels(
                        task_name='process_credit_application',
                        status='failure'
                    ).inc()
                    duration = time.time() - start_time
                    worker_task_duration_seconds.labels(
                        task_name='process_credit_application'
                    ).observe(duration)

                    raise
    finally:
        await redis_client.close()
