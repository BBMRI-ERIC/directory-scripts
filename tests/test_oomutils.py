import pytest

from oomutils import (
    DEFAULT_OOM_UPPER_BOUND_COEFFICIENT,
    ENV_OOM_UPPER_BOUND_COEFFICIENT,
    describe_oom_estimate_policy,
    estimate_count_from_oom,
    estimate_count_from_oom_or_none,
    get_oom_upper_bound_coefficient,
    normalize_oom_value,
)


def test_normalize_oom_value_supports_scalar_and_wrapped_values():
    assert normalize_oom_value(2) == 2
    assert normalize_oom_value("3") == 3
    assert normalize_oom_value({"id": "4"}) == 4
    assert normalize_oom_value(None) is None


def test_default_oom_policy_uses_lower_bound(monkeypatch):
    monkeypatch.delenv(ENV_OOM_UPPER_BOUND_COEFFICIENT, raising=False)

    assert get_oom_upper_bound_coefficient() == DEFAULT_OOM_UPPER_BOUND_COEFFICIENT
    assert estimate_count_from_oom(2) == 100
    assert describe_oom_estimate_policy() == "lower bound of the OoM interval (10**n)"


def test_configurable_oom_policy_uses_upper_bound_coefficient(monkeypatch):
    monkeypatch.setenv(ENV_OOM_UPPER_BOUND_COEFFICIENT, "0.3")

    assert get_oom_upper_bound_coefficient() == 0.3
    assert estimate_count_from_oom(2) == 300
    assert estimate_count_from_oom_or_none({"id": "2"}) == 300
    assert describe_oom_estimate_policy() == "0.3 * 10**(n+1)"


def test_invalid_oom_policy_rejected(monkeypatch):
    monkeypatch.setenv(ENV_OOM_UPPER_BOUND_COEFFICIENT, "0")

    with pytest.raises(ValueError):
        get_oom_upper_bound_coefficient()
