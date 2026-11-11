from greeting import greet


def test_greet_different_name():
    assert greet("Alice") == "Hello, Alice!"
