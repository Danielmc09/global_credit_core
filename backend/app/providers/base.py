"""Base Banking Provider Interface.

This module defines the abstract interface that all banking data providers must implement.
This abstraction allows for easy switching between different providers (mock, real APIs, etc.)
without modifying the strategy code.
"""

from abc import ABC, abstractmethod

from ..strategies.base import BankingData


class BankingProvider(ABC):
    """Abstract base class for banking data providers.

    All providers must implement the `fetch_banking_data` method to retrieve
    banking information for a given document and full name.

    This abstraction allows:
    - Easy switching between mock and real providers
    - Testing with different provider implementations
    - Future integration with multiple real providers
    - Consistent error handling and retry logic
    """

    def __init__(self, provider_name: str, country_code: str):
        """Initialize the banking provider.

        Args:
            provider_name: Name of the provider (e.g., "BRAZIL", "SPAIN")
            country_code: ISO 3166-1 alpha-2 country code (e.g., "BR", "ES")
        """
        self.provider_name = provider_name
        self.country_code = country_code


    @abstractmethod
    async def fetch_banking_data(
        self,
        document: str,
        full_name: str
    ) -> BankingData:
        """Fetch banking data from the provider.

        This method should:
        - Make the necessary API calls or data lookups
        - Handle provider-specific errors
        - Return standardized BankingData
        - Be async to support network I/O

        Args:
            document: Identity document number
            full_name: Full name of the applicant

        Returns:
            BankingData with information from the provider

        Raises:
            ProviderError: For provider-specific errors
            TimeoutError: If the request times out
            NetworkError: For network-related errors
        """
        pass


    def get_provider_name(self) -> str:
        """Get the provider name."""
        return self.provider_name


    def get_country_code(self) -> str:
        """Get the country code this provider serves."""
        return self.country_code
