"""Fetch market data, compute metrics, write docs/data/latest.json."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

from src.compute import derive_from_lasts, derive_series, history_points, maybe_scale_series, metrics
from src.providers import build_provider_registry
from src.providers.base import ErrorCode, FetchResult, Provider

log = logging.getLogger("update")
ROOT = Path(__file__).resolve().parents[1]
JST = ZoneInfo("Asia/Tokyo")


def load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val


def load_config() -> dict:
    path = ROOT / "config" / "instruments.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def ticker_label(inst: dict) -> str:
    parts = []
    if inst.get("symbol") and inst.get("provider", "yahoo") == "yahoo":
        parts.append(str(inst["symbol"]))
    for s in inst.get("listed_also") or []:
        parts.append(str(s))
    if inst.get("provider") == "fred":
        parts.append(inst.get("fred_series") or "FRED")
    if inst.get("provider") == "eodhd":
        parts.append(inst.get("eodhd_symbol") or inst.get("symbol") or "EODHD")
    if inst.get("provider") == "derived":
        parts.append("derived")
    return ", ".join(parts)


def base_item(inst: dict) -> dict:
    return {
        "id": inst["id"],
        "section": inst.get("section"),
        "market": inst.get("market") or "",
        "name": inst.get("name") or inst["id"],
        "note": inst.get("note") or "",
        "ticker": ticker_label(inst),
        "priority": inst.get("priority") or "next",
        "unit": inst.get("unit") or "",
        "provider": inst.get("provider") or "yahoo",
        "thresholds": inst.get("thresholds") or {},
    }


def missing(inst: dict, error: str) -> dict:
    item = base_item(inst)
    item.update({"status": "missing", "error": error})
    return item


def ok_from_series(inst: dict, series: pd.Series) -> tuple[dict, pd.Series]:
    series = maybe_scale_series(series, inst.get("scale_if_gt"))
    m = metrics(series)
    item = base_item(inst)
    item.update({"status": "ok", **m, "history": history_points(series)})
    return item, series


def _apply_fallback(
    inst: dict,
    result: FetchResult,
    registry: dict[str, Provider],
) -> FetchResult:
    """Apply provider-specific fallback rules while keeping providers decoupled."""
    provider_name = inst.get("provider") or "yahoo"

    # Yahoo failure may fall back to FRED when a FRED series is configured.
    if provider_name == "yahoo" and result.status == ErrorCode.NO_DATA and inst.get("fred_series"):
        fred_provider = registry.get("fred")
        if fred_provider is not None:
            fred_result = fred_provider.fetch(inst)
            if fred_result.is_ok():
                return fred_result

    # FRED failure may fall back to Yahoo when a Yahoo symbol is configured.
    if provider_name == "fred" and not result.is_ok() and inst.get("symbol"):
        yahoo_provider = registry.get("yahoo")
        if yahoo_provider is not None:
            yahoo_result = yahoo_provider.fetch(inst)
            if yahoo_result.is_ok():
                return yahoo_result

    return result


def fetch_instrument(
    inst: dict,
    registry: dict[str, Provider],
) -> tuple[dict, pd.Series | None]:
    provider_name = inst.get("provider") or "yahoo"

    provider = registry.get(provider_name)
    if provider is None:
        return missing(inst, f"unknown_provider:{provider_name}"), None

    result = _apply_fallback(inst, provider.fetch(inst), registry)

    if result.is_ok():
        item, series = ok_from_series(inst, result.series)
        item["resolved_symbol"] = result.resolved_symbol
        if result.resolved_symbol != inst.get("symbol") or provider_name == "fred":
            item["ticker"] = result.resolved_symbol + (
                f" ({item['ticker']})" if item.get("ticker") else ""
            )
        return item, series

    return missing(inst, result.error or result.status), None


def _warm_yahoo_cache(instruments: list[dict], registry: dict[str, Provider]) -> None:
    yahoo_provider = registry.get("yahoo")
    if yahoo_provider is None:
        return
    symbols: list[str] = []
    for inst in instruments:
        provider = inst.get("provider") or "yahoo"
        if provider == "yahoo" or (provider == "fred" and inst.get("symbol")):
            sym = inst.get("symbol")
            if sym:
                symbols.append(sym)
            symbols.extend(inst.get("symbol_fallbacks") or [])
    yahoo_provider.warm_cache([s for s in symbols if s])


def compute_derived(
    instruments: list[dict],
    items_by_id: dict[str, dict],
    series_store: dict[str, pd.Series],
) -> list[dict]:
    """Compute derived instruments in config order."""
    derived_items: list[tuple[dict, dict]] = []
    for inst in instruments:
        if inst.get("provider") != "derived":
            continue
        dep_ids = (inst.get("derived") or {}).get("minus") or []
        sa = series_store.get(dep_ids[0]) if len(dep_ids) == 2 else None
        sb = series_store.get(dep_ids[1]) if len(dep_ids) == 2 else None

        if sa is not None and sb is not None:
            ss = derive_series(sa, sb)
            if ss is not None:
                item, _ = ok_from_series(inst, ss)
                series_store[inst["id"]] = ss
                derived_items.append((inst, item))
                continue

        dep_items = [items_by_id.get(d) for d in dep_ids]
        derived = derive_from_lasts(dep_items[0], dep_items[1]) if len(dep_items) == 2 else None
        if derived is None:
            derived_items.append((inst, missing(inst, ErrorCode.DERIVED_MISSING_DEPS)))
        else:
            item = base_item(inst)
            item.update({"status": "ok", **derived})
            derived_items.append((inst, item))

    return [item for _, item in derived_items]


def build_payload(cfg: dict, items: list[dict]) -> dict:
    generated_at = datetime.now(JST).isoformat(timespec="seconds")
    ok_n = sum(1 for i in items if i.get("status") == "ok")
    missing_n = sum(1 for i in items if i.get("status") != "ok")

    # Preserve backwards compatibility: when every item uses Yahoo, source stays "yahoo".
    sources = {i.get("provider", "yahoo") for i in items}
    sources.discard("derived")
    source = "yahoo" if len(sources) == 1 and "yahoo" in sources else "mixed"

    return {
        "generated_at": generated_at,
        "source": source,
        "timezone": "Asia/Tokyo",
        "sections": cfg.get("sections") or [],
        "ok_count": ok_n,
        "missing_count": missing_n,
        "items": items,
    }


def run() -> dict:
    load_dotenv()
    cfg = load_config()
    instruments = cfg["instruments"]
    registry = build_provider_registry()

    _warm_yahoo_cache(instruments, registry)

    items: list[dict] = []
    items_by_id: dict[str, dict] = {}
    series_store: dict[str, pd.Series] = {}

    for inst in instruments:
        if inst.get("provider") == "derived":
            continue
        try:
            item, series = fetch_instrument(inst, registry)
        except Exception as e:
            log.exception("failed %s", inst.get("id"))
            item = missing(inst, str(e)[:200])
            series = None
        if series is not None:
            series_store[inst["id"]] = series
        items_by_id[inst["id"]] = item
        items.append(item)

    derived_items = compute_derived(instruments, items_by_id, series_store)
    items.extend(derived_items)

    return build_payload(cfg, items)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    load_dotenv()
    payload = run()
    out = ROOT / "docs" / "data" / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("wrote %s ok=%s missing=%s", out, payload["ok_count"], payload["missing_count"])
    if payload["ok_count"] == 0:
        log.error("all instruments missing")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
