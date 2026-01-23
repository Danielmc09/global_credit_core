import random
from decimal import Decimal

from ...core.constants import SystemValues
from ...strategies.base import BankingData
from .base import MockDataGenerator


class ColombiaMockDataGenerator(MockDataGenerator):
    """Generate mock banking data for Colombia."""
    
    async def generate(self, document: str, full_name: str) -> BankingData:
        """Generate mock banking data for Colombia.
        
        Uses random generation with Colombia-specific credit score ranges
        and Datacrédito score integration.
        
        Args:
            document: Colombian Cédula de Ciudadanía
            full_name: Full name of the applicant
        
        Returns:
            BankingData with Colombian mock information
        """
        await self._simulate_api_delay()
        
        credit_scores = [580, 620, 680, 740, 820]
        
        return BankingData(
            provider_name=self.provider_name,
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
