"""
Tests for Webhook Idempotency

Verifies that webhook endpoints correctly handle duplicate requests
using the provider_reference as an idempotency key.
"""

import json

import pytest
from sqlalchemy import func, select

from app.core.webhook_security import generate_webhook_signature
from app.models.webhook_event import WebhookEvent, WebhookEventStatus


class TestWebhookIdempotency:
    """Test webhook idempotency functionality"""

    def create_webhook_signature(self, payload: str) -> str:
        """Helper to create valid webhook signature"""
        return generate_webhook_signature(payload)

    @pytest.mark.asyncio()
    async def test_webhook_idempotency_first_request(self, client, auth_headers, test_db):
        """
        Test that first webhook request is processed successfully.

        Verifies:
        - Webhook is processed
        - WebhookEvent record is created
        - already_processed is False
        """
        # Create an application first
        app_data = {
            "country": "ES",
            "full_name": "Juan García López",
            "identity_document": "12345678Z",
            "requested_amount": 5000.00,
            "monthly_income": 2000.00
        }

        response = await client.post(
            "/api/v1/applications",
            json=app_data,
            headers=auth_headers
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}. Response: {response.text}"
        application_id = response.json()["id"]

        # Create webhook payload
        webhook_payload = {
            "application_id": application_id,
            "document_verified": True,
            "credit_score": 750,
            "total_debt": "1000.50",
            "monthly_obligations": "200.00",
            "has_defaults": False,
            "provider_reference": "BANK_REF_12345",  # Idempotency key
            "verified_at": "2024-01-15T10:30:00"
        }

        payload_json = json.dumps(webhook_payload)
        signature = self.create_webhook_signature(payload_json)

        # Send webhook
        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature
            }
        )

        # Verify response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
        response_data = response.json()
        assert response_data["message"] == "Webhook sent successfully"
        # application_id from JSON response is a string, application_id from create is also a string
        assert response_data["data"]["application_id"] == application_id
        assert response_data["data"]["already_processed"] is False

        # Verify WebhookEvent was created
        async with test_db() as session:
            result = await session.execute(
                select(WebhookEvent).where(
                    WebhookEvent.idempotency_key == "BANK_REF_12345"
                )
            )
            webhook_event = result.scalar_one_or_none()

        assert webhook_event is not None
        assert webhook_event.status == WebhookEventStatus.PROCESSED
        # application_id from JSON is a string, webhook_event.application_id is UUID
        assert str(webhook_event.application_id) == application_id
        assert webhook_event.processed_at is not None

    @pytest.mark.asyncio()
    async def test_webhook_idempotency_duplicate_request(self, client, auth_headers, test_db):
        """
        Test that duplicate webhook request is detected and not reprocessed.

        Verifies:
        - First request processes successfully
        - Second request with same provider_reference returns already_processed=True
        - Application data is NOT modified by second request
        - Only ONE WebhookEvent record exists
        """
        # Create an application
        app_data = {
            "country": "MX",
            "full_name": "María Rodríguez Hernández",
            "identity_document": "ROHM850215MDFDRR09",
            "requested_amount": 10000.00,
            "monthly_income": 5000.00
        }

        response = await client.post(
            "/api/v1/applications",
            json=app_data,
            headers=auth_headers
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}. Response: {response.text}"
        application_id = response.json()["id"]

        # Create webhook payload with specific credit score
        webhook_payload = {
            "application_id": application_id,
            "document_verified": True,
            "credit_score": 800,  # First credit score
            "total_debt": "500.00",
            "monthly_obligations": "100.00",
            "has_defaults": False,
            "provider_reference": "BANK_REF_DUPLICATE_TEST",  # Same idempotency key
            "verified_at": "2024-01-15T11:00:00"
        }

        payload_json = json.dumps(webhook_payload)
        signature = self.create_webhook_signature(payload_json)

        # Send webhook FIRST TIME
        response1 = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature
            }
        )

        assert response1.status_code == 200, f"Expected 200, got {response1.status_code}. Response: {response1.text}"
        response1_data = response1.json()
        assert response1_data["data"]["already_processed"] is False

        # Get application after first webhook
        response_app = await client.get(
            f"/api/v1/applications/{application_id}",
            headers=auth_headers
        )
        app_after_first = response_app.json()
        first_credit_score = app_after_first["banking_data"]["credit_score"]
        assert first_credit_score == 800

        # Modify webhook payload slightly (different credit score)
        # This tests that even with different data, idempotency prevents reprocessing
        # Use a valid credit score within range (300-850)
        webhook_payload["credit_score"] = 850  # Changed! (max valid value)
        payload_json_v2 = json.dumps(webhook_payload)
        signature_v2 = self.create_webhook_signature(payload_json_v2)

        # Send webhook SECOND TIME (duplicate!)
        response2 = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json_v2,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature_v2
            }
        )

        # Verify duplicate is detected
        assert response2.status_code == 200, f"Expected 200, got {response2.status_code}. Response: {response2.text}"
        response2_data = response2.json()
        assert response2_data["message"] == "Webhook already processed"
        assert response2_data["data"]["already_processed"] is True
        assert "processed_at" in response2_data["data"]

        # Verify application data DID NOT change
        response_app2 = await client.get(
            f"/api/v1/applications/{application_id}",
            headers=auth_headers
        )
        app_after_second = response_app2.json()
        second_credit_score = app_after_second["banking_data"]["credit_score"]
        assert second_credit_score == 800  # Still original value, not 900!

        # Verify only ONE WebhookEvent record exists
        async with test_db() as session:
            result = await session.execute(
                select(func.count()).select_from(WebhookEvent).where(
                    WebhookEvent.idempotency_key == "BANK_REF_DUPLICATE_TEST"
                )
            )
            count = result.scalar()
        assert count == 1

    @pytest.mark.asyncio()
    async def test_webhook_idempotency_different_webhooks(self, client, auth_headers, test_db):
        """
        Test that webhooks with different provider_reference are both processed.

        Verifies:
        - Two webhooks with different idempotency keys both process
        - Two separate WebhookEvent records are created
        """
        # Create an application
        app_data = {
            "country": "BR",
            "full_name": "João Silva Santos",
            "identity_document": "11144477735",  # Valid CPF with correct checksum
            "requested_amount": 15000.00,
            "monthly_income": 8000.00
        }

        response = await client.post(
            "/api/v1/applications",
            json=app_data,
            headers=auth_headers
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}. Response: {response.text}"
        application_id = response.json()["id"]

        # First webhook
        webhook_payload_1 = {
            "application_id": application_id,
            "document_verified": True,
            "credit_score": 700,
            "total_debt": "2000.00",
            "monthly_obligations": "300.00",
            "has_defaults": False,
            "provider_reference": "BANK_REF_FIRST",  # Different key
            "verified_at": "2024-01-15T12:00:00"
        }

        payload_json_1 = json.dumps(webhook_payload_1)
        signature_1 = self.create_webhook_signature(payload_json_1)

        response1 = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json_1,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature_1
            }
        )
        assert response1.status_code == 200, f"Expected 200, got {response1.status_code}. Response: {response1.text}"
        assert response1.json()["data"]["already_processed"] is False

        # Second webhook with DIFFERENT provider_reference
        webhook_payload_2 = {
            "application_id": application_id,
            "document_verified": True,
            "credit_score": 750,
            "total_debt": "1500.00",
            "monthly_obligations": "250.00",
            "has_defaults": False,
            "provider_reference": "BANK_REF_SECOND",  # Different key!
            "verified_at": "2024-01-15T12:30:00"
        }

        payload_json_2 = json.dumps(webhook_payload_2)
        signature_2 = self.create_webhook_signature(payload_json_2)

        response2 = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json_2,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature_2
            }
        )
        assert response2.status_code == 200, f"Expected 200, got {response2.status_code}. Response: {response2.text}"
        assert response2.json()["data"]["already_processed"] is False

        async with test_db() as session:
            # Use application_id as string - SQLAlchemy can handle string UUIDs in queries
            result = await session.execute(
                select(func.count()).select_from(WebhookEvent).where(
                    WebhookEvent.application_id == application_id
                )
            )
            count = result.scalar()
        assert count == 2

    @pytest.mark.asyncio()
    async def test_webhook_idempotency_failed_retry(self, client, auth_headers, test_db, sample_application_colombia):
        """
        Test that a failed webhook can be retried.

        Verifies:
        - First webhook fails (application exists but webhook processing fails)
        - WebhookEvent is marked as failed
        - Retry of same webhook (with corrected data) is allowed
        """
        # Use the sample application that was created
        valid_app_id = sample_application_colombia

        # First, send a webhook that will fail (e.g., with invalid data that causes processing to fail)
        # For this test, we'll simulate a failure by sending a webhook that will be processed
        # but then we'll manually mark it as failed, or we can test with a scenario where
        # the webhook succeeds on retry after a previous failure

        # Actually, let's test a different scenario: send webhook first time (succeeds),
        # then simulate a failure scenario by testing idempotency with a different payload
        # that would normally fail, but since it's a retry with same idempotency key, it should work

        # Create webhook payload
        webhook_payload = {
            "application_id": valid_app_id,
            "document_verified": True,
            "credit_score": 700,
            "total_debt": "1000.00",
            "monthly_obligations": "200.00",
            "has_defaults": False,
            "provider_reference": "BANK_REF_RETRY_TEST",
            "verified_at": "2024-01-15T13:00:00"
        }

        payload_json = json.dumps(webhook_payload)
        signature = self.create_webhook_signature(payload_json)

        # Send webhook first time (should succeed)
        response1 = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature
            }
        )

        # Should succeed
        assert response1.status_code == 200, f"Expected 200, got {response1.status_code}. Response: {response1.text}"

        # Verify WebhookEvent was created with PROCESSED status
        async with test_db() as session:
            result = await session.execute(
                select(WebhookEvent).where(
                    WebhookEvent.idempotency_key == "BANK_REF_RETRY_TEST"
                )
            )
            webhook_event = result.scalar_one_or_none()

        assert webhook_event is not None
        assert webhook_event.status == WebhookEventStatus.PROCESSED

        # Now manually mark it as failed to simulate a failure scenario
        # (In a real scenario, this would happen due to an error during processing)
        async with test_db() as session:
            result = await session.execute(
                select(WebhookEvent).where(
                    WebhookEvent.idempotency_key == "BANK_REF_RETRY_TEST"
                )
            )
            webhook_event = result.scalar_one_or_none()
            if webhook_event:
                webhook_event.status = WebhookEventStatus.FAILED
                webhook_event.error_message = "Simulated processing error"
                await session.commit()

        # Retry webhook with SAME provider_reference but VALID application ID
        webhook_payload["application_id"] = valid_app_id
        payload_json_retry = json.dumps(webhook_payload)
        signature_retry = self.create_webhook_signature(payload_json_retry)

        response2 = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json_retry,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature_retry
            }
        )

        # Should succeed now
        assert response2.status_code == 200, f"Expected 200, got {response2.status_code}. Response: {response2.text}"
        response2_data = response2.json()
        assert response2_data["data"]["already_processed"] is False

        # Verify WebhookEvent status changed to PROCESSED
        async with test_db() as session:
            result = await session.execute(
                select(WebhookEvent).where(
                    WebhookEvent.idempotency_key == "BANK_REF_RETRY_TEST"
                )
            )
            webhook_event_updated = result.scalar_one_or_none()
            assert webhook_event_updated is not None
            assert webhook_event_updated.status == WebhookEventStatus.PROCESSED
            assert webhook_event_updated.processed_at is not None

    @pytest.mark.asyncio()
    async def test_webhook_without_provider_reference(self, client, auth_headers):
        """
        Test that webhook without provider_reference is rejected.

        Verifies:
        - Webhook without provider_reference returns 400 error
        """
        # Create an application
        app_data = {
            "country": "PT",
            "full_name": "António Oliveira Costa",
            "identity_document": "123456789",  # Valid NIF (9 digits)
            "requested_amount": 3000.00,
            "monthly_income": 1500.00
        }

        response = await client.post(
            "/api/v1/applications",
            json=app_data,
            headers=auth_headers
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}. Response: {response.text}"
        application_id = response.json()["id"]

        # Create webhook payload WITHOUT provider_reference
        webhook_payload = {
            "application_id": application_id,
            "document_verified": True,
            "credit_score": 680,
            "total_debt": "500.00",
            "monthly_obligations": "100.00",
            "has_defaults": False,
            # "provider_reference": missing!
            "verified_at": "2024-01-15T14:00:00"
        }

        payload_json = json.dumps(webhook_payload)
        signature = self.create_webhook_signature(payload_json)

        # Send webhook
        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature
            }
        )

        # Should return 400 error
        assert response.status_code == 400, f"Expected 400, got {response.status_code}. Response: {response.text}"
        response_data = response.json()
        assert "provider_reference" in response_data["detail"].lower()
        assert "idempotency" in response_data["detail"].lower()
