"""
Deep coverage tests for applications endpoint.

These tests focus on covering remaining uncovered lines in applications.py.
"""

import pytest
from uuid import uuid4

from app.services import application_service
from app.services.cache_service import CacheService


class TestApplicationsEndpointDeepCoverage:
    """Tests to cover remaining applications endpoint lines"""

    @pytest.mark.asyncio
    async def test_delete_application_not_found(self, client, admin_headers):
        """Test delete application that doesn't exist"""
        fake_id = uuid4()

        response = await client.delete(f"/api/v1/applications/{fake_id}", headers=admin_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_application_unexpected_error(self, client, auth_headers, admin_headers, monkeypatch):
        """Test delete application with unexpected error"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]


        async def mock_delete_raises_exception(self, application_id):
            raise RuntimeError("Database connection lost")

        monkeypatch.setattr(application_service.ApplicationService, "delete_application", mock_delete_raises_exception)

        response = await client.delete(f"/api/v1/applications/{app_id}", headers=admin_headers)

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_get_audit_logs_application_not_found(self, client, auth_headers):
        """Test get audit logs for non-existent application"""
        fake_id = uuid4()

        response = await client.get(
            f"/api/v1/applications/{fake_id}/audit",
            headers=auth_headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_audit_logs_success(self, client, auth_headers, admin_headers):
        """Test get audit logs for existing application"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        await client.patch(
            f"/api/v1/applications/{app_id}",
            json={"status": "VALIDATING"},
            headers=admin_headers
        )

        response = await client.get(
            f"/api/v1/applications/{app_id}/audit",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "audit_logs" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_country_statistics_success(self, client, auth_headers):
        """Test get country statistics"""
        await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        response = await client.get("/api/v1/applications/stats/country/ES", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "country" in data
        assert data["country"] == "ES"
        assert "total_applications" in data
        assert "total_amount" in data

    @pytest.mark.asyncio
    async def test_get_country_statistics_invalid_country(self, client, auth_headers):
        """Test get country statistics with invalid country code"""
        response = await client.get("/api/v1/applications/stats/country/XX", headers=auth_headers)

        assert response.status_code == 400
        assert "not supported" in response.json()["detail"].lower() or "invalid" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_supported_countries_endpoint(self, client):
        """Test get supported countries endpoint"""
        response = await client.get("/api/v1/applications/meta/supported-countries")

        assert response.status_code == 200
        data = response.json()
        assert "supported_countries" in data
        assert "total" in data
        assert len(data["supported_countries"]) > 0

    @pytest.mark.asyncio
    async def test_update_application_cache_invalidation_error(self, client, auth_headers, admin_headers, monkeypatch):
        """Test update application when cache invalidation fails"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        async def mock_invalidate_raises(self, application_id):
            raise Exception("Cache connection lost")

        monkeypatch.setattr(CacheService, "invalidate_application", mock_invalidate_raises)

        response = await client.patch(
            f"/api/v1/applications/{app_id}",
            json={"status": "VALIDATING"},
            headers=admin_headers
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_application_unexpected_exception(self, client, auth_headers, admin_headers, monkeypatch):
        """Test update application with unexpected exception during update"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        async def mock_update_raises_exception(self, application_id, update_data):
            raise RuntimeError("Unexpected database error")

        monkeypatch.setattr(application_service.ApplicationService, "update_application", mock_update_raises_exception)

        response = await client.patch(
            f"/api/v1/applications/{app_id}",
            json={"status": "VALIDATING"},
            headers=admin_headers
        )

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_get_application_not_found(self, client, auth_headers):
        """Test get application that doesn't exist"""
        fake_id = uuid4()

        response = await client.get(f"/api/v1/applications/{fake_id}", headers=auth_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
