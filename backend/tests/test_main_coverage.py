"""Tests for main.py to improve coverage.

Tests for application startup, shutdown, and OpenAPI schema customization.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

from app.main import app, lifespan, custom_openapi


class TestMainCoverage:
    """Test suite for main.py coverage"""

    @pytest.mark.asyncio
    async def test_lifespan_startup(self, monkeypatch):
        """Test application lifespan startup"""
        # Mock all startup dependencies
        with patch('app.main.set_app_info') as mock_set_app_info:
            with patch('app.main.setup_tracing') as mock_setup_tracing:
                async def mock_redis_subscriber():
                    await asyncio.sleep(0.1)
                
                # Create a real task that can be awaited
                mock_task = asyncio.create_task(mock_redis_subscriber())
                with patch('app.main.redis_subscriber', return_value=mock_redis_subscriber()) as mock_redis_sub:
                    with patch('asyncio.create_task', return_value=mock_task) as mock_create_task:
                        # Use async context manager
                        async with lifespan(app) as ctx:
                            # Startup code runs here
                            pass
                        
                        # Verify startup was called
                        mock_set_app_info.assert_called_once()
                        mock_setup_tracing.assert_called_once()
                        mock_create_task.assert_called_once()
                        mock_task.cancel()
                        try:
                            await mock_task
                        except asyncio.CancelledError:
                            pass

    @pytest.mark.asyncio
    async def test_lifespan_shutdown(self, monkeypatch):
        """Test application lifespan shutdown"""
        with patch('app.main.redis_subscriber') as mock_redis_subscriber:
            # Create a real task-like object that can be cancelled
            async def task_coro():
                try:
                    await asyncio.sleep(10)  # Long sleep to simulate running task
                except asyncio.CancelledError:
                    pass
            mock_task = asyncio.create_task(task_coro())
            
            with patch('asyncio.create_task', return_value=mock_task) as mock_create_task:
                # Use async context manager
                async with lifespan(app) as ctx:
                    # Startup code runs here
                    pass
                # Shutdown code runs here when exiting context
                
                # Verify task was cancelled (it should be cancelled in shutdown)
                assert mock_task.cancelled()

    @pytest.mark.asyncio
    async def test_lifespan_shutdown_cancelled_error(self, monkeypatch):
        """Test application lifespan shutdown with CancelledError"""
        with patch('app.main.redis_subscriber') as mock_redis_subscriber:
            # Create a task that will raise CancelledError when awaited
            async def task_coro():
                await asyncio.sleep(0.1)
                raise asyncio.CancelledError("CancelledError")
                
            mock_task = asyncio.create_task(task_coro())
            mock_task.cancel()  # Cancel it immediately
                
            with patch('asyncio.create_task', return_value=mock_task) as mock_create_task:
                # Use async context manager
                async with lifespan(app) as ctx:
                    # Startup code runs here
                    pass
                # Shutdown code runs here when exiting context
                # CancelledError is caught in the handler
                
                # Verify task was cancelled
                assert mock_task.cancelled()

    def test_custom_openapi_schema_cached(self):
        """Test that OpenAPI schema is cached"""
        # Set cached schema
        app.openapi_schema = {"cached": True}
        
        result = custom_openapi()
        
        assert result == {"cached": True}
        assert app.openapi_schema == {"cached": True}

    def test_custom_openapi_schema_generation(self):
        """Test OpenAPI schema generation and customization"""
        # Clear cached schema
        app.openapi_schema = None
        
        # Mock app.openapi()
        original_openapi = app.openapi
        mock_schema = {
            "info": {"title": "Test API", "version": "1.0.0"},
            "components": {}
        }
        app.openapi = MagicMock(return_value=mock_schema)
        
        try:
            result = custom_openapi()
            
            # Verify schema was customized
            assert "BearerAuth" in result["components"]["securitySchemes"]
            assert "description" in result["info"]
            assert app.openapi_schema is not None
        finally:
            app.openapi = original_openapi
            app.openapi_schema = None

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = await client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "application" in data
        assert "version" in data
        assert "docs" in data
