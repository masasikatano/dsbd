"""Provider registry."""

from __future__ import annotations

from src.providers.base import Provider
from src.providers.eodhd import EodhdProvider
from src.providers.fred import FredProvider
from src.providers.yahoo import YahooProvider


def build_provider_registry() -> dict[str, Provider]:
    """Return a mapping from provider name to provider instance."""
    return {
        YahooProvider.name: YahooProvider(),
        FredProvider.name: FredProvider(),
        EodhdProvider.name: EodhdProvider(),
    }
