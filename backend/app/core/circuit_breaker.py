"""Circuit Breaker Pattern Implementation.

Provides resilience for external service calls (banking providers).
Prevents cascading failures by failing fast when a service is unavailable.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Circuit is broken, requests fail immediately
- HALF_OPEN: Testing if service has recovered
"""

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

from circuitbreaker import circuit

from .constants import (
    CircuitBreaker,
    CountryBusinessRules,
    CountryCode,
    CreditScore,
    Timeout,
)
from .exceptions import (
    ExternalServiceError,
    NetworkTimeoutError,
    RecoverableError,
)
from .logging import get_logger
from .metrics import (
    provider_circuit_breaker_state,
    provider_requests_total,
)
from ..strategies.base import BankingData
from ..utils import mask_document

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


def get_country_min_credit_score(country: str) -> int:
    """Get minimum credit score for a country.

    Args:
        country: Country code (ES, MX, BR, CO, PT, IT)

    Returns:
        Minimum credit score for the country, or default fallback if unknown
    """
    country_min_scores = {
        CountryCode.SPAIN: CountryBusinessRules.SPAIN_MIN_CREDIT_SCORE,
        CountryCode.MEXICO: CountryBusinessRules.MEXICO_MIN_CREDIT_SCORE,
        CountryCode.BRAZIL: CountryBusinessRules.BRAZIL_MIN_CREDIT_SCORE,
        CountryCode.COLOMBIA: CountryBusinessRules.COLOMBIA_MIN_CREDIT_SCORE,
        CountryCode.PORTUGAL: CountryBusinessRules.PORTUGAL_MIN_CREDIT_SCORE,
        CountryCode.ITALY: CountryBusinessRules.ITALY_MIN_CREDIT_SCORE,
    }
    return country_min_scores.get(country, CircuitBreaker.FALLBACK_CREDIT_SCORE)


def get_fallback_banking_data(country: str, document: str) -> dict:
    """Fallback data when banking provider is unavailable.

    Returns conservative defaults that will likely result in manual review.
    Uses a country-specific conservative credit score (below minimum threshold)
    to ensure applications are flagged for review rather than auto-approved/rejected.

    Args:
        country: Country code (ES, MX, BR, CO, PT, IT)
        document: Identity document (masked in logs)

    Returns:
        Dictionary with fallback banking data
    """
    logger.warning(
        f"Using fallback banking data for {country}",
        extra={'country': country, 'document_masked': mask_document(document)}
    )

    country_min_score = get_country_min_credit_score(country)

    conservative_score = max(
        CreditScore.MIN_INTERNATIONAL,
        country_min_score - CircuitBreaker.FALLBACK_SCORE_MARGIN
    )

    if conservative_score >= country_min_score:
        conservative_score = max(
            CreditScore.MIN_INTERNATIONAL,
            country_min_score - (CircuitBreaker.FALLBACK_SCORE_MARGIN * 2)
        )

    logger.info(
        f"Using conservative fallback credit score for {country}",
        extra={
            'country': country,
            'country_min_score': country_min_score,
            'fallback_score': conservative_score,
            'fallback_margin': CircuitBreaker.FALLBACK_SCORE_MARGIN,
            'note': 'Score intentionally below minimum to trigger manual review'
        }
    )

    return {
        "provider_name": f"Fallback Provider ({country})",
        "account_status": "active",
        "credit_score": conservative_score,
        "total_debt": 0,
        "monthly_obligations": 0,
        "has_defaults": False,
        "account_age_months": 0,
        "additional_data": {
            "fallback_mode": True,
            "reason": "Circuit breaker open - provider unavailable",
            "country_min_score": country_min_score,
            "fallback_score": conservative_score,
            "requires_manual_review": True,
            "warning": "This score is a fallback value and should trigger manual review"
        }
    }


async def call_provider_with_circuit_breaker(
    provider_func: Callable,
    country: str,
    provider_name: str,
    *args,
    **kwargs
) -> Any:
    """Call a banking provider with circuit breaker protection, timeout, and fallback.

    This function provides multiple layers of protection:
    1. Explicit Timeout: Provider calls are wrapped with asyncio.wait_for()
       with a timeout of 30 seconds (configurable via Timeout.PROVIDER_TIMEOUT).
       This prevents a slow provider from blocking workers indefinitely.
    2. Circuit Breaker: Protects against cascading failures when providers are down.
    3. Fallback Data: Returns conservative fallback data when circuit is open.

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
        Banking data from provider, or fallback data if circuit is open or timeout occurs

    Raises:
        NetworkTimeoutError: If provider call exceeds timeout (converted to fallback data)
        ExternalServiceError: For other provider errors (converted to fallback data)
    """
    try:
        from opentelemetry import trace
        from .tracing import get_tracer
        tracer = get_tracer(__name__)
    except ImportError:
        tracer = None
        trace = None

    breaker = BankingProviderCircuitBreaker(
        country=country,
        provider_name=provider_name
    )

    decorated_func = breaker(provider_func)

    async def call_with_timeout():
        """Wrapper to add explicit timeout to provider calls."""
        try:
            return await asyncio.wait_for(
                decorated_func(*args, **kwargs),
                timeout=Timeout.PROVIDER_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"Provider call timed out after {Timeout.PROVIDER_TIMEOUT}s: {provider_name}",
                extra={
                    'country': country,
                    'provider': provider_name,
                    'timeout_seconds': Timeout.PROVIDER_TIMEOUT,
                    'error': f'Provider call exceeded timeout of {Timeout.PROVIDER_TIMEOUT} seconds'
                }
            )

            provider_requests_total.labels(
                country=country,
                provider=provider_name,
                status='timeout'
            ).inc()

            raise NetworkTimeoutError(
                f"Provider {provider_name} call timed out after {Timeout.PROVIDER_TIMEOUT} seconds"
            ) from None

    try:
        if tracer:
            with tracer.start_as_current_span("call_banking_provider") as span:
                span.set_attribute("provider.name", provider_name)
                span.set_attribute("provider.country", country)
                span.set_attribute("provider.timeout_seconds", Timeout.PROVIDER_TIMEOUT)
                try:
                    result = await call_with_timeout()
                    span.set_attribute("provider.success", True)
                    return result
                except CIRCUIT_BREAKER_EXCEPTIONS as e:
                    span.set_attribute("provider.success", False)
                    span.set_attribute("circuit_breaker.open", True)
                    span.set_attribute("provider.fallback_used", True)
                    span.record_exception(e)

                    logger.warning(
                        f"Circuit breaker open for {provider_name}, using fallback data",
                        extra={
                            'country': country,
                            'provider': provider_name,
                            'error': str(e),
                            'exception_type': type(e).__name__
                        }
                    )

                    document = kwargs.get('document', args[0] if args else 'UNKNOWN')
                    fallback_data = get_fallback_banking_data(country, document)
                    return BankingData(**fallback_data)
                except Exception as e:
                    span.set_attribute("provider.success", False)
                    span.record_exception(e)
                    raise
        else:
            try:
                return await call_with_timeout()
            except CIRCUIT_BREAKER_EXCEPTIONS as e:
                logger.warning(
                    f"Circuit breaker open for {provider_name}, using fallback data",
                    extra={
                        'country': country,
                        'provider': provider_name,
                        'error': str(e),
                        'exception_type': type(e).__name__
                    }
                )

                document = kwargs.get('document', args[0] if args else 'UNKNOWN')
                fallback_data = get_fallback_banking_data(country, document)
                return BankingData(**fallback_data)
    except Exception as e:
        logger.error(
            f"Programming error in provider call: {provider_name}",
            extra={
                'country': country,
                'provider': provider_name,
                'error': str(e),
                'exception_type': type(e).__name__
            },
            exc_info=True
        )
        raise


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
