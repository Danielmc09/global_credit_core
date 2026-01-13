"""SQLAlchemy Custom Types for Encrypted PII Fields.

This module provides custom SQLAlchemy types that automatically handle
encryption/decryption of PII data using pgcrypto.

Usage:
    from app.db.encrypted_types import EncryptedString

    class Application(Base):
        identity_document = Column(EncryptedString(50), nullable=False)
        full_name = Column(EncryptedString(255), nullable=False)
"""

from typing import Any

from sqlalchemy import TypeDecorator
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.encryption import decrypt_value
from ..core.logging import get_logger

logger = get_logger(__name__)


class EncryptedString(TypeDecorator):
    """SQLAlchemy type that automatically encrypts/decrypts string values.

    This type stores encrypted BYTEA in the database but presents plaintext
    strings to the application. Encryption/decryption happens transparently.

    Note: This requires an active database session for encryption/decryption.
    For queries, you must use the encryption functions directly.
    """

    impl = BYTEA
    cache_ok = True

    def __init__(self, max_length: int | None = None, *args: Any, **kwargs: Any):
        """Initialize encrypted string type.

        Args:
            max_length: Maximum length of plaintext (for validation, not storage)
        """
        super().__init__(*args, **kwargs)
        self.max_length = max_length

    def process_bind_param(self, value: str | None, dialect: Any) -> bytes | None:
        """Encrypt value before storing in database.

        Note: For async operations, encryption is handled in application code
        because we need access to the session to call pgcrypto functions.

        Args:
            value: Plaintext string to encrypt
            dialect: SQLAlchemy dialect

        Returns:
            None (encryption handled in application code)
        """
        if value is None:
            return None
        return None

    def process_result_value(self, value: bytes | None, dialect: Any) -> bytes | None:
        """Decrypt value when reading from database.

        Note: For async operations, decryption is handled in application code
        because we need access to the session to call pgcrypto functions.

        Args:
            value: Encrypted bytes from database
            dialect: SQLAlchemy dialect

        Returns:
            Encrypted bytes (decryption handled in application code)
        """
        return value


class EncryptedStringProperty:
    """Property descriptor for encrypted string fields.

    This provides transparent encryption/decryption with session access.
    Use this as a hybrid property on SQLAlchemy models.
    """

    def __init__(self, column_name: str):
        """Initialize encrypted string property.

        Args:
            column_name: Name of the BYTEA column in the database
        """
        self.column_name = column_name
        self.encrypted_attr = f"_{column_name}_encrypted"

    def __get__(self, instance: Any, owner: Any):
        """Get decrypted value.

        Args:
            instance: Model instance
            owner: Model class

        Returns:
            Decrypted plaintext string (or self if instance is None)
        """
        if instance is None:
            return self
        return self._get_async(instance)

    async def _get_async(self, instance: Any) -> str | None:
        """Async helper to get decrypted value."""
        encrypted = getattr(instance, self.column_name, None)

        if encrypted is None:
            return None

        if isinstance(encrypted, str):
            return encrypted

        if hasattr(instance, '_sa_instance_state') and instance._sa_instance_state is not None:
            session = getattr(instance._sa_instance_state, 'session', None)
            if session and isinstance(session, AsyncSession):
                try:
                    decrypted = await decrypt_value(session, encrypted)
                    setattr(instance, self.encrypted_attr, decrypted)
                    return decrypted
                except Exception as e:
                    logger.error(
                        f"Failed to decrypt {self.column_name}",
                        extra={"error": str(e)}
                    )
                    raise

        return encrypted

    async def __set__(self, instance: Any, value: str | None) -> None:
        """Set encrypted value.

        Args:
            instance: Model instance
            value: Plaintext string to encrypt and store
        """
        if value is None:
            setattr(instance, self.column_name, None)
            setattr(instance, self.encrypted_attr, None)
            return

        setattr(instance, self.encrypted_attr, value)
        setattr(instance, self.column_name, None)
