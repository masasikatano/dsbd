"""Five dashboard metrics plus derived spreads."""

from __future__ import annotations

import math

import pandas as pd


def scale_yield(value: float, scale_if_gt: float | None) -> float:
    if scale_if_gt is not None and value > scale_if_gt:
        return value / 10.0
    return value


def maybe_scale_series(series: pd.Series, scale_if_gt: float | None) -> pd.Series:
    if scale_if_gt is None or series.empty:
        return series
    last = float(series.iloc[-1])
    if last > scale_if_gt:
        return series / 10.0
    return series


def metrics(series: pd.Series) -> dict:
    s = series.dropna().astype(float)
    out = {
        "last": None,
        "last_date": None,
        "chg_1d_pct": None,
        "ytd_pct": None,
        "pos_52w_pct": None,
        "dev_200d_pct": None,
        "vol_1y_pct": None,
    }
    if s.empty:
        return out
    pn = float(s.iloc[-1])
    last_ts = s.index[-1]
    out["last"] = pn
    out["last_date"] = pd.Timestamp(last_ts).strftime("%Y-%m-%d")

    if len(s) >= 2 and float(s.iloc[-2]) != 0:
        out["chg_1d_pct"] = (pn / float(s.iloc[-2]) - 1.0) * 100.0

    year = pd.Timestamp(last_ts).year
    ytd = s[s.index >= f"{year}-01-01"]
    if len(ytd) >= 1 and float(ytd.iloc[0]) != 0:
        out["ytd_pct"] = (pn / float(ytd.iloc[0]) - 1.0) * 100.0

    win = s.iloc[-252:] if len(s) >= 20 else s
    hi = float(win.max())
    lo = float(win.min())
    if hi != lo:
        out["pos_52w_pct"] = (pn - lo) / (hi - lo) * 100.0

    if len(s) >= 200:
        ma = float(s.iloc[-200:].mean())
        if ma != 0:
            out["dev_200d_pct"] = (pn / ma - 1.0) * 100.0

    if len(s) >= 60:
        rets = (s / s.shift(1)).dropna()
        rets = rets[rets > 0]
        log_rets = rets.map(math.log)
        window = log_rets.iloc[-252:] if len(log_rets) >= 252 else log_rets
        if len(window) >= 20:
            std = float(window.std(ddof=1))
            out["vol_1y_pct"] = std * math.sqrt(252) * 100.0

    return out


def monthly_metrics(series: pd.Series) -> dict:
    """Metrics for monthly economic series such as CPI.

    Returns latest value, observation date, month-over-month change and
    year-over-year change. Daily-style metrics are omitted.
    """
    s = series.dropna().astype(float)
    out = {
        "last": None,
        "last_date": None,
        "mom_pct": None,
        "yoy_pct": None,
    }
    if s.empty:
        return out
    pn = float(s.iloc[-1])
    last_ts = s.index[-1]
    out["last"] = pn
    out["last_date"] = pd.Timestamp(last_ts).strftime("%Y-%m-%d")

    if len(s) >= 2 and float(s.iloc[-2]) != 0:
        out["mom_pct"] = (pn / float(s.iloc[-2]) - 1.0) * 100.0

    # Year-over-year: compare with the value 12 months earlier.
    if len(s) >= 13 and float(s.iloc[-13]) != 0:
        out["yoy_pct"] = (pn / float(s.iloc[-13]) - 1.0) * 100.0

    return out


def spread(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return a - b


def history_points(series: pd.Series, max_points: int = 90) -> dict:
    s = series.dropna().astype(float)
    if s.empty:
        return {"t": [], "v": []}
    if len(s) > max_points:
        step = (len(s) - 1) / (max_points - 1)
        idx = [int(round(i * step)) for i in range(max_points)]
        s = s.iloc[idx]
    return {
        "t": [pd.Timestamp(i).strftime("%Y-%m-%d") for i in s.index],
        "v": [round(float(x), 6) for x in s.to_numpy()],
    }


def spread_series(a: pd.Series, b: pd.Series) -> pd.Series | None:
    left, right = a.align(b, join="inner")
    left = left.dropna()
    right = right.dropna()
    both = left.index.intersection(right.index)
    if len(both) < 2:
        return None
    return left.loc[both] - right.loc[both]


def derive_series(a: pd.Series, b: pd.Series) -> pd.Series | None:
    """Derive a spread series from two underlying series."""
    return spread_series(a, b)


def derive_from_lasts(item_a: dict, item_b: dict) -> dict | None:
    """Build a derived item from the last values of two dependencies.

    Returns a metrics-like dict with only ``last`` and ``last_date`` populated,
    or None when either dependency is missing a last value.
    """
    if not item_a or not item_b:
        return None
    if item_a.get("status") != "ok" or item_b.get("status") != "ok":
        return None
    last_a = item_a.get("last")
    last_b = item_b.get("last")
    if last_a is None or last_b is None:
        return None
    last = spread(float(last_a), float(last_b))
    if last is None:
        return None
    return {
        "last": last,
        "last_date": item_b.get("last_date") or item_a.get("last_date"),
        "chg_1d_pct": None,
        "ytd_pct": None,
        "pos_52w_pct": None,
        "dev_200d_pct": None,
        "vol_1y_pct": None,
        "history": {"t": [], "v": []},
    }
