"""Tests for transaction helper utilities."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_value
from app.models.application import Application, ApplicationStatus, CountryCode
from app.utils.transaction_helpers import safe_transaction


@pytest.mark.asyncio
async def test_safe_transaction_commits_on_success(test_db):
    """Test that safe_transaction commits on success."""
    from decimal import Decimal

    async with test_db() as db:
        async with safe_transaction(db):
            # Create a test application with encrypted fields
            encrypted_name = await encrypt_value(db, "Test User")
            encrypted_doc = await encrypt_value(db, "12345678Z")

            application = Application(
                country=CountryCode.ES,
                full_name=encrypted_name,
                identity_document=encrypted_doc,
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR",
                status=ApplicationStatus.PENDING
            )
            db.add(application)
            # Transaction should be committed automatically

        # Verify that the application was persisted
        result = await db.execute(
            select(Application).where(Application.id == application.id)
        )
        persisted_app = result.scalar_one_or_none()
        assert persisted_app is not None
        # full_name is encrypted (BYTEA), so we check it exists
        assert persisted_app.full_name is not None


@pytest.mark.asyncio
async def test_safe_transaction_rolls_back_on_error(test_db):
    """Test that safe_transaction rolls back on exception."""
    from decimal import Decimal

    async with test_db() as db:
        # Create an application first with encrypted fields
        encrypted_name = await encrypt_value(db, "Test User")
        encrypted_doc = await encrypt_value(db, "12345678Z")

        application = Application(
            country=CountryCode.ES,
            full_name=encrypted_name,
            identity_document=encrypted_doc,
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("3000.00"),
            currency="EUR",
            status=ApplicationStatus.PENDING
        )
        db.add(application)
        await db.commit()
        application_id = application.id
        original_name = application.full_name

        # Now try to update it within a transaction that fails
        with pytest.raises(ValueError, match="Test error"):
            async with safe_transaction(db):
                # Fetch the application
                result = await db.execute(
                    select(Application).where(Application.id == application_id)
                )
                app = result.scalar_one_or_none()
                assert app is not None

                # Make a change (encrypt new value)
                app.full_name = await encrypt_value(db, "Updated Name")

                # Raise an exception to trigger rollback
                raise ValueError("Test error")

        # Verify that the change was rolled back
        await db.refresh(application)
        assert application.full_name == original_name  # Original encrypted value


@pytest.mark.asyncio
async def test_safe_transaction_re_raises_exception(test_db):
    """Test that safe_transaction re-raises exceptions after rollback."""
    async with test_db() as db:
        with pytest.raises(RuntimeError, match="Test runtime error"):
            async with safe_transaction(db):
                raise RuntimeError("Test runtime error")

        # Verify that the exception was re-raised
        # (if we get here, the exception was properly re-raised)


@pytest.mark.asyncio
async def test_safe_transaction_multiple_operations(test_db):
    """Test that safe_transaction handles multiple operations correctly."""
    from decimal import Decimal

    async with test_db() as db:
        async with safe_transaction(db):
            # Create multiple applications with encrypted fields
            app1 = Application(
                country=CountryCode.ES,
                full_name=await encrypt_value(db, "User 1"),
                identity_document=await encrypt_value(db, "11111111A"),
                requested_amount=Decimal("5000.00"),
                monthly_income=Decimal("2000.00"),
                currency="EUR",
                status=ApplicationStatus.PENDING
            )
            app2 = Application(
                country=CountryCode.MX,
                full_name=await encrypt_value(db, "User 2"),
                identity_document=await encrypt_value(db, "HERM850101MDFRRR01"),
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("5000.00"),
                currency="MXN",
                status=ApplicationStatus.PENDING
            )
            db.add(app1)
            db.add(app2)
            # Transaction should commit both

        # Verify both were persisted
        result1 = await db.execute(
            select(Application).where(Application.id == app1.id)
        )
        result2 = await db.execute(
            select(Application).where(Application.id == app2.id)
        )
        assert result1.scalar_one_or_none() is not None
        assert result2.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_safe_transaction_nested_operations(test_db):
    """Test that safe_transaction works with nested database operations."""
    from decimal import Decimal

    async with test_db() as db:
        async with safe_transaction(db):
            # Create application with encrypted fields
            application = Application(
                country=CountryCode.ES,
                full_name=await encrypt_value(db, "Test User"),
                identity_document=await encrypt_value(db, "12345678Z"),
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR",
                status=ApplicationStatus.PENDING
            )
            db.add(application)
            await db.flush()  # Flush to get the ID

            # Update the application within the same transaction
            application.status = ApplicationStatus.VALIDATING
            # Transaction should commit both operations

        # Verify both operations were committed
        result = await db.execute(
            select(Application).where(Application.id == application.id)
        )
        persisted_app = result.scalar_one_or_none()
        assert persisted_app is not None
        assert persisted_app.status == ApplicationStatus.VALIDATING
