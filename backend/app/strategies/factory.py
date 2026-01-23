"""Country Strategy Factory.

Provides a factory pattern to get the correct country strategy based on country code.
This makes it easy to extend to new countries without modifying existing code.
"""

from typing import Optional

from ..core.constants import CountryCode, ErrorMessages, CountryBusinessRules
from ..providers import BankingProvider, MockBankingProvider
from .base import BaseCountryStrategy
from .brazil import BrazilStrategy
from .colombia import ColombiaStrategy
from .italy import ItalyStrategy
from .mexico import MexicoStrategy
from .portugal import PortugalStrategy
from .spain import SpainStrategy
from .argentina import AregtinaStrategy


class CountryStrategyFactory:
    """Factory for creating country-specific strategies.

    Usage:
        strategy = CountryStrategyFactory.get_strategy(CountryCode.SPAIN)
        result = strategy.validate_identity_document('12345678Z')
    """

    _strategies: dict[str, type[BaseCountryStrategy]] = {
        CountryCode.SPAIN: SpainStrategy,      # Spain - DNI
        CountryCode.PORTUGAL: PortugalStrategy,   # Portugal - NIF
        CountryCode.ITALY: ItalyStrategy,      # Italy - Codice Fiscale
        CountryCode.MEXICO: MexicoStrategy,     # Mexico - CURP
        CountryCode.COLOMBIA: ColombiaStrategy,   # Colombia - Cédula
        CountryCode.BRAZIL: BrazilStrategy,     # Brazil - CPF
        CountryCode.ARGENTINA: AregtinaStrategy,
    }

    @classmethod
    def get_strategy(
        cls,
        country_code: str,
        banking_provider: Optional[BankingProvider] = None
    ) -> BaseCountryStrategy:
        """Get the appropriate strategy for a given country code.

        This method ALWAYS provides a banking provider. If none is provided,
        a MockBankingProvider is automatically created. This ensures that
        strategies always have a provider and eliminates the need for fallback
        implementations.

        Args:
            country_code: ISO 3166-1 alpha-2 country code (e.g., CountryCode.SPAIN, CountryCode.MEXICO)
            banking_provider: Optional banking provider instance. If None, a MockBankingProvider
                            will be created automatically. In production, you should provide
                            a real BankingProvider implementation.

        Returns:
            Instance of the country-specific strategy with banking provider injected.
            The provider is guaranteed to be non-None.

        Raises:
            ValueError: If country code is not supported
        """
        country_code = country_code.upper()

        strategy_class = cls._strategies.get(country_code)

        if not strategy_class:
            raise ValueError(
                ErrorMessages.COUNTRY_NOT_SUPPORTED.format(country_code=country_code) +
                f". Supported countries: {', '.join(cls._strategies.keys())}"
            )

        # Always provide a provider - if none is provided, use MockBankingProvider
        # This ensures strategies never have None as banking_provider
        if banking_provider is None:
            banking_provider = MockBankingProvider(country_code)

        return strategy_class(banking_provider=banking_provider)

    @classmethod
    def is_country_supported(cls, country_code: str) -> bool:
        """Check if a country code is supported.

        Args:
            country_code: ISO 3166-1 alpha-2 country code

        Returns:
            True if supported, False otherwise
        """
        return country_code.upper() in cls._strategies

    @classmethod
    def get_supported_countries(cls) -> list:
        """Get list of supported country codes.

        Returns:
            List of supported country codes
        """
        return list(cls._strategies.keys())

    @classmethod
    def register_strategy(
        cls,
        country_code: str,
        strategy_class: type[BaseCountryStrategy]
    ):
        """Register a new country strategy dynamically.

        This allows for plugin-like extension of supported countries.

        Args:
            country_code: ISO 3166-1 alpha-2 country code
            strategy_class: The strategy class to register
        """
        cls._strategies[country_code.upper()] = strategy_class


def get_country_strategy(
    country_code: str,
    banking_provider: Optional[BankingProvider] = None
) -> BaseCountryStrategy:
    """Convenience function to get a country strategy.

    This function ALWAYS provides a banking provider. If none is provided,
    a MockBankingProvider is automatically created.

    Args:
        country_code: ISO 3166-1 alpha-2 country code
        banking_provider: Optional banking provider instance. If None, a MockBankingProvider
                        will be created automatically. In production, you should provide
                        a real BankingProvider implementation.

    Returns:
        Instance of the country-specific strategy with banking provider injected.
        The provider is guaranteed to be non-None.
    """
    return CountryStrategyFactory.get_strategy(country_code, banking_provider)
