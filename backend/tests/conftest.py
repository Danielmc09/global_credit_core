"""
Pytest Configuration and Shared Fixtures

This module contains shared test fixtures and configuration for all test modules.
"""

import asyncio
import gc
import os
from collections.abc import Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


os.environ["ENVIRONMENT"] = "test"

if "JWT_SECRET" not in os.environ or not os.environ.get("JWT_SECRET"):
    os.environ["JWT_SECRET"] = "test-jwt-secret-key-for-testing-only-not-for-production-use"
if "WEBHOOK_SECRET" not in os.environ or not os.environ.get("WEBHOOK_SECRET"):
    os.environ["WEBHOOK_SECRET"] = "test-webhook-secret-key-for-testing-only-not-for-production-use"
if "ENCRYPTION_KEY" not in os.environ or not os.environ.get("ENCRYPTION_KEY"):
    os.environ["ENCRYPTION_KEY"] = "test-encryption-key-for-testing-only-not-for-production-use-min-32"

from app.core.logging import get_logger
from app.core.security import create_access_token
from app.db.database import Base, get_db
from app.main import app
from app.services.cache_service import cache

logger = get_logger(__name__)

from app.models import Application, AuditLog, WebhookEvent  # noqa: F401

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")  # Default to 'postgres' for Docker
TEST_DATABASE_URL = f"postgresql+asyncpg://credit_user:credit_pass@{DB_HOST}:5432/credit_db_test"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """
    Create an event loop for the entire test session.

    This ensures all async tests share the same event loop.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_cache():
    """
    Cleanup cache connections after each test.
    
    This ensures Redis connections are properly closed and don't accumulate.
    """
    yield
    try:
        if cache._connected:
            await cache.disconnect()
    except Exception as e:
        logger.warning(f"Error disconnecting cache: {e}")


@pytest.fixture(autouse=True)
def cleanup_memory():
    """
    Force garbage collection after each test to free memory.
    
    This helps prevent memory exhaustion when running large test suites.
    """
    yield
    gc.collect()


@pytest.fixture()
def sample_spain_application():
    """Sample Spanish application data for testing"""
    return {
        "country": "ES",
        "full_name": "Juan García López",
        "identity_document": "12345678Z",
        "requested_amount": 15000.00,
        "monthly_income": 3500.00,
        "country_specific_data": {}
    }


@pytest.fixture()
def sample_mexico_application():
    """Sample Mexican application data for testing"""
    return {
        "country": "MX",
        "full_name": "María Hernández Ramírez",
        "identity_document": "HERM850101MDFRRR01",
        "requested_amount": 50000.00,
        "monthly_income": 12000.00,
        "country_specific_data": {}
    }


@pytest.fixture()
def valid_spanish_dnis():
    """List of valid Spanish DNIs for testing"""
    return [
        "12345678Z",
        "87654321X",
        "00000000T",
        "99999999R",
        "23456789D"
    ]


@pytest.fixture()
def invalid_spanish_dnis():
    """List of invalid Spanish DNIs for testing"""
    return [
        "1234567",      
        "123456789",    
        "ABCDEFGHI",    
        "1234567AA",    
        "12345-678Z",   
        "12345678A"     
    ]


@pytest.fixture()
def valid_mexican_curps():
    """List of valid Mexican CURPs for testing"""
    return [
        "HERM850101MDFRRR01",
        "GOPE900215HDFNRD09",
        "MASA950630MJCRNN02"
    ]


@pytest.fixture()
def invalid_mexican_curps():
    """List of invalid Mexican CURPs for testing"""
    return [
        "HERM850101",          
        "HERM85010AMDFRRR01", 
        "HERM850101XDFRRR01", 
        "1234567890ABCDEF12"  
    ]


@pytest_asyncio.fixture(scope="session")
async def test_db():
    """
    Create a test database session factory for PostgreSQL.

    This fixture:
    - Connects to the PostgreSQL test database
    - Enables necessary extensions (uuid-ossp)
    - Creates ENUM types
    - Creates all tables before each test
    - Provides a session factory that creates independent sessions
    - Drops all tables after the test completes

    Using PostgreSQL instead of SQLite provides:
    - Proper SELECT FOR UPDATE support for concurrency testing
    - Native UUID support (no conversion needed)
    - Better match to production environment

    IMPORTANT: For concurrency tests, this returns a sessionmaker factory.
    Each HTTP request needs its own session to avoid "concurrent operations not permitted" errors.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,  
    )

    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))

    async with engine.begin() as conn:
        def drop_tables(sync_conn):
            Base.metadata.drop_all(bind=sync_conn, checkfirst=True)

        await conn.run_sync(drop_tables)

        await conn.execute(text('DROP TYPE IF EXISTS application_status CASCADE'))
        await conn.execute(text('DROP TYPE IF EXISTS country_code CASCADE'))

    async with engine.begin() as conn:
        def create_tables(sync_conn):
            Base.metadata.create_all(bind=sync_conn, checkfirst=False)

        await conn.run_sync(create_tables)

        await conn.execute(text('''
            CREATE OR REPLACE FUNCTION log_status_change()
            RETURNS TRIGGER AS $$
            BEGIN
                IF OLD.status IS DISTINCT FROM NEW.status THEN
                    INSERT INTO audit_logs (
                        application_id,
                        old_status,
                        new_status,
                        changed_by,
                        change_reason,
                        metadata
                    ) VALUES (
                        NEW.id,
                        OLD.status,
                        NEW.status,
                        COALESCE(current_setting('app.changed_by', true), 'system'),
                        COALESCE(current_setting('app.change_reason', true), 'Status changed automatically'),
                        jsonb_build_object(
                            'previous_risk_score', OLD.risk_score,
                            'current_risk_score', NEW.risk_score,
                            'timestamp', CURRENT_TIMESTAMP,
                            'manual_change', COALESCE(current_setting('app.changed_by', true), 'system') != 'system'
                        )
                    );
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        '''))

        await conn.execute(text('''
            CREATE TRIGGER audit_status_change
                AFTER UPDATE ON applications
                FOR EACH ROW
                WHEN (OLD.status IS DISTINCT FROM NEW.status)
                EXECUTE FUNCTION log_status_change();
        '''))

    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )

    async_session_factory.engine = engine

    yield async_session_factory

    try:
        async with asyncio.timeout(5.0):
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)

                await conn.execute(text("DROP TYPE IF EXISTS application_status CASCADE"))
                await conn.execute(text("DROP TYPE IF EXISTS country_code CASCADE"))
    except asyncio.TimeoutError:
        logger.warning("Database cleanup timed out after 5 seconds")
    except Exception as e:
        logger.warning(f"Error during database cleanup: {e}")
    finally:
        await engine.dispose()
        gc.collect()



@pytest_asyncio.fixture
async def sample_application(test_db, auth_headers, client):
    """
    Create a sample application for testing.

    Returns the application ID as a string.
    """
    app_data = {
        "country": "ES",
        "full_name": "Test User Application",
        "identity_document": "12345678Z",
        "requested_amount": 10000.00,
        "monthly_income": 3000.00,
        "country_specific_data": {}
    }

    response = await client.post(
        "/api/v1/applications",
        json=app_data,
        headers=auth_headers
    )

    assert response.status_code == 201
    return response.json()["id"]


@pytest_asyncio.fixture
async def sample_application_colombia(test_db, auth_headers, client):
    """
    Create a sample Colombian application for testing.

    Returns the application ID as a string.
    """
    app_data = {
        "country": "CO",
        "full_name": "Carlos Martínez Gómez",
        "identity_document": "1234567890",
        "requested_amount": 8000000.00,  
        "monthly_income": 1500000.00,  
        "country_specific_data": {}
    }

    response = await client.post(
        "/api/v1/applications",
        json=app_data,
        headers=auth_headers
    )

    assert response.status_code == 201, f"Failed to create application: {response.text}"
    return response.json()["id"]


@pytest_asyncio.fixture(scope="function")
async def client(test_db):
    """Create test client with test database and transactional isolation"""
    async def override_get_db():
        session = test_db()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            try:
                await session.rollback()
            except Exception:
                pass
            await session.close()

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        try:
            yield ac
        finally:
            async with test_db() as cleanup_session:
                try:
                    await cleanup_session.execute(text("DELETE FROM audit_logs"))
                    await cleanup_session.execute(text("DELETE FROM webhook_events"))
                    await cleanup_session.execute(text("DELETE FROM applications"))
                    await cleanup_session.commit()
                except Exception:
                    await cleanup_session.rollback()
            await ac.aclose()

    app.dependency_overrides.clear()


@pytest.fixture()
def auth_token():
    """Generate a JWT token for a regular user for testing"""
    return create_access_token(
        data={
            "sub": "test-user",
            "email": "test@example.com",
            "role": "user"
        }
    )


@pytest.fixture()
def admin_token():
    """Generate a JWT token for an admin user for testing"""
    return create_access_token(
        data={
            "sub": "admin-user",
            "email": "admin@example.com",
            "role": "admin"
        }
    )


@pytest.fixture()
def auth_headers(auth_token):
    """Get authorization headers for a regular user for testing"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture()
def admin_headers(admin_token):
    """Get authorization headers for an admin user for testing"""
    return {"Authorization": f"Bearer {admin_token}"}
