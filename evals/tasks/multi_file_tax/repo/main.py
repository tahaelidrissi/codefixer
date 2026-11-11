from helpers import add_tax


def total_price(price: float) -> float:
    return add_tax(price, 0.2)
