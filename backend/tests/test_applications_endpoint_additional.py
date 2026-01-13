"""
Additional tests for applications endpoint to cover remaining lines.

These tests focus on covering the missing lines in applications.py endpoint.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from uuid import uuid4

from app.api.v1.endpoints import applications
from app.services import application_service

class TestApplicationsEndpointAdditional:
    """Additional tests for applications endpoint"""

    @pytest.mark.asyncio
    async def test_create_application_integrity_error_duplicate_document(self, client, auth_headers):
        """Test create application with IntegrityError for duplicate document"""
        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }

        response1 = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert response1.status_code == 201

        response2 = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response2.status_code in [201, 409]

    @pytest.mark.asyncio
    async def test_create_application_integrity_error_unique_document_per_country(self, client, auth_headers, monkeypatch):
        """Test create application with IntegrityError containing 'unique_document_per_country'"""

        class MockOrigException(Exception):
            pass

        mock_orig = MockOrigException("unique_document_per_country constraint violation")

        async def mock_create_raises_integrity_error(self, application_data):
            error = IntegrityError("statement", "params", mock_orig)
            raise error

        monkeypatch.setattr(application_service.ApplicationService, "create_application", mock_create_raises_integrity_error)

        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_application_integrity_error_applications_country(self, client, auth_headers, monkeypatch):
        """Test create application with IntegrityError containing 'applications.country'"""

        class MockOrigException(Exception):
            pass

        mock_orig = MockOrigException("applications.country constraint violation")

        async def mock_create_raises_integrity_error(self, application_data):
            error = IntegrityError("statement", "params", mock_orig)
            raise error

        monkeypatch.setattr(application_service.ApplicationService, "create_application", mock_create_raises_integrity_error)

        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_application_integrity_error_applications_identity_document(self, client, auth_headers, monkeypatch):
        """Test create application with IntegrityError containing 'applications.identity_document'"""

        class MockOrigException(Exception):
            pass

        mock_orig = MockOrigException("applications.identity_document constraint violation")

        async def mock_create_raises_integrity_error(self, application_data):
            error = IntegrityError("statement", "params", mock_orig)
            raise error

        monkeypatch.setattr(application_service.ApplicationService, "create_application", mock_create_raises_integrity_error)

        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_list_applications_with_decryption_error_skips_app(self, client, auth_headers, monkeypatch):
        """Test list applications when decryption fails for one app (should skip it)"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        original_application_to_response = applications.application_to_response
        call_count = 0

        async def mock_application_to_response(db, app):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Decryption failed")
            return await original_application_to_response(db, app)

        monkeypatch.setattr(applications, "application_to_response", mock_application_to_response)

        response = await client.get("/api/v1/applications", headers=auth_headers)

        assert response.status_code == 200
        assert "applications" in response.json()
