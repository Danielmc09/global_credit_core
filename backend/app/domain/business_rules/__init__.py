"""Business Rules - Domain Layer.

Country-specific business rules and limits.
"""

from .country_limits import (
    MAX_LOAN_AMOUNTS,
    MIN_MONTHLY_INCOMES,
    get_max_loan_amount,
    get_min_monthly_income,
)

__all__ = [
    "MAX_LOAN_AMOUNTS",
    "MIN_MONTHLY_INCOMES",
    "get_max_loan_amount",
    "get_min_monthly_income",
]
