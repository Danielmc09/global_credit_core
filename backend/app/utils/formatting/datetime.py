"""DateTime formatting utilities."""

from datetime import date, datetime


def format_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime to string.

    Args:
        dt: Datetime object to format
        format_str: Format string (default: ISO-like format)

    Returns:
        Formatted datetime string

    Examples:
        >>> format_datetime(datetime(2024, 1, 15, 10, 30, 0))
        "2024-01-15 10:30:00"
        >>> format_datetime(datetime(2024, 1, 15), "%Y-%m-%d")
        "2024-01-15"
    """
    if not dt:
        return ""
    return dt.strftime(format_str)


def parse_datetime(date_string: str, format_str: str = "%Y-%m-%d") -> datetime | None:
    """Parse datetime string to datetime object.

    Args:
        date_string: Date string to parse
        format_str: Format string to use for parsing

    Returns:
        Datetime object or None if parsing fails

    Examples:
        >>> parse_datetime("2024-01-15")
        datetime(2024, 1, 15, 0, 0)
    """
    if not date_string:
        return None
    try:
        return datetime.strptime(date_string, format_str)
    except (ValueError, TypeError):
        return None


def calculate_age(birth_date: date) -> int:
    """Calculate age from birth date.

    Args:
        birth_date: Date of birth

    Returns:
        Age in years

    Examples:
        >>> from datetime import date
        >>> calculate_age(date(1990, 1, 1))
        36  # (assuming current year is 2026)
    """
    if not birth_date:
        return 0

    today = date.today()
    age = today.year - birth_date.year

    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1

    return age
