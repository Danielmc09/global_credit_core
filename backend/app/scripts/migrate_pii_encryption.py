"""Script to migrate existing PII data to encrypted format.

This script should be run after applying the add_pii_encryption.sql migration.
It encrypts any existing plaintext data in the database.

Usage:
    python -m app.scripts.migrate_pii_encryption

IMPORTANT: 
    - Set ENCRYPTION_KEY environment variable before running
    - Backup database before running
    - Run during maintenance window
"""

import asyncio
import sys
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

# Add parent directory to path
sys.path.insert(0, str(__file__).rsplit('/', 3)[0])

from app.core.config import settings
from app.core.encryption import decrypt_value, encrypt_value, ensure_pgcrypto_extension
from app.core.logging import get_logger
from app.db.database import AsyncSessionLocal, engine
from app.models.application import Application

logger = get_logger(__name__)


async def migrate_pii_data():
    """Migrate existing PII data to encrypted format."""
    
    logger.info("Starting PII encryption migration")
    
    # Check encryption key is set
    if not settings.ENCRYPTION_KEY or len(settings.ENCRYPTION_KEY) < 32:
        logger.error(
            "ENCRYPTION_KEY not set or too short. "
            "Set ENCRYPTION_KEY environment variable (min 32 characters) before running migration."
        )
        sys.exit(1)
    
    async with AsyncSessionLocal() as session:
        try:
            # Ensure pgcrypto extension is enabled
            logger.info("Ensuring pgcrypto extension is enabled")
            await ensure_pgcrypto_extension(session)
            
            # Check if columns are already encrypted (BYTEA type)
            # If they are VARCHAR, we need to migrate
            result = await session.execute(
                text("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = 'applications' 
                    AND column_name IN ('identity_document', 'full_name')
                """)
            )
            columns = result.fetchall()
            
            is_encrypted = all(col[1] == 'bytea' for col in columns)
            
            if is_encrypted:
                logger.info("Columns are already encrypted (BYTEA). Checking for unencrypted data...")
                
                # Check if there's any data that looks like plaintext (not encrypted)
                # Encrypted BYTEA data typically starts with specific bytes
                # We'll try to decrypt all rows and see which ones fail
                result = await session.execute(
                    select(Application).where(Application.deleted_at.is_(None))
                )
                applications = result.scalars().all()
                
                migrated_count = 0
                error_count = 0
                
                for app in applications:
                    try:
                        # Try to decrypt - if it fails, it might be plaintext or corrupted
                        # For migration, we'll check if it's a string (plaintext) or bytes (encrypted)
                        if isinstance(app.identity_document, str):
                            # This is plaintext - needs encryption
                            logger.info(f"Encrypting application {app.id}")
                            encrypted_doc = await encrypt_value(session, app.identity_document)
                            encrypted_name = await encrypt_value(session, app.full_name)
                            
                            await session.execute(
                                update(Application)
                                .where(Application.id == app.id)
                                .values(
                                    identity_document=encrypted_doc,
                                    full_name=encrypted_name
                                )
                            )
                            migrated_count += 1
                        else:
                            # Already encrypted (bytes) - verify it can be decrypted
                            try:
                                decrypted = await decrypt_value(session, app.identity_document)
                                logger.debug(f"Application {app.id} already encrypted and valid")
                            except Exception as e:
                                logger.warning(
                                    f"Application {app.id} has encrypted data that cannot be decrypted: {e}"
                                )
                                error_count += 1
                    except Exception as e:
                        logger.error(
                            f"Error processing application {app.id}: {e}",
                            exc_info=True
                        )
                        error_count += 1
                
                await session.commit()
                
                logger.info(
                    f"Migration completed. Migrated: {migrated_count}, Errors: {error_count}"
                )
            else:
                logger.warning(
                    "Columns are not encrypted (VARCHAR). "
                    "Please run the SQL migration (add_pii_encryption.sql) first."
                )
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            await session.rollback()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(migrate_pii_data())
