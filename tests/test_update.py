"""Tests for src.update orchestration."""

from __future__ import annotations

import pandas as pd
import pytest

from src.providers.base import ErrorCode, FetchResult, Provider
from src.update import (
    base_item,
    build_payload,
    compute_derived,
    fetch_instrument,
    missing,
    ok_from_series,
    ticker_label,
)


def _series(values: list[float], start: str = "2026-01-02") -> pd.Series:
    dates = pd.date_range(start=start, periods=len(values), freq="B")
    return pd.Series(values, index=dates, dtype=float)


class FakeProvider:
    name = "fake"

    def __init__(self, result: FetchResult) -> None:
        self._result = result

    def fetch(self, inst: dict) -> FetchResult:
        return self._result


def test_ticker_label_yahoo():
    inst = {"symbol": "^GSPC", "provider": "yahoo", "listed_also": ["SPY"]}
    assert ticker_label(inst) == "^GSPC, SPY"


def test_ticker_label_fred():
    inst = {"provider": "fred", "fred_series": "DGS10"}
    assert ticker_label(inst) == "DGS10"


def test_ticker_label_derived():
    inst = {"provider": "derived"}
    assert ticker_label(inst) == "derived"


def test_base_item_defaults():
    inst = {"id": "test"}
    item = base_item(inst)
    assert item["id"] == "test"
    assert "status" not in item  # base_item does not set status
    assert item["priority"] == "next"


def test_missing_item():
    inst = {"id": "test"}
    item = missing(inst, "no_data")
    assert item["status"] == "missing"
    assert item["error"] == "no_data"


def test_ok_from_series():
    inst = {"id": "test", "name": "Test"}
    s = _series([100.0, 102.0])
    item, returned = ok_from_series(inst, s)
    assert item["status"] == "ok"
    assert item["last"] == 102.0
    assert returned is s


def test_fetch_instrument_ok():
    s = _series([100.0, 102.0])
    provider = FakeProvider(FetchResult(ErrorCode.OK, s, resolved_symbol="^GSPC"))
    registry = {"fake": provider}
    inst = {"id": "sp500", "name": "S&P 500", "symbol": "^GSPC", "provider": "fake"}
    item, series = fetch_instrument(inst, registry)
    assert item["status"] == "ok"
    assert item["resolved_symbol"] == "^GSPC"
    assert series is s


def test_fetch_instrument_unknown_provider():
    registry = {}
    inst = {"id": "x", "name": "X", "provider": "missing"}
    item, series = fetch_instrument(inst, registry)
    assert item["status"] == "missing"
    assert "unknown_provider" in item["error"]
    assert series is None


def test_fetch_instrument_yahoo_to_fred_fallback():
    yahoo = FakeProvider(FetchResult(ErrorCode.NO_DATA, error="yahoo_no_data"))
    s = _series([1.0, 2.0])
    fred = FakeProvider(FetchResult(ErrorCode.OK, s, resolved_symbol="DGS10"))
    registry = {"yahoo": yahoo, "fred": fred}
    inst = {
        "id": "us_10y",
        "name": "US 10Y",
        "symbol": "^TNX",
        "provider": "yahoo",
        "fred_series": "DGS10",
    }
    item, series = fetch_instrument(inst, registry)
    assert item["status"] == "ok"
    assert item["resolved_symbol"] == "DGS10"


def test_compute_derived_from_series():
    inst = {
        "id": "spread",
        "name": "Spread",
        "provider": "derived",
        "derived": {"minus": ["a", "b"]},
    }
    items_by_id = {}
    series_store = {
        "a": _series([5.0, 6.0]),
        "b": _series([1.0, 2.0]),
    }
    derived = compute_derived([inst], items_by_id, series_store)
    assert len(derived) == 1
    assert derived[0]["status"] == "ok"
    assert derived[0]["last"] == 4.0


def test_compute_derived_from_lasts():
    inst = {
        "id": "spread",
        "name": "Spread",
        "provider": "derived",
        "derived": {"minus": ["a", "b"]},
    }
    items_by_id = {
        "a": {"status": "ok", "last": 5.0, "last_date": "2026-01-03"},
        "b": {"status": "ok", "last": 2.0, "last_date": "2026-01-03"},
    }
    series_store = {}
    derived = compute_derived([inst], items_by_id, series_store)
    assert len(derived) == 1
    assert derived[0]["status"] == "ok"
    assert derived[0]["last"] == 3.0


def test_compute_derived_missing_deps():
    inst = {
        "id": "spread",
        "name": "Spread",
        "provider": "derived",
        "derived": {"minus": ["a", "b"]},
    }
    items_by_id = {"a": {"status": "missing"}}
    series_store = {}
    derived = compute_derived([inst], items_by_id, series_store)
    assert derived[0]["status"] == "missing"


def test_build_payload_counts():
    cfg = {"sections": [{"id": "s1", "title": "S1"}]}
    items = [
        {"id": "a", "status": "ok", "provider": "yahoo"},
        {"id": "b", "status": "missing", "provider": "fred"},
    ]
    payload = build_payload(cfg, items)
    assert payload["ok_count"] == 1
    assert payload["missing_count"] == 1
    assert payload["source"] == "mixed"
    assert payload["sections"] == cfg["sections"]


def test_build_payload_yahoo_only_source():
    cfg = {"sections": []}
    items = [
        {"id": "a", "status": "ok", "provider": "yahoo"},
        {"id": "b", "status": "ok", "provider": "yahoo"},
    ]
    payload = build_payload(cfg, items)
    assert payload["source"] == "yahoo"


def _monthly_series(values: list[float], start: str = "2025-01-01") -> pd.Series:
    dates = pd.date_range(start=start, periods=len(values), freq="MS")
    return pd.Series(values, index=dates, dtype=float)


def test_base_item_monthly_flag():
    inst = {"id": "us_cpi_yoy", "monthly": True}
    item = base_item(inst)
    assert item["monthly"] is True


def test_ok_from_series_monthly():
    inst = {"id": "us_cpi_yoy", "name": "CPI", "monthly": True}
    s = _monthly_series([100.0, 101.0, 102.0], start="2026-01-01")
    item, returned = ok_from_series(inst, s)
    assert item["status"] == "ok"
    assert item["last"] == 102.0
    assert item["mom_pct"] is not None
    assert "chg_1d_pct" not in item
    assert "ytd_pct" not in item


def test_ok_from_series_daily():
    inst = {"id": "sp500", "name": "S&P 500"}
    s = _series([100.0, 102.0])
    item, returned = ok_from_series(inst, s)
    assert item["status"] == "ok"
    assert "chg_1d_pct" in item
    assert "mom_pct" not in item
