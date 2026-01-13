"""Tests for encrypted_types.py to improve coverage.

Tests for EncryptedString and EncryptedStringProperty.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.encrypted_types import EncryptedString, EncryptedStringProperty


class TestEncryptedString:
    """Test suite for EncryptedString type"""

    def test_encrypted_string_init(self):
        """Test EncryptedString initialization"""
        encrypted_type = EncryptedString(max_length=50)
        assert encrypted_type.max_length == 50
        assert encrypted_type.impl is not None

    def test_encrypted_string_init_no_max_length(self):
        """Test EncryptedString initialization without max_length"""
        encrypted_type = EncryptedString()
        assert encrypted_type.max_length is None

    def test_process_bind_param_none(self):
        """Test process_bind_param with None value"""
        encrypted_type = EncryptedString()
        result = encrypted_type.process_bind_param(None, None)
        assert result is None

    def test_process_bind_param_string(self):
        """Test process_bind_param with string value"""
        encrypted_type = EncryptedString()
        # The method returns None as per implementation
        # (encryption happens in application code)
        result = encrypted_type.process_bind_param("test_value", None)
        assert result is None

    def test_process_result_value_none(self):
        """Test process_result_value with None value"""
        encrypted_type = EncryptedString()
        result = encrypted_type.process_result_value(None, None)
        assert result is None

    def test_process_result_value_bytes(self):
        """Test process_result_value with bytes value"""
        encrypted_type = EncryptedString()
        # The method returns bytes as per implementation
        # (decryption happens in application code)
        test_bytes = b"encrypted_data"
        result = encrypted_type.process_result_value(test_bytes, None)
        assert result == test_bytes


class TestEncryptedStringProperty:
    """Test suite for EncryptedStringProperty descriptor"""

    def test_encrypted_string_property_init(self):
        """Test EncryptedStringProperty initialization"""
        prop = EncryptedStringProperty("test_column")
        assert prop.column_name == "test_column"
        assert prop.encrypted_attr == "_test_column_encrypted"

    def test_encrypted_string_property_get_none_instance(self):
        """Test __get__ when instance is None (class access)"""
        prop = EncryptedStringProperty("test_column")
        result = prop.__get__(None, type)
        assert result == prop

    @pytest.mark.asyncio
    async def test_encrypted_string_property_get_none_value(self):
        """Test __get__ when column value is None"""
        prop = EncryptedStringProperty("test_column")
        
        # Create mock instance
        mock_instance = MagicMock()
        mock_instance._sa_instance_state = None
        setattr(mock_instance, "test_column", None)
        
        result = await prop.__get__(mock_instance, type)
        assert result is None

    @pytest.mark.asyncio
    async def test_encrypted_string_property_get_string_value(self):
        """Test __get__ when value is already a string (decrypted)"""
        prop = EncryptedStringProperty("test_column")
        
        # Create mock instance
        mock_instance = MagicMock()
        setattr(mock_instance, "test_column", "already_decrypted")
        
        result = await prop.__get__(mock_instance, type)
        assert result == "already_decrypted"

    @pytest.mark.asyncio
    async def test_encrypted_string_property_get_with_session(self):
        """Test __get__ with valid AsyncSession"""
        prop = EncryptedStringProperty("test_column")
        
        # Create mock instance with session
        mock_instance = MagicMock()
        mock_session = AsyncMock(spec=AsyncSession)
        mock_instance_state = MagicMock()
        mock_instance_state.session = mock_session
        mock_instance._sa_instance_state = mock_instance_state
        
        # Set encrypted bytes
        setattr(mock_instance, "test_column", b"encrypted_data")
        
        # Mock decrypt_value
        with patch('app.db.encrypted_types.decrypt_value', new_callable=AsyncMock) as mock_decrypt:
            mock_decrypt.return_value = "decrypted_value"
            
            result = await prop.__get__(mock_instance, type)
            
            assert result == "decrypted_value"
            mock_decrypt.assert_called_once_with(mock_session, b"encrypted_data")
            # Verify cached value
            assert getattr(mock_instance, "_test_column_encrypted") == "decrypted_value"

    @pytest.mark.asyncio
    async def test_encrypted_string_property_get_decrypt_error(self):
        """Test __get__ when decryption fails"""
        prop = EncryptedStringProperty("test_column")
        
        # Create mock instance with session
        mock_instance = MagicMock()
        mock_session = AsyncMock(spec=AsyncSession)
        mock_instance_state = MagicMock()
        mock_instance_state.session = mock_session
        mock_instance._sa_instance_state = mock_instance_state
        
        # Set encrypted bytes
        setattr(mock_instance, "test_column", b"encrypted_data")
        
        # Mock decrypt_value to raise exception
        with patch('app.db.encrypted_types.decrypt_value', new_callable=AsyncMock) as mock_decrypt:
            mock_decrypt.side_effect = Exception("Decryption failed")
            
            with pytest.raises(Exception, match="Decryption failed"):
                await prop.__get__(mock_instance, type)

    @pytest.mark.asyncio
    async def test_encrypted_string_property_get_no_session(self):
        """Test __get__ when instance has no session"""
        prop = EncryptedStringProperty("test_column")
        
        # Create mock instance without session
        mock_instance = MagicMock()
        mock_instance._sa_instance_state = None
        setattr(mock_instance, "test_column", b"encrypted_data")
        
        result = await prop.__get__(mock_instance, type)
        # Should return bytes as fallback
        assert result == b"encrypted_data"

    @pytest.mark.asyncio
    async def test_encrypted_string_property_set_none(self):
        """Test __set__ with None value"""
        prop = EncryptedStringProperty("test_column")
        
        mock_instance = MagicMock()
        await prop.__set__(mock_instance, None)
        
        assert getattr(mock_instance, "test_column") is None
        assert getattr(mock_instance, "_test_column_encrypted") is None

    @pytest.mark.asyncio
    async def test_encrypted_string_property_set_string(self):
        """Test __set__ with string value"""
        prop = EncryptedStringProperty("test_column")
        
        mock_instance = MagicMock()
        await prop.__set__(mock_instance, "plaintext_value")
        
        # Should cache plaintext and set column to None
        # (encryption happens in application code)
        assert getattr(mock_instance, "_test_column_encrypted") == "plaintext_value"
        assert getattr(mock_instance, "test_column") is None
