"""EODHD end-of-day closes. Returns None when the key is missing or a symbol fails."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

import pandas as pd

log = logging.getLogger(__name__)

EOD_URL = "https://eodhd.com/api/eod/"
TIMEOUT_S = 30


def has_key() -> bool:
    return bool(os.environ.get("EODHD_API_KEY"))


def fetch(symbol: str, years: int = 1) -> pd.Series | None:
    if not symbol:
        return None
    key = os.environ.get("EODHD_API_KEY")
    if not key:
        return None
    start = (date.today() - timedelta(days=365 * years + 7)).isoformat()
    params = {
        "api_token": key,
        "fmt": "json",
        "period": "d",
        "order": "a",
        "from": start,
    }
    url = EOD_URL + urllib.parse.quote(symbol) + "?" + urllib.parse.urlencode(params)
    payload = _get_json(url, symbol)
    if payload is None:
        payload = _get_json(url, symbol)
    if not isinstance(payload, list) or not payload:
        return None
    dates = []
    values = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        val = row.get("adjusted_close", row.get("close"))
        if val is None:
            continue
        try:
            values.append(float(val))
        except (TypeError, ValueError):
            continue
        dates.append(pd.Timestamp(row.get("date")))
    if not values:
        log.info("eodhd empty series %s", symbol)
        return None
    s = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s if not s.empty else None


def _get_json(url: str, symbol: str) -> list | dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "dsbd-dashboard"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        log.warning("eodhd HTTP %s for %s", e.code, symbol)
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        log.warning("eodhd request failed for %s", symbol)
        return None
