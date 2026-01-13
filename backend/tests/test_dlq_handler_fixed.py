"""Tests for Dead Letter Queue Handler.

Tests for the DLQ handler that processes failed jobs after maximum retries.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

from app.workers.dlq_handler import handle_failed_job
from app.models.failed_job import FailedJob


class TestDLQHandler:
    """Test suite for DLQ handler"""

    @pytest.mark.asyncio
    async def test_handle_failed_job_with_job_id(self, test_db, monkeypatch):
        """Test handling a failed job with job_id attribute"""
        # Create a mock job object with job_id
        # Use spec to prevent MagicMock from creating mock attributes
        mock_job = MagicMock(spec=['job_id', 'function', 'args', 'kwargs', 'retry_count', 'max_retries', 'metadata'])
        mock_job.job_id = "test-job-123"
        mock_job.function = "test_task"
        mock_job.args = ["arg1", "arg2"]
        mock_job.kwargs = {"key": "value"}
        mock_job.retry_count = 3
        mock_job.max_retries = 3
        mock_job.metadata = {"trace_context": "test-trace"}

        mock_exc = ValueError("Test error")

        ctx = {}

        # Mock AsyncSessionLocal to use test_db
        from app.workers import dlq_handler
        
        # Create a session from test_db
        async with test_db() as session:
            # Mock AsyncSessionLocal to return this session
            class MockSessionLocal:
                def __call__(self):
                    return self
                
                async def __aenter__(self):
                    return session
                
                async def __aexit__(self, *args):
                    pass  # Don't close, test_db handles it
            
            mock_session_local = MockSessionLocal()
            monkeypatch.setattr(dlq_handler, "AsyncSessionLocal", mock_session_local)

            # Call the handler
            await handle_failed_job(ctx, mock_job, mock_exc)

            # Commit to persist
            await session.commit()

            # Verify the failed job was created
            from sqlalchemy import select
            result = await session.execute(select(FailedJob).where(FailedJob.job_id == "test-job-123"))
            failed_job = result.scalar_one_or_none()
            
            assert failed_job is not None
            assert failed_job.job_id == "test-job-123"
            assert failed_job.task_name == "test_task"
            assert failed_job.retry_count == "3"  # Stored as string
            assert failed_job.max_retries == "3"  # Stored as string
            assert "Test error" in failed_job.error_message

    @pytest.mark.asyncio
    async def test_handle_failed_job_with_id_attribute(self, test_db, monkeypatch):
        """Test handling a failed job with id attribute (alternative attribute name)"""
        # Create a mock job object with id instead of job_id
        mock_job = MagicMock(spec=['id', 'function', 'args', 'kwargs', 'retry_count', 'max_retries', 'metadata'])
        mock_job.id = "test-job-456"
        mock_job.function = "test_task_2"
        mock_job.args = []
        mock_job.kwargs = {}
        mock_job.retry_count = 2
        mock_job.max_retries = 3
        mock_job.metadata = None

        mock_exc = RuntimeError("Runtime error")

        ctx = {}

        from app.workers import dlq_handler
        
        async with test_db() as session:
            class MockSessionLocal:
                def __call__(self):
                    return self
                
                async def __aenter__(self):
                    return session
                
                async def __aexit__(self, *args):
                    pass
            
            mock_session_local = MockSessionLocal()
            monkeypatch.setattr(dlq_handler, "AsyncSessionLocal", mock_session_local)

            await handle_failed_job(ctx, mock_job, mock_exc)
            await session.commit()

            from sqlalchemy import select
            result = await session.execute(select(FailedJob).where(FailedJob.job_id == "test-job-456"))
            failed_job = result.scalar_one_or_none()
            
            assert failed_job is not None
            assert failed_job.job_id == "test-job-456"
            assert failed_job.task_name == "test_task_2"

    @pytest.mark.asyncio
    async def test_handle_failed_job_with_unknown_job_id(self, test_db, monkeypatch):
        """Test handling a failed job with unknown job_id"""
        # Create a mock job object without job_id or id
        mock_job = MagicMock(spec=['function', 'args', 'kwargs', 'retry_count', 'max_retries', 'metadata'])
        # Don't set job_id or id - they should not exist
        mock_job.function = "test_task_3"
        mock_job.args = []
        mock_job.kwargs = {}
        mock_job.retry_count = None
        mock_job.max_retries = None
        mock_job.metadata = None

        mock_exc = KeyError("Key error")

        ctx = {"retry_count": 1, "max_tries": 3}

        from app.workers import dlq_handler
        
        async with test_db() as session:
            class MockSessionLocal:
                def __call__(self):
                    return self
                
                async def __aenter__(self):
                    return session
                
                async def __aexit__(self, *args):
                    pass
            
            mock_session_local = MockSessionLocal()
            monkeypatch.setattr(dlq_handler, "AsyncSessionLocal", mock_session_local)

            await handle_failed_job(ctx, mock_job, mock_exc)
            await session.commit()

            from sqlalchemy import select
            result = await session.execute(select(FailedJob).where(FailedJob.job_id == "unknown"))
            failed_job = result.scalar_one_or_none()
            
            assert failed_job is not None
            assert failed_job.job_id == "unknown"
            assert failed_job.retry_count == "1"
            assert failed_job.max_retries == "3"

    @pytest.mark.asyncio
    async def test_handle_failed_job_with_task_name_attribute(self, test_db, monkeypatch):
        """Test handling a failed job with task_name attribute"""
        # Create a mock job object with task_name instead of function
        mock_job = MagicMock(spec=['job_id', 'task_name', 'function', 'args', 'kwargs', 'retry_count', 'max_retries', 'metadata'])
        mock_job.job_id = "test-job-789"
        mock_job.task_name = "alternative_task_name"
        mock_job.function = None
        mock_job.args = []
        mock_job.kwargs = {}
        mock_job.retry_count = 0
        mock_job.max_retries = 3
        mock_job.metadata = None

        mock_exc = Exception("Generic error")

        ctx = {}

        from app.workers import dlq_handler
        
        async with test_db() as session:
            class MockSessionLocal:
                def __call__(self):
                    return self
                
                async def __aenter__(self):
                    return session
                
                async def __aexit__(self, *args):
                    pass
            
            mock_session_local = MockSessionLocal()
            monkeypatch.setattr(dlq_handler, "AsyncSessionLocal", mock_session_local)

            await handle_failed_job(ctx, mock_job, mock_exc)
            await session.commit()

            from sqlalchemy import select
            result = await session.execute(select(FailedJob).where(FailedJob.job_id == "test-job-789"))
            failed_job = result.scalar_one_or_none()
            
            assert failed_job is not None
            assert failed_job.task_name == "alternative_task_name"

    @pytest.mark.asyncio
    async def test_handle_failed_job_with_trace_context_in_kwargs(self, test_db, monkeypatch):
        """Test handling a failed job with trace_context in kwargs"""
        mock_job = MagicMock(spec=['job_id', 'function', 'args', 'kwargs', 'retry_count', 'max_retries', 'metadata'])
        mock_job.job_id = "test-job-trace"
        mock_job.function = "test_task"
        mock_job.args = []
        mock_job.kwargs = {"trace_context": "trace-from-kwargs"}
        mock_job.metadata = None
        mock_job.retry_count = 0
        mock_job.max_retries = 3

        mock_exc = ValueError("Error")

        ctx = {}

        from app.workers import dlq_handler
        
        async with test_db() as session:
            class MockSessionLocal:
                def __call__(self):
                    return self
                
                async def __aenter__(self):
                    return session
                
                async def __aexit__(self, *args):
                    pass
            
            mock_session_local = MockSessionLocal()
            monkeypatch.setattr(dlq_handler, "AsyncSessionLocal", mock_session_local)

            await handle_failed_job(ctx, mock_job, mock_exc)
            await session.commit()

            from sqlalchemy import select
            result = await session.execute(select(FailedJob).where(FailedJob.job_id == "test-job-trace"))
            failed_job = result.scalar_one_or_none()
            
            assert failed_job is not None
            assert failed_job.job_metadata == {"trace_context": "trace-from-kwargs"}

    @pytest.mark.asyncio
    async def test_handle_failed_job_with_trace_context_in_ctx(self, test_db, monkeypatch):
        """Test handling a failed job with trace_context in context"""
        mock_job = MagicMock(spec=['job_id', 'function', 'args', 'kwargs', 'retry_count', 'max_retries', 'metadata'])
        mock_job.job_id = "test-job-ctx-trace"
        mock_job.function = "test_task"
        mock_job.args = []
        mock_job.kwargs = {}
        mock_job.metadata = None
        mock_job.retry_count = 0
        mock_job.max_retries = 3

        mock_exc = ValueError("Error")

        ctx = {"trace_context": "trace-from-ctx"}

        from app.workers import dlq_handler
        
        async with test_db() as session:
            class MockSessionLocal:
                def __call__(self):
                    return self
                
                async def __aenter__(self):
                    return session
                
                async def __aexit__(self, *args):
                    pass
            
            mock_session_local = MockSessionLocal()
            monkeypatch.setattr(dlq_handler, "AsyncSessionLocal", mock_session_local)

            await handle_failed_job(ctx, mock_job, mock_exc)
            await session.commit()

            from sqlalchemy import select
            result = await session.execute(select(FailedJob).where(FailedJob.job_id == "test-job-ctx-trace"))
            failed_job = result.scalar_one_or_none()
            
            assert failed_job is not None
            assert failed_job.job_metadata == {"trace_context": "trace-from-ctx"}

    @pytest.mark.asyncio
    async def test_handle_failed_job_database_error(self, test_db, monkeypatch):
        """Test handling a failed job when database operation fails"""
        mock_job = MagicMock()
        mock_job.job_id = "test-job-db-error"
        mock_job.function = "test_task"
        mock_job.args = []
        mock_job.kwargs = {}

        mock_exc = ValueError("Original error")

        ctx = {}

        from app.workers import dlq_handler
        
        async with test_db() as session:
            # Mock create_failed_job to raise an exception
            async def mock_create_failed_job(*args, **kwargs):
                raise Exception("Database error")
            
            with patch.object(dlq_handler.FailedJobService, 'create_failed_job', side_effect=mock_create_failed_job):
                class MockSessionLocal:
                    def __call__(self):
                        return self
                    
                    async def __aenter__(self):
                        return session
                    
                    async def __aexit__(self, *args):
                        pass
                
                mock_session_local = MockSessionLocal()
                monkeypatch.setattr(dlq_handler, "AsyncSessionLocal", mock_session_local)

                # Call the handler - should not raise exception
                await handle_failed_job(ctx, mock_job, mock_exc)

    @pytest.mark.asyncio
    async def test_handle_failed_job_handler_error(self, monkeypatch):
        """Test handling when the handler itself raises an error"""
        mock_job = MagicMock()
        mock_job.job_id = "test-job-handler-error"
        mock_exc = ValueError("Test error")

        ctx = {}

        # Mock AsyncSessionLocal to raise an exception
        from app.workers import dlq_handler
        
        class FailingSessionLocal:
            def __call__(self):
                return self
            
            async def __aenter__(self):
                raise Exception("Handler error")
            
            async def __aexit__(self, *args):
                pass
        
        monkeypatch.setattr(dlq_handler, "AsyncSessionLocal", FailingSessionLocal())
        
        # Call the handler - should not raise exception (catches all errors)
        await handle_failed_job(ctx, mock_job, mock_exc)

    @pytest.mark.asyncio
    async def test_handle_failed_job_with_empty_args_kwargs(self, test_db, monkeypatch):
        """Test handling a failed job with empty args and kwargs"""
        mock_job = MagicMock(spec=['job_id', 'function', 'args', 'kwargs', 'retry_count', 'max_retries', 'metadata'])
        mock_job.job_id = "test-job-empty"
        mock_job.function = "test_task"
        mock_job.args = []
        mock_job.kwargs = {}
        mock_job.retry_count = 0
        mock_job.max_retries = 3
        mock_job.metadata = None

        mock_exc = ValueError("Error")

        ctx = {}

        from app.workers import dlq_handler
        
        async with test_db() as session:
            class MockSessionLocal:
                def __call__(self):
                    return self
                
                async def __aenter__(self):
                    return session
                
                async def __aexit__(self, *args):
                    pass
            
            mock_session_local = MockSessionLocal()
            monkeypatch.setattr(dlq_handler, "AsyncSessionLocal", mock_session_local)

            await handle_failed_job(ctx, mock_job, mock_exc)
            await session.commit()

            from sqlalchemy import select
            result = await session.execute(select(FailedJob).where(FailedJob.job_id == "test-job-empty"))
            failed_job = result.scalar_one_or_none()
            
            assert failed_job is not None
            assert failed_job.job_args == []
            assert failed_job.job_kwargs == {}
