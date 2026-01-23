"""Country-Specific Limits Configuration.

Centralized configuration for country-specific business rules.
This allows limits to be changed without code modifications.
"""

from decimal import Decimal
from typing import Optional


MAX_LOAN_AMOUNTS: dict[str, Optional[Decimal]] = {
    'ES': Decimal('50000.00'),  # €50,000
    'MX': Decimal('200000.00'),  # $200,000 MXN
    'BR': Decimal('100000.00'),  # R$ 100,000
    'CO': Decimal('50000000.00'),  # COP $50,000,000
    'PT': Decimal('30000.00'),  # €30,000
    'IT': Decimal('40000.00'),  # €40,000
}

MIN_MONTHLY_INCOMES: dict[str, Optional[Decimal]] = {
    'ES': Decimal('1500.00'),  # €1,500
    'MX': Decimal('5000.00'),  # $5,000 MXN
    'BR': Decimal('2000.00'),  # R$ 2,000
    'CO': Decimal('1500000.00'),  # COP $1,500,000
    'PT': Decimal('800.00'),  # €800
    'IT': Decimal('1200.00'),  # €1,200
}


def get_max_loan_amount(country_code: str) -> Optional[Decimal]:
    """Get maximum loan amount for a country.

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., 'ES', 'MX')

    Returns:
        Maximum loan amount as Decimal, or None if country not supported
    """
    return MAX_LOAN_AMOUNTS.get(country_code)


def get_min_monthly_income(country_code: str) -> Optional[Decimal]:
    """Get minimum monthly income requirement for a country.

    Args:
        country_code: ISO 3166-1 alpha-2 country code (e.g., 'ES', 'MX')

    Returns:
        Minimum monthly income as Decimal, or None if country not supported
    """
    return MIN_MONTHLY_INCOMES.get(country_code)


def is_country_supported(country_code: str) -> bool:
    """Check if a country is supported (has limits configured).

    Args:
        country_code: ISO 3166-1 alpha-2 country code

    Returns:
        True if country has limits configured, False otherwise
    """
    return country_code in MAX_LOAN_AMOUNTS and country_code in MIN_MONTHLY_INCOMES
