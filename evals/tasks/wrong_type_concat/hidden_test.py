from formatter import format_price


def test_format_price_different_amount():
    assert format_price(250) == "$250"
