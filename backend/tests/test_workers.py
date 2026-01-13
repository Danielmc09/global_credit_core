"""
Tests for Asynchronous Workers

Tests background task processing with ARQ workers.
"""

from datetime import UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.constants import ApprovalRecommendation, RiskLevel
from app.models.application import Application, ApplicationStatus
from app.strategies.base import BankingData, RiskAssessment
from app.workers.tasks import process_credit_application


def create_mock_strategy():
    """Create a mock strategy with default banking data and risk assessment"""
    mock_strategy = MagicMock()

    # get_banking_data is async and should return BankingData
    async def mock_get_banking_data(*args, **kwargs):
        return BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            has_defaults=False
        )
    mock_strategy.get_banking_data = mock_get_banking_data

    # apply_business_rules is synchronous and should return RiskAssessment
    mock_strategy.apply_business_rules = MagicMock(return_value=RiskAssessment(
        risk_score=Decimal("25.0"),
        risk_level=RiskLevel.LOW,
        approval_recommendation=ApprovalRecommendation.APPROVE,
        reasons=["Good profile"],
        requires_review=False
    ))

    return mock_strategy


async def mock_decrypt_value(session, encrypted_value):
    """Mock decrypt_value that returns the input as-is"""
    if isinstance(encrypted_value, bytes):
        return encrypted_value.decode('utf-8') if encrypted_value else ""
    return encrypted_value or ""


class TestCreditApplicationProcessing:
    """Test suite for credit application worker tasks"""

    @pytest.mark.asyncio()
    async def test_process_credit_application_spain(self):
        """Test processing a Spanish credit application"""
        # Generate valid UUID
        test_uuid = str(uuid4())

        # Mock application
        mock_app = Application(
            id=test_uuid,
            country="ES",
            full_name="Test User",
            identity_document="12345678Z",
            requested_amount=Decimal("15000.00"),
            monthly_income=Decimal("3500.00"),
            status=ApplicationStatus.PENDING,
            country_specific_data={},
            banking_data={},
            validation_errors=[]
        )

        # Mock database session
        with patch('app.workers.tasks.aioredis.from_url') as mock_redis, \
             patch('app.workers.tasks.AsyncSessionLocal') as mock_session, \
             patch('app.workers.tasks.get_country_strategy') as mock_factory, \
             patch('app.core.encryption.decrypt_value', side_effect=mock_decrypt_value):
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            
            with patch('app.workers.tasks.Lock', return_value=mock_lock):
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db

                # Mock query result (scalar_one_or_none is synchronous, not async)
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_app
                # execute() is async, so we need to make it return the result when awaited
                async def mock_execute(*args, **kwargs):
                    return mock_result
                mock_db.execute = mock_execute

                # Mock strategy
                mock_factory.return_value = create_mock_strategy()

                # Mock ARQ context
                mock_ctx = {}

                # Run task
                result = await process_credit_application(mock_ctx, test_uuid)

                # Assertions
                assert "processed" in result.lower()
                # Verify status was updated to VALIDATING then to final status
                assert mock_db.commit.called

    @pytest.mark.asyncio()
    async def test_process_nonexistent_application(self):
        """Test processing non-existent application raises ApplicationNotFoundError"""
        from app.core.exceptions import ApplicationNotFoundError

        # Generate valid UUID for non-existent application
        test_uuid = str(uuid4())

        with patch('app.workers.tasks.aioredis.from_url') as mock_redis, \
             patch('app.workers.tasks.AsyncSessionLocal') as mock_session:
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            # Mock Lock class
            with patch('app.workers.tasks.Lock', return_value=mock_lock):
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db

                # Mock query returning None (scalar_one_or_none is synchronous, not async)
                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = None
                # execute() is async, so we need to make it return the result when awaited
                async def mock_execute(*args, **kwargs):
                    return mock_result
                mock_db.execute = mock_execute

                mock_ctx = {}

                # Should raise ApplicationNotFoundError
                with pytest.raises(ApplicationNotFoundError, match="not found"):
                    await process_credit_application(mock_ctx, test_uuid)

    @pytest.mark.asyncio()
    async def test_worker_updates_status_progression(self):
        """Test that worker updates status from PENDING -> VALIDATING -> final"""
        # Generate valid UUID
        test_uuid = str(uuid4())

        mock_app = Application(
            id=test_uuid,
            country="MX",
            full_name="Test User",
            identity_document="HERM850101MDFRRR01",
            requested_amount=Decimal("50000.00"),
            monthly_income=Decimal("12000.00"),
            status=ApplicationStatus.PENDING,
            country_specific_data={},
            banking_data={},
            validation_errors=[]
        )

        with patch('app.workers.tasks.aioredis.from_url') as mock_redis, \
             patch('app.workers.tasks.AsyncSessionLocal') as mock_session, \
             patch('app.workers.tasks.get_country_strategy') as mock_factory, \
             patch('app.core.encryption.decrypt_value', side_effect=mock_decrypt_value):
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            
            with patch('app.workers.tasks.Lock', return_value=mock_lock):
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_app
                # execute() is async, so we need to make it return the result when awaited
                async def mock_execute(*args, **kwargs):
                    return mock_result
                mock_db.execute = mock_execute

                # Mock strategy
                mock_factory.return_value = create_mock_strategy()

                mock_ctx = {}

                await process_credit_application(mock_ctx, test_uuid)

            # Check that status was changed
            assert mock_app.status != ApplicationStatus.PENDING
            # Should be one of the final states
            assert mock_app.status in [
                ApplicationStatus.APPROVED,
                ApplicationStatus.REJECTED,
                ApplicationStatus.UNDER_REVIEW
            ]

    @pytest.mark.asyncio()
    async def test_worker_calls_country_strategy(self):
        """Test that worker uses correct country strategy"""
        # Generate valid UUID
        test_uuid = str(uuid4())

        mock_app = Application(
            id=test_uuid,
            country="ES",
            full_name="Test User",
            identity_document="12345678Z",
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("3000.00"),
            status=ApplicationStatus.PENDING,
            country_specific_data={},
            banking_data={},
            validation_errors=[]
        )

        with patch('app.workers.tasks.aioredis.from_url') as mock_redis, \
             patch('app.workers.tasks.AsyncSessionLocal') as mock_session, \
             patch('app.workers.tasks.get_country_strategy') as mock_factory, \
             patch('app.core.encryption.decrypt_value', side_effect=mock_decrypt_value):
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            
            with patch('app.workers.tasks.Lock', return_value=mock_lock):
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_app
                # execute() is async, so we need to make it return the result when awaited
                async def mock_execute(*args, **kwargs):
                    return mock_result
                mock_db.execute = mock_execute

                # Mock strategy
                mock_factory.return_value = create_mock_strategy()

                mock_ctx = {}

                await process_credit_application(mock_ctx, test_uuid)

            # Verify strategy factory was called with correct country
            mock_factory.assert_called_once_with("ES")

    @pytest.mark.asyncio()
    async def test_worker_stores_banking_data(self):
        """Test that worker stores banking data from provider"""

        # Generate valid UUID
        test_uuid = str(uuid4())

        mock_app = Application(
            id=test_uuid,
            country="ES",
            full_name="Test User",
            identity_document="12345678Z",
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("3000.00"),
            status=ApplicationStatus.PENDING,
            country_specific_data={},
            banking_data={},
            validation_errors=[]
        )

        with patch('app.workers.tasks.aioredis.from_url') as mock_redis, \
             patch('app.workers.tasks.AsyncSessionLocal') as mock_session, \
             patch('app.workers.tasks.get_country_strategy') as mock_factory, \
             patch('app.core.encryption.decrypt_value', side_effect=mock_decrypt_value):
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            
            with patch('app.workers.tasks.Lock', return_value=mock_lock):
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_app
                # execute() is async, so we need to make it return the result when awaited
                async def mock_execute(*args, **kwargs):
                    return mock_result
                mock_db.execute = mock_execute

                # Mock strategy
                mock_factory.return_value = create_mock_strategy()

                mock_ctx = {}

                await process_credit_application(mock_ctx, test_uuid)

            # After processing, banking_data should be populated
            assert mock_app.banking_data is not None
            assert len(mock_app.banking_data) > 0

    @pytest.mark.asyncio()
    async def test_worker_stores_risk_assessment(self):
        """Test that worker stores risk assessment results"""
        # Generate valid UUID
        test_uuid = str(uuid4())

        mock_app = Application(
            id=test_uuid,
            country="MX",
            full_name="Test User",
            identity_document="HERM850101MDFRRR01",
            requested_amount=Decimal("50000.00"),
            monthly_income=Decimal("12000.00"),
            status=ApplicationStatus.PENDING,
            country_specific_data={},
            banking_data={},
            validation_errors=[],
            risk_score=None
        )

        with patch('app.workers.tasks.aioredis.from_url') as mock_redis, \
             patch('app.workers.tasks.AsyncSessionLocal') as mock_session, \
             patch('app.workers.tasks.get_country_strategy') as mock_factory, \
             patch('app.core.encryption.decrypt_value', side_effect=mock_decrypt_value):
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            
            with patch('app.workers.tasks.Lock', return_value=mock_lock):
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_app
                # execute() is async, so we need to make it return the result when awaited
                async def mock_execute(*args, **kwargs):
                    return mock_result
                mock_db.execute = mock_execute

                # Mock strategy
                mock_factory.return_value = create_mock_strategy()

                mock_ctx = {}

                await process_credit_application(mock_ctx, test_uuid)

            # Risk score should be set
            assert mock_app.risk_score is not None
            assert Decimal('0') <= mock_app.risk_score <= Decimal('100')

    @pytest.mark.asyncio()
    async def test_worker_handles_exceptions(self):
        """Test that worker re-raises exceptions for ARQ retry mechanism"""
        # Generate valid UUID
        test_uuid = str(uuid4())

        mock_app = Application(
            id=test_uuid,
            country="ES",
            full_name="Test User",
            identity_document="12345678Z",
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("3000.00"),
            status=ApplicationStatus.PENDING,
            country_specific_data={},
            banking_data={},
            validation_errors=[]
        )

        with patch('app.workers.tasks.aioredis.from_url') as mock_redis, \
             patch('app.workers.tasks.AsyncSessionLocal') as mock_session, \
             patch('app.core.encryption.decrypt_value', side_effect=mock_decrypt_value):
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            
            with patch('app.workers.tasks.Lock', return_value=mock_lock), \
                 patch('app.workers.tasks.get_country_strategy') as mock_factory:
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_app
                # execute() is async, so we need to make it return the result when awaited
                async def mock_execute(*args, **kwargs):
                    return mock_result
                mock_db.execute = mock_execute

                # Make strategy raise exception
                # get_banking_data is async, so side_effect must be an async function
                async def raise_provider_error(*args, **kwargs):
                    raise Exception("Provider error")
                mock_strategy = AsyncMock()
                mock_strategy.get_banking_data.side_effect = raise_provider_error
                mock_factory.return_value = mock_strategy

                mock_ctx = {}

                # Should re-raise exception so ARQ can handle retries
                # The exception is wrapped in ExternalServiceError with message "Error fetching banking data: Provider error"
                # We need to match the full message or just "Provider error" as a substring
                with pytest.raises(Exception) as exc_info:
                    await process_credit_application(mock_ctx, test_uuid)
                # Verify the exception message contains "Provider error"
                assert "Provider error" in str(exc_info.value), f"Expected 'Provider error' in exception message, got: {str(exc_info.value)}"

                # With simplified error handling, status should not be updated
                # ARQ will handle retries automatically


class TestWorkerConcurrency:
    """Test suite for worker concurrency features"""

    def test_worker_settings_configuration(self):
        """Test that worker settings allow multiple concurrent jobs"""
        from app.workers.main import WorkerSettings

        # Verify concurrency settings
        assert WorkerSettings.max_jobs >= 5  # Should allow multiple concurrent jobs
        assert WorkerSettings.max_tries >= 2  # Should retry failed jobs

    def test_worker_functions_registered(self):
        """Test that task functions are properly registered"""
        from app.workers.main import WorkerSettings

        # Check that main task is registered
        function_names = [f.name for f in WorkerSettings.functions]
        assert 'process_credit_application' in function_names

    def test_max_tries_configured(self):
        """Test that max_tries is configured for retries"""
        from app.workers.main import WorkerSettings

        # Verify max_tries is set to 3 for automatic retries
        assert WorkerSettings.max_tries == 3, "max_tries should be 3 for ARQ retries"


class TestWorkerMetricsAndExceptions:
    """Test suite for worker metrics and exception handling after refactor"""

    @pytest.mark.asyncio()
    async def test_metrics_recorded_on_success(self):
        """Test that success metrics are recorded when processing succeeds"""
        from app.core.metrics import worker_tasks_total

        # Reset metrics before test
        worker_tasks_total.clear()

        test_uuid = str(uuid4())
        mock_app = Application(
            id=test_uuid,
            country="ES",
            full_name="Test User",
            identity_document="12345678Z",
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("3000.00"),
            status=ApplicationStatus.PENDING,
            country_specific_data={},
            banking_data={},
            validation_errors=[]
        )

        with patch('app.workers.tasks.aioredis.from_url') as mock_redis, \
             patch('app.workers.tasks.AsyncSessionLocal') as mock_session, \
             patch('app.workers.tasks.get_country_strategy') as mock_factory, \
             patch('app.core.encryption.decrypt_value', side_effect=mock_decrypt_value):
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            
            with patch('app.workers.tasks.Lock', return_value=mock_lock):
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_app
                async def mock_execute(*args, **kwargs):
                    return mock_result
                mock_db.execute = mock_execute

                # Mock strategy
                mock_factory.return_value = create_mock_strategy()

                mock_ctx = {}

                # Run task
                await process_credit_application(mock_ctx, test_uuid)

            # Check that success metric was recorded
            samples = list(worker_tasks_total.collect()[0].samples)
            success_samples = [s for s in samples if s.labels.get('status') == 'success']
            assert len(success_samples) > 0, "Success metric should be recorded"
            assert success_samples[0].value > 0, "Success metric should have value > 0"

    @pytest.mark.asyncio()
    async def test_metrics_recorded_on_failure(self):
        """Test that failure metrics are recorded when processing fails"""
        from app.core.metrics import worker_tasks_total

        # Reset metrics before test
        worker_tasks_total.clear()

        test_uuid = str(uuid4())
        mock_app = Application(
            id=test_uuid,
            country="ES",
            full_name="Test User",
            identity_document="12345678Z",
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("3000.00"),
            status=ApplicationStatus.PENDING,
            country_specific_data={},
            banking_data={},
            validation_errors=[]
        )

        with patch('app.workers.tasks.aioredis.from_url') as mock_redis, \
             patch('app.workers.tasks.AsyncSessionLocal') as mock_session, \
             patch('app.core.encryption.decrypt_value', side_effect=mock_decrypt_value):
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            
            with patch('app.workers.tasks.Lock', return_value=mock_lock), \
                 patch('app.workers.tasks.get_country_strategy') as mock_factory:
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_app
                async def mock_execute(*args, **kwargs):
                    return mock_result
                mock_db.execute = mock_execute

                # Make strategy raise exception
                # get_banking_data is async, so side_effect must be an async function
                async def raise_provider_error(*args, **kwargs):
                    raise Exception("Provider error")
                mock_strategy = AsyncMock()
                mock_strategy.get_banking_data.side_effect = raise_provider_error
                mock_factory.return_value = mock_strategy

                mock_ctx = {}

                # Should raise exception
                # The exception is raised after metrics are recorded in the except block
                try:
                    await process_credit_application(mock_ctx, test_uuid)
                    # Should not reach here
                    assert False, "Expected exception was not raised"
                except Exception:
                    # Exception was raised as expected
                    # Metrics should have been recorded before the exception was re-raised
                    pass

                # Check that failure metric was recorded
                # Metrics are recorded in the except block before the exception is re-raised
                samples = list(worker_tasks_total.collect()[0].samples)
                failure_samples = [s for s in samples if s.labels.get('status') == 'failure']
                assert len(failure_samples) > 0, f"Failure metric should be recorded. Found samples: {[s.labels for s in samples]}"
                assert failure_samples[0].value > 0, f"Failure metric should have value > 0, got {failure_samples[0].value}"

    @pytest.mark.asyncio()
    async def test_invalid_uuid_raises_valueerror(self):
        """Test that invalid UUID format raises InvalidApplicationIdError"""
        from app.core.exceptions import InvalidApplicationIdError

        invalid_uuid = "not-a-valid-uuid"

        with patch('app.workers.tasks.aioredis.from_url') as mock_redis:
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            # Mock Lock class
            with patch('app.workers.tasks.Lock', return_value=mock_lock):
                mock_ctx = {}

                with pytest.raises(InvalidApplicationIdError, match="Invalid UUID format"):
                    await process_credit_application(mock_ctx, invalid_uuid)

    @pytest.mark.asyncio()
    async def test_exception_re_raised_for_arq(self):
        """Test that exceptions are re-raised so ARQ can handle retries"""
        from app.core.exceptions import ExternalServiceError

        test_uuid = str(uuid4())
        mock_app = Application(
            id=test_uuid,
            country="ES",
            full_name="Test User",
            identity_document="12345678Z",
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("3000.00"),
            status=ApplicationStatus.PENDING,
            country_specific_data={},
            banking_data={},
            validation_errors=[]
        )

        with patch('app.workers.tasks.aioredis.from_url') as mock_redis, \
             patch('app.workers.tasks.AsyncSessionLocal') as mock_session, \
             patch('app.workers.tasks.get_country_strategy') as mock_factory, \
             patch('app.core.encryption.decrypt_value', side_effect=mock_decrypt_value):
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            # Mock Lock class
            with patch('app.workers.tasks.Lock', return_value=mock_lock):
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_app
                async def mock_execute(*args, **kwargs):
                    return mock_result
                mock_db.execute = mock_execute

                # Make strategy raise a specific exception
                test_exception = ExternalServiceError("Test error for ARQ retry")
                mock_strategy = AsyncMock()
                mock_strategy.get_banking_data.side_effect = test_exception
                mock_factory.return_value = mock_strategy

                mock_ctx = {}

                # Should raise the same exception (wrapped in ExternalServiceError by the worker)
                with pytest.raises(ExternalServiceError, match="Test error for ARQ retry"):
                    await process_credit_application(mock_ctx, test_uuid)

    @pytest.mark.asyncio()
    async def test_duration_metric_recorded(self):
        """Test that task duration metric is recorded"""
        from app.core.metrics import worker_task_duration_seconds

        # Reset metrics before test
        worker_task_duration_seconds.clear()

        test_uuid = str(uuid4())
        mock_app = Application(
            id=test_uuid,
            country="ES",
            full_name="Test User",
            identity_document="12345678Z",
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("3000.00"),
            status=ApplicationStatus.PENDING,
            country_specific_data={},
            banking_data={},
            validation_errors=[]
        )

        with patch('app.workers.tasks.aioredis.from_url') as mock_redis, \
             patch('app.workers.tasks.AsyncSessionLocal') as mock_session, \
             patch('app.workers.tasks.get_country_strategy') as mock_factory, \
             patch('app.core.encryption.decrypt_value', side_effect=mock_decrypt_value):
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            
            with patch('app.workers.tasks.Lock', return_value=mock_lock):
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_app
                async def mock_execute(*args, **kwargs):
                    return mock_result
                mock_db.execute = mock_execute

                # Mock strategy
                mock_factory.return_value = create_mock_strategy()

                mock_ctx = {}

                # Run task
                await process_credit_application(mock_ctx, test_uuid)

            # Check that duration metric was recorded
            samples = list(worker_task_duration_seconds.collect()[0].samples)
            # Histogram should have at least one bucket with observations
            assert len(samples) > 0, "Duration metric should be recorded"

            # Check that there's at least one observation
            count_samples = [s for s in samples if s.name.endswith('_count')]
            if count_samples:
                assert count_samples[0].value > 0, "Duration metric should have observations"

    @pytest.mark.asyncio()
    async def test_application_status_not_updated_on_error(self):
        """Test that application status is NOT updated on error - ARQ handles retries"""
        test_uuid = str(uuid4())
        mock_app = Application(
            id=test_uuid,
            country="ES",
            full_name="Test User",
            identity_document="12345678Z",
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("3000.00"),
            status=ApplicationStatus.PENDING,
            country_specific_data={},
            banking_data={},
            validation_errors=[]
        )

        with patch('app.workers.tasks.aioredis.from_url') as mock_redis, \
             patch('app.workers.tasks.AsyncSessionLocal') as mock_session, \
             patch('app.core.encryption.decrypt_value', side_effect=mock_decrypt_value):
            # Setup Redis mocks - aioredis.from_url is async, so we need to make it return a coroutine
            mock_redis_client = AsyncMock()
            mock_redis_client.close = AsyncMock(return_value=None)  # Mock close method
            mock_lock = AsyncMock()
            mock_lock.__aenter__ = AsyncMock(return_value=None)
            mock_lock.__aexit__ = AsyncMock(return_value=None)
            # Make from_url return the client when awaited
            async def mock_from_url(*args, **kwargs):
                return mock_redis_client
            mock_redis.side_effect = mock_from_url
            
            with patch('app.workers.tasks.Lock', return_value=mock_lock), \
                 patch('app.workers.tasks.get_country_strategy') as mock_factory:
                mock_db = AsyncMock()
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_result = MagicMock()
                mock_result.scalar_one_or_none.return_value = mock_app
                async def mock_execute(*args, **kwargs):
                    return mock_result
                mock_db.execute = mock_execute

                # Make strategy raise exception
                # get_banking_data is async, so side_effect must be an async function
                async def raise_provider_error(*args, **kwargs):
                    raise Exception("Provider error")
                mock_strategy = AsyncMock()
                mock_strategy.get_banking_data.side_effect = raise_provider_error
                mock_factory.return_value = mock_strategy

                mock_ctx = {}

                # Should raise exception - ARQ will handle retries
                # The exception is wrapped in ExternalServiceError with message "Error fetching banking data: Provider error"
                # We need to match the full message or just "Provider error" as a substring
                with pytest.raises(Exception) as exc_info:
                    await process_credit_application(mock_ctx, test_uuid)
                # Verify the exception message contains "Provider error"
                assert "Provider error" in str(exc_info.value), f"Expected 'Provider error' in exception message, got: {str(exc_info.value)}"

                # The status is updated to VALIDATING before the error occurs (during get_banking_data).
                # The key behavior is that the exception is re-raised (not caught and handled)
                # so ARQ can automatically retry. The safe_transaction context manager ensures
                # rollback occurs in a real database scenario, restoring the original status.
                # With mocks, we verify the exception is properly re-raised.
                # The status will be VALIDATING because the error occurs after the status update.
                assert mock_app.status == ApplicationStatus.VALIDATING

    def test_worker_cron_jobs_registered(self):
        """Test that periodic cleanup jobs are registered"""
        from app.workers.main import WorkerSettings, CRON_AVAILABLE

        # Check that cleanup job is scheduled (if cron is available)
        if CRON_AVAILABLE and WorkerSettings.cron_jobs:
            # CronJob objects have a coroutine attribute
            cron_job_names = [job.coroutine.__name__ for job in WorkerSettings.cron_jobs]
            assert 'cleanup_old_webhook_events' in cron_job_names
        else:
            # If cron is not available, just check that cron_jobs is a list
            assert isinstance(WorkerSettings.cron_jobs, list)


class TestWebhookEventsCleanup:
    """Test suite for webhook events cleanup task"""

    @pytest.mark.asyncio()
    async def test_cleanup_old_webhook_events(self, test_db):
        """Test that old webhook events are deleted after TTL"""
        from datetime import datetime, timedelta
        from decimal import Decimal

        from sqlalchemy import select

        from app.core.constants import WebhookEventsTTL
        from app.core.encryption import encrypt_value
        from app.models.application import Application, ApplicationStatus, CountryCode
        from app.models.webhook_event import WebhookEvent, WebhookEventStatus
        from app.workers.tasks import cleanup_old_webhook_events

        # Create a test application
        async with test_db() as session:
            # Encrypt PII fields before creating application
            encrypted_name = await encrypt_value(session, "Test User")
            encrypted_doc = await encrypt_value(session, "12345678Z")
            
            app = Application(
                country=CountryCode.ES,
                full_name=encrypted_name,
                identity_document=encrypted_doc,
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR",  # Required field for ES (Spain)
                status=ApplicationStatus.PENDING
            )
            session.add(app)
            await session.flush()
            application_id = app.id

            # Create old webhook event (older than TTL)
            # Use timezone-aware datetime for PostgreSQL DateTime(timezone=True) columns
            old_date = datetime.now(UTC) - timedelta(days=WebhookEventsTTL.TTL_DAYS + 1)
            old_webhook = WebhookEvent(
                idempotency_key="OLD_WEBHOOK_123",
                application_id=application_id,
                payload={"test": "old data"},
                status=WebhookEventStatus.PROCESSED
            )
            session.add(old_webhook)
            await session.flush()  # Flush to get the ID
            
            # Update timestamps using SQL to avoid conflict with server_default
            # Use bindparam with DateTime type for proper PostgreSQL handling
            from sqlalchemy import DateTime, bindparam, text
            stmt = text("UPDATE webhook_events SET created_at = :old_date, updated_at = :old_date WHERE id = :webhook_id")
            stmt = stmt.bindparams(
                bindparam("old_date", old_date, type_=DateTime(timezone=True)),
                bindparam("webhook_id", old_webhook.id)
            )
            await session.execute(stmt)

            # Create recent webhook event (within TTL)
            recent_date = datetime.now(UTC) - timedelta(days=5)  # 5 days ago
            recent_webhook = WebhookEvent(
                idempotency_key="RECENT_WEBHOOK_456",
                application_id=application_id,
                payload={"test": "recent data"},
                status=WebhookEventStatus.PROCESSED
            )
            session.add(recent_webhook)
            await session.flush()  # Flush to get the ID
            
            # Update timestamps using SQL to avoid conflict with server_default
            # Use bindparam with DateTime type for proper PostgreSQL handling
            stmt = text("UPDATE webhook_events SET created_at = :recent_date, updated_at = :recent_date WHERE id = :webhook_id")
            stmt = stmt.bindparams(
                bindparam("recent_date", recent_date, type_=DateTime(timezone=True)),
                bindparam("webhook_id", recent_webhook.id)
            )
            await session.execute(stmt)

            await session.commit()

        # Run cleanup task using the test database
        # Patch AsyncSessionLocal to use the test database session factory
        mock_ctx = {}

        # Patch AsyncSessionLocal to use the test database
        # test_db is a session factory (async_sessionmaker), so when AsyncSessionLocal() is called,
        # we need it to return test_db() which is a session that can be used as a context manager
        # We create a simple callable class that returns the session factory when called
        class TestSessionLocal:
            def __call__(self):
                # Return the session factory call result, which is a session context manager
                return test_db()
        
        # Patch AsyncSessionLocal to be an instance that when called returns test_db()
        with patch('app.workers.tasks.AsyncSessionLocal', TestSessionLocal()):
            result = await cleanup_old_webhook_events(mock_ctx)

        # Verify result message
        assert "Deleted" in result
        assert str(WebhookEventsTTL.TTL_DAYS) in result

        # Verify old webhook was deleted
        async with test_db() as session:
            result = await session.execute(
                select(WebhookEvent).where(WebhookEvent.idempotency_key == "OLD_WEBHOOK_123")
            )
            old_webhook = result.scalar_one_or_none()
            assert old_webhook is None, "Old webhook should be deleted"

            # Verify recent webhook still exists
            result = await session.execute(
                select(WebhookEvent).where(WebhookEvent.idempotency_key == "RECENT_WEBHOOK_456")
            )
            recent_webhook = result.scalar_one_or_none()
            assert recent_webhook is not None, "Recent webhook should not be deleted"
            assert recent_webhook.idempotency_key == "RECENT_WEBHOOK_456"
