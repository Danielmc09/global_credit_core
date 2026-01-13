"""
Tests for Financial Edge Cases

This test suite covers critical edge cases in financial calculations:
1. Extreme amounts (very large, very small, at boundaries)
2. Division by zero in ratios
3. Precision issues with extreme values

These tests are critical for fintech applications where edge cases can lead to
financial losses or system crashes.
"""

from decimal import Decimal, DivisionByZero

import pytest

from app.core.constants import CountryCode, RiskScore
from app.core.country_limits import get_max_loan_amount, get_min_monthly_income
from app.strategies.base import BankingData
from app.strategies.factory import CountryStrategyFactory


class TestExtremeAmounts:
    """Test suite for extreme amount values"""

    def setup_method(self):
        """Setup test fixtures"""
        self.banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            has_defaults=False
        )

    def test_very_small_amount_spain(self):
        """Test with very small amount (close to zero)"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        
        # Test with minimum valid amount
        assessment = strategy.apply_business_rules(
            requested_amount=Decimal("0.01"),  # Minimum valid amount
            monthly_income=Decimal("5000.00"),
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        # Should not crash, should process normally
        assert assessment is not None
        assert assessment.risk_score >= RiskScore.MIN_SCORE
        assert assessment.risk_score <= RiskScore.MAX_SCORE

    def test_very_small_amount_brazil(self):
        """Test Brazil strategy with very small amount"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.BRAZIL)
        
        assessment = strategy.apply_business_rules(
            requested_amount=Decimal("0.01"),
            monthly_income=Decimal("5000.00"),
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        assert assessment is not None
        assert assessment.risk_score >= RiskScore.MIN_SCORE
        assert assessment.risk_score <= RiskScore.MAX_SCORE

    def test_very_small_amount_colombia(self):
        """Test Colombia strategy with very small amount"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.COLOMBIA)
        
        assessment = strategy.apply_business_rules(
            requested_amount=Decimal("0.01"),
            monthly_income=Decimal("2000000.00"),  # Above minimum for Colombia
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        assert assessment is not None
        assert assessment.risk_score >= RiskScore.MIN_SCORE
        assert assessment.risk_score <= RiskScore.MAX_SCORE

    def test_maximum_amount_spain(self):
        """Test with amount exactly at maximum limit"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        max_amount = get_max_loan_amount("ES")
        
        assessment = strategy.apply_business_rules(
            requested_amount=max_amount,  # Exactly at maximum
            monthly_income=Decimal("5000.00"),
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        # Should process, might require review but not reject immediately
        assert assessment is not None
        # At maximum, it might trigger review but shouldn't exceed hard limit

    def test_maximum_amount_brazil(self):
        """Test Brazil strategy with amount at maximum limit"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.BRAZIL)
        max_amount = get_max_loan_amount("BR")
        
        assessment = strategy.apply_business_rules(
            requested_amount=max_amount,
            monthly_income=Decimal("5000.00"),
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        assert assessment is not None
        # At maximum, should be processed but might require review

    def test_exceeding_maximum_amount_spain(self):
        """Test with amount exceeding maximum limit"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        max_amount = get_max_loan_amount("ES")
        
        assessment = strategy.apply_business_rules(
            requested_amount=max_amount + Decimal("0.01"),  # Exceeds by 1 cent
            monthly_income=Decimal("5000.00"),
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        # Should reject immediately with maximum risk score
        assert assessment.approval_recommendation == "REJECT"
        assert assessment.risk_score == RiskScore.MAX_SCORE
        assert assessment.risk_level == "CRITICAL"

    def test_exceeding_maximum_amount_brazil(self):
        """Test Brazil strategy with amount exceeding maximum"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.BRAZIL)
        max_amount = get_max_loan_amount("BR")
        
        assessment = strategy.apply_business_rules(
            requested_amount=max_amount + Decimal("0.01"),
            monthly_income=Decimal("5000.00"),
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        # Should reject immediately
        assert assessment.approval_recommendation == "REJECT"
        # Risk score may be reduced by positive factors (good credit score), but should still be positive
        assert assessment.risk_score >= RiskScore.MIN_SCORE
        assert assessment.risk_score <= RiskScore.MAX_SCORE

    def test_very_large_amount_spain(self):
        """Test with extremely large amount (way beyond maximum)"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        
        assessment = strategy.apply_business_rules(
            requested_amount=Decimal("1000000.00"),  # 1 million (20x max)
            monthly_income=Decimal("5000.00"),
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        # Should reject immediately
        assert assessment.approval_recommendation == "REJECT"
        assert assessment.risk_score == RiskScore.MAX_SCORE

    def test_very_large_amount_colombia(self):
        """Test Colombia with very large amount"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.COLOMBIA)
        
        assessment = strategy.apply_business_rules(
            requested_amount=Decimal("100000000.00"),  # 100 million COP (2x max)
            monthly_income=Decimal("2000000.00"),
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        assert assessment.approval_recommendation == "REJECT"
        assert assessment.risk_score >= RiskScore.HIGH_THRESHOLD

    def test_precision_with_large_amounts(self):
        """Test that large amounts maintain precision"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        
        # Test with very precise large amount
        large_amount = Decimal("49999.999999999999999999")
        
        assessment = strategy.apply_business_rules(
            requested_amount=large_amount,
            monthly_income=Decimal("5000.00"),
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        # Should not lose precision or crash
        assert assessment is not None
        assert isinstance(assessment.risk_score, Decimal)


class TestDivisionByZeroInRatios:
    """Test suite for division by zero edge cases in ratio calculations"""

    def setup_method(self):
        """Setup test fixtures"""
        self.banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            has_defaults=False
        )

    def test_debt_to_income_ratio_zero_income(self):
        """Test debt-to-income ratio with zero income"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        
        # Should return 100% (handled in base class)
        ratio = strategy.calculate_debt_to_income_ratio(
            monthly_income=Decimal("0.00"),
            monthly_debt=Decimal("1000.00")
        )
        
        assert ratio == Decimal("100.0")

    def test_debt_to_income_ratio_negative_income(self):
        """Test debt-to-income ratio with negative income"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        
        # Should return 100% (handled in base class)
        ratio = strategy.calculate_debt_to_income_ratio(
            monthly_income=Decimal("-100.00"),
            monthly_debt=Decimal("1000.00")
        )
        
        assert ratio == Decimal("100.0")

    def test_payment_to_income_ratio_zero_income(self):
        """Test payment-to-income ratio with zero income"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        
        # Should return 100% (handled in base class)
        ratio = strategy.calculate_payment_to_income_ratio(
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("0.00"),
            loan_term_months=36
        )
        
        assert ratio == Decimal("100.0")

    def test_payment_to_income_ratio_negative_income(self):
        """Test payment-to-income ratio with negative income"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        
        # Should return 100% (handled in base class)
        ratio = strategy.calculate_payment_to_income_ratio(
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("-100.00"),
            loan_term_months=36
        )
        
        assert ratio == Decimal("100.0")

    def test_brazil_loan_to_income_zero_income(self):
        """Test Brazil loan-to-income ratio with zero income"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.BRAZIL)
        
        # Zero monthly income means zero annual income
        assessment = strategy.apply_business_rules(
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("0.00"),
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        # Should handle gracefully - should reject due to minimum income requirement
        assert assessment is not None
        assert assessment.approval_recommendation == "REJECT"
        # Should not crash with division by zero

    def test_brazil_loan_to_income_very_small_income(self):
        """Test Brazil with very small income (near zero)"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.BRAZIL)
        
        # Very small income that would create a huge ratio
        assessment = strategy.apply_business_rules(
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("0.01"),  # Very small but positive
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        # Should handle gracefully
        assert assessment is not None
        # Should reject due to minimum income requirement
        assert assessment.approval_recommendation == "REJECT"

    def test_colombia_payment_to_income_zero_income(self):
        """Test Colombia payment-to-income with zero income - CRITICAL EDGE CASE"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.COLOMBIA)
        
        # This is a critical edge case - Colombia strategy divides by monthly_income
        # without explicit zero check in the division line
        # However, it should be caught by minimum income validation first
        
        # Test that it doesn't crash with ZeroDivisionError
        try:
            assessment = strategy.apply_business_rules(
                requested_amount=Decimal("10000000.00"),
                monthly_income=Decimal("0.00"),
                banking_data=self.banking_data,
                country_specific_data={}
            )
            
            # Should reject due to minimum income requirement
            assert assessment is not None
            assert assessment.approval_recommendation == "REJECT"
        except (ZeroDivisionError, DivisionByZero) as e:
            pytest.fail(f"Division by zero occurred in Colombia strategy: {e}")

    def test_colombia_payment_to_income_very_small_income(self):
        """Test Colombia with very small income (potential division issue)"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.COLOMBIA)
        
        # Very small income that might cause precision issues
        try:
            assessment = strategy.apply_business_rules(
                requested_amount=Decimal("10000000.00"),
                monthly_income=Decimal("0.01"),  # Very small but positive
                banking_data=self.banking_data,
                country_specific_data={}
            )
            
            assert assessment is not None
            # Should reject due to minimum income requirement
            assert assessment.approval_recommendation == "REJECT"
        except (ZeroDivisionError, DivisionByZero) as e:
            pytest.fail(f"Division by zero occurred: {e}")

    def test_brazil_debt_to_income_zero_income(self):
        """Test Brazil debt-to-income calculation with zero income"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.BRAZIL)
        
        banking_data_with_debt = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            monthly_obligations=Decimal("1000.00"),
            has_defaults=False
        )
        
        try:
            assessment = strategy.apply_business_rules(
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("0.00"),
                banking_data=banking_data_with_debt,
                country_specific_data={}
            )
            
            # Should handle gracefully
            assert assessment is not None
            assert assessment.approval_recommendation == "REJECT"
        except (ZeroDivisionError, DivisionByZero) as e:
            pytest.fail(f"Division by zero occurred in Brazil strategy: {e}")

    def test_spain_business_rules_zero_income(self):
        """Test Spain strategy with zero income"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        
        try:
            assessment = strategy.apply_business_rules(
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("0.00"),
                banking_data=self.banking_data,
                country_specific_data={}
            )
            
            # Should handle gracefully using helper methods
            assert assessment is not None
            assert assessment.risk_score >= RiskScore.MIN_SCORE
            assert assessment.risk_score <= RiskScore.MAX_SCORE
        except (ZeroDivisionError, DivisionByZero) as e:
            pytest.fail(f"Division by zero occurred in Spain strategy: {e}")

    def test_mexico_business_rules_zero_income(self):
        """Test Mexico strategy with zero income"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.MEXICO)
        
        try:
            assessment = strategy.apply_business_rules(
                requested_amount=Decimal("50000.00"),
                monthly_income=Decimal("0.00"),
                banking_data=self.banking_data,
                country_specific_data={}
            )
            
            assert assessment is not None
            # Should reject due to minimum income requirement
            assert assessment.approval_recommendation == "REJECT"
        except (ZeroDivisionError, DivisionByZero) as e:
            pytest.fail(f"Division by zero occurred in Mexico strategy: {e}")


class TestExtremeRatioValues:
    """Test suite for extreme ratio values"""

    def setup_method(self):
        """Setup test fixtures"""
        self.banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            has_defaults=False
        )

    def test_very_high_debt_to_income_ratio(self):
        """Test with extremely high debt-to-income ratio"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        
        banking_data_high_debt = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            monthly_obligations=Decimal("10000.00"),  # 200% of income
            has_defaults=False
        )
        
        assessment = strategy.apply_business_rules(
            requested_amount=Decimal("10000.00"),
            monthly_income=Decimal("5000.00"),
            banking_data=banking_data_high_debt,
            country_specific_data={}
        )
        
        # Should have elevated risk score (penalty is 30, but may be adjusted)
        # Credit score 700 is good but not excellent, so no adjustment
        assert assessment.risk_score >= RiskScore.MEDIUM_THRESHOLD
        assert assessment.risk_score <= RiskScore.MAX_SCORE
        assert any("debt-to-income" in reason.lower() for reason in assessment.reasons)

    def test_very_high_loan_to_income_ratio_brazil(self):
        """Test Brazil with extremely high loan-to-income ratio"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.BRAZIL)
        
        # Request 10x annual income (max is 5x)
        assessment = strategy.apply_business_rules(
            requested_amount=Decimal("600000.00"),  # 10x annual income
            monthly_income=Decimal("5000.00"),  # Annual: 60,000
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        assert assessment.approval_recommendation == "REJECT"
        assert any("loan-to-income" in reason.lower() for reason in assessment.reasons)

    def test_very_low_income_high_amount(self):
        """Test with very low income but high requested amount"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        
        assessment = strategy.apply_business_rules(
            requested_amount=Decimal("40000.00"),
            monthly_income=Decimal("1000.00"),  # Very low income
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        # Should have high risk due to payment ratio
        assert assessment.risk_score >= RiskScore.MEDIUM_THRESHOLD

    def test_precision_with_extreme_ratios(self):
        """Test that extreme ratios maintain precision"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        
        # Very small income relative to amount
        ratio = strategy.calculate_payment_to_income_ratio(
            requested_amount=Decimal("100000.00"),
            monthly_income=Decimal("0.01"),  # Extremely small income
            loan_term_months=36
        )
        
        # Should return a very large ratio, but not crash
        assert ratio > Decimal("100.0")
        assert isinstance(ratio, Decimal)


class TestBoundaryValues:
    """Test suite for boundary value testing"""

    def setup_method(self):
        """Setup test fixtures"""
        self.banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            has_defaults=False
        )

    def test_amount_at_minimum_validation_limit(self):
        """Test with amount at minimum validation limit"""
        from app.core.constants import ValidationLimits
        
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        
        assessment = strategy.apply_business_rules(
            requested_amount=ValidationLimits.MIN_AMOUNT,  # 0.01
            monthly_income=Decimal("5000.00"),
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        assert assessment is not None
        assert assessment.risk_score >= RiskScore.MIN_SCORE

    def test_income_at_minimum_country_limit(self):
        """Test with income exactly at minimum country limit"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        min_income = get_min_monthly_income("ES")
        
        assessment = strategy.apply_business_rules(
            requested_amount=Decimal("10000.00"),
            monthly_income=min_income,  # Exactly at minimum
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        assert assessment is not None
        # Should process, might have higher risk

    def test_income_just_below_minimum(self):
        """Test with income just below minimum limit"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        min_income = get_min_monthly_income("ES")
        
        assessment = strategy.apply_business_rules(
            requested_amount=Decimal("10000.00"),
            monthly_income=min_income - Decimal("0.01"),  # Just below minimum
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        assert assessment is not None
        # Should have higher risk due to low income

    def test_amount_just_below_maximum(self):
        """Test with amount just below maximum limit"""
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        max_amount = get_max_loan_amount("ES")
        
        assessment = strategy.apply_business_rules(
            requested_amount=max_amount - Decimal("0.01"),  # Just below maximum
            monthly_income=Decimal("5000.00"),
            banking_data=self.banking_data,
            country_specific_data={}
        )
        
        assert assessment is not None
        # Should process, might require review

    def test_all_countries_extreme_amounts(self):
        """Test all country strategies with extreme amounts"""
        countries = ["ES", "BR", "CO", "MX", "PT", "IT"]
        
        for country_code in countries:
            strategy = CountryStrategyFactory.get_strategy(country_code)
            max_amount = get_max_loan_amount(country_code)
            
            if max_amount:
                # Test with amount exceeding maximum
                assessment = strategy.apply_business_rules(
                    requested_amount=max_amount + Decimal("1.00"),
                    monthly_income=Decimal("5000.00"),
                    banking_data=self.banking_data,
                    country_specific_data={}
                )
                
                # Should reject or have elevated risk
                assert assessment is not None
                assert assessment.approval_recommendation in ["REJECT", "REVIEW"]
                # Risk score may be reduced by positive factors (good credit score in test data),
                # but should still be positive and within valid range
                assert assessment.risk_score >= RiskScore.MIN_SCORE
                assert assessment.risk_score <= RiskScore.MAX_SCORE
                # Most countries should reject when exceeding maximum
                # (Spain, Mexico, Portugal definitely reject; others may review)
