from decimal import Decimal

def calculate_base_amount(amount: Decimal, exchange_rate: Decimal) -> Decimal:
    if amount is None or exchange_rate is None:
        return Decimal("0.00")

    return (amount * exchange_rate).quantize(Decimal("0.01"))