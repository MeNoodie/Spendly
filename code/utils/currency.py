"""
currency.py — Currency conversion utilities using the exchange_rates table.
"""
from code.db.queries import get_exchange_rate


def convert(
    amount: float,
    from_currency: str,
    to_currency: str,
    rate_date: str,
) -> float:
    """
    Convert amount from from_currency to to_currency using the closest
    available rate on or before rate_date.
    Raises ValueError if no rate found.
    """
    if from_currency == to_currency:
        return amount

    rate = get_exchange_rate(from_currency, to_currency, rate_date)
    if rate is None:
        # Try reverse rate
        rev = get_exchange_rate(to_currency, from_currency, rate_date)
        if rev and rev != 0:
            rate = 1.0 / rev

    if rate is None:
        raise ValueError(
            f"No exchange rate found: {from_currency} → {to_currency} on {rate_date}"
        )

    return round(amount * rate, 2)
