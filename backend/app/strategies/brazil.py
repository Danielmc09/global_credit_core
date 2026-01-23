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


class BrazilStrategy(BaseCountryStrategy):
    """Strategy for Brazil (BR) credit applications."""

    COUNTRY_CODE = CountryCode.BRAZIL
    DOCUMENT_TYPE = "CPF"
    MINIMUM_INCOME = CountryBusinessRules.BRAZIL_MIN_INCOME
    MAXIMUM_LOAN_AMOUNT = CountryBusinessRules.BRAZIL_MAX_LOAN_AMOUNT
    MAX_LOAN_TO_INCOME_RATIO = CountryBusinessRules.BRAZIL_MAX_LOAN_TO_INCOME_RATIO
    MAX_DEBT_TO_INCOME_RATIO = CountryBusinessRules.BRAZIL_MAX_DEBT_TO_INCOME
    MIN_CREDIT_SCORE = int(CountryBusinessRules.BRAZIL_MIN_CREDIT_SCORE)

    def __init__(self, banking_provider: BankingProvider):
        super().__init__(
            country_code=CountryCode.BRAZIL,
            country_name=CountryCode.COUNTRY_NAMES[CountryCode.BRAZIL],
            banking_provider=banking_provider
        )

    def validate_identity_document(self, document: str) -> ValidationResult:
        """Validate Brazilian CPF (Cadastro de Pessoas Físicas).

        Format: 11 digits
        Example: 12345678909

        Algorithm:
        - First digit: sum of first 9 digits multiplied by 10-position
        - Second digit: sum of first 10 digits multiplied by 11-position
        """
        cpf = re.sub(r'[.\-]', '', document)

        if len(cpf) != 11:
            return ValidationResult(
                is_valid=False,
                errors=[f"CPF must have 11 digits, got {len(cpf)}"],
            )

        if cpf == cpf[0] * 11:
            return ValidationResult(
                is_valid=False,
                errors=["CPF cannot have all equal digits"],
            )

        try:
            sum_first = sum(int(cpf[i]) * (10 - i) for i in range(9))
            first_digit = (sum_first * 10) % 11
            if first_digit == 10:
                first_digit = 0

            if int(cpf[9]) != first_digit:
                return ValidationResult(
                    is_valid=False,
                    errors=["Invalid CPF checksum (first digit)"],
                )

            sum_second = sum(int(cpf[i]) * (11 - i) for i in range(10))
            second_digit = (sum_second * 10) % 11
            if second_digit == 10:
                second_digit = 0

            if int(cpf[10]) != second_digit:
                return ValidationResult(
                    is_valid=False,
                    errors=["Invalid CPF checksum (second digit)"],
                )

            return ValidationResult(is_valid=True)

        except (ValueError, IndexError) as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Invalid CPF format: {e!s}"],
            )

    def apply_business_rules(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        banking_data: BankingData,
        country_specific_data: dict[str, Any],
    ) -> RiskAssessment:
        """Apply Brazil-specific business rules.

        **CRITICAL: All parameters use Decimal for precision. Never use float.**

        Rules:
        - Minimum income: R$ 2,000
        - Maximum loan amount: R$ 100,000
        - Loan-to-income ratio: <= 5x annual income
        - Debt-to-income ratio: <= 35%
        - Minimum credit score: 550
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

        # Check 3: Loan-to-income ratio
        risk_score, decision = self._check_loan_to_income_ratio(
            requested_amount, monthly_income, validation_errors, risk_score, decision
        )

        # Check 4: Debt-to-income ratio
        risk_score, decision = self._check_debt_to_income_ratio(
            requested_amount, monthly_income, banking_data, validation_errors, risk_score, decision
        )

        # Check 5: Credit score
        risk_score, decision = self._check_credit_score(
            banking_data, validation_errors, risk_score, decision
        )

        # Check 6: Active defaults
        risk_score, decision = self._check_defaults(
            banking_data, validation_errors, risk_score, decision
        )

        # Apply positive adjustments
        risk_score = self._apply_positive_adjustments(banking_data, risk_score)

        # Finalize risk score and determine level
        risk_score, risk_level, decision = self._finalize_risk_assessment(
            validation_errors, risk_score, decision
        )

        return RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            approval_recommendation=decision,
            reasons=validation_errors if validation_errors else ['Standard credit profile'],
            requires_review=(decision == ApprovalRecommendation.REVIEW)
        )


    def _check_minimum_income(
        self,
        monthly_income: Decimal,
        validation_errors: list,
        risk_score: Decimal,
        decision: str
    ) -> tuple[Decimal, str]:
        """Check if monthly income meets minimum requirement (R$ 2,000)."""
        if monthly_income < self.MINIMUM_INCOME:
            validation_errors.append(
                f"Monthly income (R$ {monthly_income:.2f}) below minimum "
                f"(R$ {self.MINIMUM_INCOME:.2f})"
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
        """Check if requested amount exceeds maximum allowed (R$ 100,000)."""
        if requested_amount > self.MAXIMUM_LOAN_AMOUNT:
            validation_errors.append(
                f"Requested amount (R$ {requested_amount:.2f}) exceeds maximum "
                f"(R$ {self.MAXIMUM_LOAN_AMOUNT:.2f})"
            )
            risk_score += BusinessRules.RISK_SCORE_PENALTY_HIGH_DEBT
            decision = ApprovalRecommendation.REJECT
        return risk_score, decision


    def _check_loan_to_income_ratio(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        validation_errors: list,
        risk_score: Decimal,
        decision: str
    ) -> tuple[Decimal, str]:
        """Check loan-to-income ratio (max 5x annual income)."""
        annual_income = monthly_income * BusinessRules.MONTHS_PER_YEAR_DECIMAL
        
        if annual_income <= 0 or abs(annual_income) < Decimal('0.01'):
            loan_to_income_ratio = RiskScore.MAX_SCORE
        else:
            loan_to_income_ratio = requested_amount / annual_income

        if loan_to_income_ratio > self.MAX_LOAN_TO_INCOME_RATIO:
            validation_errors.append(
                f"Loan-to-income ratio ({loan_to_income_ratio:.2f}x) exceeds "
                f"maximum ({self.MAX_LOAN_TO_INCOME_RATIO}x annual income)"
            )
            risk_score += BusinessRules.RISK_SCORE_PENALTY_HIGH_AMOUNT
            decision = ApprovalRecommendation.REJECT

        return risk_score, decision


    def _check_debt_to_income_ratio(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        banking_data: BankingData,
        validation_errors: list,
        risk_score: Decimal,
        decision: str
    ) -> tuple[Decimal, str]:
        """Check debt-to-income ratio (max 35%)."""
        if banking_data.monthly_obligations:
            new_monthly_payment = requested_amount / BusinessRules.DEFAULT_LOAN_TERM_MONTHS_COLOMBIA
            total_obligations = banking_data.monthly_obligations + new_monthly_payment
            
            if monthly_income <= 0 or abs(monthly_income) < Decimal('0.01'):
                debt_to_income = Decimal("100.0")
            else:
                debt_to_income = (total_obligations / monthly_income) * BusinessRules.PERCENTAGE_MULTIPLIER

            if debt_to_income > self.MAX_DEBT_TO_INCOME_RATIO:
                validation_errors.append(
                    f"Debt-to-income ratio ({debt_to_income:.1f}%) exceeds "
                    f"maximum ({self.MAX_DEBT_TO_INCOME_RATIO}%)"
                )
                risk_score += BusinessRules.RISK_SCORE_PENALTY_HIGH_DEBT_BRAZIL
                if decision == ApprovalRecommendation.APPROVE:
                    decision = ApprovalRecommendation.REVIEW

        return risk_score, decision


    def _check_credit_score(
        self,
        banking_data: BankingData,
        validation_errors: list,
        risk_score: Decimal,
        decision: str
    ) -> tuple[Decimal, str]:
        """Check credit score (minimum 550)."""
        if banking_data.credit_score and banking_data.credit_score < self.MIN_CREDIT_SCORE:
            validation_errors.append(
                f"Credit score ({banking_data.credit_score}) below minimum "
                f"({self.MIN_CREDIT_SCORE})"
            )
            risk_score += BusinessRules.RISK_SCORE_PENALTY_HIGH_AMOUNT
            decision = ApprovalRecommendation.REJECT
        return risk_score, decision


    def _check_defaults(
        self,
        banking_data: BankingData,
        validation_errors: list,
        risk_score: Decimal,
        decision: str
    ) -> tuple[Decimal, str]:
        """Check for active defaults."""
        if banking_data.has_defaults:
            validation_errors.append("Applicant has active defaults")
            risk_score += BusinessRules.RISK_SCORE_PENALTY_LOW_INCOME
            decision = ApprovalRecommendation.REJECT
        return risk_score, decision


    def _apply_positive_adjustments(
        self,
        banking_data: BankingData,
        risk_score: Decimal
    ) -> Decimal:
        """Apply positive adjustments for good credit score and account age."""
        # Good credit score bonus
        if banking_data.credit_score and banking_data.credit_score >= CreditScore.GOOD_SCORE_THRESHOLD:
            risk_score = max(RiskScore.MIN_SCORE, risk_score - BusinessRules.RISK_SCORE_ADJUSTMENT_GOOD_CREDIT)

        # Good account age bonus
        account_age_months = banking_data.additional_data.get("account_age_months")
        if account_age_months and account_age_months >= BusinessRules.MIN_ACCOUNT_AGE_MONTHS_BRAZIL:
            risk_score = max(RiskScore.MIN_SCORE, risk_score - BusinessRules.RISK_SCORE_ADJUSTMENT_ACCOUNT_AGE_BRAZIL)

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

