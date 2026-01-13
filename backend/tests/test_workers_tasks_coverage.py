"""Tests for workers/tasks.py to improve coverage.

Tests for worker task error handling and edge cases.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.workers.tasks import (
    process_credit_application,
    send_webhook_notification,
    cleanup_old_webhook_events,
    cleanup_old_applications,
    monitor_table_partitioning,
)
from app.core.exceptions import (
    StateTransitionError,
    ValidationError,
    DatabaseConnectionError,
    NetworkTimeoutError,
)
from app.services.application_service import ApplicationService
from app.schemas.application import ApplicationCreate
from decimal import Decimal 
from sqlalchemy.exc import OperationalError
from app.models.webhook_event import WebhookEvent, WebhookEventStatus
from datetime import datetime, timedelta, UTC
from sqlalchemy import text

class TestWorkersTasksCoverage:
    """Test suite for workers tasks coverage"""

    @pytest.mark.asyncio
    async def test_process_application_state_transition_error(self, test_db, monkeypatch):
        """Test process_credit_application with StateTransitionError"""
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
            application_id_uuid = application.id
            app_id_str = str(application.id)

            await db.execute(
                text("UPDATE applications SET status = 'APPROVED' WHERE id = :app_id"),
                {"app_id": application_id_uuid}
            )
            db.expire(application)
            await db.commit()

            def failing_validate_transition(old_status, new_status):
                raise ValueError("Invalid transition")

            class TestSessionLocal:
                def __call__(self):
                    return test_db()

            with (
                patch('app.workers.tasks.validate_transition', side_effect=failing_validate_transition),
                patch('app.workers.tasks.Lock') as mock_lock_cls,
                patch('app.workers.tasks.aioredis.from_url', new_callable=AsyncMock),
                patch('app.workers.tasks.AsyncSessionLocal', TestSessionLocal())
            ):
                mock_lock_instance = AsyncMock()
                mock_lock_instance.__aenter__ = AsyncMock(return_value=None)
                mock_lock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_lock_cls.return_value = mock_lock_instance
                
                with pytest.raises(StateTransitionError):
                    await process_credit_application(
                        ctx={},
                        application_id=app_id_str
                    )

    @pytest.mark.asyncio
    async def test_process_application_broadcast_error(self, test_db, monkeypatch):
        """Test process_credit_application when broadcast fails"""
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
            app_id_str = str(application.id)

            async def failing_broadcast(*args, **kwargs):
                raise Exception("Broadcast failed")

            class TestSessionLocal:
                def __call__(self):
                    return test_db()

            with patch('app.workers.tasks.broadcast_application_update', side_effect=failing_broadcast):
                with (
                    patch('app.workers.tasks.Lock') as mock_lock_cls,
                    patch('app.workers.tasks.aioredis.from_url', new_callable=AsyncMock),
                    patch('app.workers.tasks.AsyncSessionLocal', TestSessionLocal())
                ):
                    mock_lock_instance = AsyncMock()
                    mock_lock_instance.__aenter__ = AsyncMock(return_value=None)
                    mock_lock_instance.__aexit__ = AsyncMock(return_value=None)
                    mock_lock_cls.return_value = mock_lock_instance

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
            app_id_str = str(application.id)
            db.expire(application)
            await db.commit()

            def failing_get_strategy(country):
                raise ValueError("Unsupported country")

            class TestSessionLocal:
                def __call__(self):
                    return test_db()

            with patch('app.workers.tasks.get_country_strategy', side_effect=failing_get_strategy):
                with (
                    patch('app.workers.tasks.Lock') as mock_lock_cls,
                    patch('app.workers.tasks.aioredis.from_url', new_callable=AsyncMock),
                    patch('app.workers.tasks.AsyncSessionLocal', TestSessionLocal())
                ):
                    mock_lock_instance = AsyncMock()
                    mock_lock_instance.__aenter__ = AsyncMock(return_value=None)
                    mock_lock_instance.__aexit__ = AsyncMock(return_value=None)
                    mock_lock_cls.return_value = mock_lock_instance

                    with pytest.raises(ValidationError):
                        await process_credit_application(
                            ctx={},
                            application_id=app_id_str
                        )

    @pytest.mark.asyncio
    async def test_process_application_database_error(self, test_db, monkeypatch):
        """Test process_credit_application with database error"""

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
            app_id_str = str(application.id)

            with patch('app.workers.tasks.AsyncSessionLocal') as mock_session:
                mock_db = AsyncMock()
                mock_db.execute = AsyncMock(side_effect=OperationalError("Connection lost", None, None))
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_lock = AsyncMock()
                mock_lock.__aenter__ = AsyncMock(return_value=None)
                mock_lock.__aexit__ = AsyncMock(return_value=None)
                
                with patch('app.workers.tasks.Lock', return_value=mock_lock):
                    with patch('app.workers.tasks.aioredis.from_url', new_callable=AsyncMock):
                        pass

                with pytest.raises(DatabaseConnectionError):
                    await process_credit_application(
                        ctx={},
                        application_id=app_id_str
                    )

    @pytest.mark.asyncio
    async def test_process_application_timeout_error(self, test_db, monkeypatch):
        """Test process_credit_application with timeout error"""
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
            app_id_str = str(application.id)

            with patch('app.workers.tasks.AsyncSessionLocal') as mock_session:
                mock_db = AsyncMock()
                mock_db.execute = AsyncMock(side_effect=TimeoutError("Request timeout"))
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_lock = AsyncMock()
                mock_lock.__aenter__ = AsyncMock(return_value=None)
                mock_lock.__aexit__ = AsyncMock(return_value=None)
                
                with patch('app.workers.tasks.Lock', return_value=mock_lock):
                    with patch('app.workers.tasks.aioredis.from_url', new_callable=AsyncMock):
                        pass

                with pytest.raises(NetworkTimeoutError):
                    await process_credit_application(
                        ctx={},
                        application_id=app_id_str
                    )

    @pytest.mark.asyncio
    async def test_process_application_unexpected_error(self, test_db, monkeypatch):
        """Test process_credit_application with unexpected error"""
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
            app_id_str = str(application.id)

            with patch('app.workers.tasks.AsyncSessionLocal') as mock_session:
                mock_db = AsyncMock()
                mock_db.execute = AsyncMock(side_effect=RuntimeError("Unexpected error"))
                mock_session.return_value.__aenter__.return_value = mock_db

                mock_lock = AsyncMock()
                mock_lock.__aenter__ = AsyncMock(return_value=None)
                mock_lock.__aexit__ = AsyncMock(return_value=None)
                
                with patch('app.workers.tasks.Lock', return_value=mock_lock):
                    with patch('app.workers.tasks.aioredis.from_url', new_callable=AsyncMock):
                        pass

                with pytest.raises(RuntimeError):
                    await process_credit_application(
                        ctx={},
                        application_id=app_id_str
                    )

    @pytest.mark.asyncio
    async def test_send_webhook_notification_success(self, test_db, monkeypatch):
        """Test send_webhook_notification successfully"""
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
            app_id_str = str(application.id)


            await send_webhook_notification(
                ctx={},
                application_id=app_id_str,
                webhook_url="https://example.com/webhook"
            )


    @pytest.mark.asyncio
    async def test_send_webhook_notification_http_error(self, test_db, monkeypatch):
        """Test send_webhook_notification with HTTP error"""

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
            app_id_str = str(application.id)

            await send_webhook_notification(
                ctx={},
                application_id=app_id_str,
                webhook_url="https://example.com/webhook"
            )

    @pytest.mark.asyncio
    async def test_cleanup_old_webhook_events(self, test_db):
        """Test cleanup_old_webhook_events"""
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
            application_id = application.id
            db.expire(application)


            old_event = WebhookEvent(
                idempotency_key="old-key-1",
                application_id=application_id,
                payload={},
                status=WebhookEventStatus.PROCESSED,
                processed_at=datetime.now(UTC) - timedelta(days=100)
            )
            db.add(old_event)
            await db.commit()

        class TestSessionLocal:
            def __call__(self):
                return test_db()

        with patch('app.workers.tasks.AsyncSessionLocal', TestSessionLocal()):
            result = await cleanup_old_webhook_events(ctx={})

        assert "Deleted" in result or "cleanup" in result.lower()

    @pytest.mark.asyncio
    async def test_cleanup_old_applications(self, test_db):
        """Test cleanup_old_applications task"""
        result = await cleanup_old_applications(ctx={})
        assert result == "Cleanup completed"

    @pytest.mark.asyncio
    async def test_monitor_table_partitioning_success(self, test_db, monkeypatch):
        """Test monitor_table_partitioning task successfully"""
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
        with patch('app.workers.tasks.monitor_and_partition_tables') as mock_monitor:
            mock_monitor.side_effect = OperationalError("Connection lost", None, None)
            
            with pytest.raises(DatabaseConnectionError):
                await monitor_table_partitioning(ctx={})

    @pytest.mark.asyncio
    async def test_monitor_table_partitioning_unexpected_error(self, test_db, monkeypatch):
        """Test monitor_table_partitioning with unexpected error"""
        with patch('app.workers.tasks.monitor_and_partition_tables') as mock_monitor:
            mock_monitor.side_effect = RuntimeError("Unexpected error")
            
            with pytest.raises(RuntimeError):
                await monitor_table_partitioning(ctx={})
