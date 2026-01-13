"""
Additional tests for encryption module to improve coverage.

These tests focus on edge cases and error handling scenarios.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import (
    decrypt_value,
    encrypt_value,
    ensure_pgcrypto_extension,
)


class TestEncryptionEdgeCases:
    """Test encryption edge cases and error handling"""

    @pytest.mark.asyncio
    async def test_encrypt_value_empty_string(self, test_db):
        """Test encrypting empty string"""
        async with test_db() as session:
            result = await encrypt_value(session, "")

            # Should return empty bytes
            assert result == b''

    @pytest.mark.asyncio
    async def test_encrypt_value_none(self, test_db):
        """Test encrypting None (should be handled as empty)"""
        async with test_db() as session:
            # None should be treated as empty string
            result = await encrypt_value(session, None)

            # Should return empty bytes
            assert result == b''

    @pytest.mark.asyncio
    async def test_decrypt_value_empty_bytes(self, test_db):
        """Test decrypting empty bytes"""
        async with test_db() as session:
            result = await decrypt_value(session, b'')

            # Should return empty string
            assert result == ""

    @pytest.mark.asyncio
    async def test_decrypt_value_string_input(self, test_db):
        """Test decrypting string input (from mocks in tests)"""
        async with test_db() as session:
            # String input should be returned as-is (for test mocks)
            result = await decrypt_value(session, "test-string")

            assert result == "test-string"

    @pytest.mark.asyncio
    async def test_decrypt_value_memoryview(self, test_db):
        """Test decrypting memoryview input"""
        async with test_db() as session:
            # First encrypt a value
            encrypted = await encrypt_value(session, "test-value")

            # Convert to memoryview (as asyncpg might return)
            memview = memoryview(encrypted)

            # Should handle memoryview correctly
            result = await decrypt_value(session, memview)

            assert result == "test-value"

    @pytest.mark.asyncio
    async def test_decrypt_value_bytearray(self, test_db):
        """Test decrypting bytearray input"""
        async with test_db() as session:
            # First encrypt a value
            encrypted = await encrypt_value(session, "test-value")

            # Convert to bytearray (as asyncpg might return)
            bytearr = bytearray(encrypted)

            # Should handle bytearray correctly
            result = await decrypt_value(session, bytearr)

            assert result == "test-value"

    @pytest.mark.asyncio
    async def test_decrypt_value_invalid_type(self, test_db):
        """Test decrypting invalid type that can't be converted to bytes"""
        async with test_db() as session:
            # Try to decrypt an object that can't be converted to bytes
            with pytest.raises(ValueError) as exc_info:
                await decrypt_value(session, {"invalid": "type"})

            assert "Cannot decrypt" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_encrypt_value_encryption_failure(self, test_db, monkeypatch):
        """Test handling of encryption failure"""
        async with test_db() as session:
            # Mock session.execute to raise an exception
            original_execute = session.execute

            async def failing_execute(*args, **kwargs):
                raise Exception("Database error during encryption")

            monkeypatch.setattr(session, "execute", failing_execute)

            with pytest.raises(ValueError) as exc_info:
                await encrypt_value(session, "test-value")

            assert "Encryption failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_encrypt_value_returns_none(self, test_db, monkeypatch):
        """Test handling when encryption returns None"""
        async with test_db() as session:
            # Mock session.execute to return None
            class MockResult:
                def scalar(self):
                    return None

            async def mock_execute(*args, **kwargs):
                return MockResult()

            monkeypatch.setattr(session, "execute", mock_execute)

            with pytest.raises(ValueError) as exc_info:
                await encrypt_value(session, "test-value")

            assert "Encryption returned None" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_decrypt_value_decryption_failure(self, test_db):
        """Test handling of decryption failure with invalid encrypted data"""
        async with test_db() as session:
            # Try to decrypt invalid encrypted data
            invalid_encrypted = b"not-valid-encrypted-data"

            with pytest.raises(ValueError) as exc_info:
                await decrypt_value(session, invalid_encrypted)

            assert "Decryption failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_decrypt_value_returns_none(self, test_db, monkeypatch):
        """Test handling when decryption returns None"""
        async with test_db() as session:
            # First encrypt a value
            encrypted = await encrypt_value(session, "test-value")

            # Mock session.execute to return None
            class MockResult:
                def scalar(self):
                    return None

            async def mock_execute(*args, **kwargs):
                return MockResult()

            monkeypatch.setattr(session, "execute", mock_execute)

            with pytest.raises(ValueError) as exc_info:
                await decrypt_value(session, encrypted)

            assert "Decryption returned None" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_ensure_pgcrypto_extension_success(self, test_db):
        """Test ensuring pgcrypto extension (should already be enabled in test setup)"""
        async with test_db() as session:
            # Should not raise an exception (extension already exists)
            await ensure_pgcrypto_extension(session)

            # Verify extension exists
            result = await session.execute(
                text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto')")
            )
            exists = result.scalar()
            assert exists is True

    @pytest.mark.asyncio
    async def test_ensure_pgcrypto_extension_failure(self, test_db, monkeypatch):
        """Test handling of pgcrypto extension failure"""
        async with test_db() as session:
            # Mock session.execute to raise an exception
            original_execute = session.execute

            async def failing_execute(*args, **kwargs):
                if "CREATE EXTENSION" in str(args[0]):
                    raise Exception("Permission denied")
                return await original_execute(*args, **kwargs)

            monkeypatch.setattr(session, "execute", failing_execute)

            with pytest.raises(Exception):
                await ensure_pgcrypto_extension(session)

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_round_trip(self, test_db):
        """Test full encrypt/decrypt round trip"""
        async with test_db() as session:
            original_value = "test-value-12345"

            # Encrypt
            encrypted = await encrypt_value(session, original_value)
            assert encrypted != original_value
            assert isinstance(encrypted, bytes)
            assert len(encrypted) > 0

            # Decrypt
            decrypted = await decrypt_value(session, encrypted)
            assert decrypted == original_value

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_special_characters(self, test_db):
        """Test encrypting/decrypting values with special characters"""
        async with test_db() as session:
            test_cases = [
                "test@example.com",
                "123-456-7890",
                "Test Value with Spaces",
                "Unicode: 测试 🚀",
                "SQL injection attempt: '; DROP TABLE users; --",
            ]

            for original_value in test_cases:
                encrypted = await encrypt_value(session, original_value)
                decrypted = await decrypt_value(session, encrypted)
                assert decrypted == original_value
