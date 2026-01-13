"""Tests for webhook rate limiting coverage.

Tests to cover the rate limiting application logic in webhooks.py.
"""

import pytest
from unittest.mock import patch, MagicMock
import os

from app.api.v1.endpoints.webhooks import apply_rate_limit_if_needed


class TestWebhookRateLimiting:
    """Test suite for webhook rate limiting"""

    def test_apply_rate_limit_if_needed_in_test_environment(self):
        """Test that rate limiting is not applied in test environment"""
        # The function should return the original function unchanged in test environment
        def test_func():
            return "test"
        
        # In test environment (set by conftest.py), rate limiting should not be applied
        result = apply_rate_limit_if_needed(test_func)
        
        # Should return the same function (not wrapped)
        assert result == test_func

    def test_apply_rate_limit_if_needed_in_production(self, monkeypatch):
        """Test that rate limiting is applied in production environment"""
        # Temporarily change environment to production
        original_env = os.environ.get("ENVIRONMENT")
        
        try:
            # Mock settings to return production environment
            from app.core import config
            original_settings_env = config.settings.ENVIRONMENT
            
            # Patch the settings object
            with patch.object(config.settings, 'ENVIRONMENT', 'production'):
                def test_func(request):
                    return "test"
                
                # In production, rate limiting should be applied
                result = apply_rate_limit_if_needed(test_func)
                
                # Should return a wrapped function (not the same object)
                assert result != test_func
                # The wrapped function should be callable
                assert callable(result)
            
        finally:
            # Restore original environment
            if original_env:
                os.environ["ENVIRONMENT"] = original_env
            else:
                os.environ.pop("ENVIRONMENT", None)
