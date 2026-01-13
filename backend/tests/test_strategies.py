"""
Unit Tests for Country Strategies

Tests document validation and business rules for each country.
"""

from decimal import Decimal

import pytest

from app.core.constants import CountryCode
from app.strategies.base import BankingData
from app.strategies.factory import CountryStrategyFactory
from app.strategies.mexico import MexicoStrategy
from app.strategies.spain import SpainStrategy


class TestSpainStrategy:
    """Test suite for Spain (ES) strategy"""

    def setup_method(self):
        """Setup test fixtures"""
        self.strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)

    def test_valid_dni(self):
        """Test valid Spanish DNI validation"""
        # Valid DNIs with correct checksum
        valid_dnis = [
            "12345678Z",
            "87654321X",
            "00000000T",
            "99999999R"
        ]

        for dni in valid_dnis:
            result = self.strategy.validate_identity_document(dni)
            assert result.is_valid, f"DNI {dni} should be valid"
            assert len(result.errors) == 0

    def test_invalid_dni_format(self):
        """Test invalid DNI format"""
        invalid_dnis = [
            "1234567",      # Too short
            "123456789",    # No letter
            "ABCDEFGHI",    # All letters
            "1234567AA",    # Two letters
            "12345-678Z",   # Invalid characters
        ]

        for dni in invalid_dnis:
            result = self.strategy.validate_identity_document(dni)
            assert not result.is_valid, f"DNI {dni} should be invalid"
            assert len(result.errors) > 0

    def test_invalid_dni_checksum(self):
        """Test DNI with invalid checksum letter"""
        result = self.strategy.validate_identity_document("12345678A")
        assert not result.is_valid
        assert "checksum invalid" in result.errors[0].lower()

    def test_high_amount_threshold(self):
        """Test that amounts above threshold require review"""
        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            has_defaults=False
        )

        # Amount above threshold (20,000)
        assessment = self.strategy.apply_business_rules(
            requested_amount=Decimal("25000.00"),
            monthly_income=Decimal("5000.00"),
            banking_data=banking_data,
            country_specific_data={}
        )

        assert assessment.requires_review
        assert any("threshold" in reason.lower() for reason in assessment.reasons)

    def test_high_debt_to_income_ratio(self):
        """Test rejection with high debt-to-income ratio"""
        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            monthly_obligations=Decimal("2500.00"),  # 50% of income
            has_defaults=False
        )

        assessment = self.strategy.apply_business_rules(
            requested_amount=Decimal("15000.00"),
            monthly_income=Decimal("5000.00"),
            banking_data=banking_data,
            country_specific_data={}
        )

        assert assessment.risk_score >= Decimal("30.0")
        assert any("debt-to-income" in reason.lower() for reason in assessment.reasons)

    def test_low_credit_score(self):
        """Test impact of low credit score"""
        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=550,  # Below minimum (600)
            has_defaults=False
        )

        assessment = self.strategy.apply_business_rules(
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("3000.00"),
            banking_data=banking_data,
            country_specific_data={}
        )

        assert assessment.risk_score > Decimal("20.0")
        assert any("credit score" in reason.lower() for reason in assessment.reasons)

    def test_defaults_flag(self):
        """Test that defaults increase risk and require review"""
        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            has_defaults=True
        )

        assessment = self.strategy.apply_business_rules(
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("3000.00"),
            banking_data=banking_data,
            country_specific_data={}
        )

        assert assessment.requires_review
        assert any("defaults" in reason.lower() for reason in assessment.reasons)

    def test_excellent_profile(self):
        """Test low risk score for excellent profile"""
        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=800,
            monthly_obligations=Decimal("500.00"),
            has_defaults=False
        )

        assessment = self.strategy.apply_business_rules(
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("5000.00"),
            banking_data=banking_data,
            country_specific_data={}
        )

        assert assessment.risk_score < Decimal("30.0")
        assert assessment.risk_level in ["LOW", "MEDIUM"]


class TestMexicoStrategy:
    """Test suite for Mexico (MX) strategy"""

    def setup_method(self):
        """Setup test fixtures"""
        self.strategy = CountryStrategyFactory.get_strategy(CountryCode.MEXICO)

    def test_valid_curp(self):
        """Test valid Mexican CURP validation"""
        valid_curps = [
            "HERM850101MDFRRR01",  # Female, DF (CDMX), born 1985
            "GOPE900215HDFNRD09",  # Male, DF, born 1990
            "MASA950630MJCRNN02",  # Female, JC (Jalisco), born 1995
        ]

        for curp in valid_curps:
            result = self.strategy.validate_identity_document(curp)
            assert result.is_valid, f"CURP {curp} should be valid"
            assert len(result.errors) == 0

    def test_invalid_curp_length(self):
        """Test CURP with invalid length"""
        result = self.strategy.validate_identity_document("HERM850101")
        assert not result.is_valid
        assert "18 characters" in result.errors[0]

    def test_invalid_curp_format(self):
        """Test CURP with invalid format"""
        invalid_curps = [
            "HERM85010AMDFRRR01",  # Invalid date part
            "HERM850101XDFRRR01",  # Invalid gender (X)
            "1234567890ABCDEF12",  # Numbers in name part
        ]

        for curp in invalid_curps:
            result = self.strategy.validate_identity_document(curp)
            assert not result.is_valid, f"CURP {curp} should be invalid"

    def test_curp_underage(self):
        """Test CURP for underage person (< 18 years)"""
        from datetime import datetime
        current_year = datetime.now().year
        # Create CURP for someone born last year (definitely < 18)
        year_suffix = str(current_year - 1)[-2:]
        curp = f"HERM{year_suffix}0101MDFRRR01"

        result = self.strategy.validate_identity_document(curp)
        assert not result.is_valid
        assert any("18 years old" in error for error in result.errors)

    def test_minimum_income_rule(self):
        """Test minimum income requirement"""
        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=650,
            has_defaults=False
        )

        assessment = self.strategy.apply_business_rules(
            requested_amount=Decimal("50000.00"),
            monthly_income=Decimal("3000.00"),  # Below minimum (5000)
            banking_data=banking_data,
            country_specific_data={}
        )

        assert assessment.risk_score > Decimal("30.0")
        assert any("minimum" in reason.lower() for reason in assessment.reasons)

    def test_loan_to_income_multiple(self):
        """Test maximum loan-to-income multiple (3x annual)"""
        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            has_defaults=False
        )

        # Monthly income: 5,000 MXN
        # Annual income: 5,000 * 12 = 60,000 MXN
        # Max loan (3x annual): 60,000 * 3 = 180,000 MXN
        # Request: 190,000 MXN (exceeds 3x limit but below MAX_LOAN_AMOUNT of 200,000)
        assessment = self.strategy.apply_business_rules(
            requested_amount=Decimal("190000.00"),
            monthly_income=Decimal("5000.00"),
            banking_data=banking_data,
            country_specific_data={}
        )

        assert assessment.requires_review
        assert any("3x annual income" in reason.lower() for reason in assessment.reasons)

    def test_payment_to_income_ratio(self):
        """Test payment-to-income ratio limit (30%)"""
        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            has_defaults=False
        )

        # Amount that would result in >30% payment ratio
        assessment = self.strategy.apply_business_rules(
            requested_amount=Decimal("100000.00"),
            monthly_income=Decimal("5000.00"),
            banking_data=banking_data,
            country_specific_data={}
        )

        # Payment: 100,000 / 36 = 2,777 per month
        # Ratio: 2,777 / 5,000 = 55.5% (exceeds 30%)
        assert any("payment" in reason.lower() and "income" in reason.lower()
                   for reason in assessment.reasons)

    def test_good_profile_mexico(self):
        """Test low risk for good credit profile in Mexico"""
        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=750,
            monthly_obligations=Decimal("1000.00"),
            has_defaults=False
        )

        assessment = self.strategy.apply_business_rules(
            requested_amount=Decimal("50000.00"),
            monthly_income=Decimal("15000.00"),
            banking_data=banking_data,
            country_specific_data={}
        )

        assert assessment.risk_score < Decimal("40.0")
        assert assessment.approval_recommendation in ["APPROVE", "REVIEW"]


class TestCountryStrategyFactory:
    """Test suite for Strategy Factory"""

    def test_get_spain_strategy(self):
        """Test getting Spain strategy from factory"""
        strategy = CountryStrategyFactory.get_strategy('ES')
        assert isinstance(strategy, SpainStrategy)
        assert strategy.country_code == 'ES'

    def test_get_mexico_strategy(self):
        """Test getting Mexico strategy from factory"""
        strategy = CountryStrategyFactory.get_strategy('MX')
        assert isinstance(strategy, MexicoStrategy)
        assert strategy.country_code == 'MX'

    def test_unsupported_country(self):
        """Test exception for unsupported country"""
        with pytest.raises(ValueError) as exc_info:
            CountryStrategyFactory.get_strategy('US')

        assert "not supported" in str(exc_info.value).lower()

    def test_case_insensitive(self):
        """Test that country code is case insensitive"""
        strategy_upper = CountryStrategyFactory.get_strategy('ES')
        strategy_lower = CountryStrategyFactory.get_strategy('es')

        assert type(strategy_upper) == type(strategy_lower)

    def test_is_country_supported(self):
        """Test country support check"""
        assert CountryStrategyFactory.is_country_supported('ES')
        assert CountryStrategyFactory.is_country_supported('MX')
        assert not CountryStrategyFactory.is_country_supported('US')

    def test_get_supported_countries(self):
        """Test getting list of supported countries"""
        countries = CountryStrategyFactory.get_supported_countries()
        assert 'ES' in countries
        assert 'MX' in countries
        assert len(countries) >= 2


class TestBaseStrategyHelpers:
    """Test suite for base strategy helper methods"""

    def setup_method(self):
        """Setup test fixtures"""
        self.strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)

    def test_debt_to_income_ratio_calculation(self):
        """Test debt-to-income ratio calculation"""
        ratio = self.strategy.calculate_debt_to_income_ratio(
            monthly_income=Decimal("5000.00"),
            monthly_debt=Decimal("2000.00")
        )
        assert ratio == Decimal("40.0")  # 2000/5000 * 100

    def test_debt_to_income_zero_income(self):
        """Test debt-to-income with zero income returns 100%"""
        ratio = self.strategy.calculate_debt_to_income_ratio(
            monthly_income=Decimal("0.00"),
            monthly_debt=Decimal("1000.00")
        )
        assert ratio == Decimal("100.0")

    def test_payment_to_income_ratio_calculation(self):
        """Test payment-to-income ratio calculation"""
        ratio = self.strategy.calculate_payment_to_income_ratio(
            requested_amount=Decimal("36000.00"),
            monthly_income=Decimal("5000.00"),
            loan_term_months=36
        )
        # Payment: 36000/36 = 1000
        # Ratio: 1000/5000 * 100 = 20%
        assert ratio == Decimal("20.0")

    def test_document_type_name(self):
        """Test getting document type name"""
        spain = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        mexico = CountryStrategyFactory.get_strategy(CountryCode.MEXICO)

        assert spain.get_document_type_name() == "DNI"
        assert mexico.get_document_type_name() == "CURP"
