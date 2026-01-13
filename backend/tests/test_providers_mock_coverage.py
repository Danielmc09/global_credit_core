"""Tests for mock provider to improve coverage.

Tests for all country-specific mock data generation methods.
"""

import pytest

from app.providers.mock import MockBankingProvider
from app.core.constants import CountryCode


class TestMockProviderCoverage:
    """Test suite for MockBankingProvider coverage"""

    @pytest.mark.asyncio
    async def test_generate_brazil_data(self):
        """Test Brazil mock data generation"""
        provider = MockBankingProvider(CountryCode.BRAZIL)
        data = await provider.fetch_banking_data("12345678901", "João Silva")
        
        assert data.provider_name == "Brazilian Banking Provider (Serasa)"
        assert data.credit_score is not None
        assert data.total_debt is not None
        assert data.monthly_obligations is not None

    @pytest.mark.asyncio
    async def test_generate_spain_data(self):
        """Test Spain mock data generation"""
        provider = MockBankingProvider(CountryCode.SPAIN)
        data = await provider.fetch_banking_data("12345678Z", "Juan García")
        
        assert data.provider_name == "Spanish Banking Provider"
        assert data.credit_score is not None
        assert data.total_debt is not None
        assert data.monthly_obligations is not None

    @pytest.mark.asyncio
    async def test_generate_italy_data(self):
        """Test Italy mock data generation"""
        provider = MockBankingProvider(CountryCode.ITALY)
        data = await provider.fetch_banking_data("RSSMRA80A01H501Z", "Mario Rossi")
        
        assert data.provider_name == "Italian Banking Provider"
        assert data.credit_score is not None
        assert data.total_debt is not None
        assert data.monthly_obligations is not None

    @pytest.mark.asyncio
    async def test_generate_mexico_data(self):
        """Test Mexico mock data generation"""
        provider = MockBankingProvider(CountryCode.MEXICO)
        data = await provider.fetch_banking_data("ABCD123456EFG7", "Juan Pérez")
        
        assert data.provider_name == "Mexican Banking Provider (Buró de Crédito)"
        assert data.credit_score is not None
        assert data.total_debt is not None
        assert data.monthly_obligations is not None

    @pytest.mark.asyncio
    async def test_generate_portugal_data(self):
        """Test Portugal mock data generation"""
        provider = MockBankingProvider(CountryCode.PORTUGAL)
        data = await provider.fetch_banking_data("123456789", "João Silva")
        
        assert data.provider_name == "Portuguese Banking Provider"
        assert data.credit_score is not None
        assert data.total_debt is not None
        assert data.monthly_obligations is not None

    @pytest.mark.asyncio
    async def test_generate_colombia_data(self):
        """Test Colombia mock data generation"""
        provider = MockBankingProvider(CountryCode.COLOMBIA)
        data = await provider.fetch_banking_data("1234567890", "Juan Pérez")
        
        assert data.provider_name == "Colombian Banking Provider (DataCrédito)"
        assert data.credit_score is not None
        assert data.total_debt is not None
        assert data.monthly_obligations is not None

    @pytest.mark.asyncio
    async def test_generate_default_data(self):
        """Test default mock data generation for unsupported countries"""
        # Use a country code that's not in the if/elif chain
        provider = MockBankingProvider("XX")  # Unsupported country
        data = await provider.fetch_banking_data("123456", "Test User")
        
        assert data.provider_name == "Mock Provider (XX)"
        assert data.credit_score is not None
        assert data.total_debt is not None
        assert data.monthly_obligations is not None
