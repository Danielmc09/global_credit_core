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
from ..utils import sanitize_string
from .base import BankingData, BaseCountryStrategy, RiskAssessment, ValidationResult


class AregtinaStrategy(BaseCountryStrategy):
    """Credit application strategy for Spain."""

    HIGH_AMOUNT_THRESHOLD = CountryBusinessRules.SPAIN_HIGH_AMOUNT_THRESHOLD
    MAX_LOAN_AMOUNT = CountryBusinessRules.SPAIN_MAX_LOAN_AMOUNT
    MAX_DEBT_TO_INCOME_RATIO = CountryBusinessRules.SPAIN_MAX_DEBT_TO_INCOME
    MIN_CREDIT_SCORE = int(CountryBusinessRules.SPAIN_MIN_CREDIT_SCORE)

    def __init__(self, banking_provider: BankingProvider):
        super().__init__(
            country_code=CountryCode.SPAIN,
            country_name=CountryCode.COUNTRY_NAMES[CountryCode.SPAIN],
            banking_provider=banking_provider
        )


    def validate_identity_document(self, document: str) -> ValidationResult:
        """Validate Spanish DNI (Documento Nacional de Identidad).

        Format: 8 digits followed by 1 letter (checksum)
        Example: 12345678Z or 12345678-Z

        The letter is calculated using modulo 23 of the number.
        """
        document = sanitize_string(document).upper().replace(' ', '').replace('-', '')

        if not re.match(r'^\d{8}[A-Z]$', document):
            return ValidationResult(
                is_valid=False,
                errors=["DNI format invalid. Must be 8 digits followed by a letter (e.g., 12345678Z)"]
            )

        number_part = int(document[:8])
        letter_part = document[8]

        dni_letters = 'TRWAGMYFPDXBNJZSQVHLCKE'
        expected_letter = dni_letters[number_part % 23]

        if letter_part != expected_letter:
            return ValidationResult(
                is_valid=False,
                errors=[f"DNI checksum invalid. Expected letter '{expected_letter}' but got '{letter_part}'"]
            )

        return ValidationResult(is_valid=True)


    def apply_business_rules(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        banking_data: BankingData,
        country_specific_data: dict[str, Any]
    ) -> RiskAssessment:
        """Apply Spanish business rules for credit assessment.

        Rules:
        1. Maximum loan amount: €50,000 (hard limit - immediate rejection if exceeded)
        2. High amount threshold (>20,000 EUR) requires review
        3. Debt-to-income ratio must be < 40%
        4. Credit score must be >= 600
        5. No active defaults
        """
        reasons = []
        requires_review = False
        risk_points = RiskScore.MIN_SCORE

        # Check 1: Maximum loan amount (hard limit)
        max_amount_result = self._check_max_loan_amount(requested_amount)
        if max_amount_result:
            return max_amount_result

        # Check 2: High amount threshold
        risk_points, requires_review = self._check_high_amount_threshold(
            requested_amount, reasons, risk_points, requires_review
        )

        # Check 3: Debt-to-income ratio
        risk_points = self._check_debt_to_income(
            monthly_income, banking_data, reasons, risk_points
        )

        # Check 4: Credit score
        risk_points = self._check_credit_score(
            banking_data, reasons, risk_points
        )

        # Check 5: Active defaults
        risk_points, requires_review = self._check_defaults(
            banking_data, reasons, risk_points, requires_review
        )

        # Check 6: Payment-to-income ratio
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


    def _check_high_amount_threshold(
        self,
        requested_amount: Decimal,
        reasons: list,
        risk_points: int,
        requires_review: bool
    ) -> tuple[int, bool]:
        """Check if amount exceeds high threshold requiring review."""
        if requested_amount > self.HIGH_AMOUNT_THRESHOLD:
            requires_review = True
            reasons.append(
                f"Amount exceeds high threshold (€{self.HIGH_AMOUNT_THRESHOLD:,.2f}) "
                f"- requires additional review"
            )
            risk_points += BusinessRules.RISK_SCORE_PENALTY_HIGH_AMOUNT_THRESHOLD
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
                risk_points += BusinessRules.RISK_SCORE_PENALTY_HIGH_DTI_SPAIN
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
                risk_points += BusinessRules.RISK_SCORE_PENALTY_LOW_CREDIT_SPAIN
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
            risk_points += BusinessRules.RISK_SCORE_PENALTY_DEFAULTS_SPAIN
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
        return "DNI"


    def get_required_fields(self) -> list:
        return super().get_required_fields()
