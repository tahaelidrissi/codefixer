from models import Order


def test_final_total_applies_discount():
    order = Order(150)
    assert order.final_total() == 140
