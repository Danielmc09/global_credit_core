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
from ..utils import sanitize_string
from .base import BankingData, BaseCountryStrategy, RiskAssessment, ValidationResult


class PortugalStrategy(BaseCountryStrategy):
    """Credit application strategy for Portugal."""

    MAX_LOAN_AMOUNT = CountryBusinessRules.PORTUGAL_MAX_LOAN_AMOUNT
    MIN_MONTHLY_INCOME = CountryBusinessRules.PORTUGAL_MIN_INCOME
    MAX_LOAN_TO_INCOME_MULTIPLE = Decimal('4.0')
    MAX_DEBT_TO_INCOME_RATIO = CountryBusinessRules.PORTUGAL_MAX_DEBT_TO_INCOME

    MIN_CREDIT_SCORE = int(CountryBusinessRules.PORTUGAL_MIN_CREDIT_SCORE)

    def __init__(self, banking_provider: BankingProvider):
        super().__init__(
            country_code=CountryCode.PORTUGAL,
            country_name=CountryCode.COUNTRY_NAMES[CountryCode.PORTUGAL],
            banking_provider=banking_provider
        )

    def validate_identity_document(self, document: str) -> ValidationResult:
        """Validate Portuguese NIF (Número de Identificação Fiscal).

        Format: 9 digits
        Example: 123456789

        Algorithm:
        - The last digit is a checksum digit
        - Multiply first 8 digits by weights: 9, 8, 7, 6, 5, 4, 3, 2
        - Sum the products
        - Calculate: 11 - (sum % 11)
        - If result is 0 or 1, checksum is 0
        - Otherwise, checksum is the result
        """
        # Normalize: remove spaces and hyphens
        document = sanitize_string(document).replace(' ', '').replace('-', '')

        # Validate length
        if len(document) != 9:
            return ValidationResult(
                is_valid=False,
                errors=[f"NIF must be exactly 9 digits long (received {len(document)})"]
            )

        # Validate digits only
        if not document.isdigit():
            return ValidationResult(
                is_valid=False,
                errors=["NIF must contain only digits"]
            )

        try:
            # Calculate checksum
            first_8 = document[:8]
            checksum_digit = int(document[8])
            weights = [9, 8, 7, 6, 5, 4, 3, 2]
            
            weighted_sum = sum(int(first_8[i]) * weights[i] for i in range(8))
            remainder = weighted_sum % 11
            calculated_checksum = 11 - remainder
            
            if calculated_checksum >= 10:
                calculated_checksum = 0

            if checksum_digit != calculated_checksum:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"NIF checksum invalid. Expected {calculated_checksum}, got {checksum_digit}"]
                )

            return ValidationResult(is_valid=True)

        except (ValueError, IndexError) as e:
            return ValidationResult(
                is_valid=False,
                errors=[f"Error validating NIF: {e!s}"]
            )

    def apply_business_rules(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        banking_data: BankingData,
        country_specific_data: dict[str, Any]
    ) -> RiskAssessment:
        """Apply Portuguese business rules for credit assessment.

        Rules:
        1. Maximum loan amount: €30,000 (hard limit - immediate rejection if exceeded)
        2. Minimum monthly income: €800
        3. Loan-to-income multiple: max 4x annual income
        4. Debt-to-income ratio must be < 40%
        5. Credit score must be >= 600
        6. No active defaults
        """
        reasons = []
        requires_review = False
        risk_points = RiskScore.MIN_SCORE

        # Check 1: Maximum loan amount (hard limit)
        max_amount_result = self._check_max_loan_amount(requested_amount)
        if max_amount_result:
            return max_amount_result

        # Check 2: Minimum monthly income
        risk_points = self._check_minimum_income(monthly_income, reasons, risk_points)

        # Check 3: Loan-to-income ratio
        risk_points, requires_review = self._check_loan_to_income_ratio(
            requested_amount, monthly_income, reasons, risk_points, requires_review
        )

        # Check 4: Debt-to-income ratio
        risk_points = self._check_debt_to_income(
            monthly_income, banking_data, reasons, risk_points
        )

        # Check 5: Credit score
        risk_points = self._check_credit_score(
            banking_data, reasons, risk_points
        )

        # Check 6: Active defaults
        risk_points, requires_review = self._check_defaults(
            banking_data, reasons, risk_points, requires_review
        )

        # Check 7: Payment-to-income ratio
        risk_points = self._check_payment_ratio(
            requested_amount, monthly_income, reasons, risk_points
        )

        # Determine final risk level and recommendation
        risk_score, risk_level, recommendation = self._determine_risk_level(
            risk_points, requires_review
        )

        return RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            approval_recommendation=recommendation,
            reasons=reasons if reasons else ['Standard credit profile'],
            requires_review=requires_review
        )


    def _check_max_loan_amount(self, requested_amount: Decimal) -> RiskAssessment | None:
        """Check if requested amount exceeds maximum allowed.
        
        Returns RiskAssessment with rejection if exceeded, None otherwise.
        """
        if requested_amount > self.MAX_LOAN_AMOUNT:
            return RiskAssessment(
                risk_score=RiskScore.MAX_SCORE,
                risk_level=RiskLevel.CRITICAL,
                approval_recommendation=ApprovalRecommendation.REJECT,
                reasons=[
                    f"Requested amount (€{requested_amount:,.2f}) exceeds maximum "
                    f"allowed (€{self.MAX_LOAN_AMOUNT:,.2f})"
                ],
                requires_review=False
            )
        return None


    def _check_minimum_income(
        self,
        monthly_income: Decimal,
        reasons: list,
        risk_points: int
    ) -> int:
        """Check if monthly income meets minimum requirement."""
        if monthly_income < self.MIN_MONTHLY_INCOME:
            reasons.append(
                f"Monthly income (€{monthly_income:,.2f}) below minimum "
                f"(€{self.MIN_MONTHLY_INCOME:,.2f})"
            )
            risk_points += BusinessRules.RISK_SCORE_PENALTY_LOW_INCOME
        return risk_points


    def _check_loan_to_income_ratio(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        reasons: list,
        risk_points: int,
        requires_review: bool
    ) -> tuple[int, bool]:
        """Check loan-to-income ratio (max 4x annual income)."""
        annual_income = monthly_income * BusinessRules.MONTHS_PER_YEAR_DECIMAL
        
        if annual_income <= 0 or abs(annual_income) < Decimal('0.01'):
            loan_to_income_ratio = RiskScore.MAX_SCORE
        else:
            loan_to_income_ratio = requested_amount / annual_income

        if loan_to_income_ratio > self.MAX_LOAN_TO_INCOME_MULTIPLE:
            reasons.append(
                f"Loan amount ({loan_to_income_ratio:.2f}x) exceeds maximum "
                f"({self.MAX_LOAN_TO_INCOME_MULTIPLE}x annual income)"
            )
            risk_points += BusinessRules.RISK_SCORE_PENALTY_HIGH_AMOUNT
            requires_review = True
        
        return risk_points, requires_review


    def _check_debt_to_income(
        self,
        monthly_income: Decimal,
        banking_data: BankingData,
        reasons: list,
        risk_points: int
    ) -> int:
        """Check debt-to-income ratio."""
        if banking_data.monthly_obligations:
            current_dti = self.calculate_debt_to_income_ratio(
                monthly_income,
                banking_data.monthly_obligations
            )

            if current_dti > self.MAX_DEBT_TO_INCOME_RATIO:
                reasons.append(
                    f"Debt-to-income ratio too high: {current_dti:.1f}% "
                    f"(max {self.MAX_DEBT_TO_INCOME_RATIO}%)"
                )
                risk_points += BusinessRules.RISK_SCORE_PENALTY_LOW_CREDIT
        return risk_points


    def _check_credit_score(
        self,
        banking_data: BankingData,
        reasons: list,
        risk_points: int
    ) -> int:
        """Check credit score and adjust risk points."""
        if banking_data.credit_score:
            if banking_data.credit_score < self.MIN_CREDIT_SCORE:
                reasons.append(
                    f"Credit score below minimum: {banking_data.credit_score} "
                    f"(min {self.MIN_CREDIT_SCORE})"
                )
                risk_points += BusinessRules.RISK_SCORE_PENALTY_HIGH_AMOUNT
            elif banking_data.credit_score >= CreditScore.HIGH_SCORE_THRESHOLD:
                reasons.append("Excellent credit score")
                risk_points -= BusinessRules.RISK_SCORE_ADJUSTMENT_GOOD_ACCOUNT_AGE
        return risk_points


    def _check_defaults(
        self,
        banking_data: BankingData,
        reasons: list,
        risk_points: int,
        requires_review: bool
    ) -> tuple[int, bool]:
        """Check for active defaults."""
        if banking_data.has_defaults:
            reasons.append("Has active defaults in credit bureau")
            risk_points += BusinessRules.RISK_SCORE_PENALTY_DEFAULT
            requires_review = True
        return risk_points, requires_review


    def _check_payment_ratio(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        reasons: list,
        risk_points: int
    ) -> int:
        """Check payment-to-income ratio."""
        payment_ratio = self.calculate_payment_to_income_ratio(
            requested_amount,
            monthly_income
        )

        if payment_ratio > RiskScore.MAX_PAYMENT_RATIO_PERCENT:
            reasons.append(
                f"New loan payment would be {payment_ratio:.1f}% of income "
                f"(concerning if >{RiskScore.MAX_PAYMENT_RATIO_PERCENT}%)"
            )
            risk_points += BusinessRules.RISK_SCORE_PENALTY_HIGH_DEBT
        return risk_points


    def _determine_risk_level(
        self,
        risk_points: int,
        requires_review: bool
    ) -> tuple[int, str, str]:
        """Determine final risk level and approval recommendation.
        
        Returns:
            Tuple of (risk_score, risk_level, recommendation)
        """
        risk_score = min(RiskScore.MAX_SCORE, max(RiskScore.MIN_SCORE, risk_points))

        if risk_score >= RiskScore.CRITICAL_THRESHOLD:
            risk_level = RiskLevel.CRITICAL
            recommendation = ApprovalRecommendation.REJECT
        elif risk_score >= RiskScore.HIGH_THRESHOLD:
            risk_level = RiskLevel.HIGH
            recommendation = ApprovalRecommendation.REVIEW
        elif risk_score >= RiskScore.MEDIUM_THRESHOLD:
            risk_level = RiskLevel.MEDIUM
            recommendation = ApprovalRecommendation.REVIEW if requires_review else ApprovalRecommendation.APPROVE
        else:
            risk_level = RiskLevel.LOW
            recommendation = ApprovalRecommendation.APPROVE

        return risk_score, risk_level, recommendation


    def get_document_type_name(self) -> str:
        return "NIF"


    def get_required_fields(self) -> list:
        return super().get_required_fields()
