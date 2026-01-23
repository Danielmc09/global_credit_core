from slowapi import Limiter

from ....core.config import settings
from ....infrastructure.security import get_rate_limit_key

limiter = Limiter(key_func=get_rate_limit_key)


def apply_rate_limit_if_needed(func):
    """Apply rate limiting only if not in test environment.
    
    Uses settings.ENVIRONMENT to check the current environment.
    Since conftest.py sets ENVIRONMENT="test" in os.environ before
    importing application code, settings will correctly capture this value.
    
    Args:
        func: The function to potentially apply rate limiting to
        
    Returns:
        The original function or the rate-limited version
    """
    if settings.ENVIRONMENT == "test":
        return func
    
    return limiter.limit("10/minute")(func)
