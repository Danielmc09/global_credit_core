from decimal import Decimal

from ...core.constants import CreditScore, SystemValues
from ...strategies.base import BankingData
from .base import MockDataGenerator


class MexicoMockDataGenerator(MockDataGenerator):
    """Generate mock banking data for Mexico."""
    
    async def generate(self, document: str, full_name: str) -> BankingData:
        """Generate mock banking data for Mexico.
        
        Uses deterministic hash-based generation with Mexico-specific
        debt ranges and 24-month obligation calculation.
        
        Args:
            document: Mexican CURP or RFC
            full_name: Full name of the applicant
        
        Returns:
            BankingData with Mexican mock information
        """
        await self._simulate_api_delay()
        
        hash_value = self._calculate_hash(document)
        
        mock_credit_score = CreditScore.MIN_INTERNATIONAL + (
            hash_value % (CreditScore.MAX_INTERNATIONAL - CreditScore.MIN_INTERNATIONAL)
        )
        
        mock_total_debt = Decimal(f"{hash_value % 100000}.00")
        mock_monthly_obligations = mock_total_debt / Decimal('24')
        
        return BankingData(
            provider_name=self.provider_name,
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
