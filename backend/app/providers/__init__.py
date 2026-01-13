"""Banking Data Providers.

This module provides abstractions for external banking data providers.
It allows for easy switching between mock providers (for development/testing)
and real providers (for production) without changing the strategy code.
"""

from .base import BankingProvider
from .mock import MockBankingProvider

__all__ = [
    "BankingProvider",
    "MockBankingProvider",
]
