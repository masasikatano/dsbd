"""Tests for src.compute."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from src.compute import (
    derive_from_lasts,
    derive_series,
    history_points,
    maybe_scale_series,
    metrics,
    monthly_metrics,
    scale_yield,
    spread,
    spread_series,
)


def _series(values: list[float], start: str = "2024-01-01") -> pd.Series:
    dates = pd.date_range(start=start, periods=len(values), freq="B")
    return pd.Series(values, index=dates, dtype=float)


def test_scale_yield_does_not_scale_when_threshold_is_none():
    assert scale_yield(5.0, None) == 5.0


def test_scale_yield_scales_when_value_exceeds_threshold():
    assert scale_yield(25.0, 20.0) == 2.5


def test_scale_yield_does_not_scale_when_value_below_threshold():
    assert scale_yield(15.0, 20.0) == 15.0


def test_metrics_empty_series():
    s = pd.Series([], dtype=float)
    assert metrics(s) == {
        "last": None,
        "last_date": None,
        "chg_1d_pct": None,
        "ytd_pct": None,
        "pos_52w_pct": None,
        "dev_200d_pct": None,
        "vol_1y_pct": None,
    }


def test_metrics_basic():
    s = _series([100.0, 102.0, 101.0], start="2026-01-02")
    m = metrics(s)
    assert m["last"] == 101.0
    assert m["last_date"] == "2026-01-06"
    assert pytest.approx(m["chg_1d_pct"]) == (101.0 / 102.0 - 1.0) * 100.0


def test_metrics_ytd():
    s = _series([100.0, 110.0], start="2026-01-02")
    m = metrics(s)
    assert pytest.approx(m["ytd_pct"]) == 10.0


def test_metrics_52w_position():
    values = [100.0 + i for i in range(300)]
    s = _series(values, start="2025-01-01")
    m = metrics(s)
    assert pytest.approx(m["pos_52w_pct"]) == 100.0


def test_metrics_200d_deviation():
    values = list(range(1, 250))
    s = _series(values, start="2025-01-01")
    m = metrics(s)
    last = values[-1]
    ma200 = sum(values[-200:]) / 200.0
    assert pytest.approx(m["dev_200d_pct"]) == (last / ma200 - 1.0) * 100.0


def test_metrics_volatility():
    values = [100.0]
    for _ in range(252):
        values.append(values[-1] * 1.01)
    s = _series(values, start="2025-01-01")
    m = metrics(s)
    assert m["vol_1y_pct"] is not None
    assert m["vol_1y_pct"] > 0


def test_spread_with_none():
    assert spread(1.0, None) is None
    assert spread(None, 1.0) is None


def test_spread():
    assert spread(3.0, 1.0) == 2.0


def test_history_points_limits_output():
    s = _series(list(range(200)), start="2025-01-01")
    hist = history_points(s, max_points=10)
    assert len(hist["t"]) == 10
    assert len(hist["v"]) == 10


def test_history_points_empty():
    s = pd.Series([], dtype=float)
    hist = history_points(s)
    assert hist == {"t": [], "v": []}


def test_spread_series_aligns_dates():
    a = _series([10.0, 11.0, 12.0], start="2026-01-02")
    b = _series([1.0, 2.0, 3.0], start="2026-01-02")
    ss = spread_series(a, b)
    assert ss is not None
    assert list(ss.values) == pytest.approx([9.0, 9.0, 9.0])


def test_spread_series_insufficient_overlap():
    a = _series([10.0], start="2026-01-02")
    b = _series([1.0], start="2026-01-02")
    assert spread_series(a, b) is None


def test_derive_series_alias():
    a = _series([10.0, 11.0], start="2026-01-02")
    b = _series([1.0, 2.0], start="2026-01-02")
    ss = derive_series(a, b)
    assert ss is not None
    assert list(ss.values) == pytest.approx([9.0, 9.0])


def test_derive_from_lasts_success():
    a = {"status": "ok", "last": 3.0, "last_date": "2026-01-02"}
    b = {"status": "ok", "last": 1.0, "last_date": "2026-01-02"}
    d = derive_from_lasts(a, b)
    assert d is not None
    assert d["last"] == 2.0
    assert d["last_date"] == "2026-01-02"
    assert d["chg_1d_pct"] is None


def test_derive_from_lasts_missing():
    a = {"status": "ok", "last": None}
    b = {"status": "ok", "last": 1.0}
    assert derive_from_lasts(a, b) is None


def test_maybe_scale_series():
    s = _series([30.0, 31.0], start="2026-01-02")
    scaled = maybe_scale_series(s, 20.0)
    assert pytest.approx(float(scaled.iloc[-1])) == 3.1


def test_maybe_scale_series_no_scale():
    s = _series([15.0, 16.0], start="2026-01-02")
    scaled = maybe_scale_series(s, 20.0)
    assert float(scaled.iloc[-1]) == 16.0


def _monthly_series(values: list[float], start: str = "2025-01-01") -> pd.Series:
    dates = pd.date_range(start=start, periods=len(values), freq="MS")
    return pd.Series(values, index=dates, dtype=float)


def test_monthly_metrics_empty():
    s = pd.Series([], dtype=float)
    assert monthly_metrics(s) == {
        "last": None,
        "last_date": None,
        "mom_pct": None,
        "yoy_pct": None,
    }


def test_monthly_metrics_basic():
    s = _monthly_series([100.0, 101.0, 102.0], start="2026-01-01")
    m = monthly_metrics(s)
    assert m["last"] == 102.0
    assert m["last_date"] == "2026-03-01"
    assert pytest.approx(m["mom_pct"]) == (102.0 / 101.0 - 1.0) * 100.0
    assert m["yoy_pct"] is None


def test_monthly_metrics_yoy():
    values = [100.0] + [100.0 * (1.002 ** i) for i in range(1, 14)]
    s = _monthly_series(values, start="2025-01-01")
    m = monthly_metrics(s)
    assert m["last"] == pytest.approx(values[-1])
    assert pytest.approx(m["yoy_pct"]) == (values[-1] / values[-13] - 1.0) * 100.0
