import re
from decimal import Decimal
from typing import Any

from ..core.constants import (
    ApprovalRecommendation,
    BusinessRules,
    CountryBusinessRules,
    CountryCode,
    CreditScore,
    RiskLevel,
    RiskScore,
)
from ..providers import BankingProvider
from .base import (
    BankingData,
    BaseCountryStrategy,
    RiskAssessment,
    ValidationResult,
)


class ColombiaStrategy(BaseCountryStrategy):
    """Strategy for Colombia (CO) credit applications."""

    COUNTRY_CODE = CountryCode.COLOMBIA
    DOCUMENT_TYPE = "Cédula"
    MINIMUM_INCOME = CountryBusinessRules.COLOMBIA_MIN_INCOME
    MAXIMUM_LOAN_AMOUNT = CountryBusinessRules.COLOMBIA_MAX_LOAN_AMOUNT
    MAX_PAYMENT_TO_INCOME_RATIO = CountryBusinessRules.COLOMBIA_MAX_PAYMENT_TO_INCOME
    MIN_CREDIT_SCORE = int(CountryBusinessRules.COLOMBIA_MIN_CREDIT_SCORE)

    def __init__(self, banking_provider: BankingProvider):
        super().__init__(
            country_code=CountryCode.COLOMBIA,
            country_name=CountryCode.COUNTRY_NAMES[CountryCode.COLOMBIA],
            banking_provider=banking_provider
        )

    def validate_identity_document(self, document: str) -> ValidationResult:
        """Validate Colombian Cédula de Ciudadanía.

        Format: 6-10 digits
        Example: 1234567890
        """
        cedula = re.sub(r'\D', '', document)

        if len(cedula) < 6 or len(cedula) > 10:
            return ValidationResult(
                is_valid=False,
                errors=[f"Cédula must have 6-10 digits, got {len(cedula)}"],
            )

        if not cedula.isdigit():
            return ValidationResult(
                is_valid=False,
                errors=["Cédula must contain only digits"],
            )

        return ValidationResult(is_valid=True)

    def apply_business_rules(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        banking_data: BankingData,
        country_specific_data: dict[str, Any],
    ) -> RiskAssessment:
        """Apply Colombia-specific business rules.

        **CRITICAL: All parameters use Decimal for precision. Never use float.**

        Rules:
        - Minimum income: COP $1,500,000
        - Maximum loan amount: COP $50,000,000
        - Payment-to-income ratio: <= 40%
        - Minimum credit score: 600
        """
        validation_errors = []
        risk_score = Decimal("0.0")
        decision = ApprovalRecommendation.APPROVE

        # Check 1: Minimum income
        risk_score, decision = self._check_minimum_income(
            monthly_income, validation_errors, risk_score, decision
        )

        # Check 2: Maximum loan amount
        risk_score, decision = self._check_max_loan_amount(
            requested_amount, validation_errors, risk_score, decision
        )

        # Check 3: Payment-to-income ratio
        risk_score, decision = self._check_payment_to_income_ratio(
            requested_amount, monthly_income, banking_data, validation_errors, risk_score, decision
        )

        # Check 4: Credit score
        risk_score, decision = self._check_credit_score(
            banking_data, validation_errors, risk_score, decision
        )

        # Check 5: Active defaults
        risk_score, decision = self._check_defaults(
            banking_data, validation_errors, risk_score, decision
        )

        # Check 6: Total debt
        risk_score, decision = self._check_total_debt(
            monthly_income, banking_data, validation_errors, risk_score, decision
        )

        # Apply positive adjustments
        risk_score = self._apply_positive_adjustments(banking_data, risk_score)

        # Finalize risk score and determine level
        risk_score, risk_level, decision = self._finalize_risk_assessment(
            validation_errors, risk_score, decision
        )

        requires_review = decision == ApprovalRecommendation.REVIEW

        return RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            approval_recommendation=decision,
            reasons=validation_errors if validation_errors else ['Standard credit profile'],
            requires_review=requires_review
        )


    def _check_minimum_income(
        self,
        monthly_income: Decimal,
        validation_errors: list,
        risk_score: Decimal,
        decision: str
    ) -> tuple[Decimal, str]:
        """Check if monthly income meets minimum requirement."""
        if monthly_income < self.MINIMUM_INCOME:
            validation_errors.append(
                f"Monthly income (COP ${monthly_income:,.0f}) below minimum "
                f"(COP ${self.MINIMUM_INCOME:,.0f})"
            )
            risk_score += BusinessRules.RISK_SCORE_PENALTY_LOW_INCOME
            decision = ApprovalRecommendation.REJECT
        return risk_score, decision


    def _check_max_loan_amount(
        self,
        requested_amount: Decimal,
        validation_errors: list,
        risk_score: Decimal,
        decision: str
    ) -> tuple[Decimal, str]:
        """Check if requested amount exceeds maximum allowed."""
        if requested_amount > self.MAXIMUM_LOAN_AMOUNT:
            validation_errors.append(
                f"Requested amount (COP ${requested_amount:,.0f}) exceeds maximum "
                f"(COP ${self.MAXIMUM_LOAN_AMOUNT:,.0f})"
            )
            risk_score += BusinessRules.RISK_SCORE_PENALTY_HIGH_AMOUNT
            decision = ApprovalRecommendation.REJECT
        return risk_score, decision


    def _check_payment_to_income_ratio(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        banking_data: BankingData,
        validation_errors: list,
        risk_score: Decimal,
        decision: str
    ) -> tuple[Decimal, str]:
        """Check payment-to-income ratio (max 40%)."""
        loan_term = Decimal(str(BusinessRules.DEFAULT_LOAN_TERM_MONTHS_COLOMBIA))
        if loan_term <= 0:
            raise ValueError("Loan term must be greater than zero")
        
        monthly_payment = requested_amount / loan_term
        total_monthly_obligations = (
            banking_data.monthly_obligations or Decimal('0')
        ) + monthly_payment
        
        if monthly_income <= 0 or abs(monthly_income) < Decimal('0.01'):
            payment_to_income = Decimal("100.0")
        else:
            payment_to_income = (total_monthly_obligations / monthly_income) * Decimal("100")

        if payment_to_income > self.MAX_PAYMENT_TO_INCOME_RATIO:
            validation_errors.append(
                f"Payment-to-income ratio ({payment_to_income:.1f}%) exceeds "
                f"maximum ({self.MAX_PAYMENT_TO_INCOME_RATIO}%)"
            )
            risk_score += BusinessRules.RISK_SCORE_PENALTY_HIGH_RATIO
            decision = ApprovalRecommendation.REJECT
        
        return risk_score, decision


    def _check_credit_score(
        self,
        banking_data: BankingData,
        validation_errors: list,
        risk_score: Decimal,
        decision: str
    ) -> tuple[Decimal, str]:
        """Check credit score (minimum 600)."""
        if banking_data.credit_score and banking_data.credit_score < self.MIN_CREDIT_SCORE:
            validation_errors.append(
                f"Credit score ({banking_data.credit_score}) below minimum "
                f"({self.MIN_CREDIT_SCORE})"
            )
            risk_score += BusinessRules.RISK_SCORE_PENALTY_LOW_CREDIT
            decision = ApprovalRecommendation.REJECT
        return risk_score, decision


    def _check_defaults(
        self,
        banking_data: BankingData,
        validation_errors: list,
        risk_score: Decimal,
        decision: str
    ) -> tuple[Decimal, str]:
        """Check for active defaults in DataCrédito."""
        if banking_data.has_defaults:
            validation_errors.append("Applicant has active defaults in DataCrédito")
            risk_score += BusinessRules.RISK_SCORE_PENALTY_DEFAULT
            decision = ApprovalRecommendation.REJECT
        return risk_score, decision


    def _check_total_debt(
        self,
        monthly_income: Decimal,
        banking_data: BankingData,
        validation_errors: list,
        risk_score: Decimal,
        decision: str
    ) -> tuple[Decimal, str]:
        """Check if total debt exceeds maximum months of income."""
        if banking_data.total_debt and banking_data.total_debt > (
            monthly_income * Decimal(str(BusinessRules.MAX_DEBT_TO_INCOME_MONTHS))
        ):
            validation_errors.append(
                f"Total debt (COP ${banking_data.total_debt:,.0f}) exceeds "
                f"{BusinessRules.MAX_DEBT_TO_INCOME_MONTHS} months of income"
            )
            risk_score += Decimal("15")
            if decision == ApprovalRecommendation.APPROVE:
                decision = ApprovalRecommendation.REVIEW
        return risk_score, decision


    def _apply_positive_adjustments(
        self,
        banking_data: BankingData,
        risk_score: Decimal
    ) -> Decimal:
        """Apply positive adjustments for good credit score and account age."""
        # High credit score bonus
        if banking_data.credit_score and banking_data.credit_score >= CreditScore.HIGH_SCORE_THRESHOLD:
            risk_score = max(Decimal("0"), risk_score - BusinessRules.RISK_SCORE_ADJUSTMENT_HIGH_CREDIT)

        # Good account age bonus
        account_age_months = banking_data.additional_data.get("account_age_months")
        if account_age_months and account_age_months >= BusinessRules.MIN_ACCOUNT_AGE_MONTHS:
            risk_score = max(Decimal("0"), risk_score - BusinessRules.RISK_SCORE_ADJUSTMENT_GOOD_ACCOUNT_AGE)

        return risk_score


    def _finalize_risk_assessment(
        self,
        validation_errors: list,
        risk_score: Decimal,
        decision: str
    ) -> tuple[Decimal, str, str]:
        """Finalize risk score and determine risk level.
        
        Returns:
            Tuple of (risk_score, risk_level, decision)
        """
        risk_score = min(RiskScore.MAX_SCORE, risk_score)

        if not validation_errors:
            decision = ApprovalRecommendation.APPROVE
            risk_score = max(RiskScore.DEFAULT_MIN, risk_score)

        if risk_score >= RiskScore.CRITICAL_THRESHOLD:
            risk_level = RiskLevel.CRITICAL
        elif risk_score >= RiskScore.HIGH_THRESHOLD:
            risk_level = RiskLevel.HIGH
        elif risk_score >= RiskScore.MEDIUM_THRESHOLD:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        return risk_score, risk_level, decision

