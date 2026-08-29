"""Tests for src.providers."""

from __future__ import annotations

import os
from unittest.mock import patch

import pandas as pd
import pytest

from src.providers import build_provider_registry
from src.providers.base import ErrorCode
from src.providers.eodhd import EodhdProvider
from src.providers.fred import FredProvider
from src.providers.yahoo import YahooProvider, _closes


def test_registry_contains_all_providers():
    registry = build_provider_registry()
    assert set(registry) == {"yahoo", "fred", "eodhd"}


def test_yahoo_provider_no_data():
    provider = YahooProvider()
    inst = {"symbol": "INVALID_TICKER_XYZ", "symbol_fallbacks": []}
    result = provider.fetch(inst)
    assert result.status == ErrorCode.NO_DATA
    assert result.error == "yahoo_no_data"


def test_yahoo_provider_warm_cache():
    provider = YahooProvider()
    with patch.object(provider, "_fetch_many") as mock_fetch:
        mock_fetch.return_value = {}
        provider.warm_cache(["AAPL", "AAPL", "MSFT"])
        mock_fetch.assert_called_once_with(["AAPL", "MSFT"], years=2)


def test_fred_provider_no_series():
    provider = FredProvider()
    result = provider.fetch({})
    assert result.status == ErrorCode.NO_SYMBOL
    assert result.error == "fred_no_series"


def test_fred_provider_no_key():
    provider = FredProvider()
    with patch.dict(os.environ, {}, clear=True):
        result = provider.fetch({"fred_series": "DGS10"})
    assert result.status == ErrorCode.NO_KEY
    assert result.error == "fred_no_key"


def test_eodhd_provider_no_symbol():
    provider = EodhdProvider()
    result = provider.fetch({})
    assert result.status == ErrorCode.NO_SYMBOL
    assert result.error == "eodhd_no_symbol"


def test_eodhd_provider_no_key():
    provider = EodhdProvider()
    with patch.dict(os.environ, {}, clear=True):
        result = provider.fetch({"eodhd_symbol": "AAPL.US"})
    assert result.status == ErrorCode.NO_KEY
    assert result.error == "eodhd_no_key"


def test_closes_extracts_close_column():
    hist = pd.DataFrame({"Close": [1.0, 2.0, 3.0]}, index=pd.date_range("2026-01-01", periods=3))
    s = _closes(hist)
    assert s is not None
    assert list(s.values) == pytest.approx([1.0, 2.0, 3.0])


def test_closes_returns_none_when_close_missing():
    hist = pd.DataFrame({"Open": [1.0, 2.0]}, index=pd.date_range("2026-01-01", periods=2))
    assert _closes(hist) is None


def test_fred_fetch_series_parses_json():
    payload = {
        "observations": [
            {"date": "2026-01-02", "value": "1.5"},
            {"date": "2026-01-03", "value": "."},
            {"date": "2026-01-04", "value": "2.0"},
        ]
    }
    with patch.dict(os.environ, {"FRED_API_KEY": "test_key"}):
        with patch("src.providers.fred._get_json", return_value=payload):
            from src.providers.fred import _fetch_series
            s = _fetch_series("DGS10")
    assert s is not None
    assert len(s) == 2
    assert pytest.approx(float(s.iloc[-1])) == 2.0


def test_eodhd_fetch_series_parses_json():
    payload = [
        {"date": "2026-01-02", "adjusted_close": "100.0"},
        {"date": "2026-01-03", "close": "101.0"},
    ]
    with patch.dict(os.environ, {"EODHD_API_KEY": "test_key"}):
        with patch("src.providers.eodhd._get_json", return_value=payload):
            from src.providers.eodhd import _fetch_series
            s = _fetch_series("AAPL.US")
    assert s is not None
    assert len(s) == 2
    assert pytest.approx(float(s.iloc[-1])) == 101.0
