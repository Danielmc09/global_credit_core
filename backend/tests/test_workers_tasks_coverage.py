"""Tests for workers/tasks.py to improve coverage.

Tests for worker task error handling and edge cases.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from app.workers.tasks import (
    process_credit_application,
    send_webhook_notification,
    cleanup_old_webhook_events,
    cleanup_old_applications,
    monitor_table_partitioning,
)
from app.models.application import ApplicationStatus
from app.core.exceptions import (
    StateTransitionError,
    ValidationError,
    DatabaseConnectionError,
    NetworkTimeoutError,
)
from app.services.application_service import ApplicationService
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from decimal import Decimal 

class TestWorkersTasksCoverage:
    """Test suite for workers tasks coverage"""

    @pytest.mark.asyncio
    async def test_process_application_state_transition_error(self, test_db, monkeypatch):
        """Test process_credit_application with StateTransitionError"""
        # Create application
        async with test_db() as db:

            service = ApplicationService(db)
            app_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR"
            )
            application = await service.create_application(app_data)
            await db.flush()
            # Refresh to ensure all attributes are loaded
            await db.refresh(application)
            application_id_uuid = application.id
            app_id_str = str(application.id)
            await db.commit()
            # Use service to update status properly instead of direct assignment
            await service.update_application(application_id_uuid, ApplicationUpdate(status=ApplicationStatus.APPROVED))
            await db.commit()
            # Refresh again after status update to ensure trigger completed
            await db.refresh(application)

            def failing_validate_transition(old_status, new_status):
                raise ValueError("Invalid transition")

            # Create a test session factory that uses test_db
            class TestSessionLocal:
                def __call__(self):
                    return test_db()

            with patch('app.workers.tasks.validate_transition', side_effect=failing_validate_transition):
                with patch('app.workers.tasks.get_redis') as mock_redis:
                    mock_redis_client = AsyncMock()
                    mock_redis_client.close = AsyncMock()
                    mock_redis.return_value = mock_redis_client

                    with patch('app.workers.tasks.AsyncSessionLocal', TestSessionLocal()):
                        with pytest.raises(StateTransitionError):
                            await process_credit_application(
                                ctx={},
                                application_id=app_id_str
                            )

    @pytest.mark.asyncio
    async def test_process_application_broadcast_error(self, test_db, monkeypatch):
        """Test process_credit_application when broadcast fails"""
        async with test_db() as db:
            from app.services.application_service import ApplicationService
            from app.schemas.application import ApplicationCreate
            from decimal import Decimal
            service = ApplicationService(db)
            app_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR"
            )
            application = await service.create_application(app_data)
            await db.flush()
            # Refresh before commit to ensure all attributes are loaded
            await db.refresh(application)
            app_id_str = str(application.id)
            await db.commit()

            async def failing_broadcast(*args, **kwargs):
                raise Exception("Broadcast failed")

            # Create a test session factory that uses test_db
            class TestSessionLocal:
                def __call__(self):
                    return test_db()

            with patch('app.workers.tasks.broadcast_application_update', side_effect=failing_broadcast):
                with patch('app.workers.tasks.get_redis') as mock_redis:
                    mock_redis_client = AsyncMock()
                    mock_redis_client.close = AsyncMock()
                    mock_redis.return_value = mock_redis_client

                    with patch('app.workers.tasks.AsyncSessionLocal', TestSessionLocal()):
                        try:
                            await process_credit_application(
                                ctx={},
                                application_id=app_id_str
                            )
                        except Exception:
                            pass

    @pytest.mark.asyncio
    async def test_process_application_unsupported_country(self, test_db, monkeypatch):
        """Test process_credit_application with unsupported country"""
        async with test_db() as db:
            from app.services.application_service import ApplicationService
            from app.schemas.application import ApplicationCreate
            from decimal import Decimal
            service = ApplicationService(db)
            app_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR"
            )
            application = await service.create_application(app_data)
            await db.flush()
            # Refresh before commit to ensure all attributes are loaded
            await db.refresh(application)
            app_id_str = str(application.id)
            await db.commit()

            # Mock get_country_strategy to fail - don't modify the database with invalid country
            def failing_get_strategy(country):
                raise ValueError("Unsupported country")

            # Create a test session factory that uses test_db
            class TestSessionLocal:
                def __call__(self):
                    return test_db()

            with patch('app.workers.tasks.get_country_strategy', side_effect=failing_get_strategy):
                with patch('app.workers.tasks.get_redis') as mock_redis:
                    mock_redis_client = AsyncMock()
                    mock_redis_client.close = AsyncMock()
                    mock_redis.return_value = mock_redis_client

                    with patch('app.workers.tasks.AsyncSessionLocal', TestSessionLocal()):
                        with pytest.raises(ValidationError):
                            await process_credit_application(
                                ctx={},
                                application_id=app_id_str
                            )

    @pytest.mark.asyncio
    async def test_process_application_database_error(self, test_db, monkeypatch):
        """Test process_credit_application with database error"""
        from sqlalchemy.exc import OperationalError

        async with test_db() as db:
            from app.services.application_service import ApplicationService
            from app.schemas.application import ApplicationCreate
            from decimal import Decimal
            service = ApplicationService(db)
            app_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR"
            )
            application = await service.create_application(app_data)
            await db.flush()
            # Refresh before commit to ensure all attributes are loaded
            await db.refresh(application)
            app_id_str = str(application.id)
            await db.commit()

            with patch('app.workers.tasks.AsyncSessionLocal') as mock_session:
                mock_db = AsyncMock()
                mock_db.execute = AsyncMock(side_effect=OperationalError("Connection lost", None, None))
                mock_session.return_value.__aenter__.return_value = mock_db

                with patch('app.workers.tasks.get_redis') as mock_redis:
                    mock_redis_client = AsyncMock()
                    mock_redis_client.close = AsyncMock()
                    mock_redis.return_value = mock_redis_client

                    with pytest.raises(DatabaseConnectionError):
                        await process_credit_application(
                            ctx={},
                            application_id=app_id_str
                        )

    @pytest.mark.asyncio
    async def test_process_application_timeout_error(self, test_db, monkeypatch):
        """Test process_credit_application with timeout error"""
        async with test_db() as db:
            from app.services.application_service import ApplicationService
            from app.schemas.application import ApplicationCreate
            from decimal import Decimal
            service = ApplicationService(db)
            app_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR"
            )
            application = await service.create_application(app_data)
            await db.flush()
            # Refresh before commit to ensure all attributes are loaded
            await db.refresh(application)
            app_id_str = str(application.id)
            await db.commit()

            with patch('app.workers.tasks.AsyncSessionLocal') as mock_session:
                mock_db = AsyncMock()
                mock_db.execute = AsyncMock(side_effect=TimeoutError("Request timeout"))
                mock_session.return_value.__aenter__.return_value = mock_db

                with patch('app.workers.tasks.get_redis') as mock_redis:
                    mock_redis_client = AsyncMock()
                    mock_redis_client.close = AsyncMock()
                    mock_redis.return_value = mock_redis_client

                    with pytest.raises(NetworkTimeoutError):
                        await process_credit_application(
                            ctx={},
                            application_id=app_id_str
                        )

    @pytest.mark.asyncio
    async def test_process_application_unexpected_error(self, test_db, monkeypatch):
        """Test process_credit_application with unexpected error"""
        async with test_db() as db:
            from app.services.application_service import ApplicationService
            from app.schemas.application import ApplicationCreate
            from decimal import Decimal
            service = ApplicationService(db)
            app_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR"
            )
            application = await service.create_application(app_data)
            await db.flush()
            # Refresh before commit to ensure all attributes are loaded
            await db.refresh(application)
            app_id_str = str(application.id)
            await db.commit()

            with patch('app.workers.tasks.AsyncSessionLocal') as mock_session:
                mock_db = AsyncMock()
                mock_db.execute = AsyncMock(side_effect=RuntimeError("Unexpected error"))
                mock_session.return_value.__aenter__.return_value = mock_db

                with patch('app.workers.tasks.get_redis') as mock_redis:
                    mock_redis_client = AsyncMock()
                    mock_redis_client.close = AsyncMock()
                    mock_redis.return_value = mock_redis_client

                    with pytest.raises(RuntimeError):
                        await process_credit_application(
                            ctx={},
                            application_id=app_id_str
                        )

    @pytest.mark.asyncio
    async def test_send_webhook_notification_success(self, test_db, monkeypatch):
        """Test send_webhook_notification successfully"""
        async with test_db() as db:
            from app.services.application_service import ApplicationService
            from app.schemas.application import ApplicationCreate
            from decimal import Decimal
            service = ApplicationService(db)
            app_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR"
            )
            application = await service.create_application(app_data)
            await db.flush()
            # Refresh before commit to ensure all attributes are loaded
            await db.refresh(application)
            app_id_str = str(application.id)
            await db.commit()

        with patch('app.workers.tasks.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            await send_webhook_notification(
                ctx={},
                application_id=app_id_str,
                webhook_url="https://example.com/webhook"
            )

            mock_client_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_webhook_notification_http_error(self, test_db, monkeypatch):
        """Test send_webhook_notification with HTTP error"""
        import httpx

        async with test_db() as db:
            from app.services.application_service import ApplicationService
            from app.schemas.application import ApplicationCreate
            from decimal import Decimal
            service = ApplicationService(db)
            app_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR"
            )
            application = await service.create_application(app_data)
            await db.flush()
            # Refresh before commit to ensure all attributes are loaded
            await db.refresh(application)
            app_id_str = str(application.id)
            await db.commit()

        with patch('app.workers.tasks.httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Server error", request=MagicMock(), response=mock_response))
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            await send_webhook_notification(
                ctx={},
                application_id=app_id_str,
                webhook_url="https://example.com/webhook"
            )

    @pytest.mark.asyncio
    async def test_cleanup_old_webhook_events(self, test_db):
        """Test cleanup_old_webhook_events"""
        async with test_db() as db:
            from app.models.webhook_event import WebhookEvent, WebhookEventStatus
            from app.services.application_service import ApplicationService
            from app.schemas.application import ApplicationCreate
            from datetime import datetime, timedelta, UTC
            from decimal import Decimal

            # Create a valid application first
            service = ApplicationService(db)
            app_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR"
            )
            application = await service.create_application(app_data)
            await db.flush()
            # Refresh to ensure all attributes are loaded
            await db.refresh(application)
            # Extract UUID as Python native type
            application_id = application.id
            await db.commit()

            old_event = WebhookEvent(
                idempotency_key="old-key-1",
                application_id=application_id,
                payload={},
                status=WebhookEventStatus.PROCESSED,
                processed_at=datetime.now(UTC) - timedelta(days=100)
            )
            db.add(old_event)
            await db.commit()

        # Create a test session factory that uses test_db
        class TestSessionLocal:
            def __call__(self):
                return test_db()

        # Run cleanup (no days_to_keep parameter, uses default TTL)
        with patch('app.workers.tasks.AsyncSessionLocal', TestSessionLocal()):
            result = await cleanup_old_webhook_events(ctx={})

        # Verify cleanup completed
        assert "Deleted" in result or "cleanup" in result.lower()

    @pytest.mark.asyncio
    async def test_cleanup_old_applications(self, test_db):
        """Test cleanup_old_applications task"""
        # Should run without errors
        result = await cleanup_old_applications(ctx={})
        assert result == "Cleanup completed"

    @pytest.mark.asyncio
    async def test_monitor_table_partitioning_success(self, test_db, monkeypatch):
        """Test monitor_table_partitioning task successfully"""
        # Mock monitor_and_partition_tables
        with patch('app.workers.tasks.monitor_and_partition_tables') as mock_monitor:
            mock_monitor.return_value = {
                'tables_checked': 3,
                'tables_partitioned': 1,
                'tables_already_partitioned': 1,
                'tables_below_threshold': 1,
                'errors': []
            }
            
            result = await monitor_table_partitioning(ctx={})
            
            assert result['status'] == 'completed'
            assert result['summary']['tables_checked'] == 3

    @pytest.mark.asyncio
    async def test_monitor_table_partitioning_with_errors(self, test_db, monkeypatch):
        """Test monitor_table_partitioning with errors"""
        # Mock monitor_and_partition_tables to return errors
        with patch('app.workers.tasks.monitor_and_partition_tables') as mock_monitor:
            mock_monitor.return_value = {
                'tables_checked': 3,
                'tables_partitioned': 0,
                'tables_already_partitioned': 0,
                'tables_below_threshold': 0,
                'errors': ['Error 1', 'Error 2']
            }
            
            result = await monitor_table_partitioning(ctx={})
            
            assert result['status'] == 'completed'
            assert len(result['summary']['errors']) == 2

    @pytest.mark.asyncio
    async def test_monitor_table_partitioning_database_error(self, test_db, monkeypatch):
        """Test monitor_table_partitioning with database error"""
        from sqlalchemy.exc import OperationalError
        
        # Mock to raise database error
        with patch('app.workers.tasks.monitor_and_partition_tables') as mock_monitor:
            mock_monitor.side_effect = OperationalError("Connection lost", None, None)
            
            with pytest.raises(DatabaseConnectionError):
                await monitor_table_partitioning(ctx={})

    @pytest.mark.asyncio
    async def test_monitor_table_partitioning_unexpected_error(self, test_db, monkeypatch):
        """Test monitor_table_partitioning with unexpected error"""
        # Mock to raise unexpected error
        with patch('app.workers.tasks.monitor_and_partition_tables') as mock_monitor:
            mock_monitor.side_effect = RuntimeError("Unexpected error")
            
            with pytest.raises(RuntimeError):
                await monitor_table_partitioning(ctx={})
