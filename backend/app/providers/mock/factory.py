from ...core.constants import CountryCode, ProviderNames
from ...core.logging import get_logger
from .base import MockDataGenerator
from .brazil import BrazilMockDataGenerator
from .colombia import ColombiaMockDataGenerator
from .default import DefaultMockDataGenerator
from .italy import ItalyMockDataGenerator
from .mexico import MexicoMockDataGenerator
from .portugal import PortugalMockDataGenerator
from .spain import SpainMockDataGenerator

logger = get_logger(__name__)


class MockDataGeneratorFactory:
    """Factory to create country-specific mock data generators.
    
    This factory implements the Factory Pattern to create appropriate
    mock data generators based on country code.
    """
    
    _generators: dict[str, type[MockDataGenerator]] = {
        CountryCode.SPAIN: SpainMockDataGenerator,
        CountryCode.BRAZIL: BrazilMockDataGenerator,
        CountryCode.MEXICO: MexicoMockDataGenerator,
        CountryCode.ITALY: ItalyMockDataGenerator,
        CountryCode.PORTUGAL: PortugalMockDataGenerator,
        CountryCode.COLOMBIA: ColombiaMockDataGenerator,
    }
    
    _provider_names: dict[str, str] = {
        CountryCode.BRAZIL: ProviderNames.BRAZIL,
        CountryCode.SPAIN: ProviderNames.SPAIN,
        CountryCode.ITALY: ProviderNames.ITALY,
        CountryCode.MEXICO: ProviderNames.MEXICO,
        CountryCode.PORTUGAL: ProviderNames.PORTUGAL,
        CountryCode.COLOMBIA: ProviderNames.COLOMBIA,
    }
    
    @classmethod
    def create(cls, country_code: str) -> MockDataGenerator:
        """Create appropriate mock data generator for country.
        
        Args:
            country_code: Country code (ES, MX, BR, CO, PT, IT)
        
        Returns:
            MockDataGenerator instance for the country
        """
        generator_class = cls._generators.get(country_code)
        provider_name = cls._provider_names.get(
            country_code,
            f"Mock Provider ({country_code})"
        )
        
        if generator_class:
            logger.debug(
                f"Creating {generator_class.__name__} for {country_code}",
                extra={'country': country_code}
            )
            return generator_class(provider_name)
        else:
            logger.warning(
                f"No specific generator for country {country_code}, using default",
                extra={'country': country_code}
            )
            return DefaultMockDataGenerator(provider_name, country_code)
    
    @classmethod
    def get_supported_countries(cls) -> list[str]:
        """Get list of supported country codes.
        
        Returns:
            List of country codes with specific generators
        """
        return list(cls._generators.keys())
