"""Validation utilities."""

import uuid
from decimal import Decimal
from typing import Any


def validate_uuid(uuid_string: str) -> bool:
    """Validate if a string is a valid UUID.

    Args:
        uuid_string: String to validate

    Returns:
        True if valid UUID, False otherwise

    Examples:
        >>> validate_uuid("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
        True
        >>> validate_uuid("invalid")
        False
    """
    if not uuid_string:
        return False

    if not isinstance(uuid_string, str):
        try:
            uuid_string = str(uuid_string)
        except (TypeError, ValueError):
            return False

    try:
        uuid.UUID(uuid_string)
        return True
    except (ValueError, TypeError):
        return False


def validate_amount_precision(amount: Decimal | None) -> Decimal | None:
    """Validate and round amount to database precision (2 decimal places).

    This function ensures amounts are rounded to the correct precision
    before being stored in the database to prevent precision errors.

    Args:
        amount: Decimal amount to validate and round

    Returns:
        Decimal rounded to 2 decimal places, or None if input is None

    Examples:
        >>> validate_amount_precision(Decimal("1234.5678"))
        Decimal("1234.57")
        >>> validate_amount_precision(Decimal("100.00"))
        Decimal("100.00")
        >>> validate_amount_precision(None)
        None
    """
    if amount is None:
        return None

    return amount.quantize(Decimal("0.01"))


def validate_risk_score_precision(risk_score: Decimal | None) -> Decimal | None:
    """Validate and round risk score to database precision (2 decimal places).

    This function ensures risk scores are rounded to the correct precision
    before being stored in the database to prevent precision errors.

    Args:
        risk_score: Decimal risk score to validate and round

    Returns:
        Decimal rounded to 2 decimal places, or None if input is None

    Examples:
        >>> validate_risk_score_precision(Decimal("45.6789"))
        Decimal("45.68")
        >>> validate_risk_score_precision(Decimal("50.00"))
        Decimal("50.00")
        >>> validate_risk_score_precision(None)
        None
    """
    if risk_score is None:
        return None

    return risk_score.quantize(Decimal("0.01"))


def validate_banking_data_precision(banking_data: dict[str, Any]) -> dict[str, Any]:
    """Validate and round numeric fields in banking_data to database precision.

    This function ensures all Decimal fields in banking_data are rounded to
    the correct precision before being stored in the database to prevent precision errors.
    Validates total_debt and monthly_obligations to 2 decimal places.

    Args:
        banking_data: Dictionary containing banking data with potential Decimal fields

    Returns:
        Dictionary with Decimal fields rounded to correct precision

    Examples:
        >>> validate_banking_data_precision({"total_debt": Decimal("1234.5678"), "credit_score": 700})
        {"total_debt": Decimal("1234.57"), "credit_score": 700}
    """
    if not banking_data or not isinstance(banking_data, dict):
        return banking_data

    validated = banking_data.copy()

    if 'total_debt' in validated and validated['total_debt'] is not None:
        if isinstance(validated['total_debt'], Decimal):
            validated['total_debt'] = validate_amount_precision(validated['total_debt'])
        elif isinstance(validated['total_debt'], str):
            try:
                debt_decimal = Decimal(validated['total_debt'])
                validated['total_debt'] = str(validate_amount_precision(debt_decimal))
            except (ValueError, TypeError, Exception):
                pass

    if 'monthly_obligations' in validated and validated['monthly_obligations'] is not None:
        if isinstance(validated['monthly_obligations'], Decimal):
            validated['monthly_obligations'] = validate_amount_precision(validated['monthly_obligations'])
        elif isinstance(validated['monthly_obligations'], str):
            try:
                obligations_decimal = Decimal(validated['monthly_obligations'])
                validated['monthly_obligations'] = str(validate_amount_precision(obligations_decimal))
            except (ValueError, TypeError, Exception):
                pass

    return validated
