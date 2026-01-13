"""PII Encryption Module using pgcrypto.

This module provides encryption/decryption functions for PII (Personally Identifiable Information)
using PostgreSQL's pgcrypto extension. All sensitive data is encrypted at rest in the database.

Security:
- Uses pgcrypto's pgp_sym_encrypt/pgp_sym_decrypt for symmetric encryption
- Encryption key is stored in environment variable (never in code)
- All PII fields (identity_document, full_name) are encrypted before storage
"""

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)


async def encrypt_value(session: AsyncSession, plaintext: str) -> bytes:
    """Encrypt a plaintext value using pgcrypto.

    Args:
        session: Database session
        plaintext: Plain text value to encrypt

    Returns:
        Encrypted bytes (BYTEA)

    Raises:
        ValueError: If encryption fails
    """
    if not plaintext:
        return b''

    try:
        result = await session.execute(
            text("SELECT pgp_sym_encrypt(:plaintext, :key)::bytea"),
            {"plaintext": plaintext, "key": settings.ENCRYPTION_KEY}
        )
        encrypted = result.scalar()

        if encrypted is None:
            raise ValueError("Encryption returned None")

        return encrypted
    except Exception as e:
        logger.error(
            "Failed to encrypt value",
            extra={"error": str(e), "error_type": type(e).__name__}
        )
        raise ValueError(f"Encryption failed: {str(e)}") from e


async def decrypt_value(session: AsyncSession, encrypted: bytes) -> str:
    """Decrypt an encrypted value using pgcrypto.

    Args:
        session: Database session
        encrypted: Encrypted bytes (BYTEA) to decrypt

    Returns:
        Decrypted plaintext string

    Raises:
        ValueError: If decryption fails
    """
    if not encrypted:
        return ""

    try:
        if isinstance(encrypted, str):
            return encrypted

        if isinstance(encrypted, memoryview):
            encrypted = bytes(encrypted)
        elif isinstance(encrypted, bytearray):
            encrypted = bytes(encrypted)
        elif not isinstance(encrypted, bytes):
            try:
                encrypted = bytes(encrypted)
            except (TypeError, ValueError) as e:
                logger.error(
                    "Cannot convert encrypted value to bytes",
                    extra={
                        "type": type(encrypted).__name__,
                        "value_preview": str(encrypted)[:50],
                        "error": str(e)
                    }
                )
                raise ValueError(
                    f"Cannot decrypt: encrypted value is not bytes (got {type(encrypted).__name__})"
                ) from e

        stmt = text("SELECT pgp_sym_decrypt(:encrypted, :key)")
        stmt = stmt.bindparams(
            bindparam("encrypted", encrypted, type_=BYTEA),
            bindparam("key", settings.ENCRYPTION_KEY)
        )
        result = await session.execute(stmt)
        decrypted = result.scalar()

        if decrypted is None:
            raise ValueError("Decryption returned None")

        return decrypted
    except Exception as e:
        logger.error(
            "Failed to decrypt value",
            extra={"error": str(e), "error_type": type(e).__name__}
        )
        raise ValueError(f"Decryption failed: {str(e)}") from e


async def encrypt_for_query(session: AsyncSession, plaintext: str) -> bytes:
    """Encrypt a value for use in WHERE clauses.

    This is used when querying encrypted columns. The search value
    must be encrypted with the same key to match encrypted values in the database.

    Args:
        session: Database session
        plaintext: Plain text value to encrypt for querying

    Returns:
        Encrypted bytes for use in WHERE clause
    """
    return await encrypt_value(session, plaintext)


async def ensure_pgcrypto_extension(session: AsyncSession) -> None:
    """Ensure pgcrypto extension is enabled in the database.

    This should be called during database initialization/migration.

    Args:
        session: Database session
    """
    try:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        await session.commit()
        logger.info("pgcrypto extension enabled")
    except Exception as e:
        logger.error(
            "Failed to enable pgcrypto extension",
            extra={"error": str(e), "error_type": type(e).__name__}
        )
        await session.rollback()
        raise
