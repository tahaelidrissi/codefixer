from main import total_price


def test_total_price_different_amount():
    assert total_price(200) == 240
