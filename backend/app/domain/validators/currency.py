from ...core.constants import COUNTRY_CURRENCY
from ...core.logging import get_logger

logger = get_logger(__name__)


def validate_and_normalize_currency(
    country_code: str,
    currency: str | None,
    country_name: str
) -> str:
    """Validate and normalize currency for the application.
    
    Business rule: All supported countries have a fixed currency.
    If user provides a currency, it must match the country's expected currency.
    If not provided, the currency is automatically inferred from the country.
    
    Args:
        country_code: ISO country code (e.g., 'BR', 'MX', 'CO')
        currency: Currency code provided by user (can be None)
        country_name: Human-readable country name (for error messages)
        
    Returns:
        Normalized currency code (uppercase)
        
    Raises:
        ValueError: If currency doesn't match country or country has no configured currency
        
    Examples:
        >>> validate_and_normalize_currency('BR', 'brl', 'Brazil')
        'BRL'
        >>> validate_and_normalize_currency('BR', None, 'Brazil')
        'BRL'
        >>> validate_and_normalize_currency('BR', 'USD', 'Brazil')
        ValueError: Currency 'USD' does not match country 'Brazil' (BR)...
    """
    expected_currency = COUNTRY_CURRENCY.get(country_code)
    
    if not expected_currency:
        logger.error(
            "No default currency configured for country",
            extra={'country': country_code}
        )
        raise ValueError(
            f"No default currency configured for country '{country_code}'. "
            f"This is a configuration error. Please contact support."
        )
    
    if currency is not None and currency.upper() != expected_currency.upper():
        logger.warning(
            "Currency mismatch detected",
            extra={
                'country': country_code,
                'provided_currency': currency,
                'expected_currency': expected_currency
            }
        )
        raise ValueError(
            f"Currency '{currency}' does not match country '{country_name}' ({country_code}). "
            f"Expected currency: {expected_currency}"
        )
    
    logger.debug(
        "Currency validated",
        extra={'country': country_code, 'currency': expected_currency}
    )
    
    return expected_currency.upper()
