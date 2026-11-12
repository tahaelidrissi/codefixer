from models import Order


def test_final_total_without_discount():
    order = Order(50)
    assert order.final_total() == 50
