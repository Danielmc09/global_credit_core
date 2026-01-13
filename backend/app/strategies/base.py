"""Base Strategy Pattern for Country-Specific Business Rules.

This module defines the abstract interface that all country strategies must implement.
Each country has different validation rules, document types, and banking providers.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class ValidationResult(BaseModel):
    """Result of validation operations."""
    is_valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    metadata: dict[str, Any] = {}


class BankingData(BaseModel):
    """Banking data obtained from provider."""
    provider_name: str
    account_status: str
    credit_score: int | None = None
    total_debt: Decimal | None = None
    monthly_obligations: Decimal | None = None
    has_defaults: bool = False
    additional_data: dict[str, Any] = {}


class RiskAssessment(BaseModel):
    """Risk assessment result."""
    risk_score: Decimal  # 0-100
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    approval_recommendation: str  # APPROVE, REJECT, REVIEW
    reasons: list[str] = []
    requires_review: bool = False


class BaseCountryStrategy(ABC):
    """Abstract base class for country-specific credit application strategies.

    Each country implementation must provide:
    1. Document validation logic
    2. Banking provider integration
    3. Business rules for credit evaluation
    """

    def __init__(self, country_code: str, country_name: str, banking_provider: Any):
        """Initialize the country strategy.

        Args:
            country_code: ISO 3166-1 alpha-2 country code
            country_name: Human-readable country name
            banking_provider: Banking provider instance (required). Must implement
                            the BankingProvider interface.

        Raises:
            ValueError: If banking_provider is None
        """
        if banking_provider is None:
            raise ValueError(
                "banking_provider is required. A BankingProvider instance must be provided. "
                "Use CountryStrategyFactory.get_strategy() which automatically provides a provider."
            )
        self.country_code = country_code
        self.country_name = country_name
        self.banking_provider = banking_provider

    @abstractmethod
    def validate_identity_document(self, document: str) -> ValidationResult:
        """Validate the identity document format and checksum for this country.

        Args:
            document: The identity document number

        Returns:
            ValidationResult with validation status and any errors
        """

    async def get_banking_data(
        self,
        document: str,
        full_name: str
    ) -> BankingData:
        """Retrieve banking data from the country's banking provider.

        This method uses the injected banking_provider which is required at initialization.
        The provider is protected by circuit breaker for resilience.

        Args:
            document: Identity document number
            full_name: Full name of the applicant

        Returns:
            BankingData with information from the banking provider

        Raises:
            ValueError: If banking_provider was not provided during initialization
        """
        if self.banking_provider is None:
            raise ValueError(
                "banking_provider is required. A BankingProvider instance must be provided "
                "during strategy initialization. Use CountryStrategyFactory.get_strategy() "
                "which automatically provides a provider."
            )
        
        # Use provider with circuit breaker protection
        from ..core.circuit_breaker import call_provider_with_circuit_breaker
        
        # Get provider name from provider
        provider_name = self.banking_provider.get_provider_name()
        
        return await call_provider_with_circuit_breaker(
            provider_func=self.banking_provider.fetch_banking_data,
            country=self.country_code,
            provider_name=provider_name,
            document=document,
            full_name=full_name
        )

    @abstractmethod
    def apply_business_rules(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        banking_data: BankingData,
        country_specific_data: dict[str, Any]
    ) -> RiskAssessment:
        """Apply country-specific business rules to assess credit risk.

        **CRITICAL: All monetary values MUST use Decimal, never float.**
        This ensures precision in financial calculations and prevents rounding errors.

        Args:
            requested_amount: Amount of credit requested (Decimal - never float)
            monthly_income: Monthly income of applicant (Decimal - never float)
            banking_data: Banking information from provider
            country_specific_data: Additional country-specific data

        Returns:
            RiskAssessment with risk score and recommendation.
            Risk score must be Decimal, not float.

        Example:
            ```python
            # CORRECT
            assessment = strategy.apply_business_rules(
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("5000.00"),
                banking_data=banking_data,
                country_specific_data={}
            )

            # WRONG - Never use float
            assessment = strategy.apply_business_rules(
                requested_amount=10000.0,  # float
                monthly_income=5000.0,     # float
                ...
            )
            ```
        """

    def get_document_type_name(self) -> str:
        """Get the name of the document type for this country."""
        return "Identity Document"

    def get_required_fields(self) -> list[str]:
        """Get list of required fields for this country."""
        return [
            "country",
            "full_name",
            "identity_document",
            "requested_amount",
            "monthly_income"
        ]

    def calculate_debt_to_income_ratio(
        self,
        monthly_income: Decimal,
        monthly_debt: Decimal
    ) -> Decimal:
        """Helper method to calculate debt-to-income ratio.

        Args:
            monthly_income: Monthly income
            monthly_debt: Monthly debt obligations

        Returns:
            Debt-to-income ratio as a percentage
        """
        if monthly_income <= 0:
            return Decimal('100.0')
        if abs(monthly_income) < Decimal('0.01'):
            return Decimal('100.0')
        return (monthly_debt / monthly_income) * Decimal('100.0')

    def calculate_payment_to_income_ratio(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        loan_term_months: int = 36
    ) -> Decimal:
        """Helper method to estimate monthly payment and calculate payment-to-income ratio.

        Args:
            requested_amount: Amount requested
            monthly_income: Monthly income
            loan_term_months: Loan term in months (default 36)

        Returns:
            Estimated payment-to-income ratio as a percentage
        """
        if loan_term_months <= 0:
            raise ValueError("Loan term must be greater than zero")
        
        estimated_monthly_payment = requested_amount / Decimal(loan_term_months)
        
        if monthly_income <= 0:
            return Decimal('100.0')
        if abs(monthly_income) < Decimal('0.01'):
            return Decimal('100.0')
        return (estimated_monthly_payment / monthly_income) * Decimal('100.0')
