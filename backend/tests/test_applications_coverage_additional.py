"""
Additional tests for application endpoints to further improve coverage.

These tests focus on additional edge cases and error handling scenarios.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from uuid import uuid4


class TestApplicationAdditionalCoverage:
    """Additional tests for application endpoints"""

    @pytest.mark.asyncio
    async def test_create_application_integrity_error_other(self, client, auth_headers, monkeypatch):
        """Test create application with IntegrityError that's not a duplicate"""
        # Mock repository to raise IntegrityError that's not a duplicate
        async def mock_create_raises_integrity_error(self, application_data):
            # Simulate IntegrityError that's not a duplicate (e.g., foreign key violation)
            error = IntegrityError("statement", "params", Exception("foreign key constraint violation"))
            raise error

        from app.repositories import application_repository
        monkeypatch.setattr(application_repository.ApplicationRepository, "create", mock_create_raises_integrity_error)

        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        # Should return 400 (bad request) for other integrity errors
        assert response.status_code == 400
        assert "Database constraint violation" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_application_unexpected_exception(self, client, auth_headers, monkeypatch):
        """Test create application with unexpected exception"""
        # Mock service to raise unexpected exception
        async def mock_create_raises_exception(self, application_data):
            raise RuntimeError("Unexpected database error")

        from app.services import application_service
        monkeypatch.setattr(application_service.ApplicationService, "create_application", mock_create_raises_exception)

        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        # Should return 500 (internal server error)
        assert response.status_code == 500
        assert "Internal server error" in response.json()["detail"] or "INTERNAL_SERVER_ERROR" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_application_value_error_handling(self, client, auth_headers, monkeypatch):
        """Test create application with ValueError (validation error)"""
        # Mock service to raise ValueError
        async def mock_create_raises_value_error(self, application_data):
            raise ValueError("Invalid country code")

        from app.services import application_service
        monkeypatch.setattr(application_service.ApplicationService, "create_application", mock_create_raises_value_error)

        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        # Should return 400 (bad request)
        assert response.status_code == 400
        assert "Invalid country code" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_applications_with_country_and_status_filter(self, client, auth_headers):
        """Test listing applications with both country and status filters"""
        # Create applications for different countries
        await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Spanish User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        await client.post("/api/v1/applications", json={
            "country": "MX",
            "full_name": "Mexican User",
            "identity_document": "HERM850101MDFRRR01",
            "requested_amount": 20000.00,
            "monthly_income": 5000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        # List with both filters
        response = await client.get("/api/v1/applications?country=ES&status=PENDING", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # All returned applications should match filters
        for app in data["applications"]:
            assert app["country"] == "ES"
            assert app["status"] == "PENDING"

    @pytest.mark.asyncio
    async def test_list_applications_empty_result_with_filters(self, client, auth_headers):
        """Test listing applications with filters that return no results"""
        # List with filter that matches nothing (use valid country but status that doesn't exist)
        # First create an application with PENDING status
        await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        # Now filter for APPROVED status (which doesn't exist yet)
        response = await client.get("/api/v1/applications?country=ES&status=APPROVED", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["applications"]) == 0

    @pytest.mark.asyncio
    async def test_get_application_with_invalid_uuid_format(self, client, auth_headers):
        """Test getting application with invalid UUID format"""
        # Try to get with invalid UUID
        response = await client.get("/api/v1/applications/invalid-uuid-format", headers=auth_headers)

        # Should return 422 (validation error) for invalid UUID format
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_application_success(self, client, auth_headers, admin_headers):
        """Test successful deletion of application"""
        # Create an application
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        # Delete application
        response = await client.delete(f"/api/v1/applications/{app_id}", headers=admin_headers)

        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"].lower() or "success" in response.json()["message"].lower()

        # Verify application is deleted (should return 404)
        get_response = await client.get(f"/api/v1/applications/{app_id}", headers=auth_headers)
        assert get_response.status_code == 404
