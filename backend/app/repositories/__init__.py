"""Repository Layer.

Data access layer following Repository Pattern.
Separates data access logic from business logic.
"""

from .application_repository import ApplicationRepository

__all__ = ['ApplicationRepository']
