"""FRED stub. v1 does not call the API; rows stay missing until a key and series are wired."""

from __future__ import annotations

import os

import pandas as pd


def fetch(series_id: str, start, end) -> pd.DataFrame:
    if not os.environ.get("FRED_API_KEY"):
        raise RuntimeError("FRED_API_KEY not set")
    raise NotImplementedError("FRED provider is not implemented in v1")
