from budget import is_within_budget


def test_is_within_budget_boundary_cases():
    assert is_within_budget(50, 50) is True
    assert is_within_budget(51, 50) is False
