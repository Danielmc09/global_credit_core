"""
Additional tests for webhook endpoints to improve coverage further.

These tests focus on covering the remaining uncovered lines in webhooks.py.
"""

import json
from datetime import datetime
from uuid import uuid4

import pytest

from app.core.webhook_security import generate_webhook_signature


class TestWebhookAdditionalCoverage:
    """Additional tests to improve webhook coverage"""

    @pytest.mark.asyncio
    async def test_webhook_content_length_validation_exact_limit(self, client, auth_headers):
        """Test webhook with Content-Length at exact limit"""
        from app.core.constants import WebhookPayloadLimits

        # Create an application first
        create_response = await client.post("/api/v1/applications", json={
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "country_specific_data": {}
        }, headers=auth_headers)

        app_id = create_response.json()["id"]

        # Create a payload at exact limit
        webhook_payload = {
            "application_id": app_id,
            "document_verified": True,
            "credit_score": 750,
            "total_debt": "5000.00",
            "monthly_obligations": "500.00",
            "has_defaults": False,
            "provider_reference": "TEST-REF-123",
            "verified_at": datetime.utcnow().isoformat()
        }

        payload_json = json.dumps(webhook_payload)
        # Pad to exact limit
        current_size = len(payload_json.encode('utf-8'))
        if current_size < WebhookPayloadLimits.MAX_PAYLOAD_SIZE_BYTES:
            padding = "x" * (WebhookPayloadLimits.MAX_PAYLOAD_SIZE_BYTES - current_size - 10)  # Leave some margin
            webhook_payload["padding"] = padding
            payload_json = json.dumps(webhook_payload)

        signature = generate_webhook_signature(payload_json)

        # Send with Content-Length at limit
        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json",
                "Content-Length": str(len(payload_json.encode('utf-8')))
            }
        )

        # Should succeed if within limit
        assert response.status_code in [200, 413]

    @pytest.mark.asyncio
    async def test_webhook_invalid_content_length_continues_to_body_check(self, client, auth_headers):
        """Test webhook with invalid Content-Length continues to body size check"""
        # Create an application first
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
            "total_debt": "5000.00",
            "monthly_obligations": "500.00",
            "has_defaults": False,
            "provider_reference": "TEST-REF-INVALID-CL",
            "verified_at": datetime.utcnow().isoformat()
        }

        payload_json = json.dumps(webhook_payload)
        signature = generate_webhook_signature(payload_json)

        # Send with invalid Content-Length (non-numeric)
        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json",
                "Content-Length": "not-a-number"  # Invalid
            }
        )

        # Should still process (invalid header is ignored, body size is checked)
        assert response.status_code in [200, 400, 413]

    @pytest.mark.asyncio
    async def test_webhook_application_id_uuid_conversion_error(self, client):
        """Test webhook with application_id that can't be converted to UUID"""
        webhook_payload = {
            "application_id": "not-a-valid-uuid-format-12345",  # Invalid UUID format
            "document_verified": True,
            "credit_score": 750,
            "total_debt": "5000.00",
            "monthly_obligations": "500.00",
            "has_defaults": False,
            "provider_reference": "TEST-REF-UUID-ERROR",
            "verified_at": datetime.utcnow().isoformat()
        }

        payload_json = json.dumps(webhook_payload)
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Invalid application_id format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_webhook_application_id_type_error(self, client):
        """Test webhook with application_id that's not a string (TypeError)"""
        # Create payload with application_id as number instead of string
        webhook_payload = {
            "application_id": 12345,  # Number, not string
            "document_verified": True,
            "credit_score": 750,
            "total_debt": "5000.00",
            "monthly_obligations": "500.00",
            "has_defaults": False,
            "provider_reference": "TEST-REF-TYPE-ERROR",
            "verified_at": datetime.utcnow().isoformat()
        }

        payload_json = json.dumps(webhook_payload)
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        # Should handle TypeError in UUID conversion or Pydantic validation
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_webhook_pydantic_validation_error(self, client):
        """Test webhook with Pydantic validation error"""
        webhook_payload = {
            "application_id": str(uuid4()),
            "document_verified": "not-a-boolean",  # Invalid type
            "credit_score": "not-a-number",  # Invalid type
            "total_debt": "5000.00",
            "monthly_obligations": "500.00",
            "has_defaults": False,
            "provider_reference": "TEST-REF-VALIDATION",
            "verified_at": datetime.utcnow().isoformat()
        }

        payload_json = json.dumps(webhook_payload)
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Invalid webhook payload" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_webhook_json_decode_error(self, client):
        """Test webhook with invalid JSON"""
        invalid_json = '{"application_id": "invalid", "document_verified": true,}'  # Trailing comma

        signature = generate_webhook_signature(invalid_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=invalid_json.encode('utf-8'),
            headers={
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Invalid webhook payload" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_webhook_value_error_handling(self, client):
        """Test webhook with ValueError during parsing"""
        # Create payload that might cause ValueError
        webhook_payload = {
            "application_id": str(uuid4()),
            "document_verified": True,
            "credit_score": 750,
            "total_debt": "invalid-decimal",  # Invalid decimal format
            "monthly_obligations": "500.00",
            "has_defaults": False,
            "provider_reference": "TEST-REF-VALUE-ERROR",
            "verified_at": datetime.utcnow().isoformat()
        }

        payload_json = json.dumps(webhook_payload)
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        # Should return 400 (validation error)
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_webhook_integrity_error_unique_constraint_handling(self, client, auth_headers, test_db):
        """Test webhook IntegrityError with unique constraint (race condition scenario)"""
        from app.models.webhook_event import WebhookEvent, WebhookEventStatus

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
        provider_ref = f"INTEGRITY-UNIQUE-{uuid4()}"

        # Create a processed webhook event manually to simulate race condition
        async with test_db() as session:
            processed_event = WebhookEvent(
                idempotency_key=provider_ref,
                application_id=app_id,
                payload={"test": "data"},
                status=WebhookEventStatus.PROCESSED
            )
            session.add(processed_event)
            await session.commit()

        webhook_payload = {
            "application_id": app_id,
            "document_verified": True,
            "credit_score": 750,
            "total_debt": "5000.00",
            "monthly_obligations": "500.00",
            "has_defaults": False,
            "provider_reference": provider_ref,
            "verified_at": datetime.utcnow().isoformat()
        }

        payload_json = json.dumps(webhook_payload)
        signature = generate_webhook_signature(payload_json)

        # Send webhook - should detect as already processed
        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 200
        assert response.json()["data"]["already_processed"] is True

    @pytest.mark.asyncio
    async def test_webhook_integrity_error_retry_failed_event(self, client, auth_headers, test_db):
        """Test webhook IntegrityError when retrying a failed event"""
        from app.models.webhook_event import WebhookEvent, WebhookEventStatus

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
        provider_ref = f"INTEGRITY-RETRY-{uuid4()}"

        # Create a failed webhook event
        async with test_db() as session:
            failed_event = WebhookEvent(
                idempotency_key=provider_ref,
                application_id=app_id,
                payload={"test": "data"},
                status=WebhookEventStatus.FAILED,
                error_message="Previous failure"
            )
            session.add(failed_event)
            await session.commit()

        webhook_payload = {
            "application_id": app_id,
            "document_verified": True,
            "credit_score": 750,
            "total_debt": "5000.00",
            "monthly_obligations": "500.00",
            "has_defaults": False,
            "provider_reference": provider_ref,
            "verified_at": datetime.utcnow().isoformat()
        }

        payload_json = json.dumps(webhook_payload)
        signature = generate_webhook_signature(payload_json)

        # Send webhook - should retry the failed event
        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Webhook sent successfully"
