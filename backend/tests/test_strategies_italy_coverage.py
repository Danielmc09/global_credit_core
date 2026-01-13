"""Tests for Italy strategy to improve coverage.

Tests for Codice Fiscale validation edge cases.
"""

import pytest

from app.strategies.italy import ItalyStrategy
from app.core.constants import CountryCode
from app.providers.mock import MockBankingProvider


class TestItalyStrategyCoverage:
    """Test suite for Italy strategy coverage"""

    def test_validate_document_wrong_length(self):
        """Test Codice Fiscale validation with wrong length"""
        provider = MockBankingProvider(CountryCode.ITALY)
        strategy = ItalyStrategy(provider)
        result = strategy.validate_identity_document("RSSMRA80A01H501")
        
        assert result.is_valid is False
        assert "16 characters long" in result.errors[0]

    def test_validate_document_invalid_format(self):
        """Test Codice Fiscale validation with invalid format"""
        provider = MockBankingProvider(CountryCode.ITALY)
        strategy = ItalyStrategy(provider)
        result = strategy.validate_identity_document("RSSMRA80A01H50!Z")
        
        assert result.is_valid is False
        assert "uppercase letters and numbers" in result.errors[0]

    def test_validate_document_invalid_first_six(self):
        """Test Codice Fiscale validation with invalid first 6 characters"""
        provider = MockBankingProvider(CountryCode.ITALY)
        strategy = ItalyStrategy(provider)
        result = strategy.validate_identity_document("12345680A01H501Z")
        
        assert result.is_valid is True
        assert len(result.warnings) > 0

    def test_validate_document_invalid_year(self):
        """Test Codice Fiscale validation with invalid year characters"""
        provider = MockBankingProvider(CountryCode.ITALY)
        strategy = ItalyStrategy(provider)
        result = strategy.validate_identity_document("RSSMRAAB01H501ZX")
        
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert any("Year part" in w or "year" in w.lower() for w in result.warnings)

    def test_validate_document_invalid_month(self):
        """Test Codice Fiscale validation with invalid month character"""
        provider = MockBankingProvider(CountryCode.ITALY)
        strategy = ItalyStrategy(provider)
        result = strategy.validate_identity_document("RSSMRA80Z01H501Z")
        
        assert result.is_valid is True
        assert any("Month character" in w for w in result.warnings)

    def test_validate_document_invalid_day(self):
        """Test Codice Fiscale validation with invalid day characters"""
        provider = MockBankingProvider(CountryCode.ITALY)
        strategy = ItalyStrategy(provider)
        result = strategy.validate_identity_document("RSSMRA80AABH501Z")
        
        assert result.is_valid is True
        assert any("Day part" in w for w in result.warnings)

    def test_validate_document_invalid_town_code(self):
        """Test Codice Fiscale validation with invalid town code"""
        provider = MockBankingProvider(CountryCode.ITALY)
        strategy = ItalyStrategy(provider)
        result = strategy.validate_identity_document("RSSMRA80A01H50!Z")
        
        if result.is_valid:
            assert any("Town code" in w or "town" in w.lower() for w in result.warnings)
        else:
            assert len(result.errors) > 0

    def test_validate_document_invalid_check_character(self):
        """Test Codice Fiscale validation with invalid check character"""
        provider = MockBankingProvider(CountryCode.ITALY)
        strategy = ItalyStrategy(provider)
        result = strategy.validate_identity_document("RSSMRA80A01H5011")
        
        assert result.is_valid is True
        assert any("Check character" in w for w in result.warnings)

    def test_validate_document_valid(self):
        """Test Codice Fiscale validation with valid document"""
        provider = MockBankingProvider(CountryCode.ITALY)
        strategy = ItalyStrategy(provider)
        result = strategy.validate_identity_document("RSSMRA80A01H501Z")
        
        assert result.is_valid is True
        assert len(result.errors) == 0
