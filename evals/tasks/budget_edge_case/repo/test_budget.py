from budget import is_within_budget


def test_is_within_budget_at_the_exact_limit():
    assert is_within_budget(100, 100) is True
