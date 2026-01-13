"""Italy (IT) Country Strategy.

Implements business rules and validations specific to Italy:
- Document: Codice Fiscale (Tax Code)
- Financial stability and income rules
- Italian banking provider integration
"""

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


class ItalyStrategy(BaseCountryStrategy):
    """Credit application strategy for Italy."""

    MIN_MONTHLY_INCOME = CountryBusinessRules.ITALY_MIN_INCOME
    MAX_LOAN_AMOUNT = CountryBusinessRules.ITALY_MAX_LOAN_AMOUNT
    MAX_DEBT_TO_INCOME_RATIO = CountryBusinessRules.ITALY_MAX_DEBT_TO_INCOME
    MIN_CREDIT_SCORE = int(CountryBusinessRules.ITALY_MIN_CREDIT_SCORE)

    def __init__(self, banking_provider: BankingProvider):
        super().__init__(
            country_code=CountryCode.ITALY,
            country_name=CountryCode.COUNTRY_NAMES[CountryCode.ITALY],
            banking_provider=banking_provider
        )

    def validate_identity_document(self, document: str) -> ValidationResult:
        """Validate Italian Codice Fiscale (Tax Code).

        Format: 16 characters (alphanumeric)
        Structure: SSSSNNNYYMDDCCCX
        - SSSS: 3 consonants from surname + 1 consonant from name
        - NNN: 3 consonants from name
        - YY: Year of birth (last 2 digits)
        - M: Month of birth (letter: A=Jan, B=Feb, ..., T=Oct, P=Nov, S=Dec)
        - DD: Day of birth (with +40 for females)
        - CCC: Town code (3 alphanumeric)
        - X: Check character

        Example: RSSMRA80A01H501U

        For this implementation, we validate:
        - Length: 16 characters
        - Format: alphanumeric
        - Basic structure validation
        """
        errors = []
        warnings = []

        document = sanitize_string(document).upper().replace(' ', '').replace('-', '')

        if len(document) != 16:
            errors.append(
                f"Codice Fiscale must be exactly 16 characters long (received {len(document)})"
            )
            return ValidationResult(is_valid=False, errors=errors)

        if not re.match(r'^[A-Z0-9]{16}$', document):
            errors.append(
                "Codice Fiscale must contain only uppercase letters and numbers"
            )
            return ValidationResult(is_valid=False, errors=errors)

        if not re.match(r'^[A-Z]{6}', document):
            warnings.append("First 6 characters should typically be letters")

        if not document[6:8].isdigit():
            warnings.append("Year part (characters 7-8) should be digits")

        month_char = document[8]
        valid_months = 'ABCDEHLMPRST'
        if month_char not in valid_months:
            warnings.append(f"Month character '{month_char}' may be invalid")

        if not document[9:11].isdigit():
            warnings.append("Day part (characters 10-11) should be digits")

        if not re.match(r'[A-Z0-9]{3}', document[11:14]):
            warnings.append("Town code (characters 12-14) format may be invalid")

        if not document[15].isalpha():
            warnings.append("Check character (last) should be a letter")

        return ValidationResult(
            is_valid=True,
            warnings=warnings,
            metadata={
                'document_type': 'Codice Fiscale',
                'document_number': document
            }
        )

    def apply_business_rules(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        banking_data: BankingData,
        country_specific_data: dict[str, Any]
    ) -> RiskAssessment:
        """Apply Italian business rules for credit assessment.

        Rules:
        1. Minimum monthly income: €1,200
        2. Maximum loan amount: €50,000
        3. Debt-to-income ratio must be < 35%
        4. Credit score must be >= 600
        5. No active defaults
        6. Financial stability check (income consistency)
        """
        reasons = []
        requires_review = False
        risk_points = RiskScore.MIN_SCORE

        if monthly_income < self.MIN_MONTHLY_INCOME:
            reasons.append(
                f"Monthly income (€{monthly_income:,.2f}) below minimum "
                f"(€{self.MIN_MONTHLY_INCOME:,.2f})"
            )
            risk_points += BusinessRules.RISK_SCORE_PENALTY_LOW_INCOME

        if requested_amount > self.MAX_LOAN_AMOUNT:
            reasons.append(
                f"Requested amount (€{requested_amount:,.2f}) exceeds maximum "
                f"allowed (€{self.MAX_LOAN_AMOUNT:,.2f})"
            )
            risk_points += RiskScore.MAX_SCORE
            return RiskAssessment(
                risk_score=RiskScore.MAX_SCORE,
                risk_level=RiskLevel.CRITICAL,
                approval_recommendation=ApprovalRecommendation.REJECT,
                reasons=reasons,
                requires_review=False
            )

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

        if banking_data.has_defaults:
            reasons.append("Has active defaults in credit bureau")
            risk_points += BusinessRules.RISK_SCORE_PENALTY_DEFAULT
            requires_review = True

        payment_ratio = self.calculate_payment_to_income_ratio(
            requested_amount,
            monthly_income
        )

        if payment_ratio > BusinessRules.HIGH_PAYMENT_RATIO_THRESHOLD_ITALY:
            reasons.append(
                f"New loan payment would be {payment_ratio:.1f}% of income "
                f"(concerning if >{BusinessRules.HIGH_PAYMENT_RATIO_THRESHOLD_ITALY}%)"
            )
            risk_points += BusinessRules.RISK_SCORE_PENALTY_HIGH_DEBT

        annual_income = monthly_income * BusinessRules.MONTHS_PER_YEAR_DECIMAL
        if requested_amount > annual_income * BusinessRules.YEARS_FOR_STABILITY_CHECK_DECIMAL:
            reasons.append(
                f"Requested amount exceeds {BusinessRules.YEARS_FOR_STABILITY_CHECK} years of annual income - "
                "financial stability review required"
            )
            risk_points += BusinessRules.RISK_SCORE_PENALTY_FINANCIAL_STABILITY_ITALY
            requires_review = True

        risk_score = min(RiskScore.MAX_SCORE, max(RiskScore.MIN_SCORE, risk_points))

        if risk_score >= RiskScore.CRITICAL_THRESHOLD:
            risk_level = RiskLevel.CRITICAL
            recommendation = ApprovalRecommendation.REJECT
        elif risk_score >= RiskScore.HIGH_THRESHOLD:
            risk_level = RiskLevel.HIGH
            recommendation = ApprovalRecommendation.REVIEW
            requires_review = True
        elif risk_score >= RiskScore.MEDIUM_THRESHOLD:
            risk_level = RiskLevel.MEDIUM
            recommendation = ApprovalRecommendation.REVIEW if requires_review else ApprovalRecommendation.APPROVE
        else:
            risk_level = RiskLevel.LOW
            recommendation = ApprovalRecommendation.APPROVE

        return RiskAssessment(
            risk_score=risk_score,
            risk_level=risk_level,
            approval_recommendation=recommendation,
            reasons=reasons if reasons else ['Standard credit profile'],
            requires_review=requires_review
        )

    def get_document_type_name(self) -> str:
        return "Codice Fiscale"

    def get_required_fields(self) -> list:
        return super().get_required_fields()
