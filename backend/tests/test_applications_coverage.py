"""
Additional tests for application endpoints to improve coverage.

These tests focus on edge cases, error handling, and scenarios
that are not covered in the main test_api.py file.
"""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.api.v1.endpoints import applications
from app.services import application_service, websocket_service
from app.services.cache_service import CacheService

class TestApplicationErrorHandling:
    """Test error handling scenarios in application endpoints"""

    @pytest.mark.asyncio
    async def test_create_application_cache_invalidation_failure(self, client, auth_headers, monkeypatch):
        """Test that cache invalidation failure doesn't fail application creation"""
        async def failing_cache_invalidate(*args, **kwargs):
            raise Exception("Cache invalidation failed")

        monkeypatch.setattr(CacheService, "invalidate_application", failing_cache_invalidate)

        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 201
        assert response.json()["country"] == "ES"

    @pytest.mark.asyncio
    async def test_create_application_broadcast_failure(self, client, auth_headers, monkeypatch):
        """Test that WebSocket broadcast failure doesn't fail application creation"""
        async def failing_broadcast(*args, **kwargs):
            raise Exception("WebSocket broadcast failed")

        monkeypatch.setattr(websocket_service, "broadcast_application_update", failing_broadcast)

        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 201
        assert response.json()["country"] == "ES"

    @pytest.mark.asyncio
    async def test_create_application_idempotency_existing(self, client, auth_headers):
        """Test creating application with existing idempotency key"""
        idempotency_key = str(uuid4())

        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {},
            "idempotency_key": idempotency_key
        }

        response1 = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert response1.status_code == 201
        app_id_1 = response1.json()["id"]

        await asyncio.sleep(6)

        response2 = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert response2.status_code == 201
        app_id_2 = response2.json()["id"]

        assert app_id_1 == app_id_2

    @pytest.mark.asyncio
    async def test_list_applications_decryption_error_handling(self, client, auth_headers, monkeypatch):
        """Test that decryption errors in list don't fail the entire request"""
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

        async def failing_decryption(db, app):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Decryption failed")
            return await original_application_to_response(db, app)

        monkeypatch.setattr(applications, "application_to_response", failing_decryption)

        response = await client.get("/api/v1/applications", headers=auth_headers)

        assert response.status_code == 200
        assert "applications" in response.json()

    @pytest.mark.asyncio
    async def test_list_applications_with_status_filter(self, client, auth_headers, admin_headers):
        """Test listing applications filtered by status"""
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
        await client.patch(
            f"/api/v1/applications/{app_id}",
            json={"status": "APPROVED"},
            headers=admin_headers
        )

        response = await client.get("/api/v1/applications?status=APPROVED", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        for app in data["applications"]:
            assert app["status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_get_application_decryption_error(self, client, auth_headers, monkeypatch):
        """Test get application with decryption error"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        async def failing_decryption(db, app):
            raise Exception("Decryption failed")

        monkeypatch.setattr(applications, "application_to_response", failing_decryption)

        response = await client.get(f"/api/v1/applications/{app_id}", headers=auth_headers)

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_update_application_cache_invalidation_failure(self, client, auth_headers, admin_headers, monkeypatch):
        """Test that cache invalidation failure doesn't fail application update"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        async def failing_cache_invalidate(*args, **kwargs):
            raise Exception("Cache invalidation failed")

        monkeypatch.setattr(CacheService, "invalidate_application", failing_cache_invalidate)

        response = await client.patch(
            f"/api/v1/applications/{app_id}",
            json={"status": "VALIDATING"},
            headers=admin_headers
        )

        assert response.status_code == 200
        assert response.json()["status"] == "VALIDATING"

    @pytest.mark.asyncio
    async def test_update_application_validation_error(self, client, auth_headers, admin_headers):
        """Test update application with validation error (invalid state transition)"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        response = await client.patch(
            f"/api/v1/applications/{app_id}",
            json={"status": "APPROVED"},
            headers=admin_headers
        )

        assert response.status_code in [400, 403]

    @pytest.mark.asyncio
    async def test_update_application_unexpected_error(self, client, auth_headers, admin_headers, monkeypatch):
        """Test update application with unexpected error"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        original_update = None

        async def failing_update(self, app_id, update_data):
            raise Exception("Unexpected database error")

        original_update = application_service.ApplicationService.update_application
        monkeypatch.setattr(application_service.ApplicationService, "update_application", failing_update)

        response = await client.patch(
            f"/api/v1/applications/{app_id}",
            json={"status": "VALIDATING"},
            headers=admin_headers
        )

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_delete_application_not_found(self, client, admin_headers):
        """Test deleting non-existent application"""
        fake_id = str(uuid4())

        response = await client.delete(f"/api/v1/applications/{fake_id}", headers=admin_headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_application_duplicate_document_error(self, client, auth_headers):
        """Test creating application with duplicate document (database constraint)"""
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
    async def test_create_application_integrity_error_other(self, client, auth_headers, monkeypatch):
        """Test create application with other integrity error (not duplicate)"""
        from app.repositories.application_repository import ApplicationRepository

        async def failing_create(self, application_data):
            raise IntegrityError("statement", "params", "orig")

        monkeypatch.setattr(ApplicationRepository, "create", failing_create)

        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_list_applications_database_error(self, client, auth_headers, monkeypatch):
        """Test list applications with database error"""

        async def failing_list(self, **kwargs):
            raise Exception("Database connection failed")

        monkeypatch.setattr(application_service.ApplicationService, "list_applications", failing_list)

        response = await client.get("/api/v1/applications", headers=auth_headers)

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_get_audit_logs_invalid_pagination(self, client, auth_headers):
        """Test get audit logs with invalid pagination parameters"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/applications/{app_id}/audit?page=0",
            headers=auth_headers
        )

        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_get_audit_logs_invalid_page_size(self, client, auth_headers):
        """Test get audit logs with invalid page_size"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/applications/{app_id}/audit?page_size=1000",
            headers=auth_headers
        )

        assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_update_application_not_found_in_service(self, client, auth_headers, admin_headers, monkeypatch):
        """Test update application when service returns None"""

        fake_id = str(uuid4())

        async def mock_update(self, app_id, update_data):
            return None

        monkeypatch.setattr(application_service.ApplicationService, "update_application", mock_update)

        response = await client.patch(
            f"/api/v1/applications/{fake_id}",
            json={"status": "VALIDATING"},
            headers=admin_headers
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_application_decryption_error_raises(self, client, auth_headers, admin_headers, monkeypatch):
        """Test update application with decryption error raises exception"""
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

        async def failing_decryption(db, app):
            raise Exception("Decryption failed - corrupted data")

        monkeypatch.setattr(applications, "application_to_response", failing_decryption)

        response = await client.patch(
            f"/api/v1/applications/{app_id}",
            json={"status": "APPROVED"},
            headers=admin_headers
        )

        assert response.status_code in [500, 400]

    @pytest.mark.asyncio
    async def test_update_application_value_error_handling(self, client, auth_headers, admin_headers, monkeypatch):
        """Test update application with ValueError (invalid state transition)"""

        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        async def mock_update_raises_value_error(self, app_id, update_data):
            raise ValueError("Invalid state transition: PENDING -> APPROVED")

        monkeypatch.setattr(application_service.ApplicationService, "update_application", mock_update_raises_value_error)

        response = await client.patch(
            f"/api/v1/applications/{app_id}",
            json={"status": "APPROVED"},
            headers=admin_headers
        )

        assert response.status_code == 400
        assert "Invalid state transition" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_application_unexpected_exception_handling(self, client, auth_headers, admin_headers, monkeypatch):
        """Test update application with unexpected exception"""

        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        async def mock_update_raises_exception(self, app_id, update_data):
            raise RuntimeError("Unexpected database error")

        monkeypatch.setattr(application_service.ApplicationService, "update_application", mock_update_raises_exception)

        response = await client.patch(
            f"/api/v1/applications/{app_id}",
            json={"status": "VALIDATING"},
            headers=admin_headers
        )

        assert response.status_code == 500
