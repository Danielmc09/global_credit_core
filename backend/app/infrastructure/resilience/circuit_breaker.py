import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

from circuitbreaker import circuit

from ...core.constants import (
    CircuitBreaker,
    CountryBusinessRules,
    CountryCode,
    CreditScore,
    Timeout,
)
from ...core.exceptions import (
    ExternalServiceError,
    NetworkTimeoutError,
    RecoverableError,
)
from ...core.logging import get_logger
from ...infrastructure.monitoring.metrics import (
    provider_circuit_breaker_state,
    provider_requests_total,
)
from ..monitoring.tracing import get_tracer

logger = get_logger(__name__)

CB_STATE_CLOSED = CircuitBreaker.STATE_CLOSED
CB_STATE_OPEN = CircuitBreaker.STATE_OPEN
CB_STATE_HALF_OPEN = CircuitBreaker.STATE_HALF_OPEN

CIRCUIT_BREAKER_EXCEPTIONS = (
    RecoverableError,
    ExternalServiceError,
    NetworkTimeoutError,
    TimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
)


class BankingProviderCircuitBreaker:
    """Circuit breaker specifically for banking provider calls.

    Configuration:
    - failure_threshold: Number of failures before opening circuit (default: 5)
    - recovery_timeout: Seconds to wait before attempting recovery (default: 60)
    - expected_exception: Exception type that triggers the circuit breaker
    """

    def __init__(
        self,
        country: str,
        provider_name: str,
        failure_threshold: int = CircuitBreaker.DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout: int = CircuitBreaker.DEFAULT_RECOVERY_TIMEOUT,
    ):
        self.country = country
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout


    def __call__(self, func: Callable) -> Callable:
        """Decorator to wrap banking provider calls with circuit breaker.

        Usage:
            @BankingProviderCircuitBreaker(country=CountryCode.SPAIN, provider_name=ProviderNames.SPAIN)
            async def get_banking_data(document: str):
                # ... actual provider call
        """

        @circuit(
            failure_threshold=self.failure_threshold,
            recovery_timeout=self.recovery_timeout,
            expected_exception=CIRCUIT_BREAKER_EXCEPTIONS,
            name=f"{self.country}_{self.provider_name}"
        ) 
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                provider_circuit_breaker_state.labels(
                    country=self.country,
                    provider=self.provider_name
                ).set(CB_STATE_CLOSED)

                logger.debug(
                    "Calling banking provider",
                    extra={
                        'country': self.country,
                        'provider': self.provider_name
                    }
                )

                # AQUÍ SE LLAMA A LA FUNCIÓN ORIGINAL FETCH_BANKING_DATA
                result = await func(*args, **kwargs)

                provider_requests_total.labels(
                    country=self.country,
                    provider=self.provider_name,
                    status='success'
                ).inc()

                return result

            except CIRCUIT_BREAKER_EXCEPTIONS as e:
                provider_requests_total.labels(
                    country=self.country,
                    provider=self.provider_name,
                    status='failure'
                ).inc()

                provider_circuit_breaker_state.labels(
                    country=self.country,
                    provider=self.provider_name
                ).set(CB_STATE_OPEN)

                logger.error(
                    f"Banking provider call failed: {self.provider_name}",
                    extra={
                        'country': self.country,
                        'provider': self.provider_name,
                        'error': str(e),
                        'exception_type': type(e).__name__
                    },
                    exc_info=True
                )

                raise
            except Exception as e:
                logger.error(
                    f"Programming error in banking provider call: {self.provider_name}",
                    extra={
                        'country': self.country,
                        'provider': self.provider_name,
                        'error': str(e),
                        'exception_type': type(e).__name__
                    },
                    exc_info=True
                )
                raise

        return wrapper


async def _apply_timeout_to_provider_call(
    provider_func: Callable,
    timeout_seconds: int,
    provider_name: str,
    country: str,
    *args,
    **kwargs
) -> Any: # ESTE ES EL CRONOMETRO
    """Apply timeout protection to a provider call.
    
    Args:
        provider_func: Provider function to call
        timeout_seconds: Timeout in seconds
        provider_name: Name of the provider (for logging)
        country: Country code (for metrics)
        *args, **kwargs: Arguments to pass to provider_func
    
    Returns:
        Result from provider call
    
    Raises:
        NetworkTimeoutError: If call exceeds timeout
    """

    try:
        # AQUÍ SE ACTIVA EL WRAPPER
        return await asyncio.wait_for(
            provider_func(*args, **kwargs),
            timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        logger.warning(
            f"Provider call timed out after {timeout_seconds}s: {provider_name}",
            extra={
                'country': country,
                'provider': provider_name,
                'timeout_seconds': timeout_seconds
            }
        )
        
        provider_requests_total.labels(
            country=country,
            provider=provider_name,
            status='timeout'
        ).inc()
        
        raise NetworkTimeoutError(
            f"Provider {provider_name} call timed out after {timeout_seconds} seconds"
        ) from None





async def _execute_with_tracing(
    provider_func: Callable,
    provider_name: str,
    country: str,
    timeout_seconds: int,
    args: tuple,
    kwargs: dict
) -> Any:
    """Execute provider call with OpenTelemetry tracing.
    
    Args:
        provider_func: Provider function to call
        provider_name: Name of the provider
        country: Country code
        timeout_seconds: Timeout in seconds
        args: Positional arguments for provider_func
        kwargs: Keyword arguments for provider_func
    
    Returns:
        Result from provider call
        
    Raises:
        ProviderUnavailableError: When circuit breaker is open (provider unavailable)
    """
    from ...core.exceptions import ProviderUnavailableError
    
    tracer = get_tracer(__name__)
    
    with tracer.start_as_current_span("call_banking_provider") as span:
        span.set_attribute("provider.name", provider_name)
        span.set_attribute("provider.country", country)
        span.set_attribute("provider.timeout_seconds", timeout_seconds)
        
        try:
            result = await _apply_timeout_to_provider_call(
                provider_func,
                timeout_seconds,
                provider_name,
                country,
                *args,
                **kwargs
            )
            span.set_attribute("provider.success", True)
            return result
            
        except CIRCUIT_BREAKER_EXCEPTIONS as e:
            span.set_attribute("provider.success", False)
            span.set_attribute("circuit_breaker.open", True)
            span.set_attribute("provider.will_retry", True)
            span.record_exception(e)
            
            raise ProviderUnavailableError(
                f"Provider {provider_name} is unavailable (circuit breaker open): {str(e)}"
            ) from e
            
        except Exception as e:
            span.set_attribute("provider.success", False)
            span.record_exception(e)
            raise


async def call_provider_with_circuit_breaker(
    provider_func: Callable,
    country: str,
    provider_name: str,
    *args,
    **kwargs
) -> Any:
    """Call a banking provider with circuit breaker protection and timeout.

    This function provides multiple layers of protection:
    1. Explicit Timeout: Provider calls are wrapped with asyncio.wait_for()
       with a timeout of 30 seconds (configurable via Timeout.PROVIDER_TIMEOUT).
       This prevents a slow provider from blocking workers indefinitely.
    2. Circuit Breaker: Protects against cascading failures when providers are down.
    3. Retry Queue: Jobs failing with ProviderUnavailableError are queued for retry.

    Usage:
        banking_data = await call_provider_with_circuit_breaker(
            provider_func=self._call_real_provider,
            country=CountryCode.SPAIN,
            provider_name=ProviderNames.SPAIN,
            document="12345678Z"
        )

    Args:
        provider_func: The actual provider function to call
        country: Country code (ES, MX, BR, etc.)
        provider_name: Name of the provider
        *args, **kwargs: Arguments to pass to provider_func

    Returns:
        Banking data from provider

    Raises:
        ProviderUnavailableError: When circuit breaker is open (queued for retry)
        NetworkTimeoutError: If provider call exceeds timeout
        ExternalServiceError: For other provider errors
    """
    from ...core.exceptions import ProviderUnavailableError
    
    # Create circuit breaker protection
    breaker = BankingProviderCircuitBreaker(
        country=country,
        provider_name=provider_name
    )

    # Wrap function with circuit breaker
    decorated_func = breaker(provider_func)
    
    try:
        tracer = get_tracer(__name__)
        return await _execute_with_tracing(
            decorated_func,
            provider_name,
            country,
            Timeout.PROVIDER_TIMEOUT,
            args,
            kwargs
        )
    except ImportError:
        # Tracing not available, execute without it
        try:
            return await _apply_timeout_to_provider_call(
                decorated_func,
                Timeout.PROVIDER_TIMEOUT,
                provider_name,
                country,
                *args,
                **kwargs
            )
        except CIRCUIT_BREAKER_EXCEPTIONS as e:
            # Raise ProviderUnavailableError instead of returning fallback
            raise ProviderUnavailableError(
                f"Provider {provider_name} is unavailable: {str(e)}"
            ) from e


def with_circuit_breaker(country: str, provider_name: str):
    """Decorator to add circuit breaker to banking provider methods.

    Usage in strategy class:
        @with_circuit_breaker(country=CountryCode.SPAIN, provider_name=ProviderNames.SPAIN)
        async def get_banking_data(self, document: str, full_name: str):
            # ... implementation
    """
    def decorator(func: Callable) -> Callable:
        breaker = BankingProviderCircuitBreaker(
            country=country,
            provider_name=provider_name
        )
        return breaker(func)

    return decorator
