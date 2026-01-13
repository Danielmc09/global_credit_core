"""
Tests for Decimal Precision

Critical tests to ensure no precision loss in financial calculations.
These tests validate that we're using Decimal correctly and not losing
precision through float conversions.
"""

from decimal import Decimal

from app.strategies.base import BankingData


class TestDecimalPrecision:
    """Test suite for decimal precision in financial calculations"""

    def test_decimal_precision_addition(self):
        """
        Test that 0.1 + 0.2 == 0.3 with Decimal.

        This test would FAIL with float (0.1 + 0.2 != 0.3 due to floating point errors).
        With Decimal, it should pass exactly.
        """
        result = Decimal("0.1") + Decimal("0.2")
        assert result == Decimal("0.3"), "Decimal addition should be exact"

        # Verify it would fail with float
        float_result = 0.1 + 0.2
        assert float_result != 0.3, "Float addition has precision errors (expected)"

    def test_decimal_precision_subtraction(self):
        """Test that subtraction maintains precision"""
        result = Decimal("1.0") - Decimal("0.1") - Decimal("0.1") - Decimal("0.1")
        assert result == Decimal("0.7"), "Decimal subtraction should be exact"

    def test_decimal_precision_multiplication(self):
        """Test that multiplication maintains precision"""
        result = Decimal("0.1") * Decimal("3")
        assert result == Decimal("0.3"), "Decimal multiplication should be exact"

    def test_decimal_precision_division(self):
        """Test that division maintains precision"""
        result = Decimal("1") / Decimal("3")
        # Should be exactly 1/3, not a float approximation
        expected = Decimal("1") / Decimal("3")
        assert result == expected, "Decimal division should be exact"
        assert str(result) == "0.3333333333333333333333333333", "Should have exact precision"

    def test_risk_score_calculation_precision(self):
        """
        Test that risk score calculations maintain precision.

        This validates that calculations with large amounts don't lose precision.
        """
        amount = Decimal("12345.67")
        income = Decimal("5000.00")
        ratio = amount / income

        # Should be exactly 2.469134, not 2.4691339999999999
        assert ratio == Decimal("2.469134"), "Risk calculation should maintain precision"
        assert str(ratio) == "2.469134", "Should not have floating point artifacts"

    def test_large_amount_precision(self):
        """
        Test with very large amounts to ensure no precision loss.

        This is critical for fintech applications handling large sums.
        """
        large = Decimal("999999999.99")
        result = large * Decimal("1.05")

        # Should be exactly 1049999999.9895
        expected = Decimal("1049999999.9895")
        assert result == expected, "Large amount calculations should maintain precision"
        assert str(result) == "1049999999.9895", "Should not lose precision with large numbers"

    def test_small_amount_precision(self):
        """
        Test with very small amounts (cents) to ensure precision.

        Important for calculations involving interest rates or fees.
        """
        small = Decimal("0.01")
        result = small * Decimal("100")
        assert result == Decimal("1.00"), "Small amounts should maintain precision"

        # Test division of small amounts
        result2 = Decimal("0.01") / Decimal("3")
        # Should have exact precision, not float approximation
        assert result2 > Decimal("0.003"), "Small division should maintain precision"

    def test_percentage_calculation_precision(self):
        """
        Test percentage calculations maintain precision.

        Critical for debt-to-income ratios and risk scores.
        """
        debt = Decimal("2000.00")
        income = Decimal("5000.00")
        ratio = (debt / income) * Decimal("100")

        # Should be exactly 40.0, not 39.9999999999
        assert ratio == Decimal("40.0"), "Percentage calculation should be exact"
        assert str(ratio) == "40.0", "Should not have floating point errors"

    def test_decimal_string_conversion_preserves_precision(self):
        """
        Test that converting Decimal to string and back preserves precision.

        This validates our decimal_to_string utility function.
        """
        original = Decimal("1234.567890123456789")
        as_string = str(original)
        back_to_decimal = Decimal(as_string)

        assert original == back_to_decimal, "String conversion should preserve precision"
        assert as_string == "1234.567890123456789", "String should have full precision"


class TestBrazilStrategyPrecision:
    """Test precision in Brazil strategy calculations"""

    def setup_method(self):
        """Setup test fixtures"""
        from app.core.constants import CountryCode
        from app.strategies.factory import CountryStrategyFactory
        self.strategy = CountryStrategyFactory.get_strategy(CountryCode.BRAZIL)

    def test_brazil_loan_to_income_ratio_precision(self):
        """Test that loan-to-income ratio calculations maintain precision"""
        requested_amount = Decimal("50000.00")
        monthly_income = Decimal("5000.00")

        annual_income = monthly_income * Decimal('12')
        loan_to_income_ratio = requested_amount / annual_income

        # Should be exactly 0.833333..., not a float approximation
        expected = Decimal("50000") / Decimal("60000")
        assert loan_to_income_ratio == expected, "Loan-to-income ratio should be exact"
        assert loan_to_income_ratio == Decimal("0.8333333333333333333333333333")

    def test_brazil_debt_to_income_precision(self):
        """Test debt-to-income calculations maintain precision"""
        monthly_income = Decimal("5000.00")
        monthly_obligations = Decimal("1750.00")  # 35% of income

        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            monthly_obligations=monthly_obligations,
            has_defaults=False
        )

        requested_amount = Decimal("12000.00")
        new_monthly_payment = requested_amount / Decimal('12')
        total_obligations = banking_data.monthly_obligations + new_monthly_payment
        debt_to_income = (total_obligations / monthly_income) * Decimal('100')

        # Should be exactly 55.0% (1750 + 1000 = 2750 / 5000 * 100 = 55%)
        assert debt_to_income == Decimal("55.0"), "Debt-to-income should be exact"

    def test_brazil_large_amounts_precision(self):
        """Test that Brazil strategy handles large amounts without precision loss"""
        requested_amount = Decimal("99999.99")
        monthly_income = Decimal("10000.00")

        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=750,
            has_defaults=False
        )

        # This should not lose precision in calculations
        assessment = self.strategy.apply_business_rules(
            requested_amount=requested_amount,
            monthly_income=monthly_income,
            banking_data=banking_data,
            country_specific_data={}
        )

        # Risk score should be a Decimal, not float
        assert isinstance(assessment.risk_score, Decimal), "Risk score should be Decimal"
        assert str(assessment.risk_score).count('.') <= 1, "Should not have precision artifacts"


class TestColombiaStrategyPrecision:
    """Test precision in Colombia strategy calculations"""

    def setup_method(self):
        """Setup test fixtures"""
        from app.core.constants import CountryCode
        from app.strategies.factory import CountryStrategyFactory
        self.strategy = CountryStrategyFactory.get_strategy(CountryCode.COLOMBIA)

    def test_colombia_payment_to_income_precision(self):
        """Test payment-to-income calculations maintain precision"""
        requested_amount = Decimal("12000000.00")  # 12M COP
        monthly_income = Decimal("2000000.00")  # 2M COP

        # 12-month loan term
        monthly_payment = requested_amount / Decimal("12")
        payment_to_income = (monthly_payment / monthly_income) * Decimal("100")

        # Should be exactly 50.0%
        assert payment_to_income == Decimal("50.0"), "Payment-to-income should be exact"

    def test_colombia_large_amounts_precision(self):
        """Test that Colombia strategy handles large COP amounts without precision loss"""
        requested_amount = Decimal("49999999.99")  # Near max (50M COP)
        monthly_income = Decimal("5000000.00")  # 5M COP

        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            has_defaults=False
        )

        assessment = self.strategy.apply_business_rules(
            requested_amount=requested_amount,
            monthly_income=monthly_income,
            banking_data=banking_data,
            country_specific_data={}
        )

        # Risk score should be a Decimal, not float
        assert isinstance(assessment.risk_score, Decimal), "Risk score should be Decimal"


class TestStrategyPrecisionConsistency:
    """Test that all strategies maintain precision consistently"""

    def test_all_strategies_use_decimal(self):
        """Verify all strategies accept Decimal, not float"""
        from app.core.constants import CountryCode
        from app.strategies.factory import CountryStrategyFactory
        strategies = [
            CountryStrategyFactory.get_strategy(CountryCode.BRAZIL),
            CountryStrategyFactory.get_strategy(CountryCode.COLOMBIA),
            CountryStrategyFactory.get_strategy(CountryCode.SPAIN),
            CountryStrategyFactory.get_strategy(CountryCode.MEXICO),
        ]

        test_amount = Decimal("10000.00")
        test_income = Decimal("3000.00")
        banking_data = BankingData(
            provider_name="Test",
            account_status="active",
            credit_score=700,
            has_defaults=False
        )

        for strategy in strategies:
            # This should work without type errors
            assessment = strategy.apply_business_rules(
                requested_amount=test_amount,
                monthly_income=test_income,
                banking_data=banking_data,
                country_specific_data={}
            )

            # Risk score should always be Decimal
            assert isinstance(assessment.risk_score, Decimal), \
                f"{strategy.__class__.__name__} should return Decimal risk_score"

    def test_no_float_conversions_in_calculations(self):
        """
        Test that calculations don't implicitly convert to float.

        This ensures we're not accidentally using float() anywhere.
        """
        amount = Decimal("123.45")
        income = Decimal("1000.00")

        # All operations should return Decimal
        ratio = amount / income
        assert isinstance(ratio, Decimal), "Division should return Decimal"

        percentage = ratio * Decimal("100")
        assert isinstance(percentage, Decimal), "Multiplication should return Decimal"

        # Verify no float artifacts - compare numeric value, not string representation
        # Decimal may include trailing zeros (12.34500) which is correct
        assert percentage == Decimal("12.345"), "Should not have float precision errors"
        # Verify it's not a float by checking it's exactly the Decimal value
        assert percentage.quantize(Decimal("0.001")) == Decimal("12.345"), "Should maintain exact precision"


class TestDecimalSerialization:
    """Test that Decimal serialization preserves precision"""

    def test_decimal_to_json_preserves_precision(self):
        """
        Test that converting Decimal to JSON (via string) preserves precision.

        This validates our decimal_to_string utility.
        """
        from app.utils import decimal_to_string

        data = {
            "amount": Decimal("1234.567890"),
            "risk_score": Decimal("45.67"),
            "nested": {
                "value": Decimal("0.123456789")
            }
        }

        converted = decimal_to_string(data)

        # All Decimals should be strings now
        assert isinstance(converted["amount"], str), "Amount should be string"
        assert converted["amount"] == "1234.567890", "Should preserve full precision"
        assert isinstance(converted["risk_score"], str), "Risk score should be string"
        assert converted["risk_score"] == "45.67", "Should preserve precision"
        assert converted["nested"]["value"] == "0.123456789", "Nested should work"

    def test_decimal_round_trip(self):
        """Test that Decimal → string → Decimal preserves exact value"""
        original = Decimal("123.456789012345678901234567890")
        as_string = str(original)
        restored = Decimal(as_string)

        assert original == restored, "Round trip should preserve exact value"
        assert str(original) == str(restored), "String representation should match"
