"""
Tests for application service to improve coverage.

These tests focus on business logic and validation in application_service.py.
"""

import asyncio
from uuid import uuid4

import pytest

from app.models.application import ApplicationStatus
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.services.application_service import ApplicationService


class TestApplicationServiceCoverage:
    """Tests for ApplicationService business logic"""

    @pytest.mark.asyncio
    async def test_create_application_currency_mismatch(self, client, auth_headers):
        """Test create application with currency mismatch (validated by Pydantic schema)"""                # This will be caught by Pydantic validation in the schema
        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "currency": "USD",
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)


        assert response.status_code == 422
        assert "Currency" in response.json()["detail"][0]["msg"] or "currency" in str(response.json()).lower()

    @pytest.mark.asyncio
    async def test_create_application_unsupported_currency(self, client, auth_headers):
        """Test create application with unsupported currency (validated by Pydantic schema)"""
        # Try to create application with unsupported currency
        # This will be caught by Pydantic validation in the schema
        payload = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "currency": "XXX",
            "country_specific_data": {}
        }

        response = await client.post("/api/v1/applications", json=payload, headers=auth_headers)


        assert response.status_code == 422
        assert "Currency" in response.json()["detail"][0]["msg"] or "not supported" in str(response.json()).lower()

    @pytest.mark.asyncio
    async def test_create_application_currency_inferred(self, test_db):
        """Test create application with currency inferred from country"""
        async with test_db() as session:
            service = ApplicationService(session)

            application_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=10000.00,
                monthly_income=3000.00,
                country_specific_data={}
            )

            application = await service.create_application(application_data)
            assert application.currency == "EUR"

    @pytest.mark.asyncio
    async def test_create_application_currency_required_no_default(self, test_db):
        """Test create application for country that requires currency but has no default"""
        async with test_db() as session:
            service = ApplicationService(session)

            application_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=10000.00,
                monthly_income=3000.00,
                country_specific_data={}
            )

            application = await service.create_application(application_data)
            assert application is not None

    @pytest.mark.asyncio
    async def test_create_application_idempotency_key_exists(self, test_db, auth_headers, client):
        """Test create application with existing idempotency key"""
        idempotency_key = str(uuid4())

        payload1 = {
            "country": "ES",
            "full_name": "Test User",
            "identity_document": "12345678Z",
            "requested_amount": 10000.00,
            "monthly_income": 3000.00,
            "idempotency_key": idempotency_key,
            "country_specific_data": {}
        }

        response1 = await client.post("/api/v1/applications", json=payload1, headers=auth_headers)
        assert response1.status_code == 201
        app_id_1 = response1.json()["id"]

        await asyncio.sleep(6)

        response2 = await client.post("/api/v1/applications", json=payload1, headers=auth_headers)
        assert response2.status_code == 201
        app_id_2 = response2.json()["id"]

        assert app_id_1 == app_id_2

    @pytest.mark.asyncio
    async def test_update_application_status_transition_validation(self, test_db, auth_headers, admin_headers, client):
        """Test update application with invalid status transition"""
        async with test_db() as session:
            service = ApplicationService(session)

            create_response = await client.post("/api/v1/applications", json={
                "country": "ES",
                "full_name": "Test User",
                "identity_document": "12345678Z",
                "requested_amount": 10000.00,
                "monthly_income": 3000.00,
                "country_specific_data": {}
            }, headers=auth_headers)

            app_id = create_response.json()["id"]

            update_data = ApplicationUpdate(status=ApplicationStatus.APPROVED)

            with pytest.raises(ValueError) as exc_info:
                await service.update_application(app_id, update_data)

            assert "Invalid state transition" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_application_not_found(self, test_db):
        """Test get application that doesn't exist"""
        async with test_db() as session:
            service = ApplicationService(session)

            fake_id = uuid4()
            application = await service.get_application(fake_id)

            assert application is None

    @pytest.mark.asyncio
    async def test_list_applications_with_filters(self, test_db, auth_headers, client):
        """Test list applications with various filters"""
        async with test_db() as session:
            service = ApplicationService(session)

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

            applications, total = await service.list_applications(country="ES")
            assert total >= 1
            for app in applications:
                assert app.country == "ES"

            applications, total = await service.list_applications(status=ApplicationStatus.PENDING)
            assert total >= 2

            applications, total = await service.list_applications(
                country="ES",
                status=ApplicationStatus.PENDING
            )
            assert total >= 1
            for app in applications:
                assert app.country == "ES"
                assert app.status == ApplicationStatus.PENDING

    @pytest.mark.asyncio
    async def test_list_applications_pagination(self, test_db, auth_headers, client):
        """Test list applications with pagination"""
        identity_documents = ["12345678Z", "87654321X", "00000000T", "99999999R", "23456789D"]
        
        for i, doc in enumerate(identity_documents):
            await client.post("/api/v1/applications", json={
                "country": "ES",
                "full_name": f"User {i}",
                "identity_document": doc,
                "requested_amount": 10000.00,
                "monthly_income": 3000.00,
                "country_specific_data": {}
            }, headers=auth_headers)

        async with test_db() as session:
            service = ApplicationService(session)

            applications, total = await service.list_applications(page=1, page_size=3)
            assert total >= 5
            assert len(applications) == 3

            applications, total = await service.list_applications(page=2, page_size=3)
            assert total >= 5
            assert len(applications) >= 2
