"""Provider protocol and shared result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd


class ErrorCode:
    """Stable status codes for fetch results."""

    OK = "ok"
    NO_KEY = "no_key"
    NO_DATA = "no_data"
    NO_SYMBOL = "no_symbol"
    UNKNOWN_PROVIDER = "unknown_provider"
    DERIVED_MISSING_DEPS = "derived_missing_deps"


@dataclass(frozen=True)
class FetchResult:
    """Result of a provider fetch attempt."""

    status: str
    series: pd.Series | None = None
    resolved_symbol: str | None = None
    error: str | None = None

    def is_ok(self) -> bool:
        return self.status == ErrorCode.OK


class Provider(Protocol):
    """Common interface for data providers."""

    name: str

    def fetch(self, inst: dict) -> FetchResult:
        ...
