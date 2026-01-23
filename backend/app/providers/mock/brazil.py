import random
from decimal import Decimal

from ...core.constants import SystemValues
from ...strategies.base import BankingData
from .base import MockDataGenerator


class BrazilMockDataGenerator(MockDataGenerator):
    """Generate mock banking data for Brazil."""
    
    async def generate(self, document: str, full_name: str) -> BankingData:
        """Generate mock banking data for Brazil.
        
        Uses random generation with Brazil-specific credit score ranges
        and Serasa score integration.
        
        Args:
            document: Brazilian CPF
            full_name: Full name of the applicant
        
        Returns:
            BankingData with Brazilian mock information
        """
        await self._simulate_api_delay()
        
        credit_scores = [520, 580, 650, 720, 800]
        
        return BankingData(
            provider_name=self.provider_name,
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
