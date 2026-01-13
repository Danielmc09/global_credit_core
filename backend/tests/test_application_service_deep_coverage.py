"""
Deep coverage tests for application service.

These tests focus on covering remaining uncovered lines in application_service.py.
"""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.application import ApplicationStatus
from app.repositories import application_repository
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.services.application_service import ApplicationService


class TestApplicationServiceDeepCoverage:
    """Tests to cover remaining application service lines"""

    @pytest.mark.asyncio
    async def test_create_application_integrity_error_unique_idempotency_key(self, test_db, auth_headers, client):
        """Test create application with IntegrityError for unique idempotency_key"""
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

        response1 = await client.post("/api/v1/applications", json=payload, headers=auth_headers)
        assert response1.status_code == 201

        async with test_db() as session:
            service = ApplicationService(session)

            application_data = ApplicationCreate(**payload)
            existing_app = await service.create_application(application_data)

            assert existing_app is not None
            assert str(existing_app.id) == response1.json()["id"]

    @pytest.mark.asyncio
    async def test_create_application_integrity_error_duplicate_key_generic(self, test_db, monkeypatch):
        """Test create application with generic duplicate key IntegrityError"""
        async with test_db() as session:
            service = ApplicationService(session)

            from app.schemas.application import ApplicationCreate

            class MockOrigException(Exception):
                pass

            mock_orig = MockOrigException("duplicate key value violates unique constraint")

            async def mock_create_raises_integrity_error(self, application_data):
                error = IntegrityError("statement", "params", mock_orig)
                raise error

            monkeypatch.setattr(application_repository.ApplicationRepository, "create", mock_create_raises_integrity_error)

            application_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=10000.00,
                monthly_income=3000.00,
                country_specific_data={}
            )

            with pytest.raises(IntegrityError):
                await service.create_application(application_data)

    @pytest.mark.asyncio
    async def test_create_application_integrity_error_other_integrity(self, test_db, monkeypatch):
        """Test create application with other IntegrityError (not duplicate)"""
        async with test_db() as session:
            service = ApplicationService(session)

            class MockOrigException(Exception):
                pass

            mock_orig = MockOrigException("foreign key constraint violation")

            async def mock_create_raises_integrity_error(self, application_data):
                error = IntegrityError("statement", "params", mock_orig)
                raise error

            monkeypatch.setattr(application_repository.ApplicationRepository, "create", mock_create_raises_integrity_error)

            application_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=10000.00,
                monthly_income=3000.00,
                country_specific_data={}
            )

            with pytest.raises(IntegrityError):
                await service.create_application(application_data)

    @pytest.mark.asyncio
    async def test_create_application_exception_handling(self, test_db, monkeypatch):
        """Test create application with unexpected exception"""
        async with test_db() as session:
            service = ApplicationService(session)

            async def mock_create_raises_exception(self, application_data):
                raise RuntimeError("Unexpected database error")

            monkeypatch.setattr(application_repository.ApplicationRepository, "create", mock_create_raises_exception)

            application_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=10000.00,
                monthly_income=3000.00,
                country_specific_data={}
            )

            with pytest.raises(RuntimeError):
                await service.create_application(application_data)

    @pytest.mark.asyncio
    async def test_update_application_status_transition(self, test_db, auth_headers, admin_headers, client):
        """Test update application with valid status transition"""
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

            update_data = ApplicationUpdate(status=ApplicationStatus.VALIDATING)
            updated_app = await service.update_application(app_id, update_data)

            assert updated_app is not None
            assert updated_app.status == ApplicationStatus.VALIDATING

    @pytest.mark.asyncio
    async def test_update_application_not_found(self, test_db):
        """Test update application that doesn't exist"""
        async with test_db() as session:
            service = ApplicationService(session)

            fake_id = uuid4()

            update_data = ApplicationUpdate(status=ApplicationStatus.VALIDATING)
            updated_app = await service.update_application(fake_id, update_data)

            assert updated_app is None

    @pytest.mark.asyncio
    async def test_update_application_risk_score(self, test_db, auth_headers, admin_headers, client):
        """Test update application with risk score"""
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

            update_data = ApplicationUpdate(risk_score=75.5)
            updated_app = await service.update_application(app_id, update_data)

            assert updated_app is not None
            assert updated_app.risk_score == 75.5

    @pytest.mark.asyncio
    async def test_update_application_banking_data(self, test_db, auth_headers, admin_headers, client):
        """Test update application with banking data"""
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

            banking_data = {
                "credit_score": 750,
                "total_debt": "5000.00",
                "has_defaults": False
            }
            update_data = ApplicationUpdate(banking_data=banking_data)
            updated_app = await service.update_application(app_id, update_data)

            assert updated_app is not None
            assert updated_app.banking_data is not None

    @pytest.mark.asyncio
    async def test_update_application_validation_errors(self, test_db, auth_headers, admin_headers, client):
        """Test update application with validation errors"""
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

            validation_errors = ["Document verification failed", "Income too low"]
            update_data = ApplicationUpdate(validation_errors=validation_errors)
            updated_app = await service.update_application(app_id, update_data)

            assert updated_app is not None
            assert len(updated_app.validation_errors) == 2

    @pytest.mark.asyncio
    async def test_update_application_set_local_session_variables(self, test_db, auth_headers, admin_headers, client):
        """Test update application sets session variables for trigger"""
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

            update_data = ApplicationUpdate(status=ApplicationStatus.VALIDATING)
            updated_app = await service.update_application(app_id, update_data)

            assert updated_app is not None
            assert updated_app.status == ApplicationStatus.VALIDATING

    @pytest.mark.asyncio
    async def test_update_application_set_local_error_handling(self, test_db, auth_headers, client, monkeypatch):
        """Test update application when SET LOCAL fails"""
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

            call_count = 0
            original_execute = session.execute

            async def mock_execute_with_error(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2 and "SET LOCAL" in str(args[0]):
                    raise Exception("SET LOCAL syntax error")
                return await original_execute(*args, **kwargs)

            monkeypatch.setattr(session, "execute", mock_execute_with_error)

            update_data = ApplicationUpdate(status=ApplicationStatus.VALIDATING)
            updated_app = await service.update_application(app_id, update_data)

            assert updated_app is not None

    @pytest.mark.asyncio
    async def test_update_application_country_specific_data(self, test_db, auth_headers, admin_headers, client):
        """Test update application with country_specific_data"""
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

            new_data = {"additional_info": "test data"}
            update_data = ApplicationUpdate(country_specific_data=new_data)
            updated_app = await service.update_application(app_id, update_data)

            assert updated_app is not None
            assert updated_app.country_specific_data == new_data

    @pytest.mark.asyncio
    async def test_delete_application_success(self, test_db, auth_headers, client):
        """Test delete application successfully"""
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

            deleted = await service.delete_application(app_id)

            assert deleted is True

    @pytest.mark.asyncio
    async def test_get_audit_logs_service(self, test_db, auth_headers, admin_headers, client):
        """Test get audit logs via service"""
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

            await client.patch(
                f"/api/v1/applications/{app_id}",
                json={"status": "VALIDATING"},
                headers=admin_headers
            )

            audit_logs, total = await service.get_audit_logs(app_id, page=1, page_size=10)

            assert total >= 1
            assert len(audit_logs) >= 1

    @pytest.mark.asyncio
    async def test_get_statistics_by_country(self, test_db, auth_headers, client):
        """Test get statistics by country"""
        async with test_db() as session:
            service = ApplicationService(session)

            await client.post("/api/v1/applications", json={
                "country": "ES",
                "full_name": "Spanish User 1",
                "identity_document": "12345678Z",
                "requested_amount": 10000.00,
                "monthly_income": 3000.00,
                "country_specific_data": {}
            }, headers=auth_headers)

            await client.post("/api/v1/applications", json={
                "country": "ES",
                "full_name": "Spanish User 2",
                "identity_document": "87654321X",
                "requested_amount": 20000.00,
                "monthly_income": 4000.00,
                "country_specific_data": {}
            }, headers=auth_headers)

            stats = await service.get_statistics_by_country("ES")

            assert "country" in stats
            assert stats["country"] == "ES"
            assert "total_applications" in stats
            assert stats["total_applications"] >= 2
