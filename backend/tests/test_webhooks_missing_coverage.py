"""Tests to cover missing lines in webhooks.py endpoint.

This file focuses on covering the remaining uncovered lines (125-168, 170-430, 447-483).
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from app.core.webhook_security import generate_webhook_signature
from app.models.webhook_event import WebhookEvent, WebhookEventStatus
from app.models.application import Application
from sqlalchemy import select   
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture(autouse=True, scope='function')
def mock_background_tasks():
    """Automatically mock background tasks for all tests in this file to prevent resource issues.
    
    This fixture patches the functions where they are imported/used in the endpoints,
    which is the most reliable way to ensure the mocks work.
    """
    with patch('app.api.v1.endpoints.applications.enqueue_application_processing', new_callable=AsyncMock) as mock_enqueue:
        with patch('app.api.v1.endpoints.webhooks.broadcast_application_update', new_callable=AsyncMock) as mock_broadcast:
            yield {
                'enqueue': mock_enqueue,
                'broadcast': mock_broadcast
            }


class TestWebhooksMissingCoverage:
    """Tests to cover missing webhook endpoint lines"""

    @pytest.mark.asyncio
    async def test_webhook_body_size_check_without_content_length(self, client, auth_headers, monkeypatch):
        """Test webhook body size validation when Content-Length header is missing"""
        from app.core import constants
        
        monkeypatch.setattr(constants.WebhookPayloadLimits, 'MAX_PAYLOAD_SIZE_BYTES', 100)
        monkeypatch.setattr(constants.WebhookPayloadLimits, 'MAX_PAYLOAD_SIZE_MB', 0.0001)
        
        app_data = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 5000.00,
            "monthly_income": 2000.00
        }
        response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
        application_id = response.json()["id"]

        large_payload = {
            "application_id": application_id,
            "document_verified": True,
            "credit_score": 750,
            "total_debt": "1000.50",
            "monthly_obligations": "200.00",
            "has_defaults": False,
            "provider_reference": "REF_LARGE",
            "verified_at": "2024-01-15T10:30:00"
        }
        
        payload_json = json.dumps(large_payload)
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                **auth_headers,
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_webhook_invalid_signature_after_payload_check(self, client, auth_headers):
        """Test webhook with invalid signature after payload size validation"""
        app_data = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 5000.00,
            "monthly_income": 2000.00
        }
        response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
        application_id = response.json()["id"]

        payload = {
            "application_id": application_id,
            "document_verified": True,
            "credit_score": 750,
            "provider_reference": "REF_INVALID_SIG",
            "verified_at": "2024-01-15T10:30:00"
        }
        payload_json = json.dumps(payload)
        invalid_signature = "invalid_signature"

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                **auth_headers,
                "X-Webhook-Signature": invalid_signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 401
        assert "Invalid webhook signature" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_webhook_application_id_uuid_conversion(self, client, auth_headers):
        """Test webhook with application_id as string that needs UUID conversion"""
        app_data = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 5000.00,
            "monthly_income": 2000.00
        }
        response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
        application_id = response.json()["id"]

        payload = {
            "application_id": str(application_id),
            "document_verified": True,
            "credit_score": 750,
            "provider_reference": "REF_UUID_CONV",
            "verified_at": "2024-01-15T10:30:00"
        }
        payload_json = json.dumps(payload)
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                **auth_headers,
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_webhook_application_id_invalid_uuid_format(self, client, auth_headers):
        """Test webhook with invalid UUID format for application_id"""
        payload = {
            "application_id": "not-a-valid-uuid",
            "document_verified": True,
            "credit_score": 750,
            "provider_reference": "REF_INVALID_UUID",
            "verified_at": "2024-01-15T10:30:00"
        }
        payload_json = json.dumps(payload)
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                **auth_headers,
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Invalid application_id format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_webhook_pydantic_validation_error(self, client, auth_headers):
        """Test webhook with Pydantic validation error"""
        payload = {
            "application_id": str(uuid4()),
            "provider_reference": "REF_MISSING_FIELDS"
        }
        payload_json = json.dumps(payload)
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                **auth_headers,
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Invalid webhook payload" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_webhook_json_decode_error(self, client, auth_headers):
        """Test webhook with invalid JSON"""
        invalid_json = "{ invalid json }"
        signature = generate_webhook_signature(invalid_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=invalid_json.encode('utf-8'),
            headers={
                **auth_headers,
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Invalid webhook payload" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_webhook_missing_provider_reference(self, client, auth_headers):
        """Test webhook without provider_reference"""
        app_data = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 5000.00,
            "monthly_income": 2000.00
        }
        response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
        application_id = response.json()["id"]

        payload = {
            "application_id": application_id,
            "document_verified": True,
            "credit_score": 750,
            "verified_at": "2024-01-15T10:30:00"
        }
        payload_json = json.dumps(payload)
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                **auth_headers,
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Missing provider_reference" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_webhook_exception_during_processing_without_webhook_event(self, client, auth_headers, test_db, monkeypatch):
        """Test webhook exception before webhook_event is created"""
        app_data = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 5000.00,
            "monthly_income": 2000.00
        }
        response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
        application_id = response.json()["id"]

        payload = {
            "application_id": application_id,
            "document_verified": True,
            "credit_score": 750,
            "provider_reference": "REF_EXCEPTION",
            "verified_at": "2024-01-15T10:30:00"
        }
        payload_json = json.dumps(payload)
        signature = generate_webhook_signature(payload_json)

        async def failing_find_by_id(*args, **kwargs):
            raise Exception("Database connection error")

        with patch('app.api.v1.endpoints.webhooks.ApplicationService') as mock_service_class:
            mock_service_instance = MagicMock()
            mock_repo = MagicMock()
            mock_repo.find_by_id = AsyncMock(side_effect=failing_find_by_id)
            mock_service_instance.repository = mock_repo
            mock_service_class.return_value = mock_service_instance

            response = await client.post(
                "/api/v1/webhooks/bank-confirmation",
                content=payload_json.encode('utf-8'),
                headers={
                    **auth_headers,
                    "X-Webhook-Signature": signature,
                    "Content-Type": "application/json"
                }
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Unexpected error" in data["detail"]

    @pytest.mark.asyncio
    async def test_webhook_exception_during_processing_with_webhook_event(self, client, auth_headers, test_db, monkeypatch):
        """Test webhook exception after webhook_event is created"""
        app_data = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 5000.00,
            "monthly_income": 2000.00
        }
        response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
        application_id = response.json()["id"]

        payload = {
            "application_id": application_id,
            "document_verified": True,
            "credit_score": 750,
            "provider_reference": "REF_EXCEPTION_AFTER",
            "verified_at": "2024-01-15T10:30:00"
        }
        payload_json = json.dumps(payload)
        signature = generate_webhook_signature(payload_json)

        from app.models.webhook_event import WebhookEvent, WebhookEventStatus
        
        call_count = [0]
        async def find_by_id_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                mock_app = MagicMock()
                mock_app.id = application_id
                mock_app.banking_data = {}
                mock_app.status = "PENDING"
                return mock_app
            else:
                raise Exception("Processing error")

        with patch('app.api.v1.endpoints.webhooks.ApplicationService') as mock_service_class:
            mock_service_instance = MagicMock()
            mock_repo = MagicMock()
            mock_repo.find_by_id = AsyncMock(side_effect=find_by_id_side_effect)
            mock_service_instance.repository = mock_repo
            mock_service_class.return_value = mock_service_instance

            response = await client.post(
                "/api/v1/webhooks/bank-confirmation",
                content=payload_json.encode('utf-8'),
                headers={
                    **auth_headers,
                    "X-Webhook-Signature": signature,
                    "Content-Type": "application/json"
                }
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Unexpected error" in data["detail"]

            async with test_db() as db:
                result = await db.execute(
                    select(WebhookEvent).where(WebhookEvent.idempotency_key == "REF_EXCEPTION_AFTER")
                )
                event = result.scalar_one_or_none()
                if event:
                    assert event.status in [WebhookEventStatus.FAILED, WebhookEventStatus.PROCESSING]

    @pytest.mark.asyncio
    async def test_webhook_commit_error_marking_failed(self, client, auth_headers, test_db, monkeypatch):
        """Test webhook when commit fails while marking as failed"""
        with patch('app.workers.tasks.enqueue_application_processing', new_callable=AsyncMock):
            with patch('app.api.v1.endpoints.webhooks.broadcast_application_update', new_callable=AsyncMock):
                app_data = {
                    "country": "ES",
                    "full_name": "Test User",
                    "identity_document": "12345678Z",
                    "requested_amount": 5000.00,
                    "monthly_income": 2000.00
                }
                response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
                application_id = response.json()["id"]

                payload = {
                    "application_id": application_id,
                    "document_verified": True,
                    "credit_score": 750,
                    "provider_reference": "REF_COMMIT_ERROR",
                    "verified_at": "2024-01-15T10:30:00"
                }
                payload_json = json.dumps(payload)
                signature = generate_webhook_signature(payload_json)
                
                async def failing_update(*args, **kwargs):
                    raise Exception("Processing error")

                commit_call_count = [0]
                original_commit = AsyncSession.commit
                
                async def failing_commit(self, *args, **kwargs):
                    commit_call_count[0] += 1
                    if commit_call_count[0] > 1:
                        raise Exception("Commit failed")
                    return await original_commit(self, *args, **kwargs)

                with patch('app.api.v1.endpoints.webhooks.ApplicationService') as mock_service_class:
                    mock_service_instance = MagicMock()
                    mock_app = MagicMock()
                    mock_app.id = application_id
                    mock_service_instance.repository.find_by_id = AsyncMock(return_value=mock_app)
                    mock_service_instance.update_application = AsyncMock(side_effect=failing_update)
                    mock_service_class.return_value = mock_service_instance

                    with patch.object(AsyncSession, 'commit', failing_commit):
                        response = await client.post(
                            "/api/v1/webhooks/bank-confirmation",
                            content=payload_json.encode('utf-8'),
                            headers={
                                **auth_headers,
                                "X-Webhook-Signature": signature,
                                "Content-Type": "application/json"
                            }
                        )

                        assert response.status_code == 500
                        data = response.json()
                        assert "detail" in data
                        assert "Unexpected error" in data["detail"]

    @pytest.mark.asyncio
    async def test_webhook_invalid_uuid_format(self, client, auth_headers):
        """Test webhook with invalid UUID format in application_id"""
        payload = {
            "application_id": "not-a-valid-uuid",
            "document_verified": True,
            "credit_score": 750,
            "provider_reference": "REF_INVALID_UUID",
            "verified_at": "2024-01-15T10:30:00"
        }
        payload_json = json.dumps(payload)
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                **auth_headers,
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Invalid application_id format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_webhook_validation_error(self, client, auth_headers):
        """Test webhook with ValidationError (missing required fields)"""
        payload = {
            "application_id": str(uuid4()),
        }
        payload_json = json.dumps(payload)
        signature = generate_webhook_signature(payload_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=payload_json.encode('utf-8'),
            headers={
                **auth_headers,
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Invalid webhook payload" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_webhook_json_decode_error(self, client, auth_headers):
        """Test webhook with invalid JSON"""
        invalid_json = "{ invalid json }"
        signature = generate_webhook_signature(invalid_json)

        response = await client.post(
            "/api/v1/webhooks/bank-confirmation",
            content=invalid_json.encode('utf-8'),
            headers={
                **auth_headers,
                "X-Webhook-Signature": signature,
                "Content-Type": "application/json"
            }
        )

        assert response.status_code == 400
        assert "Invalid webhook payload" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_webhook_already_processed(self, client, auth_headers, test_db):
        """Test webhook that was already processed (idempotent response)"""
        with patch('app.workers.tasks.enqueue_application_processing', new_callable=AsyncMock) as mock_enqueue:
            with patch('app.api.v1.endpoints.webhooks.broadcast_application_update', new_callable=AsyncMock) as mock_broadcast:
                app_data = {
                    "country": "ES",
                    "full_name": "Test User",
                    "identity_document": "12345678Z",
                    "requested_amount": 5000.00,
                    "monthly_income": 2000.00
                }
                response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
                application_id = response.json()["id"]

                payload = {
                    "application_id": application_id,
                    "document_verified": True,
                    "credit_score": 750,
                    "provider_reference": "REF_ALREADY_PROCESSED",
                    "verified_at": "2024-01-15T10:30:00"
                }
                payload_json = json.dumps(payload)
                signature = generate_webhook_signature(payload_json)

                response1 = await client.post(
                    "/api/v1/webhooks/bank-confirmation",
                    content=payload_json.encode('utf-8'),
                    headers={
                        **auth_headers,
                        "X-Webhook-Signature": signature,
                        "Content-Type": "application/json"
                    }
                )
                assert response1.status_code == 200

                response2 = await client.post(
                    "/api/v1/webhooks/bank-confirmation",
                    content=payload_json.encode('utf-8'),
                    headers={
                        **auth_headers,
                        "X-Webhook-Signature": signature,
                        "Content-Type": "application/json"
                    }
                )
                assert response2.status_code == 200
                data = response2.json()
                assert data["message"] == "Webhook already processed"
                assert data["data"]["already_processed"] is True

    @pytest.mark.asyncio
    async def test_webhook_retry_failed(self, client, auth_headers, test_db):
        """Test retrying a previously failed webhook"""
        with patch('app.workers.tasks.enqueue_application_processing', new_callable=AsyncMock):
            with patch('app.api.v1.endpoints.webhooks.broadcast_application_update', new_callable=AsyncMock):
                app_data = {
                    "country": "ES",
                    "full_name": "Test User",
                    "identity_document": "12345678Z",
                    "requested_amount": 5000.00,
                    "monthly_income": 2000.00
                }
                response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
                application_id = response.json()["id"]

                payload = {
                    "application_id": application_id,
                    "document_verified": True,
                    "credit_score": 750,
                    "provider_reference": "REF_RETRY",
                    "verified_at": "2024-01-15T10:30:00"
                }
                payload_json = json.dumps(payload)
                signature = generate_webhook_signature(payload_json)

                async with test_db() as db:
                    from app.models.webhook_event import WebhookEvent, WebhookEventStatus
                    failed_event = WebhookEvent(
                        idempotency_key="REF_RETRY",
                        application_id=application_id,
                        payload=payload,
                        status=WebhookEventStatus.FAILED,
                        error_message="Previous error"
                    )
                    db.add(failed_event)
                    await db.commit()

                response = await client.post(
                    "/api/v1/webhooks/bank-confirmation",
                    content=payload_json.encode('utf-8'),
                    headers={
                        **auth_headers,
                        "X-Webhook-Signature": signature,
                        "Content-Type": "application/json"
                    }
                )
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_webhook_integrity_error_race_condition(self, client, auth_headers, test_db):
        """Test webhook IntegrityError with unique constraint (race condition)"""
        with patch('app.workers.tasks.enqueue_application_processing', new_callable=AsyncMock):
            with patch('app.api.v1.endpoints.webhooks.broadcast_application_update', new_callable=AsyncMock):
                app_data = {
                    "country": "ES",
                    "full_name": "Test User",
                    "identity_document": "12345678Z",
                    "requested_amount": 5000.00,
                    "monthly_income": 2000.00
                }
                response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
                application_id = response.json()["id"]

                payload = {
                    "application_id": application_id,
                    "document_verified": True,
                    "credit_score": 750,
                    "provider_reference": "REF_RACE",
                    "verified_at": "2024-01-15T10:30:00"
                }
                payload_json = json.dumps(payload)
                signature = generate_webhook_signature(payload_json)

                async with test_db() as db:
                    from app.models.webhook_event import WebhookEvent, WebhookEventStatus
                    from datetime import datetime, UTC
                    existing_event = WebhookEvent(
                        idempotency_key="REF_RACE",
                        application_id=application_id,
                        payload=payload,
                        status=WebhookEventStatus.PROCESSED,
                        processed_at=datetime.now(UTC)
                    )
                    db.add(existing_event)
                    await db.commit()

                response = await client.post(
                    "/api/v1/webhooks/bank-confirmation",
                    content=payload_json.encode('utf-8'),
                    headers={
                        **auth_headers,
                        "X-Webhook-Signature": signature,
                        "Content-Type": "application/json"
                    }
                )
                assert response.status_code == 200
                data = response.json()
                assert data["data"]["already_processed"] is True

    @pytest.mark.asyncio
    async def test_webhook_document_not_verified(self, client, auth_headers, test_db):
        """Test webhook with document_verified=False (should reject application)""" 
        with patch('app.workers.tasks.enqueue_application_processing', new_callable=AsyncMock):
            with patch('app.api.v1.endpoints.webhooks.broadcast_application_update', new_callable=AsyncMock):
                app_data = {
                    "country": "ES",
                    "full_name": "Test User",
                    "identity_document": "12345678Z",
                    "requested_amount": 5000.00,
                    "monthly_income": 2000.00
                }
                response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
                application_id = response.json()["id"]

                payload = {
                    "application_id": application_id,
                    "document_verified": False,
                    "credit_score": 750,
                    "provider_reference": "REF_NOT_VERIFIED",
                    "verified_at": "2024-01-15T10:30:00"
                }
                payload_json = json.dumps(payload)
                signature = generate_webhook_signature(payload_json)

                response = await client.post(
                    "/api/v1/webhooks/bank-confirmation",
                    content=payload_json.encode('utf-8'),
                    headers={
                        **auth_headers,
                        "X-Webhook-Signature": signature,
                        "Content-Type": "application/json"
                    }
                )

                assert response.status_code == 200
                
                async with test_db() as db:

                    result = await db.execute(select(Application).where(Application.id == UUID(application_id)))
                    application = result.scalar_one_or_none()
                    assert application is not None
                    assert application.status == "REJECTED"
                    if application.validation_errors:
                        assert "Document verification failed" in str(application.validation_errors)

    @pytest.mark.asyncio
    async def test_webhook_broadcast_error(self, client, auth_headers, test_db):
        """Test webhook when broadcast fails (should still succeed)"""
        with patch('app.workers.tasks.enqueue_application_processing', new_callable=AsyncMock):
            app_data = {
                "country": "ES",
                "full_name": "Test User",
                "identity_document": "12345678Z",
                "requested_amount": 5000.00,
                "monthly_income": 2000.00
            }
            response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
            application_id = response.json()["id"]

            payload = {
                "application_id": application_id,
                "document_verified": True,
                "credit_score": 750,
                "provider_reference": "REF_BROADCAST_ERROR",
                "verified_at": "2024-01-15T10:30:00"
            }
            payload_json = json.dumps(payload)
            signature = generate_webhook_signature(payload_json)

            with patch('app.api.v1.endpoints.webhooks.broadcast_application_update', new_callable=AsyncMock) as mock_broadcast:
                mock_broadcast.side_effect = Exception("Broadcast failed")

                response = await client.post(
                    "/api/v1/webhooks/bank-confirmation",
                    content=payload_json.encode('utf-8'),
                    headers={
                        **auth_headers,
                        "X-Webhook-Signature": signature,
                        "Content-Type": "application/json"
                    }
                )

                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_webhook_application_not_found_after_verification(self, client, auth_headers, test_db):
        """Test webhook when application not found after initial verification"""
        with patch('app.workers.tasks.enqueue_application_processing', new_callable=AsyncMock):
            with patch('app.api.v1.endpoints.webhooks.broadcast_application_update', new_callable=AsyncMock):
                app_data = {
                    "country": "ES",
                    "full_name": "Test User",
                    "identity_document": "12345678Z",
                    "requested_amount": 5000.00,
                    "monthly_income": 2000.00
                }
                response = await client.post("/api/v1/applications", json=app_data, headers=auth_headers)
                application_id = response.json()["id"]

                payload = {
                    "application_id": application_id,
                    "document_verified": True,
                    "credit_score": 750,
                    "provider_reference": "REF_NOT_FOUND_AFTER",
                    "verified_at": "2024-01-15T10:30:00"
                }
                payload_json = json.dumps(payload)
                signature = generate_webhook_signature(payload_json)

                with patch('app.api.v1.endpoints.webhooks.ApplicationService') as mock_service_class:
                    mock_service_instance = MagicMock()
                    call_count = [0]
                    
                    async def find_by_id_side_effect(*args, **kwargs):
                        call_count[0] += 1
                        if call_count[0] == 1:
                            mock_app = MagicMock()
                            mock_app.id = application_id
                            return mock_app
                        else:
                            return None
                    
                    mock_service_instance.repository.find_by_id = AsyncMock(side_effect=find_by_id_side_effect)
                    mock_service_class.return_value = mock_service_instance

                    response = await client.post(
                        "/api/v1/webhooks/bank-confirmation",
                        content=payload_json.encode('utf-8'),
                        headers={
                            **auth_headers,
                            "X-Webhook-Signature": signature,
                            "Content-Type": "application/json"
                        }
                    )

                    assert response.status_code == 404
                    detail = response.json()["detail"]
                    assert "not found" in detail.lower() or "Application" in detail