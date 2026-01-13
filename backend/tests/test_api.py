"""
Integration Tests for API Endpoints

Tests the FastAPI application endpoints with database integration.
Uses PostgreSQL test database fixtures from conftest.py
"""

import json
from datetime import datetime

import pytest

from app.core.webhook_security import generate_webhook_signature


class TestApplicationEndpoints:
    """Test suite for application CRUD endpoints"""

    @pytest.mark.asyncio()
    async def test_create_application_spain(self, client, auth_headers):
        """Test creating a Spanish application"""
        payload = {
            "country": "ES",
            "full_name": "Juan García López",
            "identity_document": "12345678Z",
            "requested_amount": 15000.00,
            "monthly_income": 3500.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["country"] == "ES"
        assert data["full_name"] == "Juan García López"
        assert data["status"] == "PENDING"
        assert "id" in data
        assert data["identity_document"] == "*****678Z"

    @pytest.mark.asyncio()
    async def test_create_application_mexico(self, client, auth_headers):
        """Test creating a Mexican application"""
        payload = {
            "country": "MX",
            "full_name": "María Hernández",
            "identity_document": "HERM850101MDFRRR01",
            "requested_amount": 50000.00,
            "monthly_income": 12000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["country"] == "MX"
        assert data["status"] == "PENDING"

    @pytest.mark.asyncio()
    async def test_create_application_invalid_document(self, client, auth_headers):
        """Test creating application with invalid document"""
        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "INVALID",
            "requested_amount": 10000.00,
            "monthly_income": 2000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 400
        assert "validation failed" in response.json()["detail"].lower()

    @pytest.mark.asyncio()
    async def test_create_application_negative_amount(self, client, auth_headers):
        """Test validation for negative amount"""
        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": -1000.00,
            "monthly_income": 2000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 422

    @pytest.mark.asyncio()
    async def test_create_application_short_name(self, client, auth_headers):
        """Test validation for short name"""
        payload = {
            "country": "ES",
            "full_name": "A",
            "identity_document": "12345678Z",
            "requested_amount": 1000.00,
            "monthly_income": 2000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)

        assert response.status_code == 422

    @pytest.mark.asyncio()
    async def test_list_applications_empty(self, client, auth_headers):
        """Test listing applications when database is empty"""
        response = await client.get("/api/v1/applications", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["applications"] == []

    @pytest.mark.asyncio()
    async def test_list_applications_with_data(self, client, auth_headers):
        """Test listing applications with data"""
        payload1 = {
            "country": "ES",
            "full_name": "User One",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }
        payload2 = {
            "country": "MX",
            "full_name": "User Two",
            "identity_document": "HERM850101MDFRRR01",
            "requested_amount": 20000.00,
            "monthly_income": 5000.00,
            "country_specific_data": {}
        }

        await client.post("/api/v1/applications", json=payload1, headers=auth_headers)
        await client.post("/api/v1/applications", json=payload2, headers=auth_headers)

        response = await client.get("/api/v1/applications", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["applications"]) == 2

    @pytest.mark.asyncio()
    async def test_list_applications_filter_by_country(self, client, auth_headers):
        """Test filtering applications by country"""
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

        response = await client.get("/api/v1/applications?country=ES", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["applications"][0]["country"] == "ES"

    @pytest.mark.asyncio()
    async def test_get_application_by_id(self, client, auth_headers):
        """Test getting a single application by ID"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        response = await client.get(f"/api/v1/applications/{app_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == app_id
        assert data["country"] == "ES"

    @pytest.mark.asyncio()
    async def test_get_application_not_found(self, client, auth_headers):
        """Test getting non-existent application"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/v1/applications/{fake_id}", headers=auth_headers)

        assert response.status_code == 404

    @pytest.mark.asyncio()
    async def test_update_application_status(self, client, auth_headers, admin_headers):
        """Test updating application status"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        update_response = await client.patch(
            f"/api/v1/applications/{app_id}",
            json={"status": "VALIDATING"},
            headers=admin_headers
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert data["status"] == "VALIDATING"

        update_response = await client.patch(
            f"/api/v1/applications/{app_id}",
            json={"status": "APPROVED"},
            headers=admin_headers
        )

        assert update_response.status_code == 200
        data = update_response.json()
        assert data["status"] == "APPROVED"

    @pytest.mark.asyncio()
    async def test_delete_application(self, client, auth_headers, admin_headers):
        """Test soft deleting an application"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        delete_response = await client.delete(f"/api/v1/applications/{app_id}", headers=admin_headers)

        assert delete_response.status_code == 200

        get_response = await client.get(f"/api/v1/applications/{app_id}", headers=auth_headers)
        assert get_response.status_code == 404

    @pytest.mark.asyncio()
    async def test_pagination(self, client, auth_headers):
        """Test pagination of application list"""
        identity_documents = ["12345678Z", "87654321X", "00000000T", "99999999R", "23456789D"]
        for i in range(5):
            response = await client.post("/api/v1/applications", json={
                "country": "ES",
                "full_name": f"User {i}",
                "identity_document": identity_documents[i],
                "requested_amount": 10000.00,
                "monthly_income": 3000.00,
                "country_specific_data": {}
            }, headers=auth_headers)
            assert response.status_code == 201, f"Failed to create application {i}: {response.text}"

        response = await client.get("/api/v1/applications?page=1&page_size=3", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["applications"]) == 3
        assert data["page"] == 1

    @pytest.mark.asyncio()
    async def test_get_audit_logs_pagination(self, client, auth_headers, admin_headers):
        """Test pagination of audit logs"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        statuses = ["VALIDATING", "UNDER_REVIEW", "APPROVED"]
        for status in statuses:
            await client.patch(
                f"/api/v1/applications/{app_id}",
                json={"status": status},
                headers=admin_headers
            )

        response = await client.get(
            f"/api/v1/applications/{app_id}/audit?page=1&page_size=2",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "audit_logs" in data
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["audit_logs"]) == 2
        assert data["total"] >= 3

    @pytest.mark.asyncio()
    async def test_get_audit_logs_pagination_total(self, client, auth_headers, admin_headers):
        """Test that audit logs pagination returns correct total"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        statuses = ["VALIDATING", "UNDER_REVIEW", "APPROVED"]
        for status in statuses:
            await client.patch(
                f"/api/v1/applications/{app_id}",
                json={"status": status},
                headers=admin_headers
            )

        response = await client.get(
            f"/api/v1/applications/{app_id}/audit",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        total = data["total"]
        assert total >= 3

        response = await client.get(
            f"/api/v1/applications/{app_id}/audit?page_size=2",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == total
        assert len(data["audit_logs"]) == 2

    @pytest.mark.asyncio()
    async def test_get_audit_logs_different_pages(self, client, auth_headers, admin_headers):
        """Test that different pages return different audit logs"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        statuses = ["VALIDATING", "UNDER_REVIEW", "APPROVED"]
        for status in statuses:
            await client.patch(
                f"/api/v1/applications/{app_id}",
                json={"status": status},
                headers=admin_headers
            )

        page1_response = await client.get(
            f"/api/v1/applications/{app_id}/audit?page=1&page_size=2",
            headers=auth_headers
        )

        assert page1_response.status_code == 200
        page1_data = page1_response.json()
        page1_ids = {log["id"] for log in page1_data["audit_logs"]}

        page2_response = await client.get(
            f"/api/v1/applications/{app_id}/audit?page=2&page_size=2",
            headers=auth_headers
        )

        assert page2_response.status_code == 200
        page2_data = page2_response.json()
        page2_ids = {log["id"] for log in page2_data["audit_logs"]}

        assert page1_ids != page2_ids
        assert len(page1_ids.intersection(page2_ids)) == 0

    @pytest.mark.asyncio()
    async def test_get_audit_logs_empty(self, client, auth_headers):
        """Test getting audit logs for application with no status changes"""
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
            f"/api/v1/applications/{app_id}/audit?page=1&page_size=10",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 0
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert isinstance(data["audit_logs"], list)

    @pytest.mark.asyncio()
    async def test_get_audit_logs_last_page_incomplete(self, client, auth_headers, admin_headers):
        """Test pagination when last page has fewer items than page_size"""
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

        response = await client.get(
            f"/api/v1/applications/{app_id}/audit?page=1&page_size=100",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        total = data["total"]
        assert total >= 1
        assert len(data["audit_logs"]) == total


class TestMetaEndpoints:
    """Test suite for metadata endpoints"""

    @pytest.mark.asyncio()
    async def test_get_supported_countries(self, client):
        """Test getting list of supported countries"""
        response = await client.get("/api/v1/applications/meta/supported-countries")

        assert response.status_code == 200
        data = response.json()
        assert "supported_countries" in data
        assert "ES" in data["supported_countries"]
        assert "MX" in data["supported_countries"]
        assert data["total"] >= 2

    @pytest.mark.asyncio()
    async def test_health_check(self, client):
        """Test health check endpoint"""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "application" in data
        assert "version" in data


class TestWebhookEndpoints:
    """Test suite for webhook endpoints"""

    @pytest.mark.asyncio()
    async def test_bank_confirmation_webhook_with_valid_signature(self, client, auth_headers):
        """Test receiving bank confirmation webhook with valid signature"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        webhook_payload = {
            "application_id": app_id,
            "document_verified": True,
            "credit_score": 750,
            "total_debt": 5000.00,
            "monthly_obligations": 500.00,
            "has_defaults": False,
            "provider_reference": "TEST-REF-123",
            "verified_at": datetime.utcnow().isoformat()
        }

        payload_json = json.dumps(webhook_payload, sort_keys=True, separators=(",", ":"))
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Webhook sent successfully"

        get_response = await client.get(f"/api/v1/applications/{app_id}", headers=auth_headers)
        app_data = get_response.json()
        assert app_data["banking_data"]["document_verified"] is True
        assert app_data["banking_data"]["credit_score"] == 750

    @pytest.mark.asyncio()
    async def test_bank_confirmation_webhook_without_signature(self, client, auth_headers):
        """Test that webhook without signature is rejected"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        webhook_payload = {
            "application_id": app_id,
            "document_verified": True,
            "credit_score": 750,
            "total_debt": 5000.00,
            "monthly_obligations": 500.00,
            "has_defaults": False,
            "provider_reference": "TEST-REF-123",
            "verified_at": datetime.utcnow().isoformat()
        }

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            json=webhook_payload
        )

        assert response.status_code == 401
        assert "signature" in response.json()["detail"].lower()

    @pytest.mark.asyncio()
    async def test_bank_confirmation_webhook_with_invalid_signature(self, client, auth_headers):
        """Test that webhook with invalid signature is rejected"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        webhook_payload = {
            "application_id": app_id,
            "document_verified": True,
            "credit_score": 750,
            "total_debt": 5000.00,
            "monthly_obligations": 500.00,
            "has_defaults": False,
            "provider_reference": "TEST-REF-123",
            "verified_at": datetime.utcnow().isoformat()
        }

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            json=webhook_payload,
            headers={"X-Webhook-Signature": "invalid-signature-12345"}
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower() or "signature" in response.json()["detail"].lower()

    @pytest.mark.asyncio()
    async def test_webhook_idempotency_duplicate_detection(self, client, auth_headers):
        """
        Test that duplicate webhooks are detected and NOT reprocessed.

        This is the CORE idempotency test:
        - First webhook should process successfully
        - Second webhook with SAME provider_reference should return already_processed=true
        - Application data should NOT change on second webhook
        """
        create_response = await client.post("/api/v1/applications", json={
            "country": "MX",
            "full_name": "María Rodríguez Hernández",
            "identity_document": "ROHM850215MDFDRR09",
            "requested_amount": 10000.00,
            "monthly_income": 5000.00
        }, headers=auth_headers)

        assert create_response.status_code == 201
        app_id = create_response.json()["id"]

        webhook_payload = {
            "application_id": app_id,
            "document_verified": True,
            "credit_score": 800,
            "total_debt": "500.00",
            "monthly_obligations": "100.00",
            "has_defaults": False,
            "provider_reference": "IDEMPOTENCY_TEST_DUPLICATE",
            "verified_at": "2024-01-15T11:00:00"
        }

        payload_json = json.dumps(webhook_payload)
        signature = generate_webhook_signature(payload_json)

        response1 = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature
            }
        )

        assert response1.status_code == 200
        response1_data = response1.json()
        assert response1_data["data"]["already_processed"] is False

        response_app = await client.get(f"/api/v1/applications/{app_id}", headers=auth_headers)
        app_after_first = response_app.json()
        first_credit_score = app_after_first["banking_data"]["credit_score"]
        assert first_credit_score == 800

        webhook_payload["credit_score"] = 850
        payload_json_v2 = json.dumps(webhook_payload)
        signature_v2 = generate_webhook_signature(payload_json_v2)

        response2 = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json_v2,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature_v2
            }
        )

        assert response2.status_code == 200
        response2_data = response2.json()
        assert response2_data["message"] == "Webhook already processed"
        assert response2_data["data"]["already_processed"] is True
        assert "processed_at" in response2_data["data"]

        response_app2 = await client.get(f"/api/v1/applications/{app_id}", headers=auth_headers)
        app_after_second = response_app2.json()
        second_credit_score = app_after_second["banking_data"]["credit_score"]
        assert second_credit_score == 800

        print("✅ Idempotency test passed: Duplicate webhook was NOT reprocessed")

    @pytest.mark.asyncio()
    async def test_webhook_without_provider_reference_rejected(self, client, auth_headers):
        """Test that webhooks without provider_reference are rejected"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "PT",
            "full_name": "António Oliveira Costa",
            "identity_document": "123456789",
            "requested_amount": 3000.00,
            "monthly_income": 1500.00
        }, headers=auth_headers)

        assert create_response.status_code == 201
        application_id = create_response.json()["id"]

        webhook_payload = {
            "application_id": application_id,
            "document_verified": True,
            "credit_score": 680,
            "total_debt": "500.00",
            "monthly_obligations": "100.00",
            "has_defaults": False,
            "verified_at": "2024-01-15T14:00:00"
        }

        payload_json = json.dumps(webhook_payload)
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature
            }
        )

        assert response.status_code == 400
        assert "provider_reference" in response.json()["detail"].lower()
        assert "idempotency" in response.json()["detail"].lower()


class TestAuthentication:
    """Test suite for authentication and authorization"""

    @pytest.mark.asyncio()
    async def test_create_application_without_auth(self, client):
        """Test that creating an application without token is rejected"""
        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload)
        assert response.status_code == 403

    @pytest.mark.asyncio()
    async def test_create_application_with_invalid_token(self, client):
        """Test that creating an application with invalid token is rejected"""
        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }

        headers = {"Authorization": "Bearer invalid-token-12345"}
        response = await client.post("/api/v1/applications", json=payload, headers=headers)
        assert response.status_code == 401

    @pytest.mark.asyncio()
    async def test_list_applications_without_auth(self, client):
        """Test that listing applications without token is rejected"""
        response = await client.get("/api/v1/applications")
        assert response.status_code == 403

    @pytest.mark.asyncio()
    async def test_get_application_without_auth(self, client):
        """Test that getting an application without token is rejected"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(f"/api/v1/applications/{fake_id}")
        assert response.status_code == 403

    @pytest.mark.asyncio()
    async def test_update_application_without_auth(self, client, auth_headers):
        """Test that updating an application without token is rejected"""
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
            json={"status": "APPROVED"}
        )
        assert response.status_code == 403

    @pytest.mark.asyncio()
    async def test_update_application_without_admin(self, client, auth_headers):
        """Test that updating an application without admin role is rejected"""
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
            headers=auth_headers
        )
        assert response.status_code == 403
        assert "admin" in response.json()["detail"].lower()

    @pytest.mark.asyncio()
    async def test_delete_application_without_auth(self, client, auth_headers):
        """Test that deleting an application without token is rejected"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        response = await client.delete(f"/api/v1/applications/{app_id}")
        assert response.status_code == 403

    @pytest.mark.asyncio()
    async def test_delete_application_without_admin(self, client, auth_headers):
        """Test that deleting an application without admin role is rejected"""
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        response = await client.delete(f"/api/v1/applications/{app_id}", headers=auth_headers)
        assert response.status_code == 403
        assert "admin" in response.json()["detail"].lower()

    @pytest.mark.asyncio()
    async def test_health_check_public(self, client):
        """Test that health check endpoint is public (no auth required)"""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio()
    async def test_supported_countries_public(self, client):
        """Test that supported countries endpoint is public (no auth required)"""
        response = await client.get("/api/v1/applications/meta/supported-countries")
        assert response.status_code == 200
        assert "supported_countries" in response.json()
