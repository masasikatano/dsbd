"""FRED observations. Returns None when the key is missing or a series fails."""

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

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
TIMEOUT_S = 30


def has_key() -> bool:
    return bool(os.environ.get("FRED_API_KEY"))


def fetch(series_id: str, years: int = 2) -> pd.Series | None:
    if not series_id:
        return None
    key = os.environ.get("FRED_API_KEY")
    if not key:
        return None
    end = date.today()
    start = end - timedelta(days=365 * years + 30)
    params = {
        "series_id": series_id,
        "api_key": key,
        "file_type": "json",
        "observation_start": start.isoformat(),
        "observation_end": end.isoformat(),
    }
    url = FRED_URL + "?" + urllib.parse.urlencode(params)
    payload = _get_json(url, series_id)
    if payload is None:
        payload = _get_json(url, series_id)
    if not payload:
        return None
    obs = payload.get("observations") or []
    dates = []
    values = []
    for row in obs:
        val = row.get("value")
        if val is None or val == ".":
            continue
        try:
            values.append(float(val))
        except (TypeError, ValueError):
            continue
        dates.append(pd.Timestamp(row.get("date")))
    if not values:
        log.info("fred empty series %s", series_id)
        return None
    s = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s if not s.empty else None


def _get_json(url: str, series_id: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "dsbd-dashboard"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        log.warning("fred HTTP %s for %s", e.code, series_id)
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        log.warning("fred request failed for %s", series_id)
        return None
