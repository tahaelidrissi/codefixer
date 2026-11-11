from shop import calculate_discount


def test_calculate_discount():
    assert calculate_discount(100, 10) == 10
