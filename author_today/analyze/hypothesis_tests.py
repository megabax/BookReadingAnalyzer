"""Статистические тесты (Welch t-test, p-value).

Раньше модуль назывался stats_test.py (ADR-006).
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def _sample_var(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - 1)


def _sample_std(xs: Sequence[float]) -> float:
    return math.sqrt(_sample_var(xs))


def mean_and_sigma(xs: Sequence[float]) -> tuple[float, float, int]:
    """Среднее, σ (несмещённое s), число наблюдений."""
    n = len(xs)
    if n == 0:
        return 0.0, 0.0, 0
    m = _mean(xs)
    return round(m, 2), round(_sample_std(xs), 2), n


def welch_ttest_pvalue(a: Sequence[float], b: Sequence[float]) -> float | None:
    """
    Двусторонний Welch t-test для независимых выборок.
    None — если в одной из выборок меньше 2 дней.
    """
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None

    ma, mb = _mean(a), _mean(b)
    va = _sample_var(a)
    vb = _sample_var(b)

    # Нулевая дисперсия: scipy даёт NaN/warning — решаем детерминированно.
    if va <= 0 and vb <= 0:
        return 1.0 if abs(ma - mb) < 1e-9 else 0.0
    if va <= 0 or vb <= 0:
        return 1.0 if abs(ma - mb) < 1e-9 else 0.0

    try:
        from scipy.stats import ttest_ind

        _, p = ttest_ind(a, b, equal_var=False)
        p_f = float(p)
        if not math.isnan(p_f):
            return min(1.0, max(0.0, p_f))
    except ImportError:
        pass

    se2 = va / na + vb / nb
    if se2 <= 0:
        return 1.0 if abs(ma - mb) < 1e-9 else 0.0

    t = abs((ma - mb) / math.sqrt(se2))
    num = se2**2
    den = (va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1)
    df = num / den if den > 0 else float(na + nb - 2)

    return _t_pvalue_two_tail(t, df)


def _t_pvalue_two_tail(t: float, df: float) -> float:
    """Двусторонний p-value для |t| и df."""
    if not math.isfinite(t) or not math.isfinite(df) or df <= 0:
        return 1.0
    if t < 1e-12:
        return 1.0
    # Очень большой t — p ≈ 0
    if t > 40:
        return 0.0
    # При больших df — нормальное приближение
    if df >= 60 or t > 6:
        return min(1.0, max(0.0, math.erfc(t / math.sqrt(2))))

    x = df / (df + t * t)
    try:
        p_one = 0.5 * _betainc_reg(df / 2, 0.5, x)
        p = min(1.0, max(0.0, 2 * p_one))
        if math.isfinite(p):
            return p
    except (OverflowError, ValueError, ZeroDivisionError):
        pass

    return min(1.0, max(0.0, math.erfc(t / math.sqrt(2))))


def _betainc_reg(a: float, b: float, x: float) -> float:
    """Регуляризованная неполная бета I_x(a,b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    if x < (a + 1) / (a + b + 2):
        ln_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
        front = math.exp(a * math.log(x) + b * math.log1p(-x) - ln_beta) / a
        return front * _betacf(a, b, x)
    return 1.0 - _betainc_reg(b, a, 1.0 - x)


def _betacf(a: float, b: float, x: float) -> float:
    """Modified Lentz continued fraction (стабильнее NR)."""
    max_iter = 500
    eps = 1e-14
    fpmin = 1e-300

    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d

    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta

        if abs(delta - 1.0) < eps:
            return h

    return h
