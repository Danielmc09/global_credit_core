import asyncio
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.constants import (
    ApprovalRecommendation,
    ErrorMessages,
    Timeout,
)
from ..core.exceptions import (
    ApplicationNotFoundError,
    ExternalServiceError,
    InvalidApplicationIdError,
    NetworkTimeoutError,
    StateTransitionError,
    ValidationError,
)
from ..core.logging import get_logger
from ..domain.state_machine import is_final_state, validate_transition
from ..infrastructure.messaging import publish_application_update
from ..infrastructure.monitoring import get_tracer
from ..infrastructure.security import decrypt_pii_fields
from ..models.application import Application, ApplicationStatus
from ..strategies.factory import get_country_strategy
from ..utils import (
    decimal_to_string,
    format_datetime,
    validate_banking_data_precision,
    validate_risk_score_precision,
)
from ..utils.transaction_helpers import safe_transaction

logger = get_logger(__name__)


class ApplicationProcessingService:
    """Service for processing credit applications.
    
    Encapsulates the business logic for:
    1. Validating application state
    2. Fetching banking data (external)
    3. Applying business rules
    4. Updating application status
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.tracer = get_tracer(__name__)


    async def process_application(self, application_id: str) -> str:
        """Process a credit application.
        
        Orchestrates the complete application processing workflow:
        1. Validates UUID and transitions to VALIDATING
        2. Fetches banking data and applies business rules
        3. Updates final status and broadcasts changes

        Args:
            application_id: Application UUID string

        Returns:
            Success message

        Raises:
            ApplicationNotFoundError, InvalidApplicationIdError, StateTransitionError, etc.
        """
        uuid_obj = self._validate_and_parse_uuid(application_id)
        
        # Check if application is already in a final state (idempotency check)
        application = await self._get_application(uuid_obj)
        if not application:
            raise ApplicationNotFoundError(
                ErrorMessages.APPLICATION_NOT_FOUND.format(application_id=application_id)
            )
        
        if is_final_state(application.status):
            logger.info(
                "Application already in final state, skipping processing",
                extra={
                    'application_id': application_id,
                    'current_status': application.status.value,
                    'reason': 'idempotency_check'
                }
            )
            return f"Application {application_id} already processed: {application.status}"
        
        await self._transition_to_validating(uuid_obj, application_id)
        
        await self._process_and_update_application(uuid_obj, application_id)
        
        if application:
            await self._broadcast_status_update(
                application_id=str(application.id),
                status=application.status,
                risk_score=application.risk_score,
                updated_at=application.updated_at
            )

        logger.info(
            "Application processing completed",
            extra={
                'application_id': application_id,
                'final_status': application.status,
            }
        )

        return f"Application {application_id} processed: {application.status}"


    def _validate_and_parse_uuid(self, application_id: str) -> UUID:
        """Validate and parse application ID to UUID.
        
        Args:
            application_id: Application UUID string
            
        Returns:
            Parsed UUID object
            
        Raises:
            InvalidApplicationIdError: If UUID format is invalid
        """
        try:
            return UUID(application_id)
        except ValueError as e:
            raise InvalidApplicationIdError(
                f"Invalid UUID format: {application_id}"
            ) from e


    async def _transition_to_validating(self, uuid_obj: UUID, application_id: str) -> None:
        """Transition application to VALIDATING status.
        
        Args:
            uuid_obj: Application UUID
            application_id: Application UUID string for error messages
            
        Raises:
            ApplicationNotFoundError: If application not found
            StateTransitionError: If transition is invalid
        """
        async with safe_transaction(self.db):
            application = await self._get_application(uuid_obj)
            if not application:
                raise ApplicationNotFoundError(
                    ErrorMessages.APPLICATION_NOT_FOUND.format(application_id=application_id)
                )

            logger.debug(
                "Validating application before processing",
                extra={'application_id': application_id}
            )
            await asyncio.sleep(Timeout.VALIDATION_STAGE_DELAY)

            old_status = application.status
            new_status = ApplicationStatus.VALIDATING
            try:
                validate_transition(old_status, new_status)
            except ValueError as e:
                raise StateTransitionError(str(e)) from e
            application.status = new_status
        
        application = await self._get_application(uuid_obj)
        if application:
            await self._broadcast_status_update(
                application_id=str(application.id),
                status=application.status,
                risk_score=application.risk_score,
                updated_at=application.updated_at
            )


    async def _process_and_update_application(self, uuid_obj: UUID, application_id: str) -> None:
        """Fetch data, apply rules, and update application.
        
        Args:
            uuid_obj: Application UUID
            application_id: Application UUID string for error messages
            
        Raises:
            ApplicationNotFoundError: If application not found
            ValidationError: If country strategy not found
        """
        async with safe_transaction(self.db):
            application = await self._get_application(uuid_obj)
            if not application:
                raise ApplicationNotFoundError(
                    ErrorMessages.APPLICATION_NOT_FOUND.format(application_id=application_id)
                )

            decrypted_full_name, decrypted_identity_document = await decrypt_pii_fields(
                self.db,
                application.full_name,
                application.identity_document
            )
            self.db.expire(application, ['full_name', 'identity_document'])
            
            strategy = self._get_country_strategy(application.country)

            banking_data = await self._fetch_banking_data(
                strategy, 
                application, 
                decrypted_identity_document, 
                decrypted_full_name
            )
            await asyncio.sleep(Timeout.BANKING_DATA_DELAY)

            risk_assessment = await self._apply_business_rules(
                strategy,
                application,
                banking_data
            )
            await asyncio.sleep(Timeout.BUSINESS_RULES_DELAY)

            self._update_application_state(application, banking_data, risk_assessment)


    async def _get_application(self, uuid_obj: UUID) -> Application | None:
        """Helper to fetch application by UUID."""
        result = await self.db.execute(
            select(Application).where(Application.id == uuid_obj)
        )
        return result.scalar_one_or_none()


    async def _broadcast_status_update(
        self,
        application_id: str,
        status: ApplicationStatus,
        risk_score: float | None,
        updated_at
    ):
        """Helper to broadcast status update.
        
        Args:
            application_id: Application UUID as string
            status: Application status enum
            risk_score: Optional risk score
            updated_at: Updated timestamp (datetime object)
        """
        status_value = status.value if hasattr(status, 'value') else str(status)
        updated_at_str = (
            format_datetime(updated_at, "%Y-%m-%dT%H:%M:%S")
            if updated_at 
            else None
        )
        
        try:
            await publish_application_update(
                application_id=application_id,
                status=status_value,
                risk_score=risk_score,
                updated_at=updated_at_str
            )
            logger.debug(
                "Published status update to Redis",
                extra={'application_id': application_id, 'status': status_value}
            )
        except Exception as e:
            logger.warning(
                "Failed to broadcast status update",
                extra={'application_id': application_id, 'error': str(e)},
                exc_info=True
            )


    async def _fetch_banking_data(self, strategy, application, identity_document, full_name):
        """Fetch banking data using the strategy."""
        logger.info(
            "Fetching banking data",
            extra={
                'application_id': str(application.id),
                'country': application.country
            }
        )
        # creamos un span para validar el timeout
        with self.tracer.start_as_current_span("fetch_banking_data") as provider_span:
            provider_span.set_attribute("provider.country", application.country)
            provider_span.set_attribute("application.id", str(application.id))
            
            try:
                banking_data = await strategy.get_banking_data(
                    identity_document,
                    full_name
                )
                provider_span.set_attribute("provider.success", True)
                return banking_data
            except (TimeoutError, asyncio.TimeoutError) as e:
                provider_span.set_attribute("provider.success", False)
                provider_span.record_exception(e)
                raise NetworkTimeoutError(
                    f"Timeout fetching banking data: {str(e)}"
                ) from e
            except Exception as e:
                provider_span.set_attribute("provider.success", False)
                provider_span.record_exception(e)
                raise ExternalServiceError(
                    f"Error fetching banking data: {str(e)}"
                ) from e


    async def _apply_business_rules(self, strategy, application, banking_data):
        """Apply business rules using the strategy."""
        logger.info(
            "Applying business rules",
            extra={'application_id': str(application.id)}
        )

        with self.tracer.start_as_current_span("apply_business_rules") as rules_span:
            rules_span.set_attribute("application.id", str(application.id))
            rules_span.set_attribute("application.country", application.country)
            rules_span.set_attribute("application.requested_amount", str(application.requested_amount))
            
            risk_assessment = strategy.apply_business_rules(
                application.requested_amount,
                application.monthly_income,
                banking_data,
                application.country_specific_data
            )
            
            rules_span.set_attribute("risk.score", str(risk_assessment.risk_score))
            rules_span.set_attribute("risk.level", risk_assessment.risk_level)
            rules_span.set_attribute("approval.recommendation", risk_assessment.approval_recommendation)
            
            return risk_assessment


    def _update_application_state(self, application, banking_data, risk_assessment):
        """Update the application object with results."""
        banking_data_dict = banking_data.dict()
        banking_data_dict = decimal_to_string(banking_data_dict)
        banking_data_dict = validate_banking_data_precision(banking_data_dict)

        application.banking_data = banking_data_dict
        application.risk_score = validate_risk_score_precision(risk_assessment.risk_score)

        if not application.country_specific_data:
            application.country_specific_data = {}
        application.country_specific_data['risk_level'] = risk_assessment.risk_level

        old_status = application.status
        if risk_assessment.approval_recommendation == ApprovalRecommendation.APPROVE:
            new_status = ApplicationStatus.APPROVED
        elif risk_assessment.approval_recommendation == ApprovalRecommendation.REJECT:
            new_status = ApplicationStatus.REJECTED
        elif risk_assessment.approval_recommendation == ApprovalRecommendation.REVIEW:
            new_status = ApplicationStatus.UNDER_REVIEW
        else:
            new_status = ApplicationStatus.UNDER_REVIEW

        try:
            validate_transition(old_status, new_status)
        except ValueError as e:
            raise StateTransitionError(str(e)) from e
        application.status = new_status

        application.validation_errors = risk_assessment.reasons


    def _get_country_strategy(self, country: str):
        """Get country strategy for processing.
        
        Args:
            country: Country code
            
        Returns:
            Country strategy instance
            
        Raises:
            ValidationError: If country is not supported
        """
        try:
            return get_country_strategy(country)
        except ValueError as e:
            raise ValidationError(f"Unsupported country: {country}") from e
