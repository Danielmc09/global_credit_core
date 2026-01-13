"""
Debug test to identify ENUM issues
"""
import traceback

import pytest
from sqlalchemy import select, text

from app.core.encryption import encrypt_value
from app.models import Application, ApplicationStatus, CountryCode


@pytest.mark.asyncio()
async def test_enum_creation_and_insert(test_db):
    """Test ENUM creation and data insertion"""
    # Create a session
    async with test_db() as session:
        # Try to query the ENUM types with more details
        result = await session.execute(text("""
            SELECT typname, typtype, typnamespace
            FROM pg_type
            WHERE typname IN ('country_code', 'application_status')
        """))
        enum_types = result.fetchall()
        print(f"Found ENUM types: {enum_types}")

        # Also check the schema
        result = await session.execute(text("""
            SELECT nspname FROM pg_namespace WHERE nspname = 'public'
        """))
        schema = result.fetchone()
        print(f"Public schema: {schema}")

        # Check if tables exist
        result = await session.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'applications'
        """))
        table = result.fetchone()
        print(f"Applications table exists: {table}")

        # Check what columns exist in the applications table
        result = await session.execute(text("""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'applications'
            ORDER BY ordinal_position
        """))
        columns = result.fetchall()
        print(f"Applications table columns: {columns}")

        # Try to insert a simple record with encrypted PII fields
        try:
            encrypted_name = await encrypt_value(session, "Test User")
            encrypted_doc = await encrypt_value(session, "12345678Z")

            app = Application(
                country=CountryCode.ES,
                full_name=encrypted_name,
                identity_document=encrypted_doc,
                requested_amount=1000.00,
                monthly_income=2000.00,
                currency="EUR",
                status=ApplicationStatus.PENDING
            )
            session.add(app)
            await session.flush()
            print(f"Successfully inserted application with ID: {app.id}")

            # Try to query it back
            result = await session.execute(
                select(Application).where(Application.id == app.id)
            )
            retrieved = result.scalar_one_or_none()
            print(f"Retrieved application: {retrieved}")

            assert retrieved is not None
            assert retrieved.country == CountryCode.ES

        except Exception as e:
            print(f"Error inserting application: {type(e).__name__}: {e}")
            traceback.print_exc()
            raise
