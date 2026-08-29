"""Yahoo Finance provider."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from src.providers.base import ErrorCode, FetchResult

log = logging.getLogger(__name__)


def _closes(hist: pd.DataFrame) -> pd.Series | None:
    if hist is None or hist.empty:
        return None
    col = "Close" if "Close" in hist.columns else None
    if col is None:
        return None
    s = hist[col].dropna()
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    s = s.astype(float)
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return s if not s.empty else None


class YahooProvider:
    """Fetches end-of-day closes from Yahoo Finance."""

    name = "yahoo"

    def __init__(self) -> None:
        self._cache: dict[str, pd.Series] = {}

    def fetch(self, inst: dict) -> FetchResult:
        symbols = [s for s in ([inst.get("symbol")] + list(inst.get("symbol_fallbacks") or [])) if s]
        used, series = self._fetch_first(symbols)
        if series is not None and used is not None:
            return FetchResult(ErrorCode.OK, series, resolved_symbol=used)
        return FetchResult(ErrorCode.NO_DATA, error="yahoo_no_data")

    def warm_cache(self, symbols: list[str], years: int = 2) -> None:
        """Batch-download symbols to avoid repeated API round-trips."""
        uniq = [s for s in dict.fromkeys(symbols) if s]
        if not uniq:
            return
        self._cache.update(self._fetch_many(uniq, years=years))

    def _fetch_first(self, symbols: list[str], years: int = 2) -> tuple[str | None, pd.Series | None]:
        for sym in symbols:
            if not sym:
                continue
            if sym in self._cache:
                return sym, self._cache[sym]
            series = self._fetch_symbol(sym, years=years)
            if series is not None:
                self._cache[sym] = series
                return sym, series
            log.info("no data for %s", sym)
        return None, None

    def _fetch_symbol(self, symbol: str, years: int = 2) -> pd.Series | None:
        end = date.today() + timedelta(days=1)
        start = end - timedelta(days=365 * years + 30)
        try:
            hist = yf.download(
                symbol,
                start=start.isoformat(),
                end=end.isoformat(),
                auto_adjust=True,
                progress=False,
                threads=False,
            )
        except Exception as e:
            log.warning("yahoo download failed %s: %s", symbol, e)
            return None
        return _closes(hist)

    def _fetch_many(self, symbols: list[str], years: int = 2) -> dict[str, pd.Series]:
        if not symbols:
            return {}
        end = date.today() + timedelta(days=1)
        start = end - timedelta(days=365 * years + 30)
        out: dict[str, pd.Series] = {}
        try:
            hist = yf.download(
                symbols,
                start=start.isoformat(),
                end=end.isoformat(),
                auto_adjust=True,
                progress=False,
                threads=True,
                group_by="ticker",
            )
        except Exception as e:
            log.warning("batch download failed: %s", e)
            for s in symbols:
                series = self._fetch_symbol(s, years=years)
                if series is not None:
                    out[s] = series
            return out
        if hist is None or hist.empty:
            return out
        if len(symbols) == 1:
            series = _closes(hist)
            if series is not None:
                out[symbols[0]] = series
            return out
        for s in symbols:
            try:
                if s in hist.columns.get_level_values(0):
                    sub = hist[s]
                else:
                    continue
            except Exception:
                continue
            series = _closes(sub)
            if series is not None:
                out[s] = series
        return out


# Backwards-compatible module-level helpers for callers that import directly.
def fetch_symbol(symbol: str, years: int = 2) -> pd.Series | None:
    return YahooProvider()._fetch_symbol(symbol, years=years)


def fetch_first(symbols: list[str], years: int = 2) -> tuple[str | None, pd.Series | None]:
    return YahooProvider()._fetch_first(symbols, years=years)


def fetch_many(symbols: list[str], years: int = 2) -> dict[str, pd.Series]:
    provider = YahooProvider()
    provider.warm_cache(symbols, years=years)
    return provider._cache
