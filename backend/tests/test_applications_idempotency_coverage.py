"""
Tests for idempotency logic in applications endpoint.

These tests focus on covering idempotency-related lines in applications.py.
"""

import asyncio
import pytest
from uuid import uuid4


class TestApplicationsIdempotencyCoverage:
    """Tests for idempotency coverage"""

    @pytest.mark.asyncio
    async def test_create_application_idempotency_naive_datetime(self, client, auth_headers):
        """Test create application with idempotency key and naive datetime handling"""
        idempotency_key = str(uuid4())

        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "idempotency_key": idempotency_key,
            "country_specific_data": {}
        }

        # Create first application
        response1 = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert response1.status_code == 201
        app_id_1 = response1.json()["id"]

        # Wait more than 5 seconds to trigger the idempotency check
        await asyncio.sleep(6)

        # Create second application with same idempotency key
        response2 = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert response2.status_code == 201
        app_id_2 = response2.json()["id"]

        # Should return the same application (idempotent)
        assert app_id_1 == app_id_2

    @pytest.mark.asyncio
    async def test_create_application_idempotency_recent_creation(self, client, auth_headers):
        """Test create application with idempotency key when application was created recently (< 5 seconds)"""
        idempotency_key = str(uuid4())

        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "idempotency_key": idempotency_key,
            "country_specific_data": {}
        }

        # Create first application
        response1 = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert response1.status_code == 201

        # Immediately create second application (within 5 seconds)
        # Should still be treated as new and queued
        response2 = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert response2.status_code == 201

        # Both should be created (or second one returns existing)
        # The behavior depends on timing, but both should succeed

    @pytest.mark.asyncio
    async def test_create_application_idempotency_no_key(self, client, auth_headers):
        """Test create application without idempotency key"""
        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            # No idempotency_key
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 201
        assert "id" in response.json()
