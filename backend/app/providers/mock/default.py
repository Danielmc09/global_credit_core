from decimal import Decimal

from ...core.constants import BusinessRules, CreditScore, SystemValues
from ...strategies.base import BankingData
from .base import MockDataGenerator


class DefaultMockDataGenerator(MockDataGenerator):
    """Fallback generator for unsupported countries."""
    
    def __init__(self, provider_name: str, country_code: str):
        """Initialize default generator.
        
        Args:
            provider_name: Name of the banking provider
            country_code: Country code for logging purposes
        """
        super().__init__(provider_name)
        self.country_code = country_code
    
    async def generate(self, document: str, full_name: str) -> BankingData:
        """Generate default mock banking data.
        
        Uses deterministic hash-based generation with conservative defaults.
        
        Args:
            document: Identity document number
            full_name: Full name of the applicant
        
        Returns:
            BankingData with default mock information
        """
        await self._simulate_api_delay()
        
        hash_value = self._calculate_hash(document)
        
        mock_credit_score = CreditScore.DEFAULT_MIN_INTERNATIONAL + (
            hash_value % (CreditScore.MAX_INTERNATIONAL - CreditScore.DEFAULT_MIN_INTERNATIONAL)
        )
        
        mock_total_debt = Decimal(f"{hash_value % 20000}.00")
        mock_monthly_obligations = mock_total_debt / BusinessRules.DEFAULT_LOAN_TERM_MONTHS_DECIMAL
        
        return BankingData(
            provider_name=self.provider_name,
            account_status=SystemValues.DEFAULT_ACCOUNT_STATUS,
            credit_score=mock_credit_score,
            total_debt=mock_total_debt,
            monthly_obligations=mock_monthly_obligations,
            has_defaults=(hash_value % 10 == 0),
            additional_data={
                'consulted_at': 'mock_timestamp',
                'data_source': 'default_mock_provider',
                'country_code': self.country_code
            }
        )
