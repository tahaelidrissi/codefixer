from formatter import format_price


def test_format_price():
    assert format_price(10) == "$10"
