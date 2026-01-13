"""
Additional tests for rate limiting to improve coverage.

These tests focus on edge cases and error handling scenarios.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request
from jose import jwt

from app.core.config import settings
from app.core.rate_limiting import _extract_user_id_from_request, get_rate_limit_key


class TestRateLimiting:
    """Test rate limiting key generation"""

    def test_get_rate_limit_key_with_valid_token(self):
        """Test rate limit key generation with valid JWT token"""
        # Create a valid token
        token = jwt.encode(
            {"sub": "test-user-123", "email": "test@example.com", "role": "user"},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM
        )

        # Create a mock request with Authorization header
        request = MagicMock(spec=Request)
        request.headers = {
            "Authorization": f"Bearer {token}",
        }

        # Mock get_remote_address to return a fixed IP
        with patch("app.core.rate_limiting.get_remote_address", return_value="192.168.1.1"):
            key = get_rate_limit_key(request)

        # Should include both IP and user_id
        assert "ip:192.168.1.1" in key
        assert "user:test-user-123" in key

    def test_get_rate_limit_key_without_token(self):
        """Test rate limit key generation without token (IP only)"""
        # Create a mock request without Authorization header
        request = MagicMock(spec=Request)
        request.headers = {}

        # Mock get_remote_address to return a fixed IP
        with patch("app.core.rate_limiting.get_remote_address", return_value="192.168.1.1"):
            key = get_rate_limit_key(request)

        # Should only include IP
        assert key == "ip:192.168.1.1"
        assert "user:" not in key

    def test_get_rate_limit_key_with_invalid_token(self):
        """Test rate limit key generation with invalid JWT token"""
        # Create a mock request with invalid token
        request = MagicMock(spec=Request)
        request.headers = {
            "Authorization": "Bearer invalid-token-12345",
        }

        # Mock get_remote_address to return a fixed IP
        with patch("app.core.rate_limiting.get_remote_address", return_value="192.168.1.1"):
            key = get_rate_limit_key(request)

        # Should fall back to IP-only (invalid token is ignored)
        assert key == "ip:192.168.1.1"
        assert "user:" not in key

    def test_get_rate_limit_key_with_expired_token(self):
        """Test rate limit key generation with expired JWT token"""
        from datetime import datetime, timedelta, timezone

        # Create an expired token
        token = jwt.encode(
            {
                "sub": "test-user-123",
                "email": "test@example.com",
                "role": "user",
                "exp": datetime.now(timezone.utc) - timedelta(hours=1)  # Expired 1 hour ago
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM
        )

        # Create a mock request with expired token
        request = MagicMock(spec=Request)
        request.headers = {
            "Authorization": f"Bearer {token}",
        }

        # Mock get_remote_address to return a fixed IP
        with patch("app.core.rate_limiting.get_remote_address", return_value="192.168.1.1"):
            key = get_rate_limit_key(request)

        # Should fall back to IP-only (expired token is ignored)
        assert key == "ip:192.168.1.1"
        assert "user:" not in key

    def test_get_rate_limit_key_with_malformed_auth_header(self):
        """Test rate limit key generation with malformed Authorization header"""
        # Test various malformed headers
        test_cases = [
            "NotBearer token123",  # Missing "Bearer"
            "token123",  # No "Bearer" prefix
            "Bearer",  # No token
            "Bearer token1 token2",  # Multiple tokens
        ]

        for auth_header in test_cases:
            request = MagicMock(spec=Request)
            request.headers = {
                "Authorization": auth_header,
            }

            # Mock get_remote_address to return a fixed IP
            with patch("app.core.rate_limiting.get_remote_address", return_value="192.168.1.1"):
                key = get_rate_limit_key(request)

            # Should fall back to IP-only
            assert key == "ip:192.168.1.1"
            assert "user:" not in key

    def test_get_rate_limit_key_with_token_no_sub(self):
        """Test rate limit key generation with token that has no 'sub' field"""
        # Create a token without 'sub' field
        token = jwt.encode(
            {"email": "test@example.com", "role": "user"},  # No 'sub'
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM
        )

        # Create a mock request
        request = MagicMock(spec=Request)
        request.headers = {
            "Authorization": f"Bearer {token}",
        }

        # Mock get_remote_address to return a fixed IP
        with patch("app.core.rate_limiting.get_remote_address", return_value="192.168.1.1"):
            key = get_rate_limit_key(request)

        # Should fall back to IP-only (no 'sub' field)
        assert key == "ip:192.168.1.1"
        assert "user:" not in key

    def test_extract_user_id_from_request_valid(self):
        """Test extracting user_id from valid request"""
        # Create a valid token
        token = jwt.encode(
            {"sub": "test-user-456", "email": "test@example.com", "role": "user"},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM
        )

        # Create a mock request
        request = MagicMock(spec=Request)
        request.headers = {
            "Authorization": f"Bearer {token}"
        }

        user_id = _extract_user_id_from_request(request)

        assert user_id == "test-user-456"

    def test_extract_user_id_from_request_no_header(self):
        """Test extracting user_id when no Authorization header"""
        request = MagicMock(spec=Request)
        request.headers = {}

        user_id = _extract_user_id_from_request(request)

        assert user_id is None

    def test_extract_user_id_from_request_invalid_token(self):
        """Test extracting user_id with invalid token"""
        request = MagicMock(spec=Request)
        request.headers = {
            "Authorization": "Bearer invalid-token"
        }

        user_id = _extract_user_id_from_request(request)

        assert user_id is None

    def test_extract_user_id_from_request_wrong_secret(self):
        """Test extracting user_id with token signed with wrong secret"""
        # Create token with wrong secret
        token = jwt.encode(
            {"sub": "test-user-789", "email": "test@example.com", "role": "user"},
            "wrong-secret-key",
            algorithm=settings.JWT_ALGORITHM
        )

        request = MagicMock(spec=Request)
        request.headers = {
            "Authorization": f"Bearer {token}"
        }

        user_id = _extract_user_id_from_request(request)

        # Should return None (token verification fails)
        assert user_id is None

    def test_extract_user_id_from_request_exception_handling(self, monkeypatch):
        """Test that exceptions in extraction don't break rate limiting"""
        # Mock jwt.decode to raise an exception
        def failing_decode(*args, **kwargs):
            raise Exception("Unexpected error")

        monkeypatch.setattr("app.core.rate_limiting.jwt.decode", failing_decode)

        request = MagicMock(spec=Request)
        request.headers = {
            "Authorization": "Bearer some-token"
        }

        user_id = _extract_user_id_from_request(request)

        # Should return None gracefully (not raise exception)
        assert user_id is None
