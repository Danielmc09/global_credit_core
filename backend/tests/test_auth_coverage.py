"""
Tests for authentication endpoints to improve coverage.

These tests focus on covering the remaining uncovered lines in auth.py.
"""

import pytest
from jose import jwt

from app.core.config import settings


class TestAuthCoverage:
    """Tests for authentication endpoints"""

    @pytest.mark.asyncio
    async def test_generate_demo_token_invalid_role(self, client):
        """Test generate demo token with invalid role"""
        payload = {
            "user_id": "test-user",
            "email": "test@example.com",
            "role": "invalid_role"  # Invalid role
        }

        response = await client.post("/api/v1/auth/demo-token", json=payload)

        assert response.status_code == 400
        assert "Invalid role" in response.json()["detail"]
        assert "user" in response.json()["detail"].lower() or "admin" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_generate_demo_token_user_role(self, client):
        """Test generate demo token with user role"""
        payload = {
            "user_id": "test-user-123",
            "email": "user@example.com",
            "role": "user"
        }

        response = await client.post("/api/v1/auth/demo-token", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] == "test-user-123"
        assert data["role"] == "user"
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_generate_demo_token_admin_role(self, client):
        """Test generate demo token with admin role"""
        payload = {
            "user_id": "test-admin-456",
            "email": "admin@example.com",
            "role": "admin"
        }

        response = await client.post("/api/v1/auth/demo-token", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] == "test-admin-456"
        assert data["role"] == "admin"
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_generate_demo_token_default_email(self, client):
        """Test generate demo token with default email"""
        payload = {
            "user_id": "test-user-default",
            "role": "user"
            # email not provided, should use default
        }

        response = await client.post("/api/v1/auth/demo-token", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        
        # Decode token to verify email is included with default value
        token = data["access_token"]
        decoded = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
        assert decoded["email"] == "demo@example.com"  # Default email

    @pytest.mark.asyncio
    async def test_generate_demo_token_default_role(self, client):
        """Test generate demo token with default role"""
        payload = {
            "user_id": "test-user-default-role"
            # role not provided, should use default "user"
        }

        response = await client.post("/api/v1/auth/demo-token", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "user"  # Default role

    @pytest.mark.asyncio
    async def test_generate_quick_demo_token(self, client):
        """Test generate quick demo token endpoint"""
        response = await client.get("/api/v1/auth/demo-token/quick")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] == "demo-user"
        assert data["role"] == "user"
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_generate_admin_demo_token(self, client):
        """Test generate admin demo token endpoint"""
        response = await client.get("/api/v1/auth/demo-token/admin")

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] == "demo-admin"
        assert data["role"] == "admin"
        assert "expires_in" in data
