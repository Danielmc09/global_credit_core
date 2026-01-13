"""Mock Banking Provider Implementation.

This module provides a mock implementation of the BankingProvider interface.
It simulates banking data retrieval for development and testing purposes.

In production, this would be replaced with real provider implementations
that call actual banking APIs.
"""

import asyncio
import random
from decimal import Decimal

from ..core.constants import (
    BusinessRules,
    CountryCode,
    CreditScore,
    ProviderNames,
    SystemValues,
)
from ..strategies.base import BankingData
from .base import BankingProvider


class MockBankingProvider(BankingProvider):
    """Mock implementation of BankingProvider for development/testing.

    This provider generates deterministic mock data based on the document number.
    Each country has its own mock data generation logic.
    """

    def __init__(self, country_code: str):
        """Initialize the mock provider for a specific country.

        Args:
            country_code: ISO 3166-1 alpha-2 country code (e.g., "BR", "ES")
        """
        provider_name = self._get_provider_name_for_country(country_code)
        super().__init__(provider_name=provider_name, country_code=country_code)

    def _get_provider_name_for_country(self, country_code: str) -> str:
        """Get the provider name for a given country code."""
        mapping = {
            CountryCode.BRAZIL: ProviderNames.BRAZIL,
            CountryCode.SPAIN: ProviderNames.SPAIN,
            CountryCode.ITALY: ProviderNames.ITALY,
            CountryCode.MEXICO: ProviderNames.MEXICO,
            CountryCode.PORTUGAL: ProviderNames.PORTUGAL,
            CountryCode.COLOMBIA: ProviderNames.COLOMBIA,
        }
        return mapping.get(country_code, f"Mock Provider ({country_code})")

    async def fetch_banking_data(
        self,
        document: str,
        full_name: str
    ) -> BankingData:
        """Fetch mock banking data for the given document and name.

        The mock data is generated deterministically based on the document number
        to ensure consistent results for testing.

        Args:
            document: Identity document number
            full_name: Full name of the applicant

        Returns:
            BankingData with mock information
        """
        # Simulate API call delay
        await asyncio.sleep(0.1)

        # Route to country-specific mock data generation
        if self.country_code == CountryCode.BRAZIL:
            return self._generate_brazil_data(document, full_name)
        elif self.country_code == CountryCode.SPAIN:
            return self._generate_spain_data(document, full_name)
        elif self.country_code == CountryCode.ITALY:
            return self._generate_italy_data(document, full_name)
        elif self.country_code == CountryCode.MEXICO:
            return self._generate_mexico_data(document, full_name)
        elif self.country_code == CountryCode.PORTUGAL:
            return self._generate_portugal_data(document, full_name)
        elif self.country_code == CountryCode.COLOMBIA:
            return self._generate_colombia_data(document, full_name)
        else:
            return self._generate_default_data(document, full_name)

    def _generate_brazil_data(self, document: str, full_name: str) -> BankingData:
        """Generate mock banking data for Brazil."""
        credit_scores = [520, 580, 650, 720, 800]
        return BankingData(
            provider_name=ProviderNames.BRAZIL,
            account_status=SystemValues.DEFAULT_ACCOUNT_STATUS,
            credit_score=random.choice(credit_scores),
            total_debt=Decimal(str(random.uniform(1000, 15000))),
            monthly_obligations=Decimal(str(random.uniform(200, 2000))),
            has_defaults=random.choice([True, False]),
            additional_data={
                "serasa_score": random.randint(0, 1000),
                "active_credit_cards": random.randint(1, 5),
                "banco_central_registration": "Active",
                "account_age_months": random.randint(6, 120),
            },
        )

    def _generate_spain_data(self, document: str, full_name: str) -> BankingData:
        """Generate mock banking data for Spain."""
        document_clean = document.replace(' ', '').replace('-', '')
        hash_value = sum(ord(c) for c in document_clean)

        mock_credit_score = CreditScore.DEFAULT_MIN_INTERNATIONAL + (
            hash_value % (CreditScore.MAX_INTERNATIONAL - CreditScore.DEFAULT_MIN_INTERNATIONAL)
        )

        mock_total_debt = Decimal(f"{hash_value % 30000}.00")
        mock_monthly_obligations = mock_total_debt / BusinessRules.DEFAULT_LOAN_TERM_MONTHS_DECIMAL

        return BankingData(
            provider_name=ProviderNames.SPAIN,
            account_status=SystemValues.DEFAULT_ACCOUNT_STATUS,
            credit_score=mock_credit_score,
            total_debt=mock_total_debt,
            monthly_obligations=mock_monthly_obligations,
            has_defaults=(hash_value % 10 == 0),
            additional_data={
                'consulted_at': 'mock_timestamp',
                'data_source': 'spanish_banking_provider_mock'
            }
        )

    def _generate_italy_data(self, document: str, full_name: str) -> BankingData:
        """Generate mock banking data for Italy."""
        document_clean = document.replace(' ', '').replace('-', '')
        hash_value = sum(ord(c) for c in document_clean)

        mock_credit_score = CreditScore.DEFAULT_MIN_INTERNATIONAL + (
            hash_value % (CreditScore.MAX_INTERNATIONAL - CreditScore.DEFAULT_MIN_INTERNATIONAL)
        )

        mock_total_debt = Decimal(f"{hash_value % 40000}.00")
        mock_monthly_obligations = mock_total_debt / BusinessRules.DEFAULT_LOAN_TERM_MONTHS_DECIMAL

        return BankingData(
            provider_name=ProviderNames.ITALY,
            account_status=SystemValues.DEFAULT_ACCOUNT_STATUS,
            credit_score=mock_credit_score,
            total_debt=mock_total_debt,
            monthly_obligations=mock_monthly_obligations,
            has_defaults=(hash_value % 10 == 0),
            additional_data={
                'consulted_at': 'mock_timestamp',
                'data_source': 'italian_banking_provider_mock',
                'crif_score': mock_credit_score
            }
        )

    def _generate_mexico_data(self, document: str, full_name: str) -> BankingData:
        """Generate mock banking data for Mexico."""
        document_clean = document.replace(' ', '').replace('-', '')
        hash_value = sum(ord(c) for c in document_clean)

        mock_credit_score = CreditScore.MIN_INTERNATIONAL + (
            hash_value % (CreditScore.MAX_INTERNATIONAL - CreditScore.MIN_INTERNATIONAL)
        )

        mock_total_debt = Decimal(f"{hash_value % 100000}.00")
        mock_monthly_obligations = mock_total_debt / Decimal('24')

        return BankingData(
            provider_name=ProviderNames.MEXICO,
            account_status=SystemValues.DEFAULT_ACCOUNT_STATUS,
            credit_score=mock_credit_score,
            total_debt=mock_total_debt,
            monthly_obligations=mock_monthly_obligations,
            has_defaults=(hash_value % 8 == 0),
            additional_data={
                'consulted_at': 'mock_timestamp',
                'data_source': 'mexican_banking_provider_mock',
                'currency': 'MXN'
            }
        )

    def _generate_portugal_data(self, document: str, full_name: str) -> BankingData:
        """Generate mock banking data for Portugal."""
        document_clean = document.replace(' ', '').replace('-', '')
        hash_value = sum(ord(c) for c in document_clean)

        mock_credit_score = CreditScore.DEFAULT_MIN_INTERNATIONAL + (
            hash_value % (CreditScore.MAX_INTERNATIONAL - CreditScore.DEFAULT_MIN_INTERNATIONAL)
        )

        mock_total_debt = Decimal(f"{hash_value % 50000}.00")
        mock_monthly_obligations = mock_total_debt / BusinessRules.DEFAULT_LOAN_TERM_MONTHS_DECIMAL

        return BankingData(
            provider_name=ProviderNames.PORTUGAL,
            account_status=SystemValues.DEFAULT_ACCOUNT_STATUS,
            credit_score=mock_credit_score,
            total_debt=mock_total_debt,
            monthly_obligations=mock_monthly_obligations,
            has_defaults=(hash_value % 10 == 0),
            additional_data={
                'consulted_at': 'mock_timestamp',
                'data_source': 'portuguese_banking_provider_mock'
            }
        )

    def _generate_colombia_data(self, document: str, full_name: str) -> BankingData:
        """Generate mock banking data for Colombia."""
        credit_scores = [580, 620, 680, 740, 820]
        return BankingData(
            provider_name=ProviderNames.COLOMBIA,
            account_status=SystemValues.DEFAULT_ACCOUNT_STATUS,
            credit_score=random.choice(credit_scores),
            total_debt=Decimal(str(random.uniform(2000000, 20000000))),
            monthly_obligations=Decimal(str(random.uniform(300000, 3000000))),
            has_defaults=random.choice([True, False]),
            additional_data={
                "datacredito_score": random.randint(150, 950),
                "active_loans": random.randint(0, 3),
                "banking_relationship_years": random.randint(1, 15),
                "account_age_months": random.randint(6, 120),
            },
        )

    def _generate_default_data(self, document: str, full_name: str) -> BankingData:
        """Generate default mock data for unsupported countries."""
        document_clean = document.replace(' ', '').replace('-', '')
        hash_value = sum(ord(c) for c in document_clean)

        mock_credit_score = CreditScore.DEFAULT_MIN_INTERNATIONAL + (
            hash_value % (CreditScore.MAX_INTERNATIONAL - CreditScore.DEFAULT_MIN_INTERNATIONAL)
        )

        mock_total_debt = Decimal(f"{hash_value % 20000}.00")
        mock_monthly_obligations = mock_total_debt / BusinessRules.DEFAULT_LOAN_TERM_MONTHS_DECIMAL

        return BankingData(
            provider_name=f"Mock Provider ({self.country_code})",
            account_status=SystemValues.DEFAULT_ACCOUNT_STATUS,
            credit_score=mock_credit_score,
            total_debt=mock_total_debt,
            monthly_obligations=mock_monthly_obligations,
            has_defaults=(hash_value % 10 == 0),
            additional_data={
                'consulted_at': 'mock_timestamp',
                'data_source': 'default_mock_provider'
            }
        )
