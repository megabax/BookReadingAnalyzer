"""Тесты Welch t-test и описательной статистики."""

from __future__ import annotations

import pytest

from author_today.analyze.stats_test import mean_and_sigma, welch_ttest_pvalue

try:
    from scipy.stats import ttest_ind

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def test_mean_and_sigma():
    mean, sigma, n = mean_and_sigma([10.0, 20.0, 30.0])
    assert mean == 20.0
    assert n == 3
    assert sigma == pytest.approx(10.0, abs=0.01)


def test_mean_and_sigma_empty():
    mean, sigma, n = mean_and_sigma([])
    assert mean == 0.0
    assert sigma == 0.0
    assert n == 0


def test_welch_identical_samples():
    a = [50.0, 50.0, 50.0, 50.0]
    b = [50.0, 50.0, 50.0, 50.0]
    p = welch_ttest_pvalue(a, b)
    assert p == 1.0


def test_welch_different_samples():
    a = [50.0] * 10
    b = [70.0] * 10
    p = welch_ttest_pvalue(a, b)
    assert p is not None
    assert p < 0.05


def test_welch_insufficient_data():
    assert welch_ttest_pvalue([50.0], [70.0]) is None
    assert welch_ttest_pvalue([50.0, 60.0], [70.0]) is None


def test_welch_zero_variance_different_means():
    p = welch_ttest_pvalue([10.0, 10.0], [20.0, 20.0])
    assert p == 0.0


def test_welch_large_t_does_not_raise():
    """Регрессия: betacf не должен падать на реальных длинных периодах."""
    import random

    random.seed(42)
    a = [random.uniform(30, 90) for _ in range(31)]
    b = [random.uniform(35, 95) for _ in range(31)]
    p = welch_ttest_pvalue(a, b)
    assert p is not None
    assert 0.0 <= p <= 1.0


@pytest.mark.skipif(not HAS_SCIPY, reason="scipy не установлен")
def test_welch_scipy_parity():
    a = [48.0, 52.0, 49.0, 51.0, 50.0, 53.0, 47.0]
    b = [58.0, 62.0, 59.0, 61.0, 60.0, 63.0, 57.0]
    _, p_scipy = ttest_ind(a, b, equal_var=False)
    p_fallback = welch_ttest_pvalue(a, b)
    assert p_fallback is not None
    assert abs(p_fallback - float(p_scipy)) < 0.01
