import asyncio
from abc import ABC, abstractmethod

from ...strategies.base import BankingData


class MockDataGenerator(ABC):
    """Base strategy for generating mock banking data by country.
    
    Each country-specific generator inherits from this class and implements
    the generate() method with country-specific logic.
    """
    
    def __init__(self, provider_name: str):
        """Initialize the generator.
        
        Args:
            provider_name: Name of the banking provider for this country
        """
        self.provider_name = provider_name
    
    @abstractmethod
    async def generate(self, document: str, full_name: str) -> BankingData:
        """Generate mock banking data for this country.
        
        Args:
            document: Identity document number
            full_name: Full name of the applicant
        
        Returns:
            BankingData with mock information
        """
        pass
    
    def _calculate_hash(self, document: str) -> int:
        """Calculate deterministic hash from document.
        
        This provides consistent mock data for the same document number.
        
        Args:
            document: Identity document number
        
        Returns:
            Hash value as integer
        """
        document_clean = document.replace(' ', '').replace('-', '')
        return sum(ord(c) for c in document_clean)
    
    async def _simulate_api_delay(self, seconds: float = 0.1):
        """Simulate API call delay.
        
        Args:
            seconds: Delay in seconds (default: 0.1)
        """
        await asyncio.sleep(seconds)
