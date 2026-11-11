from shop import calculate_discount


def test_calculate_discount_different_values():
    assert calculate_discount(200, 25) == 50
