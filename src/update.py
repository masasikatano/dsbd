"""Fetch Yahoo data, compute metrics, write docs/data/latest.json."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from src.compute import history_points, maybe_scale_series, metrics, spread, spread_series
from src.providers import yahoo

log = logging.getLogger("update")
ROOT = Path(__file__).resolve().parents[1]
JST = ZoneInfo("Asia/Tokyo")


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
    for s in inst.get("listed_jp") or []:
        parts.append(str(s))
    if inst.get("provider") == "fred":
        parts.append(inst.get("fred_series") or "FRED")
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


def ok_from_series(inst: dict, series) -> dict:
    series = maybe_scale_series(series, inst.get("scale_if_gt"))
    m = metrics(series)
    item = base_item(inst)
    item.update({"status": "ok", **m, "history": history_points(series)})
    return item, series


def fetch_yahoo(inst: dict, cache: dict):
    symbols = [inst.get("symbol")] + list(inst.get("symbol_fallbacks") or [])
    used, series = None, None
    for s in symbols:
        if s and s in cache:
            used, series = s, cache[s]
            break
    if series is None:
        used, series = yahoo.fetch_first([s for s in symbols if s])
        if used and series is not None:
            cache[used] = series
    if series is None:
        return missing(inst, "yahoo_no_data"), None
    item, series = ok_from_series(inst, series)
    if used and used != inst.get("symbol"):
        item["ticker"] = used + (f" ({item['ticker']})" if item.get("ticker") else "")
        item["resolved_symbol"] = used
    return item, series


def run() -> dict:
    cfg = load_config()
    instruments = cfg["instruments"]
    by_id: dict[str, dict] = {}
    items: list[dict] = []

    yahoo_syms: list[str] = []
    for inst in instruments:
        if (inst.get("provider") or "yahoo") != "yahoo":
            continue
        yahoo_syms.append(inst.get("symbol"))
        yahoo_syms.extend(inst.get("symbol_fallbacks") or [])
    cache = yahoo.fetch_many([s for s in yahoo_syms if s])
    series_store: dict = {}

    for inst in instruments:
        provider = inst.get("provider") or "yahoo"
        series = None
        try:
            if provider == "fred":
                item = missing(inst, "fred_not_implemented")
            elif provider == "listed_jp":
                item = missing(inst, "listed_jp_no_price")
                item["note"] = inst.get("note") or "日本上場はティッカー併記のみ"
            elif provider == "derived":
                continue
            elif provider == "yahoo":
                item, series = fetch_yahoo(inst, cache)
            else:
                item = missing(inst, f"unknown_provider:{provider}")
        except Exception as e:
            log.exception("failed %s", inst.get("id"))
            item = missing(inst, str(e)[:200])
        if series is not None:
            series_store[inst["id"]] = series
        by_id[inst["id"]] = item
        items.append(item)

    for inst in instruments:
        if inst.get("provider") != "derived":
            continue
        deps = (inst.get("derived") or {}).get("minus") or []
        sa = series_store.get(deps[0]) if len(deps) == 2 else None
        sb = series_store.get(deps[1]) if len(deps) == 2 else None
        if sa is not None and sb is not None:
            ss = spread_series(sa, sb)
            if ss is not None:
                item, series = ok_from_series(inst, ss)
                series_store[inst["id"]] = series
                by_id[inst["id"]] = item
                items.append(item)
                continue
        vals = []
        ok = True
        last_date = None
        for dep in deps:
            row = by_id.get(dep)
            if not row or row.get("status") != "ok" or row.get("last") is None:
                ok = False
                break
            vals.append(float(row["last"]))
            last_date = row.get("last_date")
        if not ok or len(vals) != 2:
            item = missing(inst, "derived_missing_deps")
        else:
            item = base_item(inst)
            last = spread(vals[0], vals[1])
            item.update(
                {
                    "status": "ok",
                    "last": last,
                    "last_date": last_date,
                    "chg_1d_pct": None,
                    "ytd_pct": None,
                    "pos_52w_pct": None,
                    "dev_200d_pct": None,
                    "vol_1y_pct": None,
                    "history": {"t": [], "v": []},
                }
            )
        by_id[inst["id"]] = item
        items.append(item)

    generated_at = datetime.now(JST).isoformat(timespec="seconds")
    ok_n = sum(1 for i in items if i.get("status") == "ok")
    missing_n = sum(1 for i in items if i.get("status") != "ok")
    payload = {
        "generated_at": generated_at,
        "source": "yahoo",
        "timezone": "Asia/Tokyo",
        "sections": cfg.get("sections") or [],
        "ok_count": ok_n,
        "missing_count": missing_n,
        "items": items,
    }
    return payload


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
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
