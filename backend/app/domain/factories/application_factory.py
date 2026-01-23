from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.security import decrypt_pii_fields, encrypt_value
from ...core.logging import get_logger
from ...domain.validators import handle_integrity_error
from ...models.application import Application, ApplicationStatus
from ...repositories.application_repository import ApplicationRepository
from ...schemas.application import ApplicationCreate
from ...utils import validate_amount_precision

logger = get_logger(__name__)


class ApplicationFactory:
    """Factory for creating Application entities with business logic."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = ApplicationRepository(db)


    async def find_by_idempotency_key_decrypted(
        self,
        idempotency_key: str | None
    ) -> Application | None:
        """Find application by idempotency key and decrypt PII fields.
        
        Args:
            idempotency_key: Idempotency key to check
            
        Returns:
            Existing application with decrypted PII if found, None otherwise
        """
        if not idempotency_key:
            return None
        
        existing_app = await self.repository.find_by_idempotency_key(
            idempotency_key,
            for_update=True
        )
        
        if existing_app:
            logger.info(
                "Idempotent request detected - returning existing application",
                extra={
                    'idempotency_key': idempotency_key,
                    'existing_application_id': str(existing_app.id),
                    'existing_status': existing_app.status
                }
            )
            # Decrypt PII fields in-place
            decrypted_name, decrypted_doc = await decrypt_pii_fields(
                self.db,
                encrypted_full_name=existing_app.full_name,
                encrypted_identity_document=existing_app.identity_document
            )
            existing_app.full_name = decrypted_name
            existing_app.identity_document = decrypted_doc
        
        return existing_app


    async def create_from_request(
        self,
        application_data: ApplicationCreate,
        currency: str,
        validation_result
    ) -> Application:
        """Create application from request data, handling encryption and persistence.
        
        Args:
            application_data: Application creation data
            currency: Normalized currency code
            validation_result: Validation result from strategy
            
        Returns:
            Created application with decrypted PII fields
            
        Raises:
            ValueError: If creation fails due to duplicates
        """
        # Validate precision
        validated_amount = validate_amount_precision(application_data.requested_amount)
        validated_income = validate_amount_precision(application_data.monthly_income)
        
        # Encrypt PII fields
        encrypted_document = await encrypt_value(self.db, application_data.identity_document)
        encrypted_name = await encrypt_value(self.db, application_data.full_name)
        
        # Create application entity
        application = Application(
            country=application_data.country,
            full_name=encrypted_name,
            identity_document=encrypted_document,
            requested_amount=validated_amount,
            monthly_income=validated_income,
            currency=currency,
            status=ApplicationStatus.PENDING,
            country_specific_data=application_data.country_specific_data or {},
            validation_errors=validation_result.warnings,
            idempotency_key=application_data.idempotency_key
        )
        
        # Persist to database
        try:
            application = await self.repository.create(application)
        except IntegrityError as e:
            return await handle_integrity_error(self.db, e, application_data)
        
        logger.info(
            "Application created",
            extra={'application_id': str(application.id), 'status': application.status}
        )
        
        # Decrypt PII fields before returning
        decrypted_name, decrypted_doc = await decrypt_pii_fields(
            self.db,
            encrypted_full_name=application.full_name,
            encrypted_identity_document=application.identity_document
        )
        application.full_name = decrypted_name
        application.identity_document = decrypted_doc
        
        return application
