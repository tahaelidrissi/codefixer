from models import Order


def get_discount(total):
    if total > 100:
        return 10
    return 0


def describe_order(order: Order) -> str:
    return f"Order total: {order.total}"
