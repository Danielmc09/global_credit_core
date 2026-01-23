"""Currency formatting utilities."""

from decimal import Decimal


def format_currency(amount: Decimal, currency_symbol: str = "$", decimals: int = 2) -> str:
    """Format decimal amount as currency string.

    Args:
        amount: Decimal amount to format
        currency_symbol: Currency symbol (default: "$")
        decimals: Number of decimal places (default: 2)

    Returns:
        Formatted currency string

    Examples:
        >>> format_currency(Decimal("1234.56"))
        "$1,234.56"
        >>> format_currency(Decimal("1000"), "€", 0)
        "€1,000"
    """
    if amount is None:
        return f"{currency_symbol}0.00"

    formatted = f"{amount:,.{decimals}f}"
    return f"{currency_symbol}{formatted}"
