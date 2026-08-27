"""Yahoo Finance fetch via yfinance."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

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


def fetch_symbol(symbol: str, years: int = 2) -> pd.Series | None:
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


def fetch_first(symbols: list[str], years: int = 2) -> tuple[str | None, pd.Series | None]:
    for sym in symbols:
        if not sym:
            continue
        series = fetch_symbol(sym, years=years)
        if series is not None:
            return sym, series
        log.info("no data for %s", sym)
    return None, None


def fetch_many(symbols: list[str], years: int = 2) -> dict[str, pd.Series]:
    uniq = [s for s in dict.fromkeys(symbols) if s]
    if not uniq:
        return {}
    end = date.today() + timedelta(days=1)
    start = end - timedelta(days=365 * years + 30)
    out: dict[str, pd.Series] = {}
    try:
        hist = yf.download(
            uniq,
            start=start.isoformat(),
            end=end.isoformat(),
            auto_adjust=True,
            progress=False,
            threads=True,
            group_by="ticker",
        )
    except Exception as e:
        log.warning("batch download failed: %s", e)
        for s in uniq:
            ser = fetch_symbol(s, years=years)
            if ser is not None:
                out[s] = ser
        return out
    if hist is None or hist.empty:
        return out
    if len(uniq) == 1:
        ser = _closes(hist)
        if ser is not None:
            out[uniq[0]] = ser
        return out
    for s in uniq:
        try:
            if s in hist.columns.get_level_values(0):
                sub = hist[s]
            else:
                continue
        except Exception:
            continue
        ser = _closes(sub)
        if ser is not None:
            out[s] = ser
    return out
