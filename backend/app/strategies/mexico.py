"""Mexico (MX) Country Strategy.

Implements business rules and validations specific to Mexico:
- Document: CURP (Clave Única de Registro de Población)
- Income-to-amount relationship rules
- Mexican banking provider integration (Buró de Crédito)
"""

import re
from datetime import date, datetime
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
from ..utils import calculate_age, sanitize_string
from .base import BankingData, BaseCountryStrategy, RiskAssessment, ValidationResult


class MexicoStrategy(BaseCountryStrategy):
    """Credit application strategy for Mexico."""

    MAX_LOAN_AMOUNT = CountryBusinessRules.MEXICO_MAX_LOAN_AMOUNT
    MAX_LOAN_TO_INCOME_MULTIPLE = Decimal('3.0')
    MIN_MONTHLY_INCOME = CountryBusinessRules.MEXICO_MIN_INCOME
    MAX_PAYMENT_TO_INCOME_RATIO = Decimal('30.0')

    def __init__(self, banking_provider: BankingProvider):
        super().__init__(
            country_code=CountryCode.MEXICO,
            country_name=CountryCode.COUNTRY_NAMES[CountryCode.MEXICO],
            banking_provider=banking_provider
        )

    def validate_identity_document(self, document: str) -> ValidationResult:
        """Validate Mexican CURP (Clave Única de Registro de Población).

        Format: 18 characters
        Structure: AAAA######HBBCCCDD
        - AAAA: First surname initial + vowel, first name initial + vowel
        - ######: Date of birth (YYMMDD)
        - H: Gender (H/M)
        - BB: State code (2 letters)
        - CCC: Internal consonants
        - DD: Check digits

        Example: HERM850101MDFRRR01
        """
        errors = []
        warnings = []

        document = sanitize_string(document).upper().replace(' ', '').replace('-', '')

        if len(document) != 18:
            errors.append(
                f"CURP must be exactly 18 characters long (received {len(document)})"
            )
            return ValidationResult(is_valid=False, errors=errors)

        if not re.match(r'^[A-Z]{4}\d{6}[HM][A-Z]{5}\d{2}$', document):
            errors.append(
                "CURP format invalid. Expected format: AAAA######HBBCCCDD "
                "(e.g., HERM850101MDFRRR01)"
            )
            return ValidationResult(is_valid=False, errors=errors)

        date_part = document[4:10]
        try:
            year = int(date_part[0:2])
            current_year_2digit = datetime.now().year % 100

            full_year = 2000 + year if year <= current_year_2digit else 1900 + year

            month = int(date_part[2:4])
            day = int(date_part[4:6])

            birth_date = date(full_year, month, day)

            age = calculate_age(birth_date)
            if age < 18:
                errors.append(f"Applicant must be at least 18 years old (age: {age})")
        except ValueError as e:
            errors.append(f"Invalid date of birth in CURP: {date_part} ({e!s})")

        gender = document[10]
        if gender not in ['H', 'M']:
            errors.append(f"Invalid gender code: {gender} (must be H or M)")

        state_code = document[11:13]
        valid_states = {
            'AS', 'BC', 'BS', 'CC', 'CL', 'CM', 'CS', 'CH', 'DF', 'DG',
            'GT', 'GR', 'HG', 'JC', 'MC', 'MN', 'MS', 'NT', 'NL', 'OC',
            'PL', 'QT', 'QR', 'SP', 'SL', 'SR', 'TC', 'TS', 'TL', 'VZ',
            'YN', 'ZS', 'NE'
        }

        if state_code not in valid_states:
            warnings.append(
                f"State code '{state_code}' not recognized in standard catalog"
            )

        if errors:
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        return ValidationResult(
            is_valid=True,
            warnings=warnings,
            metadata={
                'document_type': 'CURP',
                'birth_date': date_part,
                'gender': 'Male' if gender == 'H' else 'Female',
                'state_code': state_code
            }
        )

    def apply_business_rules(
        self,
        requested_amount: Decimal,
        monthly_income: Decimal,
        banking_data: BankingData,
        country_specific_data: dict[str, Any]
    ) -> RiskAssessment:
        """Apply Mexican business rules for credit assessment.

        Rules:
        1. Maximum loan amount: $200,000 MXN (hard limit - immediate rejection if exceeded)
        2. Minimum monthly income requirement
        3. Loan-to-income multiple (max 3x annual income)
        4. Payment-to-income ratio (max 30%)
        5. Credit score and debt evaluation
        """
        reasons = []
        requires_review = False
        risk_points = RiskScore.MIN_SCORE

        if requested_amount > self.MAX_LOAN_AMOUNT:
            reasons.append(
                f"Requested amount (${requested_amount:,.2f} MXN) exceeds maximum "
                f"allowed (${self.MAX_LOAN_AMOUNT:,.2f} MXN)"
            )
            risk_points += RiskScore.MAX_SCORE
            return RiskAssessment(
                risk_score=RiskScore.MAX_SCORE,
                risk_level=RiskLevel.CRITICAL,
                approval_recommendation=ApprovalRecommendation.REJECT,
                reasons=reasons,
                requires_review=False
            )

        if monthly_income < self.MIN_MONTHLY_INCOME:
            reasons.append(
                f"Monthly income below minimum: ${monthly_income:,.2f} MXN "
                f"(min ${self.MIN_MONTHLY_INCOME:,.2f} MXN)"
            )
            risk_points += BusinessRules.RISK_SCORE_PENALTY_LOW_INCOME_MEXICO

        annual_income = monthly_income * BusinessRules.MONTHS_PER_YEAR_DECIMAL
        max_allowed_loan = annual_income * self.MAX_LOAN_TO_INCOME_MULTIPLE

        if requested_amount > max_allowed_loan:
            reasons.append(
                f"Requested amount ${requested_amount:,.2f} exceeds maximum "
                f"allowed (${max_allowed_loan:,.2f} = 3x annual income)"
            )
            risk_points += BusinessRules.RISK_SCORE_PENALTY_LOAN_TO_INCOME_MEXICO
            requires_review = True

        payment_ratio = self.calculate_payment_to_income_ratio(
            requested_amount,
            monthly_income,
            loan_term_months=36
        )

        if payment_ratio > self.MAX_PAYMENT_TO_INCOME_RATIO:
            reasons.append(
                f"Monthly payment would be {payment_ratio:.1f}% of income "
                f"(max {self.MAX_PAYMENT_TO_INCOME_RATIO}%)"
            )
            risk_points += BusinessRules.RISK_SCORE_PENALTY_HIGH_PAYMENT_RATIO_MEXICO
        elif payment_ratio <= BusinessRules.LOW_PAYMENT_RATIO_THRESHOLD:
            reasons.append("Monthly payment is comfortably within income")
            risk_points -= BusinessRules.RISK_SCORE_ADJUSTMENT_LOW_PAYMENT_RATIO

        if banking_data.monthly_obligations:
            new_monthly_payment = requested_amount / BusinessRules.DEFAULT_LOAN_TERM_MONTHS_DECIMAL
            total_monthly_debt = banking_data.monthly_obligations + new_monthly_payment

            total_dti = self.calculate_debt_to_income_ratio(
                monthly_income,
                total_monthly_debt
            )

            if total_dti > BusinessRules.HIGH_DTI_THRESHOLD_MEXICO:
                reasons.append(
                    f"Total debt-to-income ratio would be {total_dti:.1f}% "
                    f"(concerning if >{BusinessRules.HIGH_DTI_THRESHOLD_MEXICO}%)"
                )
                risk_points += BusinessRules.RISK_SCORE_PENALTY_HIGH_DTI_MEXICO

        if banking_data.credit_score:
            if banking_data.credit_score < 550:
                reasons.append(
                    f"Credit score low: {banking_data.credit_score} (min recommended 550)"
                )
                risk_points += BusinessRules.RISK_SCORE_PENALTY_LOW_CREDIT_MEXICO
            elif banking_data.credit_score >= CreditScore.GOOD_SCORE_THRESHOLD:
                reasons.append("Good credit score")
                risk_points -= BusinessRules.RISK_SCORE_ADJUSTMENT_GOOD_CREDIT

        if banking_data.has_defaults:
            reasons.append("Has active defaults or late payments in Buró de Crédito")
            risk_points += BusinessRules.RISK_SCORE_PENALTY_DEFAULTS_MEXICO
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
        return "CURP"

    def get_required_fields(self) -> list:
        base_fields = super().get_required_fields()
        return [*base_fields, 'state']
